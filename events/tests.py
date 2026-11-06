from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import time

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

    def test_academic_approval_chain_and_faculty_publish_gate(self):
        """
        Tests:
        1. 5-Stage approval with Dean Finance budget sanction.
        2. Director approval holds event at APPROVED_PENDING_PUBLISH.
        3. Faculty coordinator uploads poster and clicks publish to release to campus!
        """
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
        
        # Must be held at APPROVED_PENDING_PUBLISH (Requirement 3)
        self.assertEqual(proposal.status, 'APPROVED_PENDING_PUBLISH')

        # Automated logistics email verification
        notifications = LogisticsNotification.objects.filter(proposal=proposal)
        self.assertEqual(notifications.count(), 3)

        # Faculty uploads poster and clicks publish!
        self.client.login(username='faculty_user', password='password123')
        res = self.client.post(f'/proposals/{proposal.id}/publish/', {
            'poster_preset': 'https://example.com/poster.jpg'
        })
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'APPROVED')
        self.assertIsNotNone(proposal.published_at)

    def test_rotating_qr_token_validation(self):
        """Requirement 4: Validates that rotating QR codes expire and prevent replay."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='RoboCombat 2026',
            description='Combat arena competition.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            co_coordinator='Prof. Priya Nair',
            guest_speaker='Dr. Kalam Lead',
            requested_budget=50000.00,
            start_date=now + timedelta(days=2),
            end_date=now + timedelta(days=3),
            venue='Indoor Stadium',
            status='APPROVED'
        )

        # 1. Current valid token
        valid_token, _ = proposal.get_rotating_qr_token()
        is_valid, msg = proposal.validate_rotating_token(valid_token)
        self.assertTrue(is_valid)

        # 2. Expired window token (e.g. simulated from 10 minutes ago)
        old_window = (int(time.time()) // proposal.ROTATION_INTERVAL) - 30
        expired_token = f"{proposal.qr_checkin_token}_{old_window}_invalidsig"
        is_valid, msg = proposal.validate_rotating_token(expired_token)
        self.assertFalse(is_valid)

    def test_student_blocked_from_proposal_creation(self):
        """Requirement 2: Students are strictly barred from creating/publishing events."""
        self.client.login(username='student_user', password='password123')
        res = self.client.get('/proposals/new/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, '/')

    def test_student_single_registration_constraint(self):
        """Requirement 1: Students can register only once; duplicate/role change blocked."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Web3 & Cloud Symposium',
            description='Advanced seminar.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            co_coordinator='Prof. S. Iyer',
            guest_speaker='Dr. Tech',
            requested_budget=30000.00,
            approved_budget=30000.00,
            start_date=now + timedelta(days=5),
            end_date=now + timedelta(days=6),
            venue='Auditorium 2',
            status='APPROVED'
        )

        # 1. Student registers for the first time as PARTICIPANT
        self.client.login(username='student_user', password='password123')
        res = self.client.post(f'/events/{proposal.id}/register/', {'role': 'PARTICIPANT'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(EventRegistration.objects.filter(event=proposal, student=self.student).count(), 1)
        reg = EventRegistration.objects.get(event=proposal, student=self.student)
        self.assertEqual(reg.role, 'PARTICIPANT')

        # 2. Student attempts second registration (e.g. as VOLUNTEER) - should be blocked
        res2 = self.client.post(f'/events/{proposal.id}/register/', {'role': 'VOLUNTEER'})
        self.assertEqual(res2.status_code, 302)
        # Total registrations must still be 1, and role must remain unchanged
        self.assertEqual(EventRegistration.objects.filter(event=proposal, student=self.student).count(), 1)
        reg.refresh_from_db()
        self.assertEqual(reg.role, 'PARTICIPANT')

        # 3. Non-student (Faculty) attempts to register - should be blocked
        self.client.login(username='faculty_user', password='password123')
        res3 = self.client.post(f'/events/{proposal.id}/register/', {'role': 'PARTICIPANT'})
        self.assertEqual(res3.status_code, 302)
        self.assertEqual(EventRegistration.objects.filter(event=proposal, student=self.faculty).count(), 0)

    def test_live_qr_restricted_to_organizer_only(self):
        """Requirement 3: Only the event proposer (organizer) can open live QR screen & API."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='Autonomous Drones Workshop',
            description='Hands on drone flying.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            co_coordinator='Prof. K. Verma',
            guest_speaker='Drone Specialist',
            requested_budget=45000.00,
            approved_budget=45000.00,
            start_date=now + timedelta(days=3),
            end_date=now + timedelta(days=4),
            venue='Open Ground',
            status='APPROVED'
        )

        # 1. Non-organizer faculty attempts to open live QR
        other_faculty = User.objects.create_user(username='other_faculty', password='password123')
        UserProfile.objects.create(user=other_faculty, role='FACULTY', department='ECE')
        self.client.login(username='other_faculty', password='password123')

        res_unauthorized = self.client.get(f'/events/{proposal.id}/live/')
        self.assertEqual(res_unauthorized.status_code, 302)
        self.assertIn(f'/proposals/{proposal.id}/', res_unauthorized.url)

        # API also blocked for non-organizer
        api_unauthorized = self.client.get(f'/events/{proposal.id}/rotating-qr-api/')
        self.assertEqual(api_unauthorized.status_code, 403)

        # Student also blocked
        self.client.login(username='student_user', password='password123')
        res_student = self.client.get(f'/events/{proposal.id}/live/')
        self.assertEqual(res_student.status_code, 302)

        # 2. Designated organizer (self.faculty) can open live QR & poll API
        self.client.login(username='faculty_user', password='password123')
        res_authorized = self.client.get(f'/events/{proposal.id}/live/')
        self.assertEqual(res_authorized.status_code, 200)

        api_authorized = self.client.get(f'/events/{proposal.id}/rotating-qr-api/')
        self.assertEqual(api_authorized.status_code, 200)
        data = api_authorized.json()
        self.assertIn('token', data)
        self.assertIn('seconds_left', data)

    def test_department_wise_hod_approval_chains(self):
        """Requirement 5: Department-specific HOD resolution in default and custom chains."""
        dept_ece = OrganizingUnit.objects.create(
            name='Department of Electronics & Communication Engineering',
            unit_type='DEPARTMENT'
        )
        dept_mech = OrganizingUnit.objects.create(
            name='Department of Mechanical Engineering',
            unit_type='DEPARTMENT'
        )

        # 1. CSE Department event gets HOD_CSE
        chain_cse = get_default_chain('ACADEMIC', unit_id=self.dept_cse.id)
        self.assertEqual(chain_cse[0]['role'], 'HOD_CSE')
        self.assertIn('Computer Science', chain_cse[0]['title'])

        # 2. ECE Department event gets HOD_ECE
        chain_ece = get_default_chain('ACADEMIC', unit_id=dept_ece.id)
        self.assertEqual(chain_ece[0]['role'], 'HOD_ECE')
        self.assertIn('Electronics', chain_ece[0]['title'])

        # 3. Mechanical Department event gets HOD_MECH
        chain_mech = get_default_chain('ACADEMIC', unit_id=dept_mech.id)
        self.assertEqual(chain_mech[0]['role'], 'HOD_MECH')
        self.assertIn('Mechanical', chain_mech[0]['title'])

        # 4. Mandatory tail must be in all chains: Dean Finance, Dean Academics, Director
        mandatory_roles = [st['role'] for st in chain_cse[-3:]]
        self.assertEqual(mandatory_roles, ['DEAN_ACCOUNTS', 'DEAN_ACADEMICS', 'DIRECTOR'])

        # 5. Custom chain with explicit department HODs
        custom_chain = get_default_chain('CUSTOM', unit_id=dept_ece.id, custom_roles=['HOD_ECE', 'REGISTRAR'])
        roles = [st['role'] for st in custom_chain]
        self.assertEqual(roles, ['HOD_ECE', 'REGISTRAR', 'DEAN_ACCOUNTS', 'DEAN_ACADEMICS', 'DIRECTOR'])

    def test_event_public_detail_view_and_organizer_roster(self):
        """Requirements 2 & 4: Public description view & Organizer roster view."""
        now = timezone.now()
        proposal = EventProposal.objects.create(
            title='VLSI Design Conclave',
            description='Semiconductor design bootcamp.',
            proposer=self.faculty,
            organizing_unit=self.dept_cse,
            co_coordinator='Prof. S. Sharma',
            guest_speaker='Dr. Anand Kumar',
            requested_budget=50000.00,
            approved_budget=50000.00,
            start_date=now + timedelta(days=4),
            end_date=now + timedelta(days=5),
            venue='Seminar Hall 1',
            status='APPROVED'
        )

        # Create registration & feedback
        reg = EventRegistration.objects.create(
            event=proposal,
            student=self.student,
            role='PARTICIPANT',
            status='VERIFIED',
            checked_in_at=now,
            selfie_image='data:image/jpeg;base64,sample'
        )
        EventFeedback.objects.create(
            registration=reg,
            rating_overall=5,
            rating_content=5,
            rating_speaker=5,
            comments='Inspiring keynote lecture!'
        )

        # 1. Public detail view accessible by student
        self.client.login(username='student_user', password='password123')
        res_public = self.client.get(f'/events/{proposal.id}/details/')
        self.assertEqual(res_public.status_code, 200)
        self.assertContains(res_public, 'VLSI Design Conclave')
        self.assertContains(res_public, 'You are registered for this event!')

        # 2. Public detail view accessible by faculty (shows campus entity view)
        self.client.login(username='hod_user', password='password123')
        res_fac = self.client.get(f'/events/{proposal.id}/details/')
        self.assertEqual(res_fac.status_code, 200)
        self.assertContains(res_fac, 'General Campus Entity View')

        # 3. Organizer proposal detail view displays Roster & Attendance stats
        self.client.login(username='faculty_user', password='password123')
        res_detail = self.client.get(f'/proposals/{proposal.id}/')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn('all_registrations', res_detail.context)
        self.assertIn('attended_students', res_detail.context)
        self.assertIn('roster_stats', res_detail.context)
        self.assertEqual(res_detail.context['roster_stats']['total_registered'], 1)
        self.assertEqual(res_detail.context['roster_stats']['total_attended'], 1)
        self.assertEqual(res_detail.context['roster_stats']['total_verified'], 1)
        self.assertContains(res_detail, 'Student Registration & Attendance Audit Roster')
        self.assertContains(res_detail, 'Inspiring keynote lecture!')
