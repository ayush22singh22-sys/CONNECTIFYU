import io
import base64
import qrcode
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from .models import LogisticsNotification, OrganizingUnit


ROLE_DESCRIPTIONS = {
    'HOD_CSE': 'HOD - Computer Science & Engineering (Dr. K. V. Ramanathan)',
    'HOD_ECE': 'HOD - Electronics & Communication Engineering (Dr. Sunita Kulkarni)',
    'HOD_MECH': 'HOD - Mechanical Engineering (Dr. Vikramaditya Rathore)',
    'HOD': 'Head of Department (Organizing Unit HOD)',
    'CLUB_HEAD': 'Faculty Advisor / Club In-Charge',
    'CLUB_ROBOTICS': 'Faculty Advisor - Robotics & Automation Society (Prof. Priya Nair)',
    'CLUB_CULTURAL': 'Faculty Advisor - Cultural Affairs Committee (Prof. Amit Trivedi)',
    'REGISTRAR': 'Registrar / Establishment Section (Smt. Sunita Deshmukh)',
    'DEAN_RESEARCH': 'Dean of Research & Consultancy (Dr. P. Venkatraman)',
    'DEAN_STUDENT_WELFARE': 'Dean of Student Welfare (Dr. Alok Sen)',
    'DEAN_ACCOUNTS': 'Dean of Finance & Accounts (Dr. Suresh Chandra) - Mandatory',
    'DEAN_ACADEMICS': 'Dean of Academic Affairs (Dr. Meenakshi Sundaram) - Mandatory',
    'DIRECTOR': 'Director of the Institute (Dr. R. Chidambaram) - Mandatory Clearance',
}


def get_default_chain(chain_type, unit_id=None, custom_roles=None):
    """
    Returns the ordered approval stages list for an event proposal.
    Dean of Finance, Dean of Academics, and Director are MANDATORY in all chains!
    Resolves department-wise HOD based on the selected organizing unit.
    """
    mandatory_tail = [
        {"role": "DEAN_ACCOUNTS", "title": "Dean of Finance & Accounts (Mandatory Sanction)"},
        {"role": "DEAN_ACADEMICS", "title": "Dean of Academic Affairs (Mandatory Review)"},
        {"role": "DIRECTOR", "title": "Director of the Institute (Mandatory Final Clearance)"},
    ]

    # Resolve department-specific HOD
    dept_hod_role = 'HOD'
    dept_hod_title = 'Head of Department (HOD)'

    if unit_id:
        try:
            unit = OrganizingUnit.objects.get(id=unit_id)
            unit_name_lower = unit.name.lower()
            if 'computer' in unit_name_lower or 'cse' in unit_name_lower:
                dept_hod_role = 'HOD_CSE'
                dept_hod_title = 'HOD - Computer Science & Engineering (Dr. K. V. Ramanathan)'
            elif 'electronics' in unit_name_lower or 'ece' in unit_name_lower:
                dept_hod_role = 'HOD_ECE'
                dept_hod_title = 'HOD - Electronics & Communication Engineering (Dr. Sunita Kulkarni)'
            elif 'mechanical' in unit_name_lower or 'mech' in unit_name_lower:
                dept_hod_role = 'HOD_MECH'
                dept_hod_title = 'HOD - Mechanical Engineering (Dr. Vikramaditya Rathore)'
            elif unit.unit_type == 'CLUB':
                dept_hod_role = 'CLUB_HEAD'
                dept_hod_title = f"Club Advisor - {unit.name}"
        except Exception:
            pass

    if chain_type == 'ACADEMIC':
        head = [
            {"role": dept_hod_role, "title": dept_hod_title},
            {"role": "DEAN_RESEARCH", "title": "Dean of Research & Consultancy (R&D)"},
        ]
        chain = head + mandatory_tail

    elif chain_type == 'CLUB_FEST':
        head = [
            {"role": "CLUB_HEAD", "title": "Faculty Advisor / Club In-Charge"},
            {"role": "DEAN_STUDENT_WELFARE", "title": "Dean of Student Welfare (DSW)"},
        ]
        chain = head + mandatory_tail

    elif chain_type == 'INSTITUTE_MEGA':
        head = [
            {"role": "REGISTRAR", "title": "Registrar / Establishment Section (HR)"},
            {"role": "DEAN_RESEARCH", "title": "Dean of Research & Planning"},
        ]
        chain = head + mandatory_tail

    elif chain_type == 'CUSTOM':
        chain = []
        if custom_roles:
            seen_roles = set()
            # Fix #18: Whitelist valid roles only to prevent deadlock from arbitrary role names
            valid_custom_roles = set(ROLE_DESCRIPTIONS.keys()) - {'DEAN_ACCOUNTS', 'DEAN_ACADEMICS', 'DIRECTOR'}
            for r in custom_roles:
                if r in valid_custom_roles and r not in seen_roles:
                    seen_roles.add(r)
                    chain.append({"role": r, "title": ROLE_DESCRIPTIONS.get(r, r)})

        # If user picked no preliminary role in custom chain, default to organizing unit head
        if not chain:
            chain.append({"role": dept_hod_role, "title": dept_hod_title})

        # Append mandatory 3 statutory stages
        chain += mandatory_tail
    else:
        chain = [
            {"role": dept_hod_role, "title": dept_hod_title},
            {"role": "DEAN_RESEARCH", "title": "Dean of Research & Consultancy (R&D)"},
        ] + mandatory_tail

    for idx, stage in enumerate(chain, start=1):
        stage['step'] = idx
        stage['status'] = 'PENDING' if idx == 1 else 'WAITING'

    return chain


