"""
Browser process monitor for auto-screenshot triggers.
Detects when monitored browser processes start.
"""

import logging
import threading
import time
from typing import Callable, List, Optional, Set

try:
    import psutil
except ImportError:
    raise ImportError("Required package: psutil. Install with: pip install psutil")

logger = logging.getLogger(__name__)


class BrowserMonitor:
    """
    Monitors running processes for browser launches.
    Triggers callback when a monitored browser is detected.
    """
    
    DEFAULT_BROWSERS = [
        'chrome.exe',
        'firefox.exe', 
        'msedge.exe',
        'brave.exe',
        'opera.exe',
        'iexplore.exe',
        'vivaldi.exe',
        'chromium.exe',
    ]
    
    def __init__(
        self, 
        browser_list: List[str] = None,
        check_interval: float = 2.0,
        cooldown: float = 30.0
    ):
        self.browser_list = [b.lower() for b in (browser_list or self.DEFAULT_BROWSERS)]
        self.check_interval = check_interval
        self.cooldown = cooldown  # Seconds to wait before triggering again
        
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._on_browser_detected: Optional[Callable] = None
        
        # Track known running browsers to detect new launches
        self._known_browsers: Set[int] = set()  # PIDs of known running browsers
        self._last_trigger: float = 0
    
    def set_callback(self, callback: Callable[[str, str], None]):
        """
        Set the callback for browser detection.
        Callback signature: callback(process_name: str, window_title: str)
        """
        self._on_browser_detected = callback
    
    def update_browser_list(self, browsers: List[str]):
        """Update the list of browsers to monitor."""
        self.browser_list = [b.lower() for b in browsers]
        logger.debug(f"Updated browser list: {self.browser_list}")
    
    def _get_running_browsers(self) -> dict:
        """Get currently running browser processes."""
        browsers = {}
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = proc.info['name'].lower()
                    if name in self.browser_list:
                        browsers[proc.info['pid']] = name
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.error(f"Error getting browser processes: {e}")
        return browsers
    
    def _check_for_new_browsers(self):
        """Check for newly launched browsers."""
        current_browsers = self._get_running_browsers()
        current_pids = set(current_browsers.keys())
        
        # Find new PIDs
        new_pids = current_pids - self._known_browsers
        
        if new_pids:
            # Check cooldown
            now = time.time()
            if now - self._last_trigger < self.cooldown:
                logger.debug(f"Browser detected but in cooldown period")
                self._known_browsers = current_pids
                return
            
            # Get first new browser
            first_new_pid = next(iter(new_pids))
            browser_name = current_browsers[first_new_pid]
            
            logger.info(f"🌐 New browser detected: {browser_name} (PID: {first_new_pid})")
            
            # Trigger callback
            if self._on_browser_detected:
                try:
                    self._on_browser_detected(browser_name, "")
                    self._last_trigger = now
                except Exception as e:
                    logger.error(f"Browser callback error: {e}")
        
        # Update known browsers
        self._known_browsers = current_pids
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        # Initial scan
        self._known_browsers = set(self._get_running_browsers().keys())
        
        while self._running:
            try:
                self._check_for_new_browsers()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            time.sleep(self.check_interval)
    
    def start(self):
        """Start browser monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Browser monitoring started")
    
    def stop(self):
        """Stop browser monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
        logger.info("Browser monitoring stopped")
    
    def is_running(self) -> bool:
        """Check if monitoring is active."""
        return self._running


# Singleton instance
_browser_monitor: Optional[BrowserMonitor] = None


def get_browser_monitor() -> Optional[BrowserMonitor]:
    """Get the browser monitor instance."""
    return _browser_monitor


def init_browser_monitor(**kwargs) -> BrowserMonitor:
    """Initialize the browser monitor singleton."""
    global _browser_monitor
    _browser_monitor = BrowserMonitor(**kwargs)
    return _browser_monitor
