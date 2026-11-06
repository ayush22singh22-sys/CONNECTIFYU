import base64
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.views import View
from django.utils.decorators import method_decorator

from events.models import Event, EventRegistration, EventQRCode
from .models import CheckIn, EventFeedback


@login_required
def qr_display(request, event_pk):
    """Faculty view: show projected QR code for a live event."""
    event = get_object_or_404(Event, pk=event_pk, status='published')
    if request.user != event.proposed_by and not request.user.is_staff:
        messages.error(request, 'Only the event coordinator can display the check-in QR.')
        return redirect(f'/events/{event_pk}/')
    try:
        qr_code = event.qr_code
    except EventQRCode.DoesNotExist:
        messages.error(request, 'QR code not yet generated for this event.')
        return redirect(f'/events/{event_pk}/')
    return render(request, 'checkin/qr_display.html', {'event': event, 'qr_code': qr_code})


@method_decorator(login_required, name='dispatch')
class CheckInView(View):
    """
    GET  ?token=<uuid>  – validates token, shows camera capture UI
    POST              – receives base64 selfie, creates CheckIn record
    """
    template_name = 'checkin/checkin_camera.html'

    def get(self, request):
        token = request.GET.get('token')
        if not token:
            messages.error(request, 'Invalid check-in link – no token provided.')
            return redirect('/events/student-dashboard/')
        try:
            token_uuid = uuid.UUID(token)
        except (ValueError, AttributeError):
            messages.error(request, 'Invalid check-in token format.')
            return redirect('/events/student-dashboard/')

        qr_code = get_object_or_404(EventQRCode, token=token_uuid)
        event = qr_code.event

        # Must be registered
        registration = EventRegistration.objects.filter(event=event, student=request.user).first()
        if not registration:
            messages.error(request, 'You are not registered for this event.')
            return redirect(f'/events/{event.pk}/')

        # Already checked in?
        if hasattr(registration, 'checkin'):
            messages.info(request, 'You have already checked in.')
            checkin = registration.checkin
            if not hasattr(checkin, 'feedback'):
                return redirect(f'/checkin/feedback/{checkin.pk}/')
            return redirect(f'/events/{event.pk}/')

        return render(request, self.template_name, {
            'event': event,
            'token': token,
            'page_title': f'Check In – {event.title}',
        })

    def post(self, request):
        token = request.POST.get('token')
        selfie_data = request.POST.get('selfie_data')

        if not token or not selfie_data:
            messages.error(request, 'Missing check-in data.')
            return redirect('/events/student-dashboard/')

        try:
            token_uuid = uuid.UUID(token)
        except (ValueError, AttributeError):
            messages.error(request, 'Invalid token.')
            return redirect('/events/student-dashboard/')

        qr_code = get_object_or_404(EventQRCode, token=token_uuid)
        event = qr_code.event

        registration = EventRegistration.objects.filter(event=event, student=request.user).first()
        if not registration:
            messages.error(request, 'You are not registered for this event.')
            return redirect(f'/events/{event.pk}/')

        if hasattr(registration, 'checkin'):
            messages.info(request, 'Already checked in.')
            return redirect(f'/checkin/feedback/{registration.checkin.pk}/')

        # Decode and save selfie
        try:
            if ',' in selfie_data:
                selfie_data = selfie_data.split(',', 1)[1]
            selfie_bytes = base64.b64decode(selfie_data)
        except Exception:
            messages.error(request, 'Could not process selfie image.')
            return redirect(f'/checkin/scan/?token={token}')

        checkin = CheckIn(registration=registration)
        checkin.selfie.save(
            f"selfie_{request.user.pk}_{event.pk}.jpg",
            ContentFile(selfie_bytes),
            save=False,
        )
        checkin.save()
        messages.success(request, 'Check-in successful! Please submit your feedback.')
        return redirect(f'/checkin/feedback/{checkin.pk}/')


@method_decorator(login_required, name='dispatch')
class FeedbackView(View):
    template_name = 'checkin/feedback_form.html'

    def get(self, request, checkin_pk):
        checkin = get_object_or_404(CheckIn, pk=checkin_pk, registration__student=request.user)
        if hasattr(checkin, 'feedback'):
            messages.info(request, 'You have already submitted feedback.')
            return redirect(f'/events/{checkin.registration.event.pk}/')
        return render(request, self.template_name, {
            'checkin': checkin,
            'page_title': 'Submit Feedback',
        })

    def post(self, request, checkin_pk):
        checkin = get_object_or_404(CheckIn, pk=checkin_pk, registration__student=request.user)
        if hasattr(checkin, 'feedback'):
            messages.info(request, 'Feedback already submitted.')
            return redirect(f'/events/{checkin.registration.event.pk}/')

        rating = request.POST.get('rating')
        comments = request.POST.get('comments', '')

        if not rating or not rating.isdigit() or int(rating) not in range(1, 6):
            messages.error(request, 'Please select a valid rating (1–5).')
            return render(request, self.template_name, {'checkin': checkin, 'page_title': 'Submit Feedback'})

        EventFeedback.objects.create(
            checkin=checkin,
            rating=int(rating),
            comments=comments,
        )
        checkin.is_verified = True
        checkin.save(update_fields=['is_verified'])
        messages.success(request, 'Thank you for your feedback!')
        return redirect(f'/events/{checkin.registration.event.pk}/')
