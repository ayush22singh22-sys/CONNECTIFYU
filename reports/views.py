from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from events.models import Event
from .generators import generate_compliance_report
from notifications.emails import send_compliance_report


@login_required
def compliance_report(request, event_pk):
    """
    Display the compliance report for an event.
    Accessible to HOD, club_head, faculty (event owner), and admins.
    Optionally email the report to the proposer.
    """
    event = get_object_or_404(Event, pk=event_pk)
    allowed_roles = ('hod', 'club_head', 'dean_academics', 'hr', 'dean_research', 'dean_accounts')
    is_owner = request.user == event.proposed_by
    is_approver_role = request.user.role in allowed_roles

    if not (is_owner or is_approver_role or request.user.is_staff):
        messages.error(request, 'You do not have permission to view this report.')
        return render(request, 'events/event_detail.html', {'event': event})

    report_data = generate_compliance_report(event)

    if request.method == 'POST' and request.POST.get('email_report'):
        recipient_emails = [event.proposed_by.email] if event.proposed_by.email else []
        if request.user.email and request.user.email not in recipient_emails:
            recipient_emails.append(request.user.email)
        if recipient_emails:
            send_compliance_report(event, report_data, recipient_emails)
            messages.success(request, 'Compliance report emailed successfully.')
        else:
            messages.warning(request, 'No email addresses configured for this event.')

    return render(request, 'reports/compliance_report.html', {
        'report': report_data,
        'event': event,
        'page_title': f'Compliance Report – {event.title}',
    })
