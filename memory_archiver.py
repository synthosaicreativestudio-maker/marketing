import os
import logging
import asyncio
from datetime import datetime
from typing import List
from google.genai import types
from drive_service import DriveService

logger = logging.getLogger(__name__)

class MemoryArchiver:
    """Service to archive chat histories into the Knowledge Base on Google Drive."""
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service
        self.folder_id = os.getenv('DRIVE_FOLDER_ID')
        self.owner_email = os.getenv('DRIVE_OWNER_EMAIL')
        self.tmp_dir = "tmp_memory"
        
        # Ensure tmp directory exists
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir, exist_ok=True)

    async def archive_user_history(self, user_id: int, history: List[types.Content]):
        """Archives user conversation to a markdown file and uploads to Drive."""
        if not self.folder_id or not self.drive_service:
            logger.warning("MemoryArchiver: Missing DRIVE_FOLDER_ID or DriveService. Skipping archival.")
            return

        try:
            # Generate file content
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            filename = f"mem_{user_id}.md"
            local_path = os.path.join(self.tmp_dir, filename)
            
            content = f"# Chat Memory: User {user_id}\n"
            content += f"Last Updated: {timestamp}\n\n"
            content += "## Conversation History\n\n"
            
            # Skip first 2 messages (system instruction + confirmation if present)
            start_idx = 0
            if len(history) >= 2:
                # Basic check for system override in first message if provided by GeminiService
                first_msg_text = ""
                if history[0].parts:
                    first_msg_text = str(history[0].parts[0])
                
                if "SYSTEM OVERRIDE" in first_msg_text:
                    start_idx = 2
                
            for msg in history[start_idx:]:
                role = "🤖 AI" if msg.role == "model" else "👤 User"
                text = ""
                if msg.parts:
                    # Extraction of text parts
                    text_parts = []
                    for p in msg.parts:
                        if hasattr(p, 'text') and p.text:
                            text_parts.append(p.text)
                        elif hasattr(p, 'function_call'):
                             text_parts.append(f"[Tool Call: {p.function_call.name}]")
                        elif hasattr(p, 'function_response'):
                             text_parts.append(f"[Tool Response: {p.function_response.name}]")
                    text = "\n".join(text_parts)
                
                if text.strip():
                    content += f"**{role}**: {text}\n\n"

            # Write locally
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Upload to Drive (Sync operation in thread)
            logger.info(f"Archiving memory for user {user_id} to Drive folder {self.folder_id}...")
            await asyncio.to_thread(
                self.drive_service.upload_file, 
                local_path, 
                self.folder_id, 
                filename,
                True, # Overwrite
                self.owner_email
            )
            
        except Exception as e:
            logger.error(f"Failed to archive memory for user {user_id}: {e}", exc_info=True)

    def cleanup(self):
        """Cleanup temporary memory files."""
        if os.path.exists(self.tmp_dir):
            import shutil
            try:
                shutil.rmtree(self.tmp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up memory tmp files: {e}")
