import io
import base64
import qrcode
from django.core.mail import send_mail
from django.conf import settings
from .models import LogisticsNotification

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
    Once an event clears all stages, system emails the college's transport,
    mess, and maintenance staff with exact requirements and timestamps.
    """
    notifications = []

    # 1. Mess & Catering
    if proposal.mess_requirements:
        mess_body = (
            f"URGENT / LOGISTICS ORDER: Catering & Refreshments\n"
            f"Event: {proposal.title}\n"
            f"Organized by: {proposal.organizing_unit.name} (Lead: {proposal.proposer.get_full_name()})\n"
            f"Date & Time: {proposal.start_date.strftime('%Y-%m-%d %H:%M')} to {proposal.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"Venue: {proposal.venue}\n"
            f"Expected Attendees: {proposal.expected_attendees}\n"
            f"----------------------------------------\n"
            f"Specific Mess Requirements:\n{proposal.mess_requirements}\n"
        )
        notif = LogisticsNotification.objects.create(
            proposal=proposal,
            logistics_type='MESS',
            recipient_email='mess.catering@college.edu',
            subject=f"[Approved Event Logistics] Catering Request: {proposal.title}",
            body=mess_body
        )
        notifications.append(notif)
        try:
            send_mail(
                subject=notif.subject,
                message=notif.body,
                from_email='noreply-events@college.edu',
                recipient_list=[notif.recipient_email],
                fail_silently=True
            )
        except Exception:
            pass

    # 2. Transport & Fleet
    if proposal.transport_requirements:
        transport_body = (
            f"URGENT / LOGISTICS ORDER: Fleet & Vehicle Dispatch\n"
            f"Event: {proposal.title}\n"
            f"Guest Speaker: {proposal.guest_speaker}\n"
            f"Date & Time: {proposal.start_date.strftime('%Y-%m-%d %H:%M')} to {proposal.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"----------------------------------------\n"
            f"Specific Transport Requirements:\n{proposal.transport_requirements}\n"
        )
        notif = LogisticsNotification.objects.create(
            proposal=proposal,
            logistics_type='TRANSPORT',
            recipient_email='transport.fleet@college.edu',
            subject=f"[Approved Event Logistics] Transport Request: {proposal.title}",
            body=transport_body
        )
        notifications.append(notif)
        try:
            send_mail(
                subject=notif.subject,
                message=notif.body,
                from_email='noreply-events@college.edu',
                recipient_list=[notif.recipient_email],
                fail_silently=True
            )
        except Exception:
            pass

    # 3. Auditorium & Maintenance
    if proposal.maintenance_requirements:
        maint_body = (
            f"URGENT / LOGISTICS ORDER: Venue & Audio/Visual Setup\n"
            f"Event: {proposal.title}\n"
            f"Venue: {proposal.venue}\n"
            f"Date & Time: {proposal.start_date.strftime('%Y-%m-%d %H:%M')} to {proposal.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"----------------------------------------\n"
            f"Specific Maintenance Requirements:\n{proposal.maintenance_requirements}\n"
        )
        notif = LogisticsNotification.objects.create(
            proposal=proposal,
            logistics_type='MAINTENANCE',
            recipient_email='maintenance.av@college.edu',
            subject=f"[Approved Event Logistics] AV & Hall Setup: {proposal.title}",
            body=maint_body
        )
        notifications.append(notif)
        try:
            send_mail(
                subject=notif.subject,
                message=notif.body,
                from_email='noreply-events@college.edu',
                recipient_list=[notif.recipient_email],
                fail_silently=True
            )
        except Exception:
            pass

    return notifications
