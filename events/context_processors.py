from django.contrib.auth.models import User
from events.models import UserProfile, EventProposal

def demo_roles_processor(request):
    """Provides demo user accounts and quick stats for the global navigation."""
    demo_accounts = [
        {'username': 'faculty', 'label': 'Faculty / Proposer', 'name': 'Prof. Alan Turing', 'role': 'FACULTY'},
        {'username': 'hod_cs', 'label': 'HOD (CS Dept)', 'name': 'Dr. Grace Hopper', 'role': 'HOD'},
        {'username': 'club_head', 'label': 'Club President', 'name': 'Alex Johnson', 'role': 'CLUB_HEAD'},
        {'username': 'hr_admin', 'label': 'HR Reviewer', 'name': 'Sarah Jenkins', 'role': 'HR'},
        {'username': 'dean_research', 'label': 'Dean of Research', 'name': 'Dr. Richard Feynman', 'role': 'DEAN_RESEARCH'},
        {'username': 'dean_accounts', 'label': 'Dean of Accounts', 'name': 'Dr. Milton Friedman', 'role': 'DEAN_ACCOUNTS'},
        {'username': 'dean_academics', 'label': 'Dean of Academics / Director', 'name': 'Dr. APJ Kalam', 'role': 'DEAN_ACADEMICS'},
        {'username': 'student1', 'label': 'Student 1', 'name': 'John Doe', 'role': 'STUDENT'},
        {'username': 'student2', 'label': 'Student 2', 'name': 'Jane Smith', 'role': 'STUDENT'},
    ]

    pending_count = 0
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        role = request.user.profile.role
        if role == 'HOD':
            pending_count = EventProposal.objects.filter(status='STAGE_1_UNIT_HEAD', organizing_unit__unit_type='DEPARTMENT').count()
        elif role == 'CLUB_HEAD':
            pending_count = EventProposal.objects.filter(status='STAGE_1_UNIT_HEAD', organizing_unit__unit_type='CLUB').count()
        elif role == 'HR':
            pending_count = EventProposal.objects.filter(status='STAGE_2_HR').count()
        elif role == 'DEAN_RESEARCH':
            pending_count = EventProposal.objects.filter(status='STAGE_3_DEAN_RESEARCH').count()
        elif role == 'DEAN_ACCOUNTS':
            pending_count = EventProposal.objects.filter(status='STAGE_4_DEAN_ACCOUNTS').count()
        elif role == 'DEAN_ACADEMICS':
            pending_count = EventProposal.objects.filter(status='STAGE_5_DEAN_ACADEMICS').count()

    return {
        'demo_accounts': demo_accounts,
        'pending_approvals_count': pending_count
    }
