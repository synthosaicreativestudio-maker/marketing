import logging
import asyncio
from typing import Dict, Any, Optional, List
from sheets_gateway import AsyncGoogleSheetsGateway
import os

logger = logging.getLogger(__name__)

class UserProfileManagerSheets:
    """Manages user profiles in a Google Sheets tab instead of JSON files to avoid Drive quota issues."""
    
    def __init__(self, sheets_gateway: AsyncGoogleSheetsGateway):
        self.gateway = sheets_gateway
        self.spreadsheet_id = os.getenv('APPEALS_SHEET_ID') or os.getenv('SPREADSHEET_ID')
        self.sheet_name = "profiles"
        self._cache: Dict[int, Dict[str, Any]] = {}
        logger.info(f"UserProfileManagerSheets initialized with Spreadsheet ID: {self.spreadsheet_id}")
        
    async def _ensure_sheet(self):
        """Checks if 'profiles' sheet exists, creates it with headers if not."""
        try:
            client = await self.gateway.authorize_client()
            spreadsheet = await self.gateway.open_spreadsheet(client, self.spreadsheet_id)
            worksheets = await asyncio.to_thread(spreadsheet.worksheets)
            titles = [s.title for s in worksheets]
            
            if self.sheet_name not in titles:
                logger.info(f"Creating sheet '{self.sheet_name}' in spreadsheet {self.spreadsheet_id}")
                worksheet = await asyncio.to_thread(spreadsheet.add_worksheet, title=self.sheet_name, rows=5000, cols=10)
                
                # Add headers
                headers = [['user_id', 'first_name', 'last_name', 'username', 'interests', 'city', 'last_note', 'last_seen']]
                await self.gateway.update(worksheet, 'A1:H1', headers)
                logger.info("Sheet 'profiles' created successfully.")
        except Exception as e:
            logger.error(f"Error ensuring profiles sheet: {e}")

    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        """Retrieves user profile from Sheets."""
        if user_id in self._cache:
            return self._cache[user_id]
            
        await self._ensure_sheet()
        
        try:
            client = await self.gateway.authorize_client()
            spreadsheet = await self.gateway.open_spreadsheet(client, self.spreadsheet_id)
            worksheet = await self.gateway.get_worksheet_async(spreadsheet, self.sheet_name)
            
            rows = await self.gateway.get_all_records(worksheet)
            if not rows:
                return self._get_default(user_id)
                
            for i, row in enumerate(rows, start=2): # Header is row 1
                if str(row.get('user_id')) == str(user_id):
                    # Found user!
                    profile = dict(row)
                    # Handle interests (stored as comma-string)
                    if isinstance(profile.get('interests'), str):
                        profile['interests'] = [i.strip() for i in profile['interests'].split(',')] if profile['interests'] else []
                    
                    profile['row_index'] = i
                    self._cache[user_id] = profile
                    return profile
                    
        except Exception as e:
            logger.error(f"Error getting profile for {user_id}: {e}")
            
        return self._get_default(user_id)

    def _get_default(self, user_id: int) -> Dict[str, Any]:
        return {"user_id": user_id, "first_name": "Unknown", "interests": [], "last_seen": None}

    async def update_profile(self, user_id: int, updates: Dict[str, Any]):
        """Updates user profile in Sheets."""
        profile = await self.get_profile(user_id)
        profile.update(updates)
        self._cache[user_id] = profile
        
        await self._ensure_sheet()
        
        # Prepare row data
        interests_str = ", ".join(profile.get('interests', [])) if isinstance(profile.get('interests'), list) else ""
        row_data = [
            str(user_id),
            profile.get('first_name', ''),
            profile.get('last_name', ''),
            profile.get('username', ''),
            interests_str,
            profile.get('city', ''),
            profile.get('last_note', ''),
            profile.get('last_seen', str(profile.get('last_seen', '')))
        ]
        
        try:
            client = await self.gateway.authorize_client()
            spreadsheet = await self.gateway.open_spreadsheet(client, self.spreadsheet_id)
            worksheet = await self.gateway.get_worksheet_async(spreadsheet, self.sheet_name)
            
            row_idx = profile.get('row_index')
            if row_idx:
                # Update existing row
                range_name = f"A{row_idx}:H{row_idx}"
                await self.gateway.update(worksheet, range_name, [row_data])
            else:
                # Append new row
                await self.gateway.append_row(worksheet, row_data)
                # After append, find its index to avoid duplicate appends next time
                new_rows = await self.gateway.get_all_records(worksheet)
                profile['row_index'] = len(new_rows) + 1
        except Exception as e:
            logger.error(f"Error updating profile for {user_id}: {e}")

    async def get_system_context(self, user_id: int) -> str:
        """Generates a system prompt snippet based on the user profile."""
        profile = await self.get_profile(user_id)
        name = profile.get("first_name", "User")
        interests = ", ".join(profile.get("interests", [])) if isinstance(profile.get("interests"), list) else ""
        
        context = f"\n[USER PROFILE]\nName: {name}\nInterests: {interests}\n"
        if profile.get("last_note"):
            context += f"Important Note: {profile['last_note']}\n"
        return context
