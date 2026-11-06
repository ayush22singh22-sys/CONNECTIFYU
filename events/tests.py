from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from events.models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification
)
from events.utils import dispatch_logistics_notifications


class EventLifecycleTestCase(TestCase):
    def setUp(self):
        # 1. Setup personas
        self.faculty = User.objects.create_user(username='faculty_user', password='password123')
        UserProfile.objects.create(user=self.faculty, role='FACULTY', department='Computer Science')

        self.hod_cs = User.objects.create_user(username='hod_user', password='password123')
        UserProfile.objects.create(user=self.hod_cs, role='HOD', department='Computer Science')

        self.hr = User.objects.create_user(username='hr_user', password='password123')
        UserProfile.objects.create(user=self.hr, role='HR', department='Human Resources')

        self.dean_res = User.objects.create_user(username='dean_res_user', password='password123')
        UserProfile.objects.create(user=self.dean_res, role='DEAN_RESEARCH', department='Research Office')

        self.dean_acc = User.objects.create_user(username='dean_acc_user', password='password123')
        UserProfile.objects.create(user=self.dean_acc, role='DEAN_ACCOUNTS', department='Finance Office')

        self.dean_acad = User.objects.create_user(username='dean_acad_user', password='password123')
        UserProfile.objects.create(user=self.dean_acad, role='DEAN_ACADEMICS', department='Directorate')

        self.student = User.objects.create_user(username='student_user', password='password123')
        UserProfile.objects.create(user=self.student, role='STUDENT', department='Computer Science', roll_or_emp_id='CS001')

        # 2. Organizing Unit
        self.dept_cs = OrganizingUnit.objects.create(
            name='Computer Science Department',
            unit_type='DEPARTMENT',
            head=self.hod_cs
        )

        self.client = Client()

    def test_end_to_end_approval_and_logistics_trigger(self):
        """Tests the full 5-stage approval chain, budget adjustment, and logistics automated notifications."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Autonomous AI Summit',
            description='A 2-day technical symposium.',
            proposer=self.faculty,
            organizing_unit=self.dept_cs,
            co_coordinator='Dr. Turing',
            guest_speaker='Dr. Andrew Ng',
            requested_budget=5000.00,
            approved_budget=5000.00,
            start_date=now + timedelta(days=5),
            end_date=now + timedelta(days=6),
            venue='Auditorium A',
            mess_requirements='Lunch for 200 participants.',
            transport_requirements='VIP sedan pickup for guest speaker.',
            maintenance_requirements='Podium mic, dual projectors.',
            status='STAGE_1_UNIT_HEAD'
        )

        self.assertEqual(proposal.stage_number, 1)
        self.assertTrue(proposal.is_awaiting_user(self.hod_cs))
        self.assertFalse(proposal.is_awaiting_user(self.hr))

        # --- Stage 1: HOD Approves ---
        self.client.login(username='hod_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Approved by HOD'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'STAGE_2_HR')
        self.assertEqual(proposal.stage_number, 2)

        # --- Stage 2: HR Approves ---
        self.client.login(username='hr_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Approved by HR, no schedule conflicts.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'STAGE_3_DEAN_RESEARCH')

        # --- Stage 3: Dean of Research Approves ---
        self.client.login(username='dean_res_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Keynote speaker and content endorsed.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'STAGE_4_DEAN_ACCOUNTS')

        # --- Stage 4: Dean of Accounts Modifies Budget ---
        self.client.login(username='dean_acc_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'REVISE_BUDGET',
            'new_budget': 4500.00,
            'remarks': 'Sanctioned $4500 as per hospitality upper limit.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'STAGE_5_DEAN_ACADEMICS')
        self.assertEqual(proposal.approved_budget, 4500.00)

        # --- Stage 5: Dean of Academics / Director Grants Final Clearance ---
        self.client.login(username='dean_acad_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'APPROVE',
            'remarks': 'Final directorate clearance granted.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'APPROVED')

        # Verify automated email / logistics records created for Mess, Transport, Maintenance
        notifications = LogisticsNotification.objects.filter(proposal=proposal)
        self.assertEqual(notifications.count(), 3)
        types = set(notifications.values_list('logistics_type', flat=True))
        self.assertEqual(types, {'MESS', 'TRANSPORT', 'MAINTENANCE'})

    def test_revision_cycle_workflow(self):
        """Tests that requesting revision returns proposal to faculty and resubmitting increments revision count."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Drone Racing Exhibition',
            description='Exhibition race.',
            proposer=self.faculty,
            organizing_unit=self.dept_cs,
            co_coordinator='Dr. Turing',
            guest_speaker='Drone expert',
            requested_budget=2000.00,
            start_date=now + timedelta(days=10),
            end_date=now + timedelta(days=11),
            venue='Ground',
            status='STAGE_1_UNIT_HEAD'
        )

        # HOD requests revision
        self.client.login(username='hod_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/action/', {
            'action': 'REQUEST_REVISION',
            'remarks': 'Please provide comprehensive safety net plan.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'REVISION_REQUESTED')

        # Faculty edits and resubmits
        self.client.login(username='faculty_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/edit/', {
            'title': 'Drone Racing Exhibition (Safety Vetted)',
            'description': 'Exhibition race with netting enclosures.',
            'organizing_unit': self.dept_cs.id,
            'co_coordinator': 'Dr. Turing',
            'guest_speaker': 'Drone expert',
            'requested_budget': 2000.00,
            'start_date': (now + timedelta(days=10)).strftime('%Y-%m-%dT%H:%M'),
            'end_date': (now + timedelta(days=11)).strftime('%Y-%m-%dT%H:%M'),
            'venue': 'Ground',
            'expected_attendees': 100,
            'resubmission_notes': 'Enclosed safety protocol and netting blueprints.'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'STAGE_1_UNIT_HEAD')
        self.assertEqual(proposal.revision_count, 1)
        self.assertTrue(proposal.is_revision)

    def test_student_checkin_and_feedback_verification_gate(self):
        """Tests that attendance remains CHECKED_IN until feedback is submitted, then becomes VERIFIED."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Cybersecurity Workshop',
            description='Hands-on hacking defense.',
            proposer=self.faculty,
            organizing_unit=self.dept_cs,
            co_coordinator='Dr. Turing',
            guest_speaker='Security Lead',
            requested_budget=1000.00,
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=1, hours=4),
            venue='Lab 3',
            status='APPROVED'
        )

        self.client.login(username='student_user', password='password123')

        # 1. Student registers
        res = self.client.post(f'/events/{proposal.id}/register/', {'role': 'PARTICIPANT'})
        reg = EventRegistration.objects.get(event=proposal, student=self.student)
        self.assertEqual(reg.status, 'REGISTERED')

        # 2. Student scans QR & takes selfie check-in
        res = self.client.post('/events/checkin/', {
            'token': proposal.qr_checkin_token,
            'selfie_image': 'data:image/png;base64,mockselfiedata'
        })
        reg.refresh_from_db()
        self.assertEqual(reg.status, 'CHECKED_IN')
        self.assertIsNotNone(reg.checked_in_at)

        # 3. Student submits feedback -> Attendance unlocks VERIFIED status!
        res = self.client.post(f'/registrations/{reg.id}/feedback/', {
            'rating_overall': 5,
            'rating_content': 5,
            'rating_speaker': 4,
            'comments': 'Super practical demonstration!'
        })
        reg.refresh_from_db()
        self.assertEqual(reg.status, 'VERIFIED')
        self.assertTrue(hasattr(reg, 'feedback'))
        self.assertEqual(reg.feedback.rating_overall, 5)
