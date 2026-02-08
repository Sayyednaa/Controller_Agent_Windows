from rest_framework import serializers
from .models import ExtensionCredential

class ExtensionCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtensionCredential
        fields = ['url', 'username', 'email', 'password', 'captured_at']
