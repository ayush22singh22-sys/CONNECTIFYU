from events.models import EventProposal

def demo_roles_processor(request):
    """Provides authentic Indian college demo user accounts and live pending review counters."""
    demo_accounts = [
        {'username': 'faculty', 'label': 'Faculty Coordinator', 'name': 'Prof. Rajesh Sharma', 'role': 'FACULTY'},
        {'username': 'hod_cse', 'label': 'HOD (CSE Dept)', 'name': 'Dr. K. V. Ramanathan', 'role': 'HOD'},
        {'username': 'club_lead', 'label': 'Club Faculty Advisor', 'name': 'Prof. Priya Nair', 'role': 'CLUB_HEAD'},
        {'username': 'registrar', 'label': 'Registrar (Admin/HR)', 'name': 'Smt. Sunita Deshmukh', 'role': 'REGISTRAR'},
        {'username': 'dean_research', 'label': 'Dean (R&D)', 'name': 'Dr. P. Venkatraman', 'role': 'DEAN_RESEARCH'},
        {'username': 'dean_dsw', 'label': 'Dean (Student Welfare)', 'name': 'Dr. Alok Sen', 'role': 'DEAN_STUDENT_WELFARE'},
        {'username': 'dean_finance', 'label': 'Dean (Finance & Accounts)', 'name': 'Dr. Suresh Chandra', 'role': 'DEAN_ACCOUNTS'},
        {'username': 'dean_academics', 'label': 'Dean (Academics)', 'name': 'Dr. Meenakshi Sundaram', 'role': 'DEAN_ACADEMICS'},
        {'username': 'director', 'label': 'Director of Institute', 'name': 'Dr. R. Chidambaram', 'role': 'DIRECTOR'},
        {'username': 'student1', 'label': 'Student 1', 'name': 'Aarav Patel', 'role': 'STUDENT'},
        {'username': 'student2', 'label': 'Student 2', 'name': 'Ananya Sen', 'role': 'STUDENT'},
    ]

    pending_count = 0
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        role = request.user.profile.role
        if role != 'STUDENT':
            # Count proposals currently awaiting this user
            all_proposals = EventProposal.objects.filter(status='UNDER_REVIEW')
            pending_count = sum(1 for p in all_proposals if p.is_awaiting_user(request.user))

    return {
        'demo_accounts': demo_accounts,
        'pending_approvals_count': pending_count
    }
