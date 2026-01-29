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
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
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

    def list_files(self, folder_id: str) -> List[Dict]:
        """List PDF, PPTX, Docs, and Slides files in the folder."""
        if not self.service:
            logger.warning("DriveService not initialized, cannot list files")
            return []
            
        if not folder_id or str(folder_id).lower() in ('none', ''):
            logger.warning("Invalid folder_id provided for list_files")
            return []
            
        try:
            # Query for supported types not in trash
            # Mime types: application/pdf, application/vnd.openxmlformats-officedocument.presentationml.presentation
            # application/vnd.openxmlformats-officedocument.wordprocessingml.document
            # text/plain
            # application/vnd.google-apps.document (Google Docs)
            # application/vnd.google-apps.presentation (Google Slides)
            
            query = (
                f"'{folder_id}' in parents and trashed = false and ("
                "mimeType = 'application/pdf' or "
                "mimeType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation' or "
                "mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
                "mimeType = 'text/plain' or "
                "mimeType = 'application/vnd.google-apps.document' or "
                "mimeType = 'application/vnd.google-apps.presentation')"
            )
            
            results = self.service.files().list(
                q=query,
                pageSize=50,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)"
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
            
            # Handle Google Apps files (Export to PDF)
            if mime_type in ('application/vnd.google-apps.document', 'application/vnd.google-apps.presentation'):
                # Append .pdf if not present
                if not file_name.lower().endswith('.pdf'):
                    file_name += '.pdf'
                
                logger.info(f"Exporting Google App file {file_name} as PDF...")
                request = self.service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            else:
                # Regular download
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
