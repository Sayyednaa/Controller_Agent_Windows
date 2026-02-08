"""
WSGI config for Controller Agent server.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controller.settings')

application = get_wsgi_application()
