"""
Email notification helpers for the College Event Management System.
All functions catch exceptions internally so a failed email never breaks the main workflow.
"""
from django.core.mail import send_mail, send_mass_mail
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def _send(subject, body, recipient_list):
    """Helper to send a single email, silently failing on error."""
    if not recipient_list:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception:
        pass


def notify_next_approver(event, stage):
    """Notify the approver(s) responsible for the given stage."""
    from events.services import get_approvers_for_stage
    approvers = get_approvers_for_stage(event, stage.stage_number)
    emails = [u.email for u in approvers if u.email]
    stage_label = dict(stage.STAGE_CHOICES).get(stage.stage_number, f'Stage {stage.stage_number}')

    subject = f'[Action Required] Event Approval – Stage {stage.stage_number}: {event.title}'
    body = (
        f'Dear Approver,\n\n'
        f'An event proposal requires your approval at {stage_label}.\n\n'
        f'Event: {event.title}\n'
        f'Type: {event.get_event_type_display()}\n'
        f'Proposed by: {event.proposed_by.get_full_name() or event.proposed_by.username}\n'
        f'Venue: {event.venue}\n'
        f'Date: {event.start_datetime.strftime("%d %b %Y, %H:%M")}\n'
        f'Requested Budget: ₹{event.requested_budget}\n\n'
        f'Please log in to the portal to review and act on this proposal.\n\n'
        f'– College Event Management System'
    )
    _send(subject, body, emails)


def notify_faculty_revision(event, remark):
    """Notify the faculty that their event needs revision."""
    email = event.proposed_by.email
    if not email:
        return
    subject = f'[Revision Required] Your Event Proposal: {event.title}'
    body = (
        f'Dear {event.proposed_by.get_full_name() or event.proposed_by.username},\n\n'
        f'Your event proposal "{event.title}" requires revision.\n\n'
        f'Reviewer Remark:\n{remark}\n\n'
        f'Please log in and update your proposal.\n\n'
        f'– College Event Management System'
    )
    _send(subject, body, [email])


def notify_faculty_rejection(event, remark):
    """Notify the faculty that their event was rejected."""
    email = event.proposed_by.email
    if not email:
        return
    subject = f'[Rejected] Your Event Proposal: {event.title}'
    body = (
        f'Dear {event.proposed_by.get_full_name() or event.proposed_by.username},\n\n'
        f'We regret to inform you that your event proposal "{event.title}" has been rejected.\n\n'
        f'Reason:\n{remark}\n\n'
        f'– College Event Management System'
    )
    _send(subject, body, [email])


def notify_infra_staff(event):
    """
    Notify transport, mess, and/or maintenance staff about their requirements
    after an event is fully approved.
    """
    messages_to_send = []

    subject_base = f'[Action Required] Infrastructure Support – {event.title}'
    event_info = (
        f'Event: {event.title}\n'
        f'Date: {event.start_datetime.strftime("%d %b %Y, %H:%M")}\n'
        f'Venue: {event.venue}\n'
        f'Expected Attendees: {event.expected_attendees}\n'
        f'Approved Budget: ₹{event.approved_budget or event.requested_budget}\n\n'
    )

    if event.transport_required:
        staff = User.objects.filter(role='transport', is_active=True).exclude(email='')
        emails = [u.email for u in staff]
        if emails:
            body = (
                f'Dear Transport Team,\n\n'
                f'Your support is needed for the following approved event:\n\n'
                + event_info
                + f'Transport Details:\n{event.transport_details}\n\n'
                + '– College Event Management System'
            )
            for email in emails:
                messages_to_send.append((subject_base, body, settings.DEFAULT_FROM_EMAIL, [email]))

    if event.mess_required:
        staff = User.objects.filter(role='mess', is_active=True).exclude(email='')
        emails = [u.email for u in staff]
        if emails:
            body = (
                f'Dear Mess Team,\n\n'
                f'Your support is needed for the following approved event:\n\n'
                + event_info
                + f'Mess Details:\n{event.mess_details}\n\n'
                + '– College Event Management System'
            )
            for email in emails:
                messages_to_send.append((subject_base, body, settings.DEFAULT_FROM_EMAIL, [email]))

    if event.maintenance_required:
        staff = User.objects.filter(role='maintenance', is_active=True).exclude(email='')
        emails = [u.email for u in staff]
        if emails:
            body = (
                f'Dear Maintenance Team,\n\n'
                f'Your support is needed for the following approved event:\n\n'
                + event_info
                + f'Maintenance Details:\n{event.maintenance_details}\n\n'
                + '– College Event Management System'
            )
            for email in emails:
                messages_to_send.append((subject_base, body, settings.DEFAULT_FROM_EMAIL, [email]))

    if messages_to_send:
        try:
            send_mass_mail(messages_to_send, fail_silently=True)
        except Exception:
            pass


def send_compliance_report(event, report_data, recipient_emails):
    """Email a plain-text compliance report summary to HOD / event managers."""
    subject = f'[Compliance Report] {event.title}'
    body = (
        f'Compliance Report – {event.title}\n'
        f'{"=" * 60}\n\n'
        f'Date: {event.start_datetime.strftime("%d %b %Y, %H:%M")} – '
        f'{event.end_datetime.strftime("%H:%M")}\n'
        f'Venue: {event.venue}\n'
        f'Approved Budget: ₹{report_data.get("approved_budget", "N/A")}\n\n'
        f'Attendance\n'
        f'----------\n'
        f'  Registered: {report_data.get("registered_count", 0)}\n'
        f'  Checked In: {report_data.get("checkin_count", 0)}\n'
        f'  Verified (feedback given): {report_data.get("verified_count", 0)}\n\n'
        f'Feedback\n'
        f'--------\n'
        f'  Avg Rating: {report_data.get("avg_rating", "N/A")}/5\n'
        f'  Comments:\n'
    )
    for comment in report_data.get('comments', []):
        body += f'    • {comment}\n'
    body += '\n– College Event Management System'
    _send(subject, body, recipient_emails)
