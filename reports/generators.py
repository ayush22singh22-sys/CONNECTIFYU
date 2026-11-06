"""
Compliance report generator for the College Event Management System.
"""
from django.db.models import Avg


def generate_compliance_report(event):
    """
    Returns a dict with event details, final approved budget,
    attendance count (verified check-ins), avg feedback rating,
    and feedback comments list.
    """
    from checkin.models import CheckIn, EventFeedback
    from events.models import EventRegistration

    registrations = EventRegistration.objects.filter(event=event)
    registered_count = registrations.count()

    checkins = CheckIn.objects.filter(registration__event=event)
    checkin_count = checkins.count()
    verified_count = checkins.filter(is_verified=True).count()

    feedbacks = EventFeedback.objects.filter(checkin__registration__event=event)
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg']
    if avg_rating is not None:
        avg_rating = round(avg_rating, 2)
    comments = list(feedbacks.exclude(comments='').values_list('comments', flat=True))

    # Build approval timeline
    stages = []
    for stage in event.approval_stages.order_by('stage_number'):
        stages.append({
            'stage_number': stage.stage_number,
            'stage_label': stage.get_stage_number_display(),
            'approver': stage.approver.get_full_name() if stage.approver else 'N/A',
            'action': stage.get_action_display(),
            'remark': stage.remark,
            'revised_budget': stage.revised_budget,
            'acted_at': stage.acted_at,
        })

    return {
        'event': event,
        'approved_budget': event.approved_budget or event.requested_budget,
        'requested_budget': event.requested_budget,
        'registered_count': registered_count,
        'checkin_count': checkin_count,
        'verified_count': verified_count,
        'avg_rating': avg_rating or 'No ratings yet',
        'comments': comments,
        'approval_stages': stages,
    }
