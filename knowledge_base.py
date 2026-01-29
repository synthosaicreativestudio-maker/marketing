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
        self.cached_content_name = None
        self.last_update_time = 0
        self.ttl_minutes = 60 # Cache TTL (standard is 1 hour)
        self.is_updating = False
        self._lock = asyncio.Lock()
        
        # Initialize Gemini Client with Proxy Support
        proxy_key = os.getenv("PROXYAPI_KEY")
        proxy_url = os.getenv("PROXYAPI_BASE_URL")
        
        self.client = None
        try:
            if proxy_key and proxy_url:
                logger.info("KnowledgeBase using Proxy API")
                self.client = genai.Client(
                    api_key=proxy_key,
                    http_options={
                        'base_url': proxy_url, 
                        'api_version': 'v1beta'
                    }
                )
            elif self.api_key:
                logger.info("KnowledgeBase using Direct API")
                self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
             logger.error(f"Failed to initialize Gemini Client in KnowledgeBase: {e}")

    async def initialize(self):
        """Initial check and cache creation."""
        if not self.client or not self.folder_id or str(self.folder_id).lower() in ('none', ''):
            logger.warning(f"KnowledgeBase disabled: client missing or invalid folder_id: {self.folder_id}")
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
        # Если кэша нет или он явно инвалидирован
        if not self.cached_content_name:
            return None
        
        current_age = time.time() - self.last_update_time
        cache_lifetime = self.ttl_minutes * 60
        
        # Если кэш полностью истек (с запасом 1 минута на clock skew)
        if current_age > (cache_lifetime + 60):
            logger.warning("⚠️ Cache fully expired (beyond TTL), invalidating...")
            await self.invalidate_cache()
            return None
        
        # Если кэш скоро истечет - триггерим фоновое обновление
        if current_age > (cache_lifetime - 300):  # 5 mins before expiry
            if not self.is_updating and self.cached_content_name:
                logger.info("Cache is nearing expiry, triggering refresh...")
                asyncio.create_task(self.refresh_cache())
        
        return self.cached_content_name
    
    async def invalidate_cache(self) -> None:
        """Invalidates the current cache (called on errors)."""
        if self.cached_content_name:
            logger.warning(f"🗑️ Invalidating cache: {self.cached_content_name}")
            old_cache = self.cached_content_name
            self.cached_content_name = None
            self.last_update_time = 0  # Force immediate refresh on next request
            
            # Попытка удалить кэш из API (best effort)
            try:
                await self.client.aio.caches.delete(name=old_cache)
                logger.info(f"✅ Cache deleted from API: {old_cache}")
            except Exception as e:
                logger.warning(f"Failed to delete cache from API (already gone?): {e}")

    async def refresh_cache(self, system_instruction: Optional[str] = None, tools: Optional[List[types.Tool]] = None):
        """Refreshes the knowledge base cache in a non-blocking way."""
        async with self._lock:
            if self.is_updating:
                return
            
            self.is_updating = True
        logger.info("🔄 Starting Knowledge Base Refresh (Non-blocking)...")
        
        try:
            # 1. List files from Drive (Sync operation -> Thread)
            files_meta = await asyncio.to_thread(self.drive_service.list_files, self.folder_id)
            if not files_meta:
                logger.warning("No files found in Knowledge Base folder.")
                self.is_updating = False
                return

            # 2. Download files locally (Sync operation -> Thread)
            local_files = []
            for f in files_meta:
                # Wrap each download in a thread to keep event loop free
                path = await asyncio.to_thread(
                    self.drive_service.download_file, 
                    f['id'], f['name'], f['mimeType']
                )
                if path:
                    local_files.append(path)
            
            if not local_files:
                logger.warning("Failed to download any files.")
                self.is_updating = False
                return

            # 3. Upload to Gemini File API (Using Async Client)
            gemini_files = []
            import mimetypes
            
            for path in local_files:
                try:
                    # Guess mime type (Lightweight but good for thread)
                    mime_type, _ = await asyncio.to_thread(mimetypes.guess_type, path)
                    
                    # Upload file using AIO client
                    logger.info(f"Uploading {path} (type: {mime_type}) to Gemini Async...")
                    with open(path, 'rb') as f_data:
                        file_upload = await self.client.aio.files.upload(
                            file=f_data,
                            config={
                                'display_name': os.path.basename(path),
                                'mime_type': mime_type
                            }
                        )
                    
                    # Wait for processing (Non-blocking sleep)
                    while file_upload.state.name == "PROCESSING":
                        logger.info(f"Waiting for {file_upload.name} to process...")
                        await asyncio.sleep(2) 
                        file_upload = await self.client.aio.files.get(name=file_upload.name)
                        
                    if file_upload.state.name != "ACTIVE":
                        logger.error(f"File {file_upload.name} failed processing: {file_upload.state.name}")
                        continue
                        
                    gemini_files.append(file_upload)
                    logger.info(f"File {file_upload.display_name} is ACTIVE.")
                    
                except Exception as e:
                    logger.error(f"Error uploading {path}: {e}")
                
                # Small delay to avoid rate limits/geo-checks
                await asyncio.sleep(2)

            if not gemini_files:
                logger.error("No files successfully uploaded to Gemini.")
                await asyncio.to_thread(self.drive_service.cleanup_tmp_files)
                self.is_updating = False
                return

            # 4. Create Context Cache with Instructions and Tools
            try:
                logger.info("Creating CachedContent with instructions and tools (Async)...")
                
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

                # Create cache using AIO client
                cached_content = await self.client.aio.caches.create(
                    model='gemini-3-pro-preview', 
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
                logger.info(f"✅ Cache Created Successfully (Async): {self.cached_content_name}")
                
            except Exception as e:
                logger.error(f"Failed to create cache: {e}")
                
            # Cleanup local files (Thread)
            await asyncio.to_thread(self.drive_service.cleanup_tmp_files)
            
        except Exception as e:
            logger.error(f"Error during cache refresh: {e}")
        finally:
            self.is_updating = False

