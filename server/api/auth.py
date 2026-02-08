"""
Custom token-based authentication for device agents.
"""

from rest_framework import authentication, exceptions
from .models import Device


class DeviceTokenAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication using device tokens.
    
    Clients should authenticate by passing the token in the "Authorization"
    HTTP header, prepended with the string "Token ".
    
    Example:
        Authorization: Token abc123xyz...
    """
    
    keyword = 'Token'
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
        
        parts = auth_header.split()
        
        if len(parts) != 2:
            return None
        
        if parts[0].lower() != self.keyword.lower():
            return None
        
        token = parts[1]
        return self.authenticate_credentials(token, request)
    
    def authenticate_credentials(self, token, request):
        try:
            device = Device.objects.select_related('config').get(
                token=token,
                is_active=True
            )
        except Device.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or inactive device token.')
        
        # Update last seen and IP
        update_fields = ['last_seen']
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        if ip and device.ip_address != ip:
            device.ip_address = ip
            update_fields.append('ip_address')
        
        device.save(update_fields=update_fields)
        
        # Return (user, auth) tuple - we use device as the "user"
        return (device, token)
    
    def authenticate_header(self, request):
        return self.keyword


class DeviceUser:
    """
    A minimal user-like object that wraps a Device for DRF compatibility.
    This is used when DRF expects a user object but we have a device.
    """
    
    def __init__(self, device):
        self.device = device
        self.is_authenticated = True
    
    @property
    def is_active(self):
        return self.device.is_active
    
    def __str__(self):
        return str(self.device)
