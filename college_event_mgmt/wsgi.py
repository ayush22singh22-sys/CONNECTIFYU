"""
WSGI config for college_event_mgmt project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_event_mgmt.settings')
application = get_wsgi_application()
