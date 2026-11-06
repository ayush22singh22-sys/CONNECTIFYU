from django.urls import path
from . import views

app_name = 'checkin'

urlpatterns = [
    path('qr/<int:event_pk>/', views.qr_display, name='qr_display'),
    path('scan/', views.CheckInView.as_view(), name='checkin'),
    path('feedback/<int:checkin_pk>/', views.FeedbackView.as_view(), name='feedback'),
]
