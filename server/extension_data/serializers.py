from rest_framework import serializers
from .models import ExtensionCredential

class ExtensionCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionCredential
        fields = ['url', 'username', 'email', 'password', 'captured_at']
        read_only_fields = ['captured_at']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
            'username': {'required': False, 'allow_blank': True},
        }
