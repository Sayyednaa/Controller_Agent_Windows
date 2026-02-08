"""
Screenshot capture engine.
Captures screen with active window context.
"""

import ctypes
import io
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Optional, Tuple

try:
    import mss
    from PIL import Image
except ImportError as e:
    raise ImportError("Required packages: mss, Pillow. Install with: pip install mss Pillow") from e

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """
    Captures screenshots with window context.
    Uses mss for fast multi-monitor support.
    """
    
    def __init__(self, quality: int = 75, temp_dir: str = None):
        self.quality = quality
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # Windows API for window titles
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
    
    def get_active_window_info(self) -> Tuple[str, str]:
        """
        Get the currently active window title and process name.
        Returns (window_title, process_name)
        """
        try:
            hwnd = self.user32.GetForegroundWindow()
            if not hwnd:
                return "Unknown Window", ""
            
            # Get window title
            length = self.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buf, length + 1)
            window_title = buf.value
            
            # Get process name
            process_name = ""
            try:
                import psutil
                pid = ctypes.c_ulong()
                self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                process = psutil.Process(pid.value)
                process_name = process.name()
            except Exception:
                pass
            
            return window_title, process_name
            
        except Exception as e:
            logger.error(f"Error getting window info: {e}")
            return "Unknown", ""
    
    def capture(
        self, 
        monitor: int = 0,
        save_path: str = None
    ) -> Optional[Tuple[str, int, int, str, str]]:
        """
        Capture a screenshot.
        
        Args:
            monitor: Monitor index (0 = all monitors, 1+ = specific monitor)
            save_path: Optional path to save the screenshot
        
        Returns:
            Tuple of (file_path, width, height, window_title, process_name) or None
        """
        try:
            with mss.mss() as sct:
                # Get monitor to capture
                if monitor == 0:
                    # All monitors combined
                    mon = sct.monitors[0]
                else:
                    # Specific monitor
                    mon = sct.monitors[min(monitor, len(sct.monitors) - 1)]
                
                # Capture
                screenshot = sct.grab(mon)
                
                # Convert to PIL Image
                img = Image.frombytes(
                    'RGB', 
                    (screenshot.width, screenshot.height), 
                    screenshot.rgb
                )
                
                # Get window info
                window_title, process_name = self.get_active_window_info()
                
                # Generate filename if not provided
                if not save_path:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
                    save_path = os.path.join(self.temp_dir, filename)
                
                # Save as JPEG with quality setting
                img.save(save_path, 'JPEG', quality=self.quality, optimize=True)
                
                logger.info(f"📸 Screenshot captured: {save_path} ({img.width}x{img.height})")
                
                return (
                    save_path,
                    img.width,
                    img.height,
                    window_title,
                    process_name
                )
                
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None
    
    def capture_to_bytes(self, monitor: int = 0) -> Optional[Tuple[bytes, int, int, str, str]]:
        """
        Capture a screenshot and return as bytes (without saving to disk).
        
        Returns:
            Tuple of (jpeg_bytes, width, height, window_title, process_name) or None
        """
        try:
            with mss.mss() as sct:
                if monitor == 0:
                    mon = sct.monitors[0]
                else:
                    mon = sct.monitors[min(monitor, len(sct.monitors) - 1)]
                
                screenshot = sct.grab(mon)
                img = Image.frombytes(
                    'RGB', 
                    (screenshot.width, screenshot.height), 
                    screenshot.rgb
                )
                
                window_title, process_name = self.get_active_window_info()
                
                # Save to bytes
                buffer = io.BytesIO()
                img.save(buffer, 'JPEG', quality=self.quality, optimize=True)
                jpeg_bytes = buffer.getvalue()
                
                return (
                    jpeg_bytes,
                    img.width,
                    img.height,
                    window_title,
                    process_name
                )
                
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None


# Singleton instance
_screenshot_capture: Optional[ScreenshotCapture] = None


def get_screenshot_capture() -> Optional[ScreenshotCapture]:
    """Get the screenshot capture instance."""
    return _screenshot_capture


def init_screenshot_capture(quality: int = 75) -> ScreenshotCapture:
    """Initialize the screenshot capture singleton."""
    global _screenshot_capture
    _screenshot_capture = ScreenshotCapture(quality=quality)
    return _screenshot_capture
