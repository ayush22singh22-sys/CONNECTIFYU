import io
import base64
import qrcode
from django.core.mail import send_mail
from .models import LogisticsNotification


def get_default_chain(chain_type, custom_roles=None):
    """
    Returns the ordered approval stages list for an event proposal.
    Dean of Finance, Dean of Academics, and Director are MANDATORY in all chains!
    """
    mandatory_tail = [
        {"role": "DEAN_ACCOUNTS", "title": "Dean of Finance & Accounts (Mandatory Sanction)"},
        {"role": "DEAN_ACADEMICS", "title": "Dean of Academic Affairs (Mandatory Review)"},
        {"role": "DIRECTOR", "title": "Director of the Institute (Mandatory Final Clearance)"},
    ]

    role_titles = {
        'HOD': 'Head of Department (HOD)',
        'CLUB_HEAD': 'Faculty Advisor / Club In-Charge',
        'REGISTRAR': 'Registrar / Establishment Section (HR)',
        'DEAN_RESEARCH': 'Dean of Research & Consultancy (R&D)',
        'DEAN_STUDENT_WELFARE': 'Dean of Student Welfare (DSW)',
        'DEAN_ACCOUNTS': 'Dean of Finance & Accounts (Mandatory)',
        'DEAN_ACADEMICS': 'Dean of Academic Affairs (Mandatory)',
        'DIRECTOR': 'Director of the Institute (Mandatory)',
    }

    if chain_type == 'ACADEMIC':
        head = [
            {"role": "HOD", "title": "Head of Department (HOD)"},
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
            for r in custom_roles:
                # Do not duplicate mandatory roles in custom head
                if r not in ['DEAN_ACCOUNTS', 'DEAN_ACADEMICS', 'DIRECTOR']:
                    chain.append({"role": r, "title": role_titles.get(r, r)})
        # Always append mandatory 3 stages
        chain += mandatory_tail
    else:
        chain = [
            {"role": "HOD", "title": "Head of Department (HOD)"},
            {"role": "DEAN_RESEARCH", "title": "Dean of Research & Consultancy (R&D)"},
        ] + mandatory_tail

    # Number each step sequentially
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
    """
    notifications = []

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
        notif = LogisticsNotification.objects.create(
            proposal=proposal,
            logistics_type='MESS',
            recipient_email='catering.mess@college.ac.in',
            subject=f"[Approved Event Logistics] Catering Request: {proposal.title}",
            body=mess_body
        )
        notifications.append(notif)
        try:
            send_mail(
                subject=notif.subject,
                message=notif.body,
                from_email='noreply-events@college.ac.in',
                recipient_list=[notif.recipient_email],
                fail_silently=True
            )
        except Exception:
            pass

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
        notif = LogisticsNotification.objects.create(
            proposal=proposal,
            logistics_type='TRANSPORT',
            recipient_email='estate.transport@college.ac.in',
            subject=f"[Approved Event Logistics] Transport Request: {proposal.title}",
            body=transport_body
        )
        notifications.append(notif)
        try:
            send_mail(
                subject=notif.subject,
                message=notif.body,
                from_email='noreply-events@college.ac.in',
                recipient_list=[notif.recipient_email],
                fail_silently=True
            )
        except Exception:
            pass

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
        notif = LogisticsNotification.objects.create(
            proposal=proposal,
            logistics_type='MAINTENANCE',
            recipient_email='maintenance.av@college.ac.in',
            subject=f"[Approved Event Logistics] AV & Hall Setup: {proposal.title}",
            body=maint_body
        )
        notifications.append(notif)
        try:
            send_mail(
                subject=notif.subject,
                message=notif.body,
                from_email='noreply-events@college.ac.in',
                recipient_list=[notif.recipient_email],
                fail_silently=True
            )
        except Exception:
            pass

    return notifications
