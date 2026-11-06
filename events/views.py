from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator

from .models import Event, ApprovalStage, EventRegistration
from .forms import EventForm, ApprovalActionForm, EventRegistrationForm
from .services import advance_approval, can_user_approve_stage, get_approvers_for_stage


def role_required(*roles):
    """Decorator factory that restricts access to users with specific roles."""
    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission to view this page.')
                return redirect('/events/dashboard/')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@login_required
def dashboard(request):
    """Route the user to the appropriate dashboard based on their role."""
    user = request.user
    if user.role in ('faculty', 'club_head'):
        return faculty_dashboard(request)
    elif user.is_approver:
        return approver_dashboard(request)
    else:
        return student_dashboard(request)


@login_required
def faculty_dashboard(request):
    events = Event.objects.filter(proposed_by=request.user).order_by('-created_at')
    context = {
        'events': events,
        'page_title': 'My Event Proposals',
    }
    return render(request, 'events/dashboard_faculty.html', context)


@login_required
def approver_dashboard(request):
    user = request.user
    # Determine which stage this approver is responsible for
    ROLE_STAGE_MAP = {
        'hod': 1,
        'club_head': 1,
        'hr': 2,
        'dean_research': 3,
        'dean_accounts': 4,
        'dean_academics': 5,
    }
    stage_num = ROLE_STAGE_MAP.get(user.role)

    if stage_num is None:
        messages.error(request, 'Your role does not have approval privileges.')
        return redirect('/')

    # Get pending stages at this approver's level
    pending_stages = ApprovalStage.objects.filter(
        stage_number=stage_num,
        action='pending',
        event__status='pending',
    ).select_related('event', 'event__proposed_by')

    # For stage 1: filter by event type matching the approver role
    if user.role == 'hod':
        pending_stages = pending_stages.filter(event__event_type='department')
    elif user.role == 'club_head':
        pending_stages = pending_stages.filter(event__event_type='club')

    context = {
        'pending_stages': pending_stages,
        'stage_num': stage_num,
        'page_title': f'Approval Dashboard – Stage {stage_num}',
    }
    return render(request, 'events/dashboard_approver.html', context)


@login_required
def student_dashboard(request):
    published_events = Event.objects.filter(status='published').order_by('start_datetime')
    # Get events the student is registered for
    registrations = EventRegistration.objects.filter(student=request.user).select_related('event')
    registered_event_ids = set(r.event_id for r in registrations)

    context = {
        'events': published_events,
        'registered_event_ids': registered_event_ids,
        'registrations': registrations,
        'page_title': 'Available Events',
    }
    return render(request, 'events/dashboard_student.html', context)


@method_decorator(login_required, name='dispatch')
class EventCreateView(View):
    template_name = 'events/event_form.html'

    def get(self, request):
        if request.user.role not in ('faculty', 'club_head', 'hod'):
            messages.error(request, 'Only faculty or club heads can propose events.')
            return redirect('/events/dashboard/')
        form = EventForm()
        return render(request, self.template_name, {'form': form, 'page_title': 'Propose New Event'})

    def post(self, request):
        if request.user.role not in ('faculty', 'club_head', 'hod'):
            messages.error(request, 'Only faculty or club heads can propose events.')
            return redirect('/events/dashboard/')
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.proposed_by = request.user
            event.status = 'pending'
            event.save()
            # Create the first approval stage
            ApprovalStage.objects.create(event=event, stage_number=1, action='pending')
            messages.success(request, f'Event "{event.title}" submitted for approval.')
            return redirect(f'/events/{event.pk}/')
        return render(request, self.template_name, {'form': form, 'page_title': 'Propose New Event'})


