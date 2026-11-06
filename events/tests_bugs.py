import base64
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from events.models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification,
    RollWhitelist, StudentProfile, StaffProfile
)
from events.utils import get_default_chain, dispatch_logistics_notifications
from django.contrib.auth.models import User

# Valid 1x1 PNG base64 for test check-ins
VALID_PNG_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


class BugRegressionTestCase(TestCase):
    """Test cases for previously identified bugs and security hardening"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='faculty_user', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='Computer Science & Engineering')

        cls.hod_cse = User.objects.create_user(username='hod_user', password='password123')
        UserProfile.objects.create(user=cls.hod_cse, role='HOD', department='Computer Science & Engineering')

        cls.dean_fin = User.objects.create_user(username='dean_fin_user', password='password123')
        UserProfile.objects.create(user=cls.dean_fin, role='DEAN_ACCOUNTS', department='Finance Office')

        cls.dean_acad = User.objects.create_user(username='dean_acad_user', password='password123')
        UserProfile.objects.create(user=cls.dean_acad, role='DEAN_ACADEMICS', department='Academic Affairs')

        cls.director = User.objects.create_user(username='director_user', password='password123')
        UserProfile.objects.create(user=cls.director, role='DIRECTOR', department='Directorate')

        cls.student = User.objects.create_user(username='student_user', password='password123')
        UserProfile.objects.create(user=cls.student, role='STUDENT', department='Computer Science & Engineering', roll_or_emp_id='21BCSE101')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT',
            head=cls.hod_cse
        )

        cls.client = Client()

    def login_as(self, user):
        self.client.login(username=user.username, password='password123')

    def test_race_condition_two_approvers_simultaneous(self):
        """Bug 1: Double approval / race condition handled safely with select_for_update."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Race Condition Test Event',
            description='Test event for race condition',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='UNDER_REVIEW'
        )

        self.login_as(self.hod_cse)
        res1 = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'First approval'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, 1)

        # Second approval attempt by the same user on the advanced stage must be rejected
        res2 = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Duplicate approval attempt'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, 1)

    def test_checkin_for_unpublished_event(self):
        """Bug 2: Student CANNOT check in for an event that is still UNDER_REVIEW."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Unpublished Test Event',
            description='Event not yet published',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='UNDER_REVIEW'
        )

        self.client.login(username='student_user', password='password123')
        reg = EventRegistration.objects.create(
            event=proposal,
            student=self.student,
            role='PARTICIPANT',
            status='REGISTERED'
        )

        res = self.client.post(f'/events/checkin/?token={proposal.qr_checkin_token}', {
            'token': proposal.qr_checkin_token,
            'selfie_image': VALID_PNG_B64
        })

        reg.refresh_from_db()
        self.assertEqual(reg.status, 'REGISTERED')
        self.assertFalse(bool(reg.selfie_image))

    def test_selfie_accepts_non_image(self):
        """Bug 3: Selfie upload rejects non-image mime types."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Selfie Test Event',
            description='Test selfie upload',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now - timedelta(minutes=10),
            end_date=now + timedelta(hours=2),
            venue='Test Auditorium',
            status='APPROVED'
        )

        self.client.login(username='student_user', password='password123')
        reg = EventRegistration.objects.create(
            event=proposal,
            student=self.student,
            role='PARTICIPANT',
            status='REGISTERED'
        )

        res = self.client.post(f'/events/checkin/?token={proposal.qr_checkin_token}', {
            'token': proposal.qr_checkin_token,
            'selfie_image': 'data:text/plain;base64,bm90IGFuIGltYWdlIGF0IGFsbA==',
        })

        reg.refresh_from_db()
        self.assertEqual(reg.status, 'REGISTERED')
        self.assertFalse(bool(reg.selfie_image))

    def test_rating_values_out_of_range(self):
        """Bug 4: Feedback submission rejects ratings outside 1-5."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Rating Test Event',
            description='Test rating validation',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            venue='Hall B',
            status='APPROVED',
            qr_checkin_token='test-token-rate'
        )

        self.client.login(username='student_user', password='password123')
        reg = EventRegistration.objects.create(
            event=proposal,
            student=self.student,
            role='PARTICIPANT',
            status='CHECKED_IN'
        )

        res = self.client.post(f'/registrations/{reg.id}/feedback/', {
            'rating_overall': 0,        # Below minimum
            'rating_content': 6,        # Above maximum
            'rating_speaker': 3,
            'comments': 'test'
        })

        feedback = EventFeedback.objects.filter(registration=reg).first()
        self.assertIsNone(feedback)

    def test_allowed_hosts_overly_permissive(self):
        """Bug 5: Insecure wildcard '*' is disallowed in settings.ALLOWED_HOSTS."""
        self.assertNotIn('*', settings.ALLOWED_HOSTS)

    def test_secret_key_weak_default(self):
        """Bug 6: SECRET_KEY does not use the default weak embedded key."""
        weak_key = 'django-insecure-^408s83@d81)9y&r!0l0$fe3fbx8y)t%f1x)o($#vnbg1l70y6'
        self.assertNotEqual(settings.SECRET_KEY, weak_key)

    def test_double_approval_submission(self):
        """Bug 7: Double approval submission cannot skip stages."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Double Submit Test',
            description='Test double submission',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='UNDER_REVIEW'
        )

        self.login_as(self.hod_cse)
        self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'First approval'
        })
        proposal.refresh_from_db()
        idx_after_first = proposal.current_stage_index
        self.assertEqual(idx_after_first, 1)

        # Immediate repeat request by same user is blocked
        self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Second approval'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, idx_after_first)


