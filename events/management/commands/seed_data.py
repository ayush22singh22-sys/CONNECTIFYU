from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from events.models import UserProfile, OrganizingUnit, EventProposal, ApprovalLog, EventRegistration, EventFeedback


class Command(BaseCommand):
    help = 'Seeds initial users, organizing units, and demonstration event proposals'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding College Event Management System data...")

        # 1. Create Users
        users_meta = [
            ('faculty', 'Alan', 'Turing', 'faculty@college.edu', 'FACULTY', 'Computer Science', 'FAC-CS-101'),
            ('hod_cs', 'Grace', 'Hopper', 'hod_cs@college.edu', 'HOD', 'Computer Science', 'HOD-CS-001'),
            ('club_head', 'Alex', 'Johnson', 'robotics@college.edu', 'CLUB_HEAD', 'Robotics Club', 'STU-ROB-042'),
            ('hr_admin', 'Sarah', 'Jenkins', 'hr@college.edu', 'HR', 'Human Resources', 'EMP-HR-005'),
            ('dean_research', 'Richard', 'Feynman', 'dean_research@college.edu', 'DEAN_RESEARCH', 'Research Office', 'DEAN-RES-01'),
            ('dean_accounts', 'Milton', 'Friedman', 'dean_accounts@college.edu', 'DEAN_ACCOUNTS', 'Finance Office', 'DEAN-ACC-01'),
            ('dean_academics', 'Dr. APJ', 'Kalam', 'dean_academics@college.edu', 'DEAN_ACADEMICS', 'Directorate', 'DIR-ACAD-01'),
            ('student1', 'John', 'Doe', 'johndoe@student.college.edu', 'STUDENT', 'Computer Science', 'CS21B001'),
            ('student2', 'Jane', 'Smith', 'janesmith@student.college.edu', 'STUDENT', 'Mechanical', 'ME21B015'),
            ('admin', 'System', 'Administrator', 'admin@college.edu', 'DEAN_ACADEMICS', 'Administration', 'ADMIN-001'),
        ]

        created_users = {}
        for username, first, last, email, role, dept, roll_or_emp in users_meta:
            user, created = User.objects.get_or_create(username=username, defaults={
                'first_name': first,
                'last_name': last,
                'email': email,
                'is_staff': True if role != 'STUDENT' else False,
                'is_superuser': True if username == 'admin' else False,
            })
            user.set_password('password123')
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.department = dept
            profile.roll_or_emp_id = roll_or_emp
            profile.phone = '+1 555-0199'
            profile.save()

            created_users[username] = user

        # 2. Organizing Units
        cs_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Computer Science & Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_cs']}
        )
        cs_dept.head = created_users['hod_cs']
        cs_dept.save()

        mech_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Mechanical Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_cs']}
        )

        robotics_club, _ = OrganizingUnit.objects.get_or_create(
            name='Robotics & Automation Club',
            defaults={'unit_type': 'CLUB', 'head': created_users['club_head']}
        )
        robotics_club.head = created_users['club_head']
        robotics_club.save()

        # 3. Create Event Proposals at different stages

        # Event 1: Currently at Stage 4 (Dean of Accounts) - Showcases past approvals
        now = timezone.now()
        event1, _ = EventProposal.objects.get_or_create(
            title='Annual National AI & Robotics Hackathon 2026',
            defaults={
                'description': 'A 36-hour inter-college hackathon bringing together over 300 student innovators to build autonomous agents, AI tools, and embedded robotics solutions.',
                'proposer': created_users['faculty'],
                'co_coordinator': 'Dr. Ada Lovelace (CS Dept, ext 4402)',
                'guest_speaker': 'Dr. Yann LeCun, Chief AI Scientist',
                'organizing_unit': cs_dept,
                'requested_budget': 7500.00,
                'approved_budget': 7500.00,
                'start_date': now + timedelta(days=14),
                'end_date': now + timedelta(days=16),
                'venue': 'APJ Abdul Kalam Auditorium & CS Labs 1-4',
                'expected_attendees': 300,
                'mess_requirements': 'Day 1 dinner for 300 students + 20 mentors. Continuous coffee/tea stations during hackathon. Breakfast Day 2.',
                'transport_requirements': '2 campus shuttle buses from metro station on Friday evening and Sunday morning.',
                'maintenance_requirements': 'High-density WiFi routers, uninterrupted power supply (UPS backups), and 3 PA podium mics.',
                'status': 'STAGE_4_DEAN_ACCOUNTS',
                'revision_count': 0,
                'is_revision': False,
            }
        )

        # Clear existing logs for fresh seed
        ApprovalLog.objects.filter(proposal=event1).delete()
        ApprovalLog.objects.create(
            proposal=event1,
            approver=created_users['hod_cs'],
            stage_name='Stage 1: Organizing Unit Head (HOD CS)',
            action='APPROVED',
            remarks='Proposal aligns strongly with department technical milestones. Recommended enthusiastically.',
            created_at=now - timedelta(days=3)
        )
        ApprovalLog.objects.create(
            proposal=event1,
            approver=created_users['hr_admin'],
            stage_name='Stage 2: HR Review',
            action='APPROVED',
            remarks='No academic timetable clash. Duty leaves for student volunteers approved.',
            created_at=now - timedelta(days=2)
        )
        ApprovalLog.objects.create(
            proposal=event1,
            approver=created_users['dean_research'],
            stage_name='Stage 3: Dean of Research',
            action='APPROVED',
            remarks='Guest keynote speaker and research challenge domains vetted and endorsed.',
            created_at=now - timedelta(days=1)
        )

        # Event 2: Fully APPROVED & Published - Ready for student registrations, QR scan, selfie & feedback
        event2, _ = EventProposal.objects.get_or_create(
            title='Symposium on Quantum Computing & Cryptography',
            defaults={
                'description': 'A full-day flagship seminar exploring post-quantum cryptography algorithms, quantum circuits, and industry implications.',
                'proposer': created_users['faculty'],
                'co_coordinator': 'Prof. Claude Shannon (ext 1042)',
                'guest_speaker': 'Dr. Peter Shor (MIT Quantum Research Group)',
                'organizing_unit': cs_dept,
                'requested_budget': 4200.00,
                'approved_budget': 3800.00,
                'budget_revision_reason': 'Adjusted honorarium in accordance with standard visiting scientist allowances.',
                'start_date': now + timedelta(days=3),
                'end_date': now + timedelta(days=3, hours=8),
                'venue': 'Main Seminar Hall B',
                'expected_attendees': 150,
                'mess_requirements': 'High tea and boxed lunch for 150 participants.',
                'transport_requirements': 'VIP sedan airport pick-up and drop for guest speaker.',
                'maintenance_requirements': 'Dual projector projection, stage lighting, and lapel microphone.',
                'status': 'APPROVED',
                'revision_count': 1,
                'is_revision': True,
            }
        )

        # Event 3: Revision Requested - Proposer needs to fix remarks and resubmit
        event3, _ = EventProposal.objects.get_or_create(
            title='All-India Inter-Collegiate Drone Racing Derby',
            defaults={
                'description': 'Outdoor drone obstacle course racing competition with 20 college teams participating.',
                'proposer': created_users['club_head'],
                'co_coordinator': 'Alex Johnson & Club Council',
                'guest_speaker': 'Capt. Vikram Batra Foundation Drone Lead',
                'organizing_unit': robotics_club,
                'requested_budget': 9000.00,
                'approved_budget': 9000.00,
                'start_date': now + timedelta(days=21),
                'end_date': now + timedelta(days=22),
                'venue': 'College Sports Ground & East Pavilion',
                'expected_attendees': 200,
                'mess_requirements': 'Energy drinks and snack boxes for drone pilots.',
                'transport_requirements': 'Heavy equipment transport trolley from lab to field.',
                'maintenance_requirements': 'Safety netting enclosure, medical first-aid tent with ambulance standby.',
                'status': 'REVISION_REQUESTED',
                'revision_count': 1,
                'is_revision': True,
            }
        )
        ApprovalLog.objects.filter(proposal=event3).delete()
        ApprovalLog.objects.create(
            proposal=event3,
            approver=created_users['dean_research'],
            stage_name='Stage 3: Dean of Research',
            action='REVISION_REQUESTED',
            remarks='Safety clearance protocol required: Please provide an explicit FAA/DGCA airspace safety waiver and detailed emergency contingency procedure before this can proceed.',
            created_at=now - timedelta(hours=6)
        )

        # Event 4: Seed a completed registration with feedback for verification demonstration
        reg1, _ = EventRegistration.objects.get_or_create(
            event=event2,
            student=created_users['student1'],
            defaults={'role': 'PARTICIPANT', 'status': 'REGISTERED'}
        )

        reg2, _ = EventRegistration.objects.get_or_create(
            event=event2,
            student=created_users['student2'],
            defaults={
                'role': 'VOLUNTEER',
                'status': 'VERIFIED',
                'checked_in_at': now - timedelta(hours=2),
                'selfie_image': 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="%234f46e5"/><text x="50" y="55" font-size="12" fill="white" text-anchor="middle">Selfie OK</text></svg>'
            }
        )
        EventFeedback.objects.get_or_create(
            registration=reg2,
            defaults={
                'rating_overall': 5,
                'rating_content': 5,
                'rating_speaker': 5,
                'comments': 'Exceptional talk on quantum algorithms! Looking forward to hands-on quantum lab sessions.'
            }
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with demo users, stages, and events!"))
