import os
import io
import logging
from typing import List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

class DriveService:
    """Service to interact with Google Drive API."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file', 
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive' # Full access for permissions management
    ]
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Drive Service."""
        self.credentials_path = credentials_path or os.getenv('GCP_SA_FILE', 'credentials.json')
        self.creds = None
        self.service = None
        self._authenticate()
        
    def _authenticate(self):
        """Authenticate using Service Account."""
        try:
            if not os.path.exists(self.credentials_path):
                logger.error(f"Credentials file not found: {self.credentials_path}")
                return

            self.creds = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=self.creds)
            logger.info("DriveService authenticated successfully")
        except Exception as e:
            logger.error(f"Failed to authenticate DriveService: {e}")
            self.service = None

    def check_access(self, folder_id: str) -> bool:
        """Check if the service account has access to the folder."""
        if not self.service:
            return False
        try:
            self.service.files().get(fileId=folder_id, fields='id, name').execute()
            return True
        except Exception as e:
            logger.error(f"Access check failed for folder {folder_id}: {e}")
            return False

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Create a folder on Drive."""
        if not self.service:
            return None
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            file = self.service.files().create(body=file_metadata, fields='id').execute()
            folder_id = file.get('id')
            logger.info(f"Created folder '{name}' on Drive (ID: {folder_id})")
            return folder_id
        except Exception as e:
            logger.error(f"Error creating folder {name}: {e}")
            return None

    def list_files(self, folder_id: str) -> List[Dict]:
        """List PDF, PPTX, Docs, and Slides files in the folder."""
        if not self.service:
            logger.warning("DriveService not initialized, cannot list files")
            return []
            
        if not folder_id or str(folder_id).lower() in ('none', ''):
            logger.warning("Invalid folder_id provided for list_files")
            return []
            
        try:
            # Mime types: application/pdf, pptx, docx, text/plain, Google Docs/Slides, Images (png, jpg), Sheets (Google/XLSX)
            query = (
                f"'{folder_id}' in parents and trashed = false and ("
                "mimeType = 'application/pdf' or "
                "mimeType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation' or "
                "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
                "mimeType = 'text/plain' or "
                "mimeType = 'application/vnd.google-apps.document' or "
                "mimeType = 'application/vnd.google-apps.presentation' or "
                "mimeType = 'image/png' or "
                "mimeType = 'image/jpeg' or "
                "mimeType = 'application/vnd.google-apps.spreadsheet' or "
                "mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
            )
            
            results = self.service.files().list(
                q=query,
                pageSize=50,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, size)"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} supported files in Drive folder")
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []

    def download_file(self, file_id: str, file_name: str, mime_type: str) -> Optional[str]:
        """Download a file to a local temporary path. Exports Google Apps to PDF."""
        if not self.service:
            return None
            
        try:
            # Ensure tmp directory exists
            tmp_dir = "tmp_drive_files"
            os.makedirs(tmp_dir, exist_ok=True)
            
            # Handle Google Apps files (Export to PDF or CSV)
            if mime_type in ('application/vnd.google-apps.document', 'application/vnd.google-apps.presentation'):
                # Append .pdf if not present
                if not file_name.lower().endswith('.pdf'):
                    file_name += '.pdf'
                
                logger.info(f"Exporting Google App file {file_name} as PDF...")
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Export Google Sheets as CSV
                if not file_name.lower().endswith('.csv'):
                    file_name += '.csv'
                
                logger.info(f"Exporting Google Sheet {file_name} as CSV...")
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='text/csv'
                )
            else:
                # Regular download (PDF, PPTX, DOCX, TXT, Images, XLSX)
                request = self.service.files().get_media(fileId=file_id)
            
            file_path = os.path.join(tmp_dir, file_name)
            
            fh = io.FileIO(file_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            logger.info(f"Downloaded {file_name} to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None

    def cleanup_tmp_files(self):
        """Clean up temporary files."""
        import shutil
        tmp_dir = "tmp_drive_files"
        if os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
                logger.info("Cleaned up temporary drive files")
            except Exception as e:
                logger.error(f"Error cleaning up tmp files: {e}")

    def upload_file(self, local_path: str, folder_id: str, display_name: Optional[str] = None, overwrite: bool = True, owner_email: Optional[str] = None) -> Optional[str]:
        """Upload a local file to a specific Drive folder. Overwrites if it already exists.
        If owner_email is provided, attempts to transfer ownership to avoid quota issues."""
        if not self.service:
            logger.error("DriveService not initialized, cannot upload")
            return None
        
        from googleapiclient.http import MediaFileUpload
        try:
            name = display_name or os.path.basename(local_path)
            media = MediaFileUpload(local_path, resumable=True)
            
            # 1. Look for existing file
            existing_id = None
            if overwrite:
                query = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
                results = self.service.files().list(q=query, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                files = results.get('files', [])
                if files:
                    existing_id = files[0].get('id')

            if existing_id:
                logger.info(f"Updating existing file {name} (ID: {existing_id})...")
                file = self.service.files().update(
                    fileId=existing_id,
                    media_body=media,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                return existing_id
            else:
                # 2. Create new file
                logger.info(f"Creating NEW file {name} in folder {folder_id}...")
                file_metadata = {
                    'name': name,
                    'parents': [folder_id]
                }
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                file_id = file.get('id')
                
                # 3. Transfer ownership IMMEDIATELY if possible to avoid quota issues for next updates
                if owner_email and file_id:
                    try:
                        logger.info(f"Transferring ownership of {name} to {owner_email}...")
                        self.service.permissions().create(
                            fileId=file_id,
                            body={'type': 'user', 'role': 'owner', 'emailAddress': owner_email},
                            transferOwnership=True,
                            supportsAllDrives=True
                        ).execute()
                    except Exception as pe:
                        logger.warning(f"Could not transfer ownership of {name}: {pe}")
                
                return file_id
        except Exception as e:
            if 'storageQuotaExceeded' in str(e):
                logger.error(f"QUOTA ERROR: Service Account has no quota to create '{name}'. Please ask owner to create a placeholder file.")
            else:
                logger.error(f"Error uploading file {local_path} to Drive: {e}")
            return None