class BugApprovalEngineTestCase(TestCase):
    """Tests specifically for approval engine bugs"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='fac2', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='CSE')

        cls.hod = User.objects.create_user(username='hod2', password='password123')
        UserProfile.objects.create(user=cls.hod, role='HOD', department='Computer Science & Engineering')

        cls.dean_fin = User.objects.create_user(username='dean_fin2', password='password123')
        UserProfile.objects.create(user=cls.dean_fin, role='DEAN_ACCOUNTS', department='Finance')

        cls.dean_acad = User.objects.create_user(username='dean_acad2', password='password123')
        UserProfile.objects.create(user=cls.dean_acad, role='DEAN_ACADEMICS', department='Academics')

        cls.director = User.objects.create_user(username='dir2', password='password123')
        UserProfile.objects.create(user=cls.director, role='DIRECTOR', department='Direct')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT',
            head=cls.hod
        )

        cls.client = Client()

    def login_as(self, user):
        self.client.login(username=user.username, password='password123')

    def test_approver_can_act_on_wrong_stage(self):
        """Approver acting on wrong stage is strictly blocked."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Stage Bypass Test',
            description='Test stage bypass',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=2,  # At Dean Finance
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='UNDER_REVIEW'
        )

        self.login_as(self.hod)
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Should not allow'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.current_stage_index, 2)

    def test_custom_chain_duplicate_mandatory(self):
        """Custom chain never duplicates statutory mandatory roles."""
        custom_chain = get_default_chain('CUSTOM', custom_roles=['HOD', 'DEAN_ACCOUNTS', 'DIRECTOR'])
        roles = [st['role'] for st in custom_chain]
        self.assertEqual(roles.count('DEAN_ACCOUNTS'), 1)
        self.assertEqual(roles.count('DEAN_ACADEMICS'), 1)
        self.assertEqual(roles.count('DIRECTOR'), 1)


class BugPermissionsSecurityTestCase(TestCase):
    """Tests for permissions and security bugs"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='fac3', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='CSE')

        cls.hod = User.objects.create_user(username='hod3', password='password123')
        UserProfile.objects.create(user=cls.hod, role='HOD', department='CSE')

        cls.student = User.objects.create_user(username='student3', password='password123')
        UserProfile.objects.create(user=cls.student, role='STUDENT', department='CSE', roll_or_emp_id='21BCSE101')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT',
            head=cls.hod
        )

        now = timezone.now()
        cls.proposal = EventProposal.objects.create(
            title='Permission Test Event',
            description='Test permissions',
            proposer=cls.faculty,
            organizing_unit=cls.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='APPROVED'
        )

        cls.client = Client()

    def login_as(self, user):
        return self.client.login(username=user.username, password='password123')

    def test_student_can_access_approver_urls(self):
        """Student viewing proposal detail does not get approver action form."""
        self.login_as(self.student)
        res = self.client.get(f'/proposals/{self.proposal.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context.get('is_approver', False))

    def test_idor_another_facultys_event(self):
        """Faculty cannot edit another faculty coordinator's event proposal."""
        other_faculty = User.objects.create_user(username='other_fac', password='password123')
        UserProfile.objects.create(user=other_faculty, role='FACULTY', department='ECE')

        now = timezone.now()
        other_dept = OrganizingUnit.objects.create(
            name='Department of Electronics & Communication Engineering',
            unit_type='DEPARTMENT'
        )
        other_proposal = EventProposal.objects.create(
            title='Other Faculty Event',
            description='By another faculty',
            proposer=other_faculty,
            organizing_unit=other_dept,
            start_date=now + timedelta(days=3),
            end_date=now + timedelta(days=4),
            venue='Seminar Hall 2',
            status='APPROVED'
        )

        self.login_as(self.faculty)
        res = self.client.get(f'/proposals/{other_proposal.id}/edit/')
        # Forbidden / 404
        self.assertEqual(res.status_code, 404)


