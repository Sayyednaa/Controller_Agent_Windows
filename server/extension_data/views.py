from rest_framework import generics, permissions
from .models import ExtensionCredential
from .serializers import ExtensionCredentialSerializer

class ExtensionCredentialCreateView(generics.CreateAPIView):
    queryset = ExtensionCredential.objects.all()
    serializer_class = ExtensionCredentialSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return response
