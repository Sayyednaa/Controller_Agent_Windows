"""
URL configuration for Controller Agent server.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/extension/', include('extension_data.urls')),
    # Dashboard web frontend
    path('', include('api.dashboard_urls')),
]