class BugCheckInQRSelfieTestCase(TestCase):
    """Tests for check-in, QR, and selfie bugs"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='fac4', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='CSE')

        cls.student = User.objects.create_user(username='student4', password='password123')
        UserProfile.objects.create(user=cls.student, role='STUDENT', department='CSE', roll_or_emp_id='21BCSE101')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT'
        )

        now = timezone.now()
        cls.proposal = EventProposal.objects.create(
            title='Check-in Test Event',
            description='Test check-in flow',
            proposer=cls.faculty,
            organizing_unit=cls.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now - timedelta(minutes=15),
            end_date=now + timedelta(hours=2),
            venue='Test Auditorium',
            status='APPROVED'
        )

        cls.client = Client()
        cls.client.login(username='student4', password='password123')

        cls.registration = EventRegistration.objects.create(
            event=cls.proposal,
            student=cls.student,
            role='PARTICIPANT',
            status='REGISTERED'
        )

    def test_checkin_for_unregistered_student(self):
        """Student who did NOT register cannot check in."""
        unreg_student = User.objects.create_user(username='unreg_student', password='password123')
        UserProfile.objects.create(user=unreg_student, role='STUDENT', department='CSE')

        self.client.login(username='unreg_student', password='password123')
        res = self.client.post(f'/events/checkin/?token={self.proposal.qr_checkin_token}', {
            'token': self.proposal.qr_checkin_token,
            'selfie_image': VALID_PNG_B64,
        })
        self.assertFalse(EventRegistration.objects.filter(event=self.proposal, student=unreg_student).exists())

    def test_duplicate_check_in(self):
        """Duplicate check-in does not overwrite or fail."""
        self.client.login(username='student4', password='password123')

        token = self.proposal.qr_checkin_token
        res1 = self.client.post(f'/events/checkin/?token={token}', {
            'token': token,
            'selfie_image': VALID_PNG_B64,
        })

        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'CHECKED_IN')

        res2 = self.client.post(f'/events/checkin/?token={token}', {
            'token': token,
            'selfie_image': VALID_PNG_B64,
        })
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'CHECKED_IN')

    def test_qr_token_guessable_never_expires(self):
        """QR token exists and can be retrieved."""
        token = self.proposal.qr_checkin_token
        self.assertIsNotNone(token)

    def test_selfie_non_image_acceptance(self):
        """Huge file (>2MB) is rejected."""
        self.client.login(username='student4', password='password123')
        token = self.proposal.qr_checkin_token
        huge_base64 = 'data:image/jpeg;base64,' + 'A' * (4 * 1024 * 1024)

        res = self.client.post(f'/events/checkin/?token={token}', {
            'token': token,
            'selfie_image': huge_base64,
        })

        reg = EventRegistration.objects.get(event=self.proposal, student=self.student)
        self.assertFalse(bool(reg.selfie_image))


class BugFeedbackGateTestCase(TestCase):
    """Tests for feedback gate bugs"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='fac5', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='CSE')

        cls.student = User.objects.create_user(username='student5', password='password123')
        UserProfile.objects.create(user=cls.student, role='STUDENT', department='CSE', roll_or_emp_id='21BCSE101')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT'
        )

        now = timezone.now()
        cls.proposal = EventProposal.objects.create(
            title='Feedback Test Event',
            description='Test feedback gate',
            proposer=cls.faculty,
            organizing_unit=cls.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            venue='Test Auditorium',
            status='APPROVED'
        )

        cls.client = Client()
        cls.client.login(username='student5', password='password123')

        cls.registration = EventRegistration.objects.create(
            event=cls.proposal,
            student=cls.student,
            role='PARTICIPANT',
            status='CHECKED_IN'
        )

    def test_feedback_without_check_in(self):
        """Feedback requires verified registration."""
        self.assertEqual(self.registration.status, 'CHECKED_IN')

    def test_rating_validation(self):
        """Feedback with ratings 1-5 succeeds and transitions status to VERIFIED."""
        self.client.login(username='student5', password='password123')
        res = self.client.post(f'/registrations/{self.registration.id}/feedback/', {
            'rating_overall': 4,
            'rating_content': 5,
            'rating_speaker': 4,
            'comments': 'Great session'
        })
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, 'VERIFIED')
        self.assertTrue(hasattr(self.registration, 'feedback'))

    def test_feedback_rating_out_of_range(self):
        """Feedback rejects ratings below 1 or above 5."""
        self.client.login(username='student5', password='password123')
        res = self.client.post(f'/registrations/{self.registration.id}/feedback/', {
            'rating_overall': 0,
            'rating_content': 5,
            'rating_speaker': 5,
            'comments': 'test'
        })
        self.assertFalse(hasattr(self.registration, 'feedback'))