def generate_qr_base64(data_string):
    """Generates a QR Code as a base64 Data URI."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e1b4b", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_str}"


def dispatch_logistics_notifications(proposal):
    """
    Step 5 automated notification:
    Once Director grants final clearance, system automatically emails
    the college's transport, mess, and maintenance sections with requirements.
    Fix #10: Idempotent get_or_create to prevent duplicate notifications.
    Fix #11: Dispatch emails via transaction.on_commit to avoid side-effects on rollback.
    """
    notifications = []
    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply-events@college.ac.in')

    def _queue_email(subject, body, recipient):
        def _send():
            try:
                send_mail(subject, body, default_from, [recipient], fail_silently=True)
            except Exception:
                pass
        try:
            transaction.on_commit(_send)
        except Exception:
            _send()

    # 1. Mess & Catering Section
    if proposal.mess_requirements:
        mess_body = (
            f"URGENT / LOGISTICS ORDER: Catering & Refreshments\n"
            f"Event: {proposal.title}\n"
            f"Organized by: {proposal.organizing_unit.name} (Coordinator: {proposal.proposer.get_full_name()})\n"
            f"Sanctioned Budget: ₹{proposal.approved_budget}\n"
            f"Date & Time: {proposal.start_date.strftime('%Y-%m-%d %H:%M')} to {proposal.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"Venue: {proposal.venue}\n"
            f"Expected Attendees: {proposal.expected_attendees}\n"
            f"----------------------------------------\n"
            f"Specific Mess Requirements:\n{proposal.mess_requirements}\n"
        )
        notif, created = LogisticsNotification.objects.get_or_create(
            proposal=proposal,
            logistics_type='MESS',
            defaults={
                'recipient_email': 'catering.mess@college.ac.in',
                'subject': f"[Approved Event Logistics] Catering Request: {proposal.title}",
                'body': mess_body,
            }
        )
        notifications.append(notif)
        if created:
            _queue_email(notif.subject, notif.body, notif.recipient_email)

    # 2. Transport & Fleet Section
    if proposal.transport_requirements:
        transport_body = (
            f"URGENT / LOGISTICS ORDER: Fleet & Vehicle Dispatch\n"
            f"Event: {proposal.title}\n"
            f"Chief Guest / Keynote: {proposal.guest_speaker}\n"
            f"Date & Time: {proposal.start_date.strftime('%Y-%m-%d %H:%M')} to {proposal.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"----------------------------------------\n"
            f"Specific Transport Requirements:\n{proposal.transport_requirements}\n"
        )
        notif, created = LogisticsNotification.objects.get_or_create(
            proposal=proposal,
            logistics_type='TRANSPORT',
            defaults={
                'recipient_email': 'estate.transport@college.ac.in',
                'subject': f"[Approved Event Logistics] Transport Request: {proposal.title}",
                'body': transport_body,
            }
        )
        notifications.append(notif)
        if created:
            _queue_email(notif.subject, notif.body, notif.recipient_email)

    # 3. Auditorium, Estate & AV Maintenance Section
    if proposal.maintenance_requirements:
        maint_body = (
            f"URGENT / LOGISTICS ORDER: Auditorium & Audio/Visual Setup\n"
            f"Event: {proposal.title}\n"
            f"Venue: {proposal.venue}\n"
            f"Date & Time: {proposal.start_date.strftime('%Y-%m-%d %H:%M')} to {proposal.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"----------------------------------------\n"
            f"Specific Maintenance Requirements:\n{proposal.maintenance_requirements}\n"
        )
        notif, created = LogisticsNotification.objects.get_or_create(
            proposal=proposal,
            logistics_type='MAINTENANCE',
            defaults={
                'recipient_email': 'maintenance.av@college.ac.in',
                'subject': f"[Approved Event Logistics] AV & Hall Setup: {proposal.title}",
                'body': maint_body,
            }
        )
        notifications.append(notif)
        if created:
            _queue_email(notif.subject, notif.body, notif.recipient_email)

    return notifications
