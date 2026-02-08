import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controller.settings')
django.setup()

from extension_data.models import ExtensionCredential

count = ExtensionCredential.objects.count()
print(f"Total Extension Credentials: {count}")

if count > 0:
    last_cred = ExtensionCredential.objects.last()
    print(f"Last Credential: {last_cred}")
