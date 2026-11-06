from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('faculty-dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('approver-dashboard/', views.approver_dashboard, name='approver_dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('list/', views.event_list, name='event_list'),
    path('new/', views.EventCreateView.as_view(), name='event_create'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    path('<int:pk>/edit/', views.EventEditView.as_view(), name='event_edit'),
    path('<int:pk>/approve/', views.ApprovalActionView.as_view(), name='approval_action'),
    path('<int:pk>/register/', views.register_for_event, name='register_for_event'),
]
