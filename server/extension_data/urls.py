from django.urls import path
from .views import ExtensionCredentialCreateView

urlpatterns = [
    path('credentials/', ExtensionCredentialCreateView.as_view(), name='extension_credential_create'),
]
