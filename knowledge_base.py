import os
import logging
import asyncio
import time
from typing import Optional, List
from google import genai
from google.genai import types

from drive_service import DriveService

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """Manages the Knowledge Base (cache) for Gemini."""
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service
        self.folder_id = os.getenv('DRIVE_FOLDER_ID')
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self.cached_content_name = None
        self.last_update_time = 0
        self.ttl_minutes = 60 # Cache TTL (standard is 1 hour)
        self.is_updating = False
        
        # Initialize Gemini Client
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client in KnowledgeBase: {e}")

    async def initialize(self):
        """Initial check and cache creation."""
        if not self.client or not self.folder_id:
            logger.warning("KnowledgeBase disabled: client or folder_id missing")
            return
            
        # Check drive access
        if not self.drive_service.check_access(self.folder_id):
            logger.error(f"Service Account does NOT have access to folder {self.folder_id}")
            return
            
        logger.info("KnowledgeBase initialized. Access verified.")
        # Trigger initial cache creation in background
        asyncio.create_task(self.refresh_cache())

    async def get_cache_name(self) -> Optional[str]:
        """Returns the current active cache name."""
        # Simple TTL check for determining if we should TRIGGER an update
        # But we always return the current valid one if it exists
        if time.time() - self.last_update_time > (self.ttl_minutes * 60 - 300): # Refresh 5 mins before expiry
            if not self.is_updating and self.cached_content_name:
                logger.info("Cache is nearing expiry, triggering refresh...")
                asyncio.create_task(self.refresh_cache())
                
        return self.cached_content_name

    async def refresh_cache(self, system_instruction: Optional[str] = None, tools: Optional[List[types.Tool]] = None):
        """Refreshes the knowledge base cache."""
        if self.is_updating:
            return
        
        self.is_updating = True
        logger.info("🔄 Starting Knowledge Base Refresh...")
        
        try:
            # 1. List files from Drive
            files_meta = self.drive_service.list_files(self.folder_id)
            if not files_meta:
                logger.warning("No files found in Knowledge Base folder.")
                self.is_updating = False
                return

            # 2. Download files locally
            local_files = []
            for f in files_meta:
                 path = self.drive_service.download_file(f['id'], f['name'], f['mimeType'])
                 if path:
                     local_files.append(path)
            
            if not local_files:
                logger.warning("Failed to download any files.")
                self.is_updating = False
                return

            # 3. Upload to Gemini File API
            gemini_files = []
            for path in local_files:
                try:
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(path)
                    
                    # Upload file
                    logger.info(f"Uploading {path} (type: {mime_type}) to Gemini...")
                    with open(path, 'rb') as f:
                        file_upload = self.client.files.upload(
                            file=f,
                            config={
                                'display_name': os.path.basename(path),
                                'mime_type': mime_type
                            }
                        )
                    
                    # Wait for processing
                    while file_upload.state.name == "PROCESSING":
                        logger.info(f"Waiting for {file_upload.name} to process...")
                        await asyncio.sleep(1) 
                        file_upload = self.client.files.get(name=file_upload.name)
                        
                    if file_upload.state.name != "ACTIVE":
                        logger.error(f"File {file_upload.name} failed processing: {file_upload.state.name}")
                        continue
                        
                    gemini_files.append(file_upload)
                    logger.info(f"File {file_upload.display_name} is ACTIVE.")
                    
                except Exception as e:
                    logger.error(f"Error uploading {path}: {e}")

            if not gemini_files:
                logger.error("No files successfully uploaded to Gemini.")
                self.drive_service.cleanup_tmp_files() 
                self.is_updating = False
                return

            # 4. Create Context Cache with Instructions and Tools
            try:
                logger.info("Creating CachedContent with instructions and tools...")
                
                content_parts = []
                for gf in gemini_files:
                    content_parts.append(types.Part.from_uri(
                        file_uri=gf.uri,
                        mime_type=gf.mime_type
                    ))
                
                ttl_seconds = self.ttl_minutes * 60
                
                # Подготовка system_instruction для кэша
                si_content = None
                if system_instruction:
                    si_content = types.Content(parts=[types.Part(text=system_instruction)])

                cached_content = self.client.caches.create(
                    model='gemini-3-flash-preview', 
                    config=types.CreateCachedContentConfig(
                        contents=[types.Content(role='user', parts=content_parts)],
                        system_instruction=si_content,
                        tools=tools,
                        ttl=f"{ttl_seconds}s",
                        display_name="marketing_knowledge_base"
                    )
                )

                self.cached_content_name = cached_content.name
                self.last_update_time = time.time()
                logger.info(f"✅ Cache Created Successfully with Embedded Rules: {self.cached_content_name}")
                
            except Exception as e:
                logger.error(f"Failed to create cache: {e}")
                
            # Cleanup local files
            self.drive_service.cleanup_tmp_files()
            
        except Exception as e:
            logger.error(f"Error during cache refresh: {e}")
        finally:
            self.is_updating = False

