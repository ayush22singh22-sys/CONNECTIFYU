from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from events.models import (
    UserProfile, OrganizingUnit, EventProposal, ApprovalLog, EventRegistration,
    EventFeedback, LogisticsNotification, RollWhitelist, StudentProfile, StaffProfile,
)
from events.utils import get_default_chain, dispatch_logistics_notifications


class Command(BaseCommand):
    help = 'Wipes old data and re-seeds an authentic pre-provisioned database of Indian college entities, students, HODs, and events'

    def handle(self, *args, **kwargs):
        self.stdout.write("Wiping previous test records and provisioning clean database...")

        # 1. Clean slate for registrations and feedback
        EventFeedback.objects.all().delete()
        EventRegistration.objects.all().delete()
        LogisticsNotification.objects.all().delete()
        ApprovalLog.objects.all().delete()
        EventProposal.objects.all().delete()

        # 2. Provision Official College Database of Entities
        users_directory = [
            # Superadmin
            ('admin', 'Super', 'Administrator', 'admin@college.ac.in', 'DIRECTOR', 'Campus IT Centre & Directorate', 'ADMIN-ROOT-001', True),

            # Faculty Coordinators
            ('faculty', 'Rajesh', 'Sharma', 'rsharma@college.ac.in', 'FACULTY', 'Department of Computer Science & Engineering', 'FAC-CSE-104', False),
            ('faculty_ece', 'Arvind', 'Swaminathan', 'aswami@college.ac.in', 'FACULTY', 'Department of Electronics & Communication Engineering', 'FAC-ECE-108', False),

            # HODs of Different Departments
            ('hod_cse', 'K. V.', 'Ramanathan', 'hod.cse@college.ac.in', 'HOD', 'Department of Computer Science & Engineering', 'HOD-CSE-001', False),
            ('hod_ece', 'Sunita', 'Kulkarni', 'hod.ece@college.ac.in', 'HOD', 'Department of Electronics & Communication Engineering', 'HOD-ECE-002', False),
            ('hod_mech', 'Vikramaditya', 'Rathore', 'hod.mech@college.ac.in', 'HOD', 'Department of Mechanical Engineering', 'HOD-MECH-003', False),

            # Club Faculty Advisors
            ('club_lead', 'Priya', 'Nair', 'robotics.lead@college.ac.in', 'CLUB_HEAD', 'Robotics & Automation Society (RAS)', 'FAC-ADV-022', False),
            ('club_cultural', 'Amit', 'Trivedi', 'cultural.lead@college.ac.in', 'CLUB_HEAD', 'Cultural Affairs Committee (Rangmanch)', 'FAC-ADV-045', False),

            # Statutory Administration & Deans
            ('registrar', 'Sunita', 'Deshmukh', 'registrar@college.ac.in', 'REGISTRAR', 'Administration & HR Establishment Section', 'REG-ADM-001', False),
            ('dean_research', 'P.', 'Venkatraman', 'dean.rnd@college.ac.in', 'DEAN_RESEARCH', 'Office of Dean (Research & Consultancy - R&D)', 'DEAN-RND-01', False),
            ('dean_dsw', 'Alok', 'Sen', 'dean.dsw@college.ac.in', 'DEAN_STUDENT_WELFARE', 'Office of Dean (Student Welfare - DSW)', 'DEAN-DSW-01', False),
            ('dean_finance', 'Suresh', 'Chandra', 'dean.finance@college.ac.in', 'DEAN_ACCOUNTS', 'Office of Dean (Finance & Accounts)', 'DEAN-FIN-01', False),
            ('dean_academics', 'Meenakshi', 'Sundaram', 'dean.acad@college.ac.in', 'DEAN_ACADEMICS', 'Office of Dean (Academic Affairs)', 'DEAN-ACAD-01', False),
            ('director', 'R.', 'Chidambaram', 'director@college.ac.in', 'DIRECTOR', 'Directorate of the Institute', 'DIR-INST-01', False),

            # Pre-provisioned Student Database (No public sign-up allowed!)
            ('student1', 'Aarav', 'Patel', 'aarav.21bcse@student.college.ac.in', 'STUDENT', 'Department of Computer Science & Engineering', '21BCSE101', False),
            ('student2', 'Ananya', 'Sen', 'ananya.21bece@student.college.ac.in', 'STUDENT', 'Department of Electronics & Communication Engineering', '21BECE034', False),
            ('student3', 'Rohan', 'Gupta', 'rohan.22bmee@student.college.ac.in', 'STUDENT', 'Department of Mechanical Engineering', '22BMEE012', False),
            ('student4', 'Sneha', 'Reddy', 'sneha.20bcse@student.college.ac.in', 'STUDENT', 'Department of Computer Science & Engineering', '20BCSE088', False),
            ('student5', 'Aditya', 'Verma', 'aditya.22bece@student.college.ac.in', 'STUDENT', 'Department of Electronics & Communication Engineering', '22BECE055', False),
        ]

        created_users = {}
        for username, first, last, email, role, dept, roll_or_emp, is_admin in users_directory:
            user, _ = User.objects.get_or_create(username=username, defaults={
                'first_name': first,
                'last_name': last,
                'email': email,
                'is_staff': True if (role != 'STUDENT' or is_admin) else False,
                'is_superuser': is_admin,
            })
            user.set_password('password123')
            user.first_name = first
            user.last_name = last
            user.email = email
            user.is_staff = True if (role != 'STUDENT' or is_admin) else False
            user.is_superuser = is_admin
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.department = dept
            profile.roll_or_emp_id = roll_or_emp
            profile.phone = '+91 98765 43210'
            profile.save()

            # Seed StudentProfile or StaffProfile
            if role == 'STUDENT':
                StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={'roll_number': roll_or_emp, 'department': dept, 'year': 1}
                )
                # Seed whitelist entry as USED
                RollWhitelist.objects.get_or_create(
                    roll_number=roll_or_emp,
                    defaults={'name': f"{first} {last}", 'department': dept, 'year': 1, 'is_used': True}
                )
            else:
                StaffProfile.objects.get_or_create(
                    user=user,
                    defaults={'designation': f"{role} — {dept}"}
                )

            created_users[username] = user

        # 1b. Seed some UNUSED roll numbers in whitelist for testing fresh student signup
        demo_whitelist = [
            ('22BCSE045', 'Rohan Gupta', 'Computer Science & Engineering', 2),
            ('22BECE012', 'Pooja Verma', 'Electronics & Communication', 2),
            ('23BMECH08', 'Karan Mehra', 'Mechanical Engineering', 1),
            ('23BCIVIL03', 'Sneha Roy', 'Civil Engineering', 1),
        ]
        for roll, name, dept, year in demo_whitelist:
            RollWhitelist.objects.get_or_create(
                roll_number=roll,
                defaults={'name': name, 'department': dept, 'year': year, 'is_used': False}
            )

        # 3. Organizing Units mapped to specific HODs
        cse_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Department of Computer Science & Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_cse']}
        )
        cse_dept.head = created_users['hod_cse']
        cse_dept.save()

        ece_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Department of Electronics & Communication Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_ece']}
        )
        ece_dept.head = created_users['hod_ece']
        ece_dept.save()

        mech_dept, _ = OrganizingUnit.objects.get_or_create(
            name='Department of Mechanical Engineering',
            defaults={'unit_type': 'DEPARTMENT', 'head': created_users['hod_mech']}
        )
        mech_dept.head = created_users['hod_mech']
        mech_dept.save()

        robotics_soc, _ = OrganizingUnit.objects.get_or_create(
            name='Robotics & Automation Society (RAS)',
            defaults={'unit_type': 'CLUB', 'head': created_users['club_lead']}
        )
        robotics_soc.head = created_users['club_lead']
        robotics_soc.save()

        now = timezone.now()

        # 4. Create Sample Event Proposals demonstrating new features:

        # --- EVENT A: Approved by Director, held in APPROVED_PENDING_PUBLISH ---
        # Demonstrates Requirement 3: Faculty coordinator has poster upload & publish button!
        chain_pending = get_default_chain('ACADEMIC')
        for stage in chain_pending:
            stage['status'] = 'APPROVED'

        event_pending_pub = EventProposal.objects.create(
            title='National Conference on Generative AI & Autonomous Systems (NCGAIS-2026)',
            description='A 3-day flagship national research conference with paper presentations, IEEE workshops, and technical keynotes.',
            proposer=created_users['faculty'],
            organizing_unit=cse_dept,
            co_coordinator='Dr. S. Radhakrishnan (CSE Dept, Intercom 4120)',
            guest_speaker='Prof. V. Kamakoti (Director, IIT Madras) & Dr. Geetha Manjunath (Niramai AI)',
            chain_type='ACADEMIC',
            approval_chain=chain_pending,
            current_stage_index=5,
            requested_budget=350000.00,
            approved_budget=320000.00,
            budget_revision_reason='Approved ₹3,20,000 as per hospitality guidelines by Dean Finance.',
            start_date=now + timedelta(days=14),
            end_date=now + timedelta(days=16),
            venue='Dr. APJ Abdul Kalam Central Auditorium',
            expected_attendees=350,
            mess_requirements='High tea and working lunch for 350 delegates and 20 dignitaries.',
            transport_requirements='2 VIP Innova vehicles for airport reception and drop.',
            maintenance_requirements='Dual 4K laser projectors, collar microphones, and continuous UPS power backup.',
            status='APPROVED_PENDING_PUBLISH', # Held for faculty upload & publish!
            revision_count=0,
            is_revision=False,
        )
        dispatch_logistics_notifications(event_pending_pub)

        ApprovalLog.objects.create(
            proposal=event_pending_pub,
            approver=created_users['director'],
            stage_name='Stage 5: Director of the Institute',
            action='APPROVED',
            remarks='Final executive clearance granted. Forwarded to Faculty Coordinator for poster upload & campus publishing.',
            created_at=now - timedelta(hours=2)
        )

        # --- EVENT B: Officially PUBLISHED (Ready for Rotating QR & Live Check-In) ---
        # Demonstrates Requirement 4: Rotating QR Code Screen!
        chain_published = get_default_chain('CLUB_FEST')
        for stage in chain_published:
            stage['status'] = 'APPROVED'

        event_published = EventProposal.objects.create(
            title='TechKriti 2026: All-India Inter-College Hackathon & Robotics Derby',
            description='A 36-hour non-stop hackathon and robotics arena combat for 500 engineering students across India.',
            proposer=created_users['faculty'],
            organizing_unit=robotics_soc,
            co_coordinator='Prof. Priya Nair & Robotics Council',
            guest_speaker='Dr. Tessy Thomas (Distinguished Scientist & Missile Woman of India)',
            chain_type='CLUB_FEST',
            approval_chain=chain_published,
            current_stage_index=5,
            requested_budget=250000.00,
            approved_budget=220000.00,
            budget_revision_reason='Sanctioned ₹2,20,000 after adjusting stage decoration overheads.',
            start_date=now + timedelta(days=3),
            end_date=now + timedelta(days=5),
            venue='Visvesvaraya Central Seminar Complex & Indoor Sports Stadium',
            expected_attendees=500,
            poster_data_uri='https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?auto=format&fit=crop&w=800&q=80',
            mess_requirements='Continuous snacks, energy drinks, tea/coffee counters, and lunch for 500 students.',
            transport_requirements='Campus shuttle buses between railway station and institute every 2 hours.',
            maintenance_requirements='Gigabit Wi-Fi nodes, 150 power extension cables, sound system, and floodlights.',
            status='APPROVED',
            published_at=now - timedelta(days=1),
            revision_count=1,
            is_revision=True,
        )
        dispatch_logistics_notifications(event_published)

        # Pre-seed registrations for demonstration
        EventRegistration.objects.create(
            event=event_published,
            student=created_users['student1'],
            role='PARTICIPANT',
            status='REGISTERED'
        )
        reg2 = EventRegistration.objects.create(
            event=event_published,
            student=created_users['student2'],
            role='VOLUNTEER',
            status='VERIFIED',
            checked_in_at=now - timedelta(hours=1),
            selfie_image='data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="%23059669"/><text x="50" y="55" font-size="11" fill="white" text-anchor="middle">Selfie OK</text></svg>'
        )
        EventFeedback.objects.create(
            registration=reg2,
            rating_overall=5,
            rating_content=5,
            rating_speaker=5,
            comments='Outstanding hackathon organization, mentors were available round the clock!'
        )

        # --- EVENT C: Under Review at Stage 3 (Dean Finance) ---
        chain_under_review = get_default_chain('ACADEMIC')
        chain_under_review[0]['status'] = 'APPROVED'
        chain_under_review[1]['status'] = 'APPROVED'
        chain_under_review[2]['status'] = 'PENDING'

        EventProposal.objects.create(
            title='National Faculty Development Programme on VLSI & Chip Design 2026',
            description='One-week intensive training for faculty and researchers on open-source EDA tools and RISC-V architectures.',
            proposer=created_users['faculty_ece'],
            organizing_unit=ece_dept,
            co_coordinator='Dr. Sunita Kulkarni (HOD ECE)',
            guest_speaker='Dr. Satya Gupta (President, VLSI Society of India)',
            chain_type='ACADEMIC',
            approval_chain=chain_under_review,
            current_stage_index=2, # Awaiting Dean Finance!
            requested_budget=180000.00,
            approved_budget=180000.00,
            start_date=now + timedelta(days=22),
            end_date=now + timedelta(days=27),
            venue='Sir C. V. Raman Computing Hall & ECE Labs',
            expected_attendees=80,
            mess_requirements='Morning high tea, working lunch, and evening snacks for 80 faculty participants.',
            transport_requirements='Pickup for visiting expert from city guest house.',
            maintenance_requirements='80 high-performance Linux workstations configured with RISC-V tools.',
            status='UNDER_REVIEW',
            revision_count=0,
            is_revision=False,
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully with pre-provisioned Indian college entities, distinct HODs, pending publish gate, and rotating QR!"))
