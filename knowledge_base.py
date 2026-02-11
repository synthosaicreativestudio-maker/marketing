import os
import logging
import asyncio
import time
import hashlib
from typing import Optional, List
from google import genai
from google.genai import types

from drive_service import DriveService
from rag.document_processor import DocumentProcessor
from rag.search_engine import SearchEngine

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
        self._refresh_task = None
        self.index_path = os.getenv("RAG_INDEX_PATH", "rag_index.json")
        self.skip_initial_refresh = os.getenv("RAG_SKIP_INITIAL_REFRESH", "true").lower() in ("1", "true", "yes", "y")
        self._files_signature = None
        
        # Feature flag: Context Caching (CAG) — принудительно выключено в proxy-only режиме
        self.caching_enabled = False
        self.active_files = [] # Список активных файлов Gemini для RAG без кэша
        self.file_links = {}   # Mapping of filename -> Drive webViewLink
        
        # New: Universal RAG components
        self.doc_processor = DocumentProcessor()
        self.search_engine = SearchEngine()
        self.local_context_ready = False
        
        # Initialize Gemini Client with Proxy Support
        proxy_key = os.getenv("PROXYAPI_KEY")
        proxy_url = os.getenv("PROXYAPI_BASE_URL")
        
        self.client = None
        try:
            if proxy_key and proxy_url:
                logger.info(f"KnowledgeBase using Proxy API: {proxy_url}")
                api_version = os.getenv("PROXYAPI_VERSION", "v1beta")
                self.client = genai.Client(
                    api_key=proxy_key,
                    http_options={
                        'base_url': proxy_url, 
                        'api_version': api_version
                    }
                )
            else:
                logger.error("KnowledgeBase proxy-only mode: PROXYAPI_BASE_URL is required.")
        except Exception as e:
             logger.error(f"Failed to initialize Gemini Client in KnowledgeBase: {e}")

    async def initialize(self):
        """Initial check and cache creation."""
        # Try to load local RAG index for fast startup
        if self.index_path:
            if self.search_engine.load_index(self.index_path):
                self.local_context_ready = True
                logger.info("KnowledgeBase: Local RAG index loaded from disk.")
                if self.skip_initial_refresh:
                    logger.info("KnowledgeBase: Initial refresh skipped (RAG_SKIP_INITIAL_REFRESH=true).")
                    return

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
            if self.client:
                try:
                    await self.client.aio.caches.delete(name=old_cache)
                    logger.info(f"✅ Cache deleted from API: {old_cache}")
                except Exception as e:
                    logger.warning(f"Failed to delete cache from API (already gone?): {e}")

    async def start_auto_refresh(self, target_hour_local: int = 23, tz_offset_hours: int = 5):
        """Starts a background task to refresh the knowledge base daily at target_hour_local (Ekb by default)."""
        if self._refresh_task and not self._refresh_task.done():
            logger.info("Knowledge Base auto-refresh is already running.")
            return

        async def _refresh_loop():
            logger.info(
                f"Starting Knowledge Base auto-refresh loop (daily at {target_hour_local:02d}:00 UTC{tz_offset_hours:+d})"
            )
            from datetime import datetime, timedelta, timezone
            tz = timezone(timedelta(hours=tz_offset_hours))
            while True:
                try:
                    now_local = datetime.now(tz)
                    target_local = now_local.replace(hour=target_hour_local, minute=0, second=0, microsecond=0)
                    if target_local <= now_local:
                        target_local = target_local + timedelta(days=1)
                    sleep_seconds = (target_local - now_local).total_seconds()
                    await asyncio.sleep(sleep_seconds)
                    await self.refresh_cache()
                    logger.info("Knowledge Base auto-refresh successful. Next refresh scheduled for tomorrow.")
                except Exception as e:
                    logger.error(f"Error during Knowledge Base auto-refresh: {e}")
                    await asyncio.sleep(60)

        # Создаем задачу через task_tracker для мониторинга
        from task_tracker import task_tracker
        self._refresh_task = task_tracker.create_tracked_task(_refresh_loop(), "kb_auto_refresh")

    async def refresh_cache(self, system_instruction: Optional[str] = None, tools: Optional[List[types.Tool]] = None):
        """Refreshes the knowledge base files and optionally the cache."""
        if not self.client:
            logger.error("KnowledgeBase refresh failed: client not initialized")
            return
        
        async with self._lock:
            if self.is_updating:
                return
            
            self.is_updating = True
        logger.info("🔄 Starting Knowledge Base Refresh (Non-blocking)...")
        try:
            # 1. List files from Drive
            files_meta = await asyncio.to_thread(self.drive_service.list_files, self.folder_id)
            if not files_meta:
                logger.warning("No files found in Knowledge Base folder.")
                self.is_updating = False
                return

            # Skip refresh if nothing changed (by id/modifiedTime/size/mimeType)
            signature_items = []
            for f in files_meta:
                signature_items.append((
                    f.get('id'),
                    f.get('modifiedTime'),
                    f.get('size'),
                    f.get('mimeType')
                ))
            signature = tuple(sorted(signature_items))
            if self._files_signature == signature and self.local_context_ready:
                logger.info("Knowledge Base refresh skipped: no file changes detected.")
                self.last_update_time = time.time()
                self.is_updating = False
                return
            self._files_signature = signature

            # Filter heavy/unsupported files to reduce CPU/IO
            max_mb = int(os.getenv("MAX_DRIVE_FILE_MB", "25"))
            max_bytes = max_mb * 1024 * 1024
            filtered_files = []
            
            # Предварительный сбор ссылок для всех файлов (включая картинки)
            all_links = {f['name']: f['webViewLink'] for f in files_meta if 'name' in f and 'webViewLink' in f}
            self.file_links = all_links
            
            for f in files_meta:
                mime = f.get('mimeType', '')
                size = int(f.get('size') or 0)
                name = f.get('name', '')
                
                # Пропускаем только "чистые" картинки, но оставляем .ocr.txt
                if mime in ('image/png', 'image/jpeg') and not name.lower().endswith('.ocr.txt'):
                    logger.info(f"Skipping image file: {name} (waiting for OCR version)")
                    continue
                
                if size and size > max_bytes:
                    logger.info(f"Skipping large file (> {max_mb}MB): {name}")
                    continue
                    
                filtered_files.append(f)
            
            files_meta = filtered_files
            logger.info(f"Indexed {len(self.file_links)} file links, will download {len(files_meta)} text-based files")
            # 2. Download/process files with incremental cache
            local_files = []
            all_chunks = []
            
            # ???????????????? ?????? ?????????? ???????????? ?????? ????????????????????????
            ocr_files = {f['name'] for f in files_meta if f['name'].endswith('.ocr.txt')}
            
            for f in files_meta:
                name = f['name']
                # ???????? ?????? ???????????????? ?? ?????? ???????? ???????? OCR-???????????? - ???????????????????? ????????????????
                if not name.endswith('.ocr.txt'):
                    if f"{name}.ocr.txt" in ocr_files:
                        logger.info(f"Deduplication: skipping original {name} (using OCR version)")
                        continue

                file_id = f.get('id', '')
                modified = f.get('modifiedTime', '')
                file_key = f"{file_id}:{modified}"
                file_hash = hashlib.md5(file_key.encode('utf-8')).hexdigest()
                cached = self.search_engine.persistent_cache.get_cached_chunks(file_hash)
                if cached:
                    all_chunks.extend(cached)
                    continue

                path = await asyncio.to_thread(self.drive_service.download_file, f['id'], f['name'], f['mimeType'])
                if path:
                    local_files.append(path)
                    chunks = self.doc_processor.process_file(path)
                    if chunks:
                        all_chunks.extend(chunks)
                        self.search_engine.persistent_cache.cache_chunks(file_hash, name, chunks)
            
            if not all_chunks:
                logger.warning("Failed to process any files.")
                self.is_updating = False
                return

            # 3. Universal RAG: Local Indexing
            logger.info("Universal RAG: Starting local indexing...")
            if all_chunks:
                self.search_engine.clear()
                self.search_engine.add_chunks(all_chunks)
                self.local_context_ready = True
                logger.info(f"✅ Universal RAG: Indexed {len(all_chunks)} chunks.")
                # Persist local RAG index for fast restarts
                if self.index_path:
                    self.search_engine.save_index(self.index_path)
            else:
                logger.warning("Universal RAG: No text chunks extracted.")

            # 4. Gemini-specific: Upload to File API (ONLY if Context Caching is enabled)
            gemini_files = []
            if self.client and self.caching_enabled:
                import mimetypes
                for path in local_files:
                    try:
                        mime_type, _ = await asyncio.to_thread(mimetypes.guess_type, path)
                        logger.info(f"Uploading {path} to Gemini for Cache...")
                        with open(path, 'rb') as f_data:
                            file_upload = await self.client.aio.files.upload(
                                file=f_data,
                                config={'display_name': os.path.basename(path), 'mime_type': mime_type}
                            )
                        
                        while file_upload.state.name == "PROCESSING":
                            await asyncio.sleep(2) 
                            file_upload = await self.client.aio.files.get(name=file_upload.name)
                            
                        if file_upload.state.name == "ACTIVE":
                            gemini_files.append(file_upload)
                    except Exception as e:
                        logger.warning(f"Optional Gemini upload failed: {e}")
                self.active_files = gemini_files
            else:
                self.active_files = []
                if self.caching_enabled:
                    logger.warning("KnowledgeBase: client missing, cannot upload to Gemini")
                else:
                    logger.info("KnowledgeBase: Gemini file upload skipped (caching disabled)")


            # 5. Create Context Cache (CAG)
            if self.caching_enabled and gemini_files:
                try:
                    logger.info("Creating Gemini Context Cache (CAG)...")
                    content_parts = [types.Part.from_uri(file_uri=gf.uri, mime_type=gf.mime_type) for gf in gemini_files]
                    ttl_seconds = self.ttl_minutes * 60
                    si_content = types.Content(parts=[types.Part(text=system_instruction)]) if system_instruction else None
                    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-preview-02-05")
                    cached_content = await self.client.aio.caches.create(
                        model=model_name, 
                        config=types.CreateCachedContentConfig(
                            contents=[types.Content(role='user', parts=content_parts)],
                            system_instruction=si_content,
                            tools=tools,
                            ttl=f"{ttl_seconds}s",
                            display_name="marketing_knowledge_base"
                        )
                    )
                    self.cached_content_name = cached_content.name
                except Exception as e:
                    logger.error(f"Failed to create Gemini cache: {e}")
            
            self.last_update_time = time.time()
            await asyncio.to_thread(self.drive_service.cleanup_tmp_files)
            
        except Exception as e:
            logger.error(f"Error during cache refresh: {e}")
        finally:
            self.is_updating = False

    def get_relevant_context(self, query: str, top_k: int = 5, window_size: int = 1) -> str:
        """Returns the most relevant chunks formatted for the LLM prompt."""
        if not self.search_engine:
            return ""
        
        # Передаем window_size в поисковый движок
        results = self.search_engine.search(query, top_k=top_k, window_size=window_size)
        if not results:
            return ""
        
        context = []
        for res in results:
            metadata = res.get('metadata', {})
            source = metadata.get('source', 'unknown')
            content = res.get('content', '')
            
            # Пытаемся добавить ссылку на файл из Drive
            link = self.file_links.get(source, "")
            source_info = f"{source} (Link: {link})" if link else source
            
            context.append(f"SOURCE: {source_info}\nCONTENT: {content}\n")
            
        return "\n---\n".join(context)

    async def get_active_files(self) -> List[types.File]:
        """Returns the list of active files in Gemini for RAG without cache."""
        return self.active_files

    def get_file_links(self) -> dict:
        """Returns the mapping of filename to Drive URL."""
        return self.file_links
