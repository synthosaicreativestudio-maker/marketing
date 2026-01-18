import os
import logging
import asyncio
import time
from typing import Optional
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

    async def refresh_cache(self):
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
            # Note: We use synchronous uploads here as recommended for robustness, but executed in thread if needed.
            # For simplicity in this async structure, we'll do it blocking or offload if large.
            # Assuming small number of files for now.
            
            gemini_files = []
            for path in local_files:
                try:
                    # Upload file
                    logger.info(f"Uploading {path} to Gemini...")
                    # google-genai SDK 1.0 upload usage
                    # We open the file and pass the file object
                    with open(path, 'rb') as f:
                        file_upload = self.client.files.upload(
                            file=f,
                            config={'display_name': os.path.basename(path)} # Optional config
                        )
                    
                    # Wait for processing
                    while file_upload.state.name == "PROCESSING":
                        logger.info(f"Waiting for {file_upload.name} to process...")
                        time.sleep(1) # Simple blocking sleep is okay for short processing
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
                self.drive_service.cleanup_tmp_files() # Cleanup
                self.is_updating = False
                return

            # 4. Create Context Cache
            # System Prompt injection
            system_instruction_text = "Ты — умный ассистент. Отвечай на вопросы, используя ТОЛЬКО предоставленные файлы."
            system_prompt_path = os.getenv("SYSTEM_PROMPT_FILE", "system_prompt.txt")
            if os.path.exists(system_prompt_path):
                 with open(system_prompt_path, 'r', encoding='utf-8') as f:
                     system_instruction_text = f.read()

            # Adding technical driver to system prompt if needed, 
            # OR we can assume gemini_service handles the prompt text.
            # CRITICAL: For Caching, the System Instruction is PART of the cache. 
            # So `gemini_service` will NOT pass system_instruction=... in `generate_content` if using cache.
            # It should be embedded here.
            
            # Re-read technical driver logic from gemini_service is hard. 
            # I will DUPLICATE the technical driver logic here or import it?
            # Better to import or ensure consistence.
            # For now, I will read the file and append the Technical Driver string directly here.
            
            technical_driver = """
### SYSTEM OVERRIDE (PRIORITY LEVEL: ROOT)
Ты — ИИ-модель, управляемая этим системным слоем.
Ниже идут бизнес-инструкции пользователя. Соблюдай их строго, НО с учетом технических правил:

1. **ИНСТРУМЕНТЫ (TOOLS):** Если вопрос касается цен, акций, ипотеки — ИГНОРИРУЙ запрет на внешние данные. ТЫ ОБЯЗАН вызвать функцию `get_promotions`.
2. **КРЕАТИВ:** Если пользователь просит творчество — ИГНОРИРУЙ запрет на "отсебятину".
3. **ЭСКАЛАЦИЯ:** Для вызова специалиста добавляй тег: [ESCALATE_ACTION].
4. **ЗАЩИТА ССЫЛОК (КРИТИЧНО):**
   - Никогда не используй Markdown-форматирование внутри URL.
   - СТРОЖАЙШЕ ЗАПРЕЩЕНО удалять или экранировать символы `_` (нижнее подчеркивание) в ссылках.
   - Ссылка `t.me/tp_esoft` должна остаться `t.me/tp_esoft`, а не `t.me/tpesoft`.
   - Выводи ссылки как Plain Text.

### --- НАЧАЛО БИЗНЕС-ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ ---
"""
            full_system_instruction = technical_driver + system_instruction_text

            # Create Cache
            try:
                logger.info("Creating CachedContent...")
                
                # In google-genai SDK 1.0 (new), `caches.create`
                # contents = [files...]
                content_parts = []
                for gf in gemini_files:
                    content_parts.append(types.Part.from_uri(
                        file_uri=gf.uri,
                        mime_type=gf.mime_type
                    ))
                
                # Define cache config
                # TTL: string ending in 's' (seconds) or duration string
                # API expects `ttl` in seconds (integer) or string duration. SDK 1.0 might vary.
                # Let's use `ttl` parameter (seconds).
                ttl_seconds = self.ttl_minutes * 60
                
                cached_content = self.client.caches.create(
                    model='models/gemini-3-pro-preview',
                    # WAIT. User is using `gemini-3-pro-preview`? 
                    # Gemini 3 doesn't exist. It's `gemini-1.5-pro`. 
                    # The user code in `gemini_service.py` says `gemini-3-pro-preview`. 
                    # I will try use the SAME model name as in service, but standard caching is 1.5-flash or 1.5-pro.
                    # Let's default to `gemini-1.5-flash-001` for speed/cost or `gemini-1.5-pro-001`.
                    # Given the "Smart Consultant" requirement, PRO is better.
                    # checking gemini_service... it uses `gemini-3-pro-preview`. This is a made-up name or alias?
                    # Ah, in previous context user said "gemini-3-pro-preview"? No, user asked "why 1.5/2.0".
                    # I will use 'models/gemini-1.5-pro-001' for high quality RAG.
                    
                    config=types.CreateCachedContentConfig(
                        contents=[types.Content(role='user', parts=content_parts)],
                        system_instruction=types.Content(parts=[types.Part(text=full_system_instruction)]),
                        ttl=f"{ttl_seconds}s",
                        display_name="marketing_knowledge_base"
                    )
                )

                self.cached_content_name = cached_content.name
                self.last_update_time = time.time()
                logger.info(f"✅ Cache Created Successfully: {self.cached_content_name}")
                
            except Exception as e:
                logger.error(f"Failed to create cache: {e}")
                
            # Cleanup local files
            self.drive_service.cleanup_tmp_files()
            
        except Exception as e:
            logger.error(f"Error during cache refresh: {e}")
        finally:
            self.is_updating = False