@method_decorator(login_required, name='dispatch')
class EventEditView(View):
    template_name = 'events/event_form.html'

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if event.proposed_by != request.user:
            messages.error(request, 'You can only edit your own events.')
            return redirect('/events/dashboard/')
        if event.status not in ('draft', 'revision_required'):
            messages.error(request, 'Only draft or revision-required events can be edited.')
            return redirect(f'/events/{pk}/')
        form = EventForm(instance=event)
        return render(request, self.template_name, {'form': form, 'event': event, 'page_title': 'Edit Event'})

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        if event.proposed_by != request.user:
            messages.error(request, 'You can only edit your own events.')
            return redirect('/events/dashboard/')
        if event.status not in ('draft', 'revision_required'):
            messages.error(request, 'Only draft or revision-required events can be edited.')
            return redirect(f'/events/{pk}/')
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.status = 'pending'
            if event.is_revision:
                event.revision_number += 1
            else:
                event.is_revision = True
                event.revision_number = 1
            event.save()
            # Create a fresh stage-1 approval
            event.approval_stages.filter(action='pending').delete()
            ApprovalStage.objects.create(event=event, stage_number=1, action='pending')
            messages.success(request, 'Event resubmitted for approval.')
            return redirect(f'/events/{event.pk}/')
        return render(request, self.template_name, {'form': form, 'event': event, 'page_title': 'Edit Event'})


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    stages = event.approval_stages.order_by('stage_number')
    registration = None
    if request.user.role == 'student':
        registration = EventRegistration.objects.filter(event=event, student=request.user).first()
    context = {
        'event': event,
        'stages': stages,
        'registration': registration,
        'page_title': event.title,
    }
    return render(request, 'events/event_detail.html', context)


@login_required
def event_list(request):
    """Public list of published events (for students to browse)."""
    events = Event.objects.filter(status__in=['published', 'completed']).order_by('start_datetime')
    return render(request, 'events/event_list.html', {'events': events, 'page_title': 'All Events'})


@method_decorator(login_required, name='dispatch')
class ApprovalActionView(View):
    template_name = 'events/approval_action.html'

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        # Find the pending stage for this approver
        stage_obj = self._get_pending_stage(request.user, event)
        if stage_obj is None:
            messages.error(request, 'No pending approval stage found for your role on this event.')
            return redirect(f'/events/{pk}/')
        form = ApprovalActionForm()
        context = {
            'event': event,
            'stage_obj': stage_obj,
            'form': form,
            'page_title': f'Approval Action – {event.title}',
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        stage_obj = self._get_pending_stage(request.user, event)
        if stage_obj is None:
            messages.error(request, 'No pending approval stage found for your role on this event.')
            return redirect(f'/events/{pk}/')
        form = ApprovalActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            remark = form.cleaned_data['remark']
            revised_budget = form.cleaned_data.get('revised_budget')
            budget_reason = form.cleaned_data.get('budget_revision_reason', '')
            advance_approval(event, stage_obj, action, remark, request.user, revised_budget, budget_reason)
            messages.success(request, f'Action "{action}" recorded for "{event.title}".')
            return redirect('/events/approver-dashboard/')
        context = {
            'event': event,
            'stage_obj': stage_obj,
            'form': form,
            'page_title': f'Approval Action – {event.title}',
        }
        return render(request, self.template_name, context)

    def _get_pending_stage(self, user, event):
        """Return the stage object this user can act on, or None."""
        ROLE_STAGE_MAP = {
            'hod': 1,
            'club_head': 1,
            'hr': 2,
            'dean_research': 3,
            'dean_accounts': 4,
            'dean_academics': 5,
        }
        stage_num = ROLE_STAGE_MAP.get(user.role)
        if stage_num is None:
            return None
        try:
            stage_obj = event.approval_stages.get(stage_number=stage_num, action='pending')
        except ApprovalStage.DoesNotExist:
            return None
        if not can_user_approve_stage(user, event, stage_num):
            return None
        return stage_obj


@login_required
def register_for_event(request, pk):
    event = get_object_or_404(Event, pk=pk, status='published')
    if request.user.role != 'student':
        messages.error(request, 'Only students can register for events.')
        return redirect(f'/events/{pk}/')
    existing = EventRegistration.objects.filter(event=event, student=request.user).first()
    if existing:
        messages.info(request, 'You are already registered for this event.')
        return redirect(f'/events/{pk}/')
    form = EventRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        EventRegistration.objects.create(
            event=event,
            student=request.user,
            role=form.cleaned_data['role'],
        )
        messages.success(request, f'Successfully registered for "{event.title}"!')
        return redirect(f'/events/{pk}/')
    return render(request, 'events/event_detail.html', {
        'event': event,
        'registration_form': form,
        'stages': event.approval_stages.order_by('stage_number'),
        'page_title': event.title,
    })
