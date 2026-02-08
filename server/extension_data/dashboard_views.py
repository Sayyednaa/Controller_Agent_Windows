from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import ExtensionCredential

class ExtensionCredentialListView(LoginRequiredMixin, ListView):
    model = ExtensionCredential
    template_name = 'extension_data/credential_list.html'
    context_object_name = 'credentials'
    ordering = ['-captured_at']
    paginate_by = 50
