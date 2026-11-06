from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('event/<int:event_pk>/', views.compliance_report, name='compliance_report'),
]
