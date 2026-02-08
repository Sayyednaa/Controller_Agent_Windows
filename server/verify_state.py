import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controller.settings')
django.setup()

from api.models import BrowserCredential, BrowserHistory, Device

print(f"Total Devices: {Device.objects.count()}")
print(f"Total Credentials: {BrowserCredential.objects.count()}")
print(f"Total History Items: {BrowserHistory.objects.count()}")

# Check for v20 labels to see if any are still App-Bound (should be 0 or renamed)
v20_count = BrowserCredential.objects.filter(password_value__icontains='v20').count()
print(f"App-Bound (v20) labeled credentials: {v20_count}")

# Check for Error 13/87 labels
error_count = BrowserCredential.objects.filter(password_value__icontains='Error').count()
print(f"Error labeled credentials: {error_count}")

try:
    from api.models import BrowserCookie
    print("BrowserCookie model still exists!")
except ImportError:
    print("BrowserCookie model successfully removed.")
