from django.db import models

class ExtensionCredential(models.Model):
    url = models.URLField(max_length=2000)
    username = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255)
    captured_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username or self.email} @ {self.url}"
