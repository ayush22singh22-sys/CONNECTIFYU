"""
Approval chain service logic for the events app.
"""
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

# Maps stage number to the role(s) that approve at that stage.
# Stage 1 is split between hod (dept events) and club_head (club events).
STAGE_APPROVER_ROLES = {
    1: ['hod', 'club_head'],
    2: ['hr'],
    3: ['dean_research'],
    4: ['dean_accounts'],
    5: ['dean_academics'],
}


def get_approver_role_for_stage(event, stage_number):
    """Return the role name(s) expected to approve at a given stage."""
    if stage_number == 1:
        if event.event_type == 'club':
            return ['club_head']
        return ['hod']
    return STAGE_APPROVER_ROLES.get(stage_number, [])


def get_approvers_for_stage(event, stage_number):
    """Return a QuerySet of Users who can approve at this stage."""
    roles = get_approver_role_for_stage(event, stage_number)
    return User.objects.filter(role__in=roles, is_active=True)


def can_user_approve_stage(user, event, stage_number):
    """Check whether the given user can act on the given stage."""
    allowed_roles = get_approver_role_for_stage(event, stage_number)
    return user.role in allowed_roles


def advance_approval(event, current_stage_obj, action, remark, actor, revised_budget=None, budget_reason=''):
    """
    Process an approval action on current_stage_obj.
    - 'approved' + stage < 5 → create next pending stage, notify next approver
    - 'approved' + stage == 5 → mark event published, send infra emails
    - 'rejected'  → mark event rejected, notify faculty
    - 'revision_required' → mark event revision_required, notify faculty
    """
    from notifications.emails import (
        notify_next_approver,
        notify_faculty_revision,
        notify_faculty_rejection,
        notify_infra_staff,
    )
    from .models import ApprovalStage

    current_stage_obj.action = action
    current_stage_obj.remark = remark
    current_stage_obj.approver = actor
    current_stage_obj.acted_at = timezone.now()

    if revised_budget is not None:
        current_stage_obj.revised_budget = revised_budget
        current_stage_obj.budget_revision_reason = budget_reason
        event.approved_budget = revised_budget

    current_stage_obj.save()

    if action == 'approved':
        next_stage = current_stage_obj.stage_number + 1
        if next_stage <= 5:
            new_stage = ApprovalStage.objects.create(
                event=event,
                stage_number=next_stage,
                action='pending',
            )
            event.status = 'pending'
            event.save(update_fields=['status'])
            try:
                notify_next_approver(event, new_stage)
            except Exception:
                pass
        else:
            # Final approval
            if event.approved_budget is None:
                event.approved_budget = event.requested_budget
            event.status = 'published'
            event.save(update_fields=['status', 'approved_budget'])
            # Generate QR code for the event
            _generate_event_qr(event)
            try:
                notify_infra_staff(event)
            except Exception:
                pass

    elif action == 'rejected':
        event.status = 'rejected'
        event.save(update_fields=['status'])
        try:
            notify_faculty_rejection(event, remark)
        except Exception:
            pass

    elif action == 'revision_required':
        event.status = 'revision_required'
        event.save(update_fields=['status'])
        try:
            notify_faculty_revision(event, remark)
        except Exception:
            pass


def _generate_event_qr(event):
    """Generate and save a QR code for event check-in."""
    import qrcode
    import uuid
    import io
    from django.core.files.base import ContentFile
    from .models import EventQRCode

    token = uuid.uuid4()
    checkin_url = f"/checkin/scan/?token={token}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(checkin_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    qr_obj, _ = EventQRCode.objects.get_or_create(event=event, defaults={'token': token})
    qr_obj.token = token
    qr_obj.qr_image.save(f"qr_{event.pk}.png", ContentFile(buffer.read()), save=True)