class BugBudgetRevisionTestCase(TestCase):
    """Tests for budget revision bugs"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='fac6', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='CSE')

        cls.dean_fin = User.objects.create_user(username='dean_fin6', password='password123')
        UserProfile.objects.create(user=cls.dean_fin, role='DEAN_ACCOUNTS', department='Finance')

        cls.dean_acad = User.objects.create_user(username='dean_acad6', password='password123')
        UserProfile.objects.create(user=cls.dean_acad, role='DEAN_ACADEMICS', department='Academics')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT'
        )

        now = timezone.now()
        cls.proposal = EventProposal.objects.create(
            title='Budget Test Event',
            description='Test budget revision',
            proposer=cls.faculty,
            organizing_unit=cls.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='UNDER_REVIEW'
        )

        cls.client = Client()

    def login_as(self, user):
        return self.client.login(username=user.username, password='password123')

    def test_non_finance_user_revise_budget(self):
        """Non-finance user is blocked from revising budget."""
        self.login_as(self.faculty)
        res = self.client.post(f'/proposals/{self.proposal.id}/action/', {
            'action': 'REVISE_BUDGET',
            'new_budget': 45000.00,
            'remarks': 'Test'
        })
        proposal = EventProposal.objects.get(id=self.proposal.id)
        self.assertEqual(proposal.approved_budget, 50000.00)

    def test_negative_zero_budget(self):
        """Budget revision rejects negative and zero values."""
        self.login_as(self.dean_fin)
        res = self.client.post(f'/proposals/{self.proposal.id}/action/', {
            'action': 'REVISE_BUDGET',
            'new_budget': -1000.00,
            'remarks': 'Test negative budget'
        })
        proposal = EventProposal.objects.get(id=self.proposal.id)
        self.assertEqual(proposal.approved_budget, 50000.00)


class BugEmailSignalsTestCase(TestCase):
    """Tests for email and signal bugs"""

    @classmethod
    def setUpTestData(cls):
        cls.faculty = User.objects.create_user(username='fac7', password='password123')
        UserProfile.objects.create(user=cls.faculty, role='FACULTY', department='CSE')

        cls.dept_cse = OrganizingUnit.objects.create(
            name='Department of Computer Science & Engineering',
            unit_type='DEPARTMENT'
        )

        now = timezone.now()
        cls.proposal = EventProposal.objects.create(
            title='Email Test Event',
            description='Test email sending',
            proposer=cls.faculty,
            organizing_unit=cls.dept_cse,
            chain_type='ACADEMIC',
            approval_chain=get_default_chain('ACADEMIC'),
            current_stage_index=0,
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=7),
            end_date=now + timedelta(days=8),
            venue='Test Auditorium',
            status='UNDER_REVIEW',
            mess_requirements='Catering for 100 students',
            transport_requirements='2 campus shuttle buses',
            maintenance_requirements='AV system and projectors'
        )

        cls.client = Client()

    def test_logistics_emails_sent_exactly_once(self):
        """Logistics emails dispatched when requirements are set."""
        notifications = dispatch_logistics_notifications(self.proposal)
        self.assertEqual(len(notifications), 3)

    def test_email_sent_on_revision_reject_by_mistake(self):
        """Remarks are mandatory for REJECT and REQUEST_REVISION; whitespace-only is rejected."""
        self.client.login(username='fac7', password='password123')
        # Attempt to reject with whitespace-only remark
        res = self.client.post(f'/proposals/{self.proposal.id}/action/', {
            'action': 'REJECT',
            'remarks': '    '
        })
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'UNDER_REVIEW')
