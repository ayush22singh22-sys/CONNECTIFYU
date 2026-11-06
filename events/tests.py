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
