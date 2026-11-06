"""
Django signals for the College Event Management System notifications.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='events.ApprovalStage')
def on_approval_stage_save(sender, instance, created, **kwargs):
    """
    When a new ApprovalStage is created with action='pending',
    we notify the next approver. This is already called explicitly in
    services.advance_approval, so here we guard against double-sending.
    """
    pass  # Notifications are handled directly in services.py for precise control


@receiver(post_save, sender='checkin.EventFeedback')
def on_feedback_submitted(sender, instance, created, **kwargs):
    """Mark the associated check-in as verified when feedback is first submitted."""
    if created:
        checkin = instance.checkin
        if not checkin.is_verified:
            checkin.is_verified = True
            checkin.save(update_fields=['is_verified'])
