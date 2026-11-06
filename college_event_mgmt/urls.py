"""college_event_mgmt URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('events/', include('events.urls')),
    path('checkin/', include('checkin.urls')),
    path('reports/', include('reports.urls')),
    path('', RedirectView.as_view(url='/events/dashboard/', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
