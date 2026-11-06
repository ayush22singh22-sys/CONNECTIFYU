from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from events.models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification
)
from events.utils import get_default_chain, dispatch_logistics_notifications


class EventLifecycleTestCase(TestCase):
    def setUp(self):
        # 1. Setup Indian Personas
        self.faculty = User.objects.create_user(username='faculty_user', password='password123')
        UserProfile.objects.create(user=self.faculty, role='FACULTY', department='Computer Science & Engineering')

        self.hod_cse = User.objects.create_user(username='hod_user', password='password123')
        UserProfile.objects.create(user=self.hod_cse, role='HOD', department='Computer Science & Engineering')

        self.dean_rnd = User.objects.create_user(username='dean_rnd_user', password='password123')
        UserProfile.objects.create(user=self.dean_rnd, role='DEAN_RESEARCH', department='Research & Consultancy')

        self.dean_fin = User.objects.create_user(username='dean_fin_user', password='password123')
        UserProfile.objects.create(user=self.dean_fin, role='DEAN_ACCOUNTS', department='Finance Office')

        self.dean_acad = User.objects.create_user(username='dean_acad_user', password='password123')
        UserProfile.objects.create(user=self.dean_acad, role='DEAN_ACADEMICS', department='Academic Affairs')

        self.director = User.objects.create_user(username='director_user', password='password123')
        UserProfile.objects.create(user=self.director, role='DIRECTOR', department='Directorate')

        self.student = User.objects.create_user(username='student_user', password='password123')
        UserProfile.objects.create(user=self.student, role='STUDENT', department='Computer Science & Engineering', roll_or_emp_id='21BCSE101')

        # 2. Organizing Unit
        self.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT',
            head=self.hod_cse
        )

        self.client = Client()

    def test_academic_approval_chain_and_logistics_dispatch(self):
        """Tests the Academic approval chain with Dean of Finance budget sanction and Director final clearance."""
        now = timezone.now()
        chain = get_default_chain('ACADEMIC')

        proposal = EventProposal.objects.create(
            title='National AI Summit 2026',
            description='Research symposium on machine learning.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            co_coordinator='Dr. S. Radhakrishnan',
            guest_speaker='Prof. V. Kamakoti',
            chain_type='ACADEMIC',
            approval_chain=chain,
            current_stage_index=0,
            requested_budget=200000.00,
            approved_budget=200000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='APJ Abdul Kalam Auditorium',
            mess_requirements='Lunch for 200 participants.',
            transport_requirements='VIP vehicle for guest speaker.',
            maintenance_requirements='4K Projector and audio system.',
            status='UNDER_REVIEW'
        )

        # Stage 1: HOD Approves
        self.assertEqual(proposal.stage_number, 1)
        self.assertTrue(proposal.is_awaiting_user(self.hod_cse))
        self.client.login(username='hod_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Approved by HOD'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, 1) # Stage 2: Dean R&D

        # Stage 2: Dean R&D Approves
        self.client.login(username='dean_rnd_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Research keynote endorsed.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, 2) # Stage 3: Dean Finance

        # Stage 3: Dean Finance revises budget in INR (₹)
        self.client.login(username='dean_fin_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'REVISE_BUDGET',
            'new_budget': 175000.00,
            'remarks': 'Sanctioned ₹1,75,000 as per hospitality guidelines.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.approved_budget, 175000.00)
        self.assertEqual(proposal.current_stage_index, 3) # Stage 4: Dean Academics

        # Stage 4: Dean Academics Approves
        self.client.login(username='dean_acad_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Academic schedule verified.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, 4) # Stage 5: Director

        # Stage 5: Director Grants Executive Clearance
        self.client.login(username='director_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Final executive clearance granted.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'APPROVED')

        # Automated logistics email verification
        notifications = LogisticsNotification.objects.filter(proposal=proposal)
        self.assertEqual(notifications.count(), 3)

    def test_custom_approval_chain_creation(self):
        """Tests building a custom chain where Dean Finance, Dean Academics, and Director are mandatory."""
        custom_chain = get_default_chain('CUSTOM', custom_roles=['HOD', 'DEAN_RESEARCH'])
        roles = [stage['role'] for stage in custom_chain]

        # Must have custom stages + mandatory 3
        self.assertEqual(roles, ['HOD', 'DEAN_RESEARCH', 'DEAN_ACCOUNTS', 'DEAN_ACADEMICS', 'DIRECTOR'])

    def test_student_blocked_from_proposal_creation(self):
        """Requirement 2: Students are strictly barred from creating/publishing events."""
        self.client.login(username='student_user', password='password123')
        res = self.client.get('/proposals/new/')
        # Should redirect to dashboard ('/') with error
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/')


class AccountsAndSecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Seed whitelist entry for testing signup
        self.whitelist_roll = '22BCSE999'
        from events.models import RollWhitelist
        RollWhitelist.objects.create(
            roll_number=self.whitelist_roll,
            name='Test Student',
            department='Computer Science & Engineering',
            year=2,
            is_used=False
        )

    def test_student_signup_valid_domain_and_whitelist(self):
        """Valid signup with @college.ac.in and whitelisted roll number succeeds."""
        from events.models import RollWhitelist, StudentProfile
        res = self.client.post('/register/', {
            'username': 'teststudent22',
            'first_name': 'Test',
            'last_name': 'Student',
            'email': 'teststudent22@college.ac.in',
            'roll_no': self.whitelist_roll,
            'department': 'Computer Science & Engineering',
            'year': 2,
            'password': 'password123',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/')

        # Verify whitelist consumed
        whitelist_entry = RollWhitelist.objects.get(roll_number=self.whitelist_roll)
        self.assertTrue(whitelist_entry.is_used)

        # Verify StudentProfile created
        user = User.objects.get(username='teststudent22')
        self.assertFalse(user.is_staff)
        self.assertTrue(hasattr(user, 'student_profile'))
        self.assertEqual(user.student_profile.roll_number, self.whitelist_roll)

    def test_student_signup_invalid_email_domain(self):
        """Signup with unauthorized domain (e.g. @gmail.com) is rejected."""
        res = self.client.post('/register/', {
            'username': 'bademailstudent',
            'first_name': 'Bad',
            'last_name': 'Email',
            'email': 'bademail@gmail.com',
            'roll_no': self.whitelist_roll,
            'department': 'Computer Science',
            'year': 1,
            'password': 'password123',
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(username='bademailstudent').exists())

    def test_student_signup_unwhitelisted_roll(self):
        """Signup with roll number not in RollWhitelist is rejected."""
        res = self.client.post('/register/', {
            'username': 'randomstudent',
            'first_name': 'Random',
            'last_name': 'Student',
            'email': 'random@college.ac.in',
            'roll_no': '99UNKNOWN01',
            'department': 'Computer Science',
            'year': 1,
            'password': 'password123',
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(username='randomstudent').exists())

    def test_student_signup_already_used_roll(self):
        """Signup with an already consumed roll number is blocked."""
        from events.models import RollWhitelist
        # Mark as used
        RollWhitelist.objects.filter(roll_number=self.whitelist_roll).update(is_used=True)

        res = self.client.post('/register/', {
            'username': 'dupstudent',
            'first_name': 'Duplicate',
            'last_name': 'Student',
            'email': 'dup@college.ac.in',
            'roll_no': self.whitelist_roll,
            'department': 'Computer Science',
            'year': 1,
            'password': 'password123',
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(username='dupstudent').exists())

    def test_checkin_requires_registration(self):
        """Unregistered student attempting check-in gets an error."""
        faculty = User.objects.create_user(username='fac_ck', password='password123', is_staff=True)
        UserProfile.objects.create(user=faculty, role='FACULTY')
        unit = OrganizingUnit.objects.create(name='Test Unit', unit_type='DEPARTMENT')

        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Checkin Test Event',
            description='Test event',
            proposer=faculty,
            organizing_unit=unit,
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=2),
            venue='Hall A',
            chain_type='ACADEMIC',
            status='APPROVED',
            qr_checkin_token='test-token-123',
        )

        student = User.objects.create_user(username='stu_unregistered', password='password123')
        UserProfile.objects.create(user=student, role='STUDENT')

        self.client.login(username='stu_unregistered', password='password123')
        res = self.client.post('/events/checkin/', {'token': proposal.qr_checkin_token})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(EventRegistration.objects.filter(event=proposal, student=student).exists())


class PhaseBStudentPortalTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.faculty = User.objects.create_user(username='fac_portal', password='password123', is_staff=True)
        UserProfile.objects.create(user=self.faculty, role='FACULTY')

        self.student = User.objects.create_user(username='stu_portal', password='password123', is_staff=False)
        UserProfile.objects.create(user=self.student, role='STUDENT')

        self.dept_cse = OrganizingUnit.objects.create(name='CSE Department', unit_type='DEPARTMENT')
        self.club_robotics = OrganizingUnit.objects.create(name='Robotics Club', unit_type='CLUB')

        now = timezone.now()
        # 1. Approved CSE event
        self.approved_event = EventProposal.objects.create(
            title='Hackathon 2026',
            description='Coding marathon on AI tools.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            start_date=now + timedelta(days=5),
            end_date=now + timedelta(days=6),
            venue='Central Lab',
            guest_speaker='Dr. S. Raman',
            status='APPROVED',
            qr_checkin_token='hack-qr-token'
        )

        # 2. Approved Robotics Club event
        self.robotics_event = EventProposal.objects.create(
            title='Robotics Derby',
            description='Autonomous bot fight contest.',
            proposer=self.faculty,
            organizing_unit=self.club_robotics,
            start_date=now + timedelta(days=10),
            end_date=now + timedelta(days=11),
            venue='Indoor Stadium',
            status='APPROVED',
            qr_checkin_token='derby-qr-token'
        )

        # 3. Unapproved (UNDER_REVIEW) proposal
        self.draft_proposal = EventProposal.objects.create(
            title='Secret Future Conclave',
            description='Still waiting for dean approvals.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            start_date=now + timedelta(days=20),
            end_date=now + timedelta(days=21),
            venue='Auditorium 2',
            status='UNDER_REVIEW',
            qr_checkin_token='secret-token'
        )

    def test_student_events_search_and_filtering(self):
        """Phase B: Verify search query and organizing unit filters."""
        self.client.login(username='stu_portal', password='password123')

        # 1. Default shows both approved events
        res = self.client.get('/events/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Hackathon 2026')
        self.assertContains(res, 'Robotics Derby')
        self.assertNotContains(res, 'Secret Future Conclave')

        # 2. Filter by search query 'Robotics'
        res_search = self.client.get('/events/?q=Robotics')
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, 'Robotics Derby')
        self.assertNotContains(res_search, 'Hackathon 2026')

        # 3. Filter by department unit ID
        res_dept = self.client.get(f'/events/?unit={self.dept_cse.id}')
        self.assertEqual(res_dept.status_code, 200)
        self.assertContains(res_dept, 'Hackathon 2026')
        self.assertNotContains(res_dept, 'Robotics Derby')

    def test_unpublished_event_hidden_from_students(self):
        """Phase B: Students cannot view unpublished event detail pages."""
        self.client.login(username='stu_portal', password='password123')
        res = self.client.get(f'/events/{self.draft_proposal.id}/')
        # Redirects to student_events with error message
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/events/')

        # Staff can view the unpublished event
        self.client.login(username='fac_portal', password='password123')
        res_staff = self.client.get(f'/events/{self.draft_proposal.id}/')
        self.assertEqual(res_staff.status_code, 200)

    def test_event_registration_lifecycle_and_cancellation(self):
        """Phase B: Register -> Update role -> Cancel registration."""
        self.client.login(username='stu_portal', password='password123')

        # 1. Register as PARTICIPANT
        res_reg = self.client.post(f'/events/{self.approved_event.id}/register/', {'role': 'PARTICIPANT'})
        self.assertEqual(res_reg.status_code, 302)
        reg = EventRegistration.objects.get(event=self.approved_event, student=self.student)
        self.assertEqual(reg.role, 'PARTICIPANT')
        self.assertEqual(reg.status, 'REGISTERED')

        # 2. Change role to VOLUNTEER
        res_update = self.client.post(f'/events/{self.approved_event.id}/register/', {'role': 'VOLUNTEER'})
        self.assertEqual(res_update.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.role, 'VOLUNTEER')

        # 3. View detail page shows registered status
        res_detail = self.client.get(f'/events/{self.approved_event.id}/')
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, 'You Are Registered!')
        self.assertContains(res_detail, 'Student Volunteer')

        # 4. Cancel registration
        res_cancel = self.client.post(f'/events/{self.approved_event.id}/cancel/')
        self.assertEqual(res_cancel.status_code, 302)
        self.assertFalse(EventRegistration.objects.filter(event=self.approved_event, student=self.student).exists())

    def test_staff_blocked_from_student_registration(self):
        """Staff members are barred from registering as student attendees."""
        self.client.login(username='fac_portal', password='password123')
        res = self.client.post(f'/events/{self.approved_event.id}/register/', {'role': 'PARTICIPANT'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, f'/events/{self.approved_event.id}/')
        self.assertFalse(EventRegistration.objects.filter(event=self.approved_event, student=self.faculty).exists())

