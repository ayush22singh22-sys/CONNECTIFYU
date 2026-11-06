from django.urls import path
from . import views

urlpatterns = [
    # Auth & Demo Switcher
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_student_view, name='register'),
    path('switch/<str:username>/', views.switch_user_view, name='switch_user'),

    # Faculty & Proposal Management
    path('proposals/new/', views.create_proposal_view, name='create_proposal'),
    path('proposals/<int:proposal_id>/', views.proposal_detail_view, name='proposal_detail'),
    path('proposals/<int:proposal_id>/edit/', views.edit_proposal_view, name='edit_proposal'),
    path('proposals/<int:proposal_id>/action/', views.process_approval_view, name='process_approval'),

    # Student Event Discovery & Registration
    path('events/', views.student_events_view, name='student_events'),
    path('events/<int:proposal_id>/', views.event_detail_view, name='event_detail'),
    path('events/<int:proposal_id>/register/', views.event_register_view, name='event_register'),
    path('events/<int:proposal_id>/cancel/', views.cancel_registration_view, name='cancel_registration'),
    path('my-registrations/', views.my_registrations_view, name='my_registrations'),

    # QR Presentation & Camera Check-in
    path('events/<int:proposal_id>/live/', views.live_event_view, name='live_event'),
    path('events/checkin/', views.checkin_view, name='checkin'),
    path('registrations/<int:registration_id>/feedback/', views.feedback_view, name='event_feedback'),

    # Compliance & Audit Reports
    path('proposals/<int:proposal_id>/compliance-report/', views.compliance_report_view, name='compliance_report'),
]
