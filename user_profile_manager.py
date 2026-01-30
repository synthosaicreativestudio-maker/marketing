import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from drive_service import DriveService

logger = logging.getLogger(__name__)

class UserProfileManager:
    """Manages user profile cards (JSON) on Google Drive for long-term memory."""
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service
        self.folder_id = os.getenv('DRIVE_PROFILES_FOLDER_ID') # Separate folder for profiles
        self.owner_email = os.getenv('DRIVE_OWNER_EMAIL')
        self.local_cache_dir = "tmp_profiles"
        self._profiles_cache: Dict[int, Dict[str, Any]] = {}
        
        if not os.path.exists(self.local_cache_dir):
            os.makedirs(self.local_cache_dir, exist_ok=True)

    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        """Retrieves user profile. Checks local cache, then Drive."""
        if user_id in self._profiles_cache:
            return self._profiles_cache[user_id]
        
        filename = f"profile_{user_id}.json"
        local_path = os.path.join(self.local_cache_dir, filename)
        
        # 1. Try to download from Drive
        if self.folder_id and self.drive_service:
            try:
                # Find file ID on Drive
                files = await asyncio.to_thread(self.drive_service.list_files, self.folder_id)
                profile_file = next((f for f in files if f['name'] == filename), None)
                
                if profile_file:
                    path = await asyncio.to_thread(
                        self.drive_service.download_file, 
                        profile_file['id'], filename, 'application/json'
                    )
                    if path and os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                            self._profiles_cache[user_id] = profile
                            return profile
            except Exception as e:
                logger.error(f"Error downloading profile for {user_id}: {e}")

        # 2. Defaults if not found
        return {"user_id": user_id, "first_name": "Unknown", "interests": [], "last_seen": None}

    async def update_profile(self, user_id: int, updates: Dict[str, Any]):
        """Updates user profile locally and on Drive."""
        profile = await self.get_profile(user_id)
        profile.update(updates)
        self._profiles_cache[user_id] = profile
        
        filename = f"profile_{user_id}.json"
        local_path = os.path.join(self.local_cache_dir, filename)
        
        try:
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            
            if self.folder_id and self.drive_service:
                await asyncio.to_thread(
                    self.drive_service.upload_file,
                    local_path,
                    self.folder_id,
                    filename,
                    True, # Overwrite
                    self.owner_email
                )
        except Exception as e:
            logger.error(f"Error saving profile for {user_id}: {e}")

    async def get_system_context(self, user_id: int) -> str:
        """Generates a system prompt snippet based on the user profile."""
        profile = await self.get_profile(user_id)
        name = profile.get("first_name", "User")
        interests = ", ".join(profile.get("interests", []))
        city = profile.get("city", "Unknown")
        
        context = f"\n[USER PROFILE]\nName: {name}\nCity: {city}\nInterests: {interests}\n"
        if profile.get("last_note"):
            context += f"Important Note: {profile['last_note']}\n"
        return context
