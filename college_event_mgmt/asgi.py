"""
ASGI config for college_event_mgmt project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_event_mgmt.settings')
application = get_asgi_application()
