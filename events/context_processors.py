from django.conf import settings
from events.models import EventProposal

def demo_roles_processor(request):
    """
    Provides demo user accounts and live pending review counters.
    Fix #1 & #22: Demo switcher only visible to superusers in DEBUG mode.
    Avoids information leakage to unauthenticated visitors and regular users.
    """
    demo_accounts = []
    if settings.DEBUG and request.user.is_authenticated and request.user.is_superuser:
        demo_accounts = [
            {'username': 'admin', 'label': 'Superadmin (DB Admin)', 'name': 'Super Administrator', 'role': 'SUPERADMIN'},
            {'username': 'faculty', 'label': 'Faculty Coordinator', 'name': 'Prof. Rajesh Sharma', 'role': 'FACULTY'},
            {'username': 'hod_cse', 'label': 'HOD (CSE)', 'name': 'Dr. K. V. Ramanathan', 'role': 'HOD'},
            {'username': 'hod_ece', 'label': 'HOD (ECE)', 'name': 'Dr. Sunita Kulkarni', 'role': 'HOD'},
            {'username': 'hod_mech', 'label': 'HOD (Mech)', 'name': 'Dr. Vikramaditya Rathore', 'role': 'HOD'},
            {'username': 'club_lead', 'label': 'Club Advisor', 'name': 'Prof. Priya Nair', 'role': 'CLUB_HEAD'},
            {'username': 'dean_finance', 'label': 'Dean (Finance)*', 'name': 'Dr. Suresh Chandra', 'role': 'DEAN_ACCOUNTS'},
            {'username': 'dean_academics', 'label': 'Dean (Academics)*', 'name': 'Dr. Meenakshi Sundaram', 'role': 'DEAN_ACADEMICS'},
            {'username': 'director', 'label': 'Director*', 'name': 'Dr. R. Chidambaram', 'role': 'DIRECTOR'},
            {'username': 'student1', 'label': 'Student 1', 'name': 'Aarav Patel', 'role': 'STUDENT'},
            {'username': 'student2', 'label': 'Student 2', 'name': 'Ananya Sen', 'role': 'STUDENT'},
        ]

    pending_count = 0
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        role = request.user.profile.role
        if role != 'STUDENT':
            # Count proposals currently awaiting this user
            all_proposals = EventProposal.objects.filter(status='UNDER_REVIEW').select_related('organizing_unit')
            pending_count = sum(1 for p in all_proposals if p.is_awaiting_user(request.user))

    return {
        'demo_accounts': demo_accounts,
        'pending_approvals_count': pending_count
    }
