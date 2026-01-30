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
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = "profiles"
        self._cache: Dict[int, Dict[str, Any]] = {}
        
    async def _ensure_sheet(self):
        """Checks if 'profiles' sheet exists, creates it with headers if not."""
        try:
            spreadsheet = await asyncio.to_thread(
                self.gateway.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute
            )
            sheets = [s.get('properties', {}).get('title') for s in spreadsheet.get('sheets', [])]
            
            if self.sheet_name not in sheets:
                logger.info(f"Creating sheet '{self.sheet_name}' in spreadsheet {self.spreadsheet_id}")
                body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': self.sheet_name,
                                'gridProperties': {'rowCount': 5000, 'columnCount': 10}
                            }
                        }
                    }]
                }
                await asyncio.to_thread(
                    self.gateway.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute
                )
                
                # Add headers
                headers = [['user_id', 'first_name', 'last_name', 'username', 'interests', 'city', 'last_note', 'last_seen']]
                await asyncio.to_thread(
                    self.gateway.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{self.sheet_name}!A1:H1",
                        valueInputOption='RAW',
                        body={'values': headers}
                    ).execute
                )
                logger.info("Sheet 'profiles' created successfully.")
        except Exception as e:
            logger.error(f"Error ensuring profiles sheet: {e}")

    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        """Retrieves user profile from Sheets."""
        if user_id in self._cache:
            return self._cache[user_id]
            
        await self._ensure_sheet()
        
        try:
            result = await asyncio.to_thread(
                self.gateway.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A:H"
                ).execute
            )
            rows = result.get('values', [])
            if not rows or len(rows) < 2:
                return self._get_default(user_id)
                
            headers = rows[0]
            for i, row in enumerate(rows[1:], start=2):
                if row and str(row[0]) == str(user_id):
                    # Found user!
                    profile = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}
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
            profile.get('last_seen', '')
        ]
        
        try:
            row_idx = profile.get('row_index')
            if row_idx:
                # Update existing row
                range_name = f"{self.sheet_name}!A{row_idx}:H{row_idx}"
                await asyncio.to_thread(
                    self.gateway.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body={'values': [row_data]}
                    ).execute
                )
            else:
                # Append new row
                await asyncio.to_thread(
                    self.gateway.service.spreadsheets().values().append(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"{self.sheet_name}!A:H",
                        valueInputOption='RAW',
                        body={'values': [row_data]}
                    ).execute
                )
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
