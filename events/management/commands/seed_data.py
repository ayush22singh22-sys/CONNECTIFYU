from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from events.models import UserProfile, OrganizingUnit, EventProposal, ApprovalLog, EventRegistration, EventFeedback
from events.utils import get_default_chain, dispatch_logistics_notifications


class Command(BaseCommand):
    help = 'Seeds authentic Indian college users, departments, clubs, and event proposals with 3 approval chains'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding Indian College Event Management System (CEMS) data...")

        # 1. Create Indian Personas
        users_meta = [
            ('faculty', 'Rajesh', 'Sharma', 'rsharma@college.ac.in', 'FACULTY', 'Computer Science & Engineering', 'FAC-CSE-104'),
            ('hod_cse', 'K. V.', 'Ramanathan', 'hod.cse@college.ac.in', 'HOD', 'Computer Science & Engineering', 'HOD-CSE-001'),
            ('club_lead', 'Priya', 'Nair', 'robotics.lead@college.ac.in', 'CLUB_HEAD', 'Robotics & Automation Society', 'FAC-ADV-022'),
            ('registrar', 'Sunita', 'Deshmukh', 'registrar@college.ac.in', 'REGISTRAR', 'Administration & HR Section', 'REG-ADM-001'),
            ('dean_research', 'P.', 'Venkatraman', 'dean.rnd@college.ac.in', 'DEAN_RESEARCH', 'Research & Consultancy (R&D)', 'DEAN-RND-01'),
            ('dean_dsw', 'Alok', 'Sen', 'dean.dsw@college.ac.in', 'DEAN_STUDENT_WELFARE', 'Dean of Student Welfare (DSW)', 'DEAN-DSW-01'),
            ('dean_finance', 'Suresh', 'Chandra', 'dean.finance@college.ac.in', 'DEAN_ACCOUNTS', 'Finance & Accounts Office', 'DEAN-FIN-01'),
            ('dean_academics', 'Meenakshi', 'Sundaram', 'dean.acad@college.ac.in', 'DEAN_ACADEMICS', 'Academic Affairs Office', 'DEAN-ACAD-01'),
            ('director', 'R.', 'Chidambaram', 'director@college.ac.in', 'DIRECTOR', 'Directorate of the Institute', 'DIR-INST-01'),
            ('student1', 'Aarav', 'Patel', 'aarav.21bcse@student.college.ac.in', 'STUDENT', 'Computer Science & Engineering', '21BCSE101'),
            ('student2', 'Ananya', 'Sen', 'ananya.21bece@student.college.ac.in', 'STUDENT', 'Electronics & Communication', '21BECE034'),
            ('admin', 'Central', 'Administrator', 'admin@college.ac.in', 'DIRECTOR', 'Campus IT Centre', 'ADMIN-ROOT-01'),
        ]

        created_users = {}
        for username, first, last, email, role, dept, roll_or_emp in users_meta:
            user, _ = User.objects.get_or_create(username=username, defaults={
                'first_name': first,
                'last_name': last,
                'email': email,
                'is_staff': True if role != 'STUDENT' else False,
                'is_superuser': True if username == 'admin' else False,
            })
            user.set_password('password123')
            user.first_name = first
            user.last_name = last
            user.email = email
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.department = dept
            profile.roll_or_emp_id = roll_or_emp
            profile.phone = '+91 98765 43210'
            profile.save()

            created_users[username] = user

        # 2. Organizing Units
        cse_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Department of Computer Science & Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_cse']}
        )
        cse_dept.head = created_users['hod_cse']
        cse_dept.save()

        ece_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Department of Electronics & Communication Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_cse']}
        )

        robotics_soc, _ = OrganizingUnit.objects.get_or_create(
            name='Robotics & Automation Society (RAS)',
            defaults={'unit_type': 'CLUB', 'head': created_users['club_lead']}
        )
        robotics_soc.head = created_users['club_lead']
        robotics_soc.save()

        inst_council, _ = OrganizingUnit.objects.get_or_create(
            name='Central Institutional Affairs Committee',
            defaults={'unit_type': 'INSTITUTE', 'head': created_users['registrar']}
        )

        now = timezone.now()

        # 3. Create Event Proposals demonstrating the 3 distinct approval chains

        # --- EVENT 1: Academic & Research Chain ---
        # Currently at Stage 3: Dean of Finance (₹)
        chain1 = get_default_chain('ACADEMIC')
        chain1[0]['status'] = 'APPROVED'
        chain1[1]['status'] = 'APPROVED'
        chain1[2]['status'] = 'PENDING'

        event1, _ = EventProposal.objects.get_or_create(
            title='National Conference on Generative AI & Autonomous Robotics (NCGAR-2026)',
            defaults={
                'description': 'A 3-day flagship national conference featuring top researchers, paper presentations, and research workshops on foundation models and robotics.',
                'proposer': created_users['faculty'],
                'co_coordinator': 'Dr. S. Radhakrishnan (CSE Dept, Intercom: 4120)',
                'guest_speaker': 'Prof. V. Kamakoti (Director, IIT Madras) & Dr. Geetha Manjunath (Niramai AI)',
                'organizing_unit': cse_dept,
                'chain_type': 'ACADEMIC',
                'approval_chain': chain1,
                'current_stage_index': 2, # Stage 3: Dean Finance
                'requested_budget': 350000.00,
                'approved_budget': 350000.00,
                'start_date': now + timedelta(days=18),
                'end_date': now + timedelta(days=20),
                'venue': 'Dr. APJ Abdul Kalam Central Auditorium & CSE Complex',
                'expected_attendees': 350,
                'mess_requirements': 'High tea and working lunch for 350 delegates and 25 keynote speakers for 3 days. Special dinner on Day 1.',
                'transport_requirements': '2 Innova Crysta vehicles for airport reception and drop of guest speakers from Bangalore/Chennai airport.',
                'maintenance_requirements': 'Dual high-lumen 4K projectors, collar microphones, podium mic, and uninterrupted power backup (UPS) across all seminar halls.',
                'status': 'UNDER_REVIEW',
                'revision_count': 0,
                'is_revision': False,
            }
        )
        ApprovalLog.objects.filter(proposal=event1).delete()
        ApprovalLog.objects.create(
            proposal=event1,
            approver=created_users['hod_cse'],
            stage_name='Stage 1: Head of Department (HOD CSE)',
            action='APPROVED',
            remarks='Proposal aligns with NBA/NIRF research benchmarks. Strongly recommended for sanction.',
            created_at=now - timedelta(days=4)
        )
        ApprovalLog.objects.create(
            proposal=event1,
            approver=created_users['dean_research'],
            stage_name='Stage 2: Dean of Research & Consultancy (R&D)',
            action='APPROVED',
            remarks='Keynote profiles and call-for-papers review committee vetted. Approved.',
            created_at=now - timedelta(days=2)
        )

        # --- EVENT 2: Student Club & Cultural Fest Chain ---
        # Fully Approved & Published! (Shows live QR, student selfie, feedback, and compliance report)
        chain2 = get_default_chain('CLUB_FEST')
        for stage in chain2:
            stage['status'] = 'APPROVED'

        event2, _ = EventProposal.objects.get_or_create(
            title='TechKriti 2026: All-India Inter-College Hackathon & Robotics Derby',
            defaults={
                'description': 'A 36-hour hackathon, bot combat, and line-follower challenge bringing over 500 engineering students across India.',
                'proposer': created_users['faculty'],
                'co_coordinator': 'Prof. Priya Nair & Student Council',
                'guest_speaker': 'Dr. Tessy Thomas (Distinguished Scientist & Missile Woman of India)',
                'organizing_unit': robotics_soc,
                'chain_type': 'CLUB_FEST',
                'approval_chain': chain2,
                'current_stage_index': 5, # Cleared all 5 stages!
                'requested_budget': 250000.00,
                'approved_budget': 220000.00,
                'budget_revision_reason': 'Sanctioned ₹2,20,000 after adjusting non-essential decoration overheads as per student activity funding guidelines.',
                'start_date': now + timedelta(days=4),
                'end_date': now + timedelta(days=6),
                'venue': 'Visvesvaraya Central Seminar Complex & Indoor Sports Stadium',
                'expected_attendees': 500,
                'mess_requirements': 'Midnight snacks, energy drinks, tea/coffee counters, and lunch for 500 participants over 36 continuous hours.',
                'transport_requirements': 'Institute shuttle buses between railway station and campus every 2 hours on Friday evening.',
                'maintenance_requirements': 'High-speed gigabit Wi-Fi nodes, 150 power extension strips, sound system, and stadium floodlights.',
                'status': 'APPROVED',
                'revision_count': 1,
                'is_revision': True,
            }
        )
        dispatch_logistics_notifications(event2)

        # Pre-seed registrations for student1 and student2
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
                'checked_in_at': now - timedelta(hours=3),
                'selfie_image': 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="%23059669"/><text x="50" y="55" font-size="11" fill="white" text-anchor="middle">Selfie OK</text></svg>'
            }
        )
        EventFeedback.objects.get_or_create(
            registration=reg2,
            defaults={
                'rating_overall': 5,
                'rating_content': 5,
                'rating_speaker': 5,
                'comments': 'Incredible organization and problem statements! The mentors were extremely helpful throughout the 36-hour sprint.'
            }
        )

        # --- EVENT 3: Institute Mega Event Chain ---
        # Currently in Revision Requested status (shows clear remarks & allows resubmission)
        chain3 = get_default_chain('INSTITUTE_MEGA')
        chain3[0]['status'] = 'APPROVED'
        chain3[1]['status'] = 'REVISION_REQUESTED'

        event3, _ = EventProposal.objects.get_or_create(
            title='Annual Institute Convocation & Industry-Academia Conclave 2026',
            defaults={
                'description': 'Annual formal degree conferment ceremony and convocation address, followed by industry partnership MOUs.',
                'proposer': created_users['faculty'],
                'co_coordinator': 'Dr. S. K. Gupta (Intercom: 1002)',
                'guest_speaker': 'Shri N. R. Narayana Murthy (Founder, Infosys)',
                'organizing_unit': inst_council,
                'chain_type': 'INSTITUTE_MEGA',
                'approval_chain': chain3,
                'current_stage_index': 1,
                'requested_budget': 600000.00,
                'approved_budget': 600000.00,
                'start_date': now + timedelta(days=25),
                'end_date': now + timedelta(days=26),
                'venue': 'Open Air Amphitheatre & Sir C. V. Raman Auditorium',
                'expected_attendees': 1200,
                'mess_requirements': 'VIP luncheon for 50 dignitaries and buffet lunch for 1200 graduating students and parents.',
                'transport_requirements': 'Fleet escort vehicles from state guest house to campus.',
                'maintenance_requirements': 'Full ceremonial stage decoration, memento stalls, live YouTube stream broadcast setup.',
                'status': 'REVISION_REQUESTED',
                'revision_count': 1,
                'is_revision': True,
            }
        )
        ApprovalLog.objects.filter(proposal=event3).delete()
        ApprovalLog.objects.create(
            proposal=event3,
            approver=created_users['dean_research'],
            stage_name='Stage 2: Dean of Research & Planning',
            action='REVISION_REQUESTED',
            remarks='Security and protocol clearance required: Please provide an exact VIP seating blueprint and security liaison officer details before this can move to Finance.',
            created_at=now - timedelta(hours=8)
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with authentic Indian personas, Rupee (INR) budgets, and 3 distinct approval chains!"))
