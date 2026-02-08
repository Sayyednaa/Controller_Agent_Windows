"""
Device authentication and hardware identification.
"""

import hashlib
import logging
import os
import platform
import socket
import subprocess
import uuid
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def get_hardware_id() -> str:
    """
    Generate a unique hardware ID for this device.
    Based on a combination of system identifiers for stability.
    """
    # Check for custom hardware ID in environment
    custom_id = os.getenv('HARDWARE_ID')
    if custom_id:
        return custom_id
    
    identifiers = []
    
    # 1. Machine UUID (most reliable on Windows)
    try:
        result = subprocess.run(
            ['wmic', 'csproduct', 'get', 'uuid'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                machine_uuid = lines[1].strip()
                if machine_uuid and machine_uuid != 'UUID':
                    identifiers.append(machine_uuid)
    except Exception as e:
        logger.debug(f"Could not get machine UUID: {e}")
    
    # 2. MAC address as fallback
    try:
        mac = uuid.getnode()
        mac_str = ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))
        identifiers.append(mac_str)
    except Exception as e:
        logger.debug(f"Could not get MAC address: {e}")
    
    # 3. Computer name
    try:
        identifiers.append(socket.gethostname())
    except Exception:
        pass
    
    # Combine and hash for consistent length
    combined = '|'.join(identifiers)
    hardware_id = hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    return hardware_id


def get_hostname() -> str:
    """Get the computer hostname."""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


def get_os_version() -> str:
    """Get the operating system version string."""
    try:
        return f"{platform.system()} {platform.release()} {platform.version()}"
    except Exception:
        return "Unknown OS"


class DeviceAuth:
    """
    Handles device authentication with the server.
    """
    
    AGENT_VERSION = "1.0.0"
    
    def __init__(self, queue_manager):
        self.queue_manager = queue_manager
        self._token: Optional[str] = None
        self._device_id: Optional[str] = None
        self._load_stored_auth()
    
    def _load_stored_auth(self):
        """Load stored authentication from database."""
        self._token = self.queue_manager.get_auth_token()
        self._device_id = self.queue_manager.get_device_id()
        
        if self._token:
            logger.info("Loaded stored authentication token")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid auth token."""
        return self._token is not None
    
    @property
    def token(self) -> Optional[str]:
        """Get the current auth token."""
        return self._token
    
    @property
    def device_id(self) -> Optional[str]:
        """Get the stored device ID."""
        return self._device_id
    
    def store_auth(self, token: str, device_id: str):
        """Store authentication credentials."""
        self._token = token
        self._device_id = device_id
        self.queue_manager.set_auth_token(token)
        self.queue_manager.set_device_id(device_id)
        logger.info(f"Stored authentication for device {device_id}")
    
    def clear_auth(self):
        """Clear stored authentication."""
        self._token = None
        self._device_id = None
        # Note: We don't delete from DB to allow recovery
        logger.info("Cleared authentication")
    
    def get_registration_data(self) -> dict:
        """Get data for device registration request."""
        return {
            'hardware_id': get_hardware_id(),
            'hostname': get_hostname(),
            'os_version': get_os_version(),
            'agent_version': self.AGENT_VERSION,
        }
    
    def get_auth_headers(self) -> dict:
        """Get authentication headers for API requests."""
        if not self._token:
            return {}
        return {'Authorization': f'Token {self._token}'}
