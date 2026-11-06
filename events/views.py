import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse, HttpResponseForbidden

from .models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification
)
from .utils import generate_qr_base64, dispatch_logistics_notifications, get_default_chain


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'registration/login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('login')


def switch_user_view(request, username):
    """
    Requirement: Always cleanly default to the dashboard screen
    when switching between entities (Student, Organizer, HOD, Deans, Director).
    """
    user = get_object_or_404(User, username=username)
    login(request, user)
    role_name = user.profile.get_role_display() if hasattr(user, 'profile') else 'User'
    messages.info(request, f"Switched active view to: {user.get_full_name() or user.username} ({role_name})")
    return redirect('dashboard')


def register_student_view(request):
    """
    Public student self-registration has been completely disabled.
    All student accounts are pre-provisioned in the institutional database.
    """
    messages.warning(request, "Public self-registration is disabled. All student and faculty accounts are pre-provisioned by College IT Administration.")
    return redirect('login')


@login_required
def dashboard_view(request):
    """
    Default screen for EVERY entity:
    - Students see their dedicated Student Dashboard (NO proposal features!).
    - Faculty/Organizers see proposal pipeline & live publishing tools.
    - Approvers (HODs, Deans, Director) see their actionable review queue.
    """
    user = request.user
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else 'STUDENT'

    # --- 1. DEDICATED STUDENT DASHBOARD ---
    if role == 'STUDENT':
        registrations = EventRegistration.objects.filter(student=user).select_related('event', 'event__organizing_unit').order_by('-registered_at')
        verified_count = registrations.filter(status='VERIFIED').count()
        checked_in_count = registrations.filter(status='CHECKED_IN').count()
        
        # Only published events (APPROVED or COMPLETED) are discoverable by students
        upcoming_events = EventProposal.objects.filter(status__in=['APPROVED', 'COMPLETED']).order_by('start_date')[:6]

        context = {
            'is_student': True,
            'role': 'STUDENT',
            'profile': profile,
            'registrations': registrations,
            'verified_count': verified_count,
            'checked_in_count': checked_in_count,
            'upcoming_events': upcoming_events,
        }
        return render(request, 'events/dashboard.html', context)

    # --- 2. FACULTY, APPROVER & EXECUTIVE DASHBOARD ---
    my_proposals = EventProposal.objects.filter(proposer=user).order_by('-created_at')

    # Find proposals waiting for this specific user's approval
    all_under_review = EventProposal.objects.filter(status='UNDER_REVIEW').order_by('-updated_at')
    pending_approvals = [p for p in all_under_review if p.is_awaiting_user(user)]

    all_approved = EventProposal.objects.filter(status__in=['APPROVED', 'COMPLETED']).order_by('-start_date')[:6]
    total_sanctioned_budget = EventProposal.objects.filter(status__in=['APPROVED', 'APPROVED_PENDING_PUBLISH', 'COMPLETED']).aggregate(Sum('approved_budget'))['approved_budget__sum'] or 0

    context = {
        'is_student': False,
        'role': role,
        'profile': profile,
        'my_proposals': my_proposals,
        'pending_approvals': pending_approvals,
        'all_approved': all_approved,
        'stats': {
            'total_proposals': EventProposal.objects.count(),
            'approved_count': EventProposal.objects.filter(status='APPROVED').count(),
            'pending_publish_count': EventProposal.objects.filter(status='APPROVED_PENDING_PUBLISH').count(),
            'revision_count': EventProposal.objects.filter(status='REVISION_REQUESTED').count(),
            'total_students': UserProfile.objects.filter(role='STUDENT').count(),
            'total_budget_sanctioned': total_sanctioned_budget,
        }
    }
    return render(request, 'events/dashboard.html', context)


@login_required
def create_proposal_view(request):
    """
    Requirement 5: Department-wise HOD approval chains.
    Students are strictly barred.
    """
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.role == 'STUDENT':
        messages.error(request, "Access Denied: Students are not authorized to propose or publish college events.")
        return redirect('dashboard')

    units = OrganizingUnit.objects.all().order_by('name')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        unit_id = request.POST.get('organizing_unit')
        co_coordinator = request.POST.get('co_coordinator')
        guest_speaker = request.POST.get('guest_speaker')
        requested_budget = request.POST.get('requested_budget', 0)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        venue = request.POST.get('venue')
        expected_attendees = request.POST.get('expected_attendees', 100)

        # Department-Specific Approval Chain Selection
        chain_type = request.POST.get('chain_type', 'ACADEMIC')
        custom_roles = request.POST.getlist('custom_roles') if chain_type == 'CUSTOM' else None
        chain_list = get_default_chain(chain_type, unit_id=unit_id, custom_roles=custom_roles)

        mess_req = request.POST.get('mess_requirements', '')
        transport_req = request.POST.get('transport_requirements', '')
        maint_req = request.POST.get('maintenance_requirements', '')

        unit = get_object_or_404(OrganizingUnit, id=unit_id)

        proposal = EventProposal.objects.create(
            title=title,
            description=description,
            proposer=request.user,
            organizing_unit=unit,
            co_coordinator=co_coordinator,
            guest_speaker=guest_speaker,
            requested_budget=requested_budget,
            approved_budget=requested_budget,
            start_date=start_date,
            end_date=end_date,
            venue=venue,
            expected_attendees=expected_attendees,
            chain_type=chain_type,
            approval_chain=chain_list,
            current_stage_index=0,
            mess_requirements=mess_req,
            transport_requirements=transport_req,
            maintenance_requirements=maint_req,
            status='UNDER_REVIEW'
        )

        first_stage = proposal.current_stage
        stage_title = first_stage.get('title', 'Stage 1') if first_stage else 'Stage 1'
        messages.success(request, f"Event proposal '{proposal.title}' filed! Routed to Stage 1: {stage_title}.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    return render(request, 'events/proposal_form.html', {'units': units, 'is_edit': False})


@login_required
def edit_proposal_view(request, proposal_id):
    """Allows proposer to fix remarks and resubmit proposal through the full chain from Stage 1."""
    proposal = get_object_or_404(EventProposal, id=proposal_id, proposer=request.user)
    if proposal.status != 'REVISION_REQUESTED':
        messages.warning(request, "This proposal is not currently marked for revision.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    units = OrganizingUnit.objects.all().order_by('name')

    if request.method == 'POST':
        proposal.title = request.POST.get('title')
        proposal.description = request.POST.get('description')
        unit_id = request.POST.get('organizing_unit')
        proposal.organizing_unit = get_object_or_404(OrganizingUnit, id=unit_id)
        proposal.co_coordinator = request.POST.get('co_coordinator')
        proposal.guest_speaker = request.POST.get('guest_speaker')
        proposal.requested_budget = request.POST.get('requested_budget', proposal.requested_budget)
        proposal.approved_budget = proposal.requested_budget
        proposal.start_date = request.POST.get('start_date')
        proposal.end_date = request.POST.get('end_date')
        proposal.venue = request.POST.get('venue')
        proposal.expected_attendees = request.POST.get('expected_attendees', 100)
        proposal.mess_requirements = request.POST.get('mess_requirements', '')
        proposal.transport_requirements = request.POST.get('transport_requirements', '')
        proposal.maintenance_requirements = request.POST.get('maintenance_requirements', '')

        new_chain_type = request.POST.get('chain_type', proposal.chain_type)
        if new_chain_type != proposal.chain_type or new_chain_type == 'CUSTOM':
            custom_roles = request.POST.getlist('custom_roles') if new_chain_type == 'CUSTOM' else None
            proposal.chain_type = new_chain_type
            proposal.approval_chain = get_default_chain(new_chain_type, unit_id=unit_id, custom_roles=custom_roles)
        else:
            for idx, st in enumerate(proposal.approval_chain, start=1):
                st['status'] = 'PENDING' if idx == 1 else 'WAITING'

        proposal.status = 'UNDER_REVIEW'
        proposal.current_stage_index = 0
        proposal.revision_count += 1
        proposal.is_revision = True
        proposal.save()

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=f'Resubmission (Revision Cycle {proposal.revision_count})',
            action='APPROVED',
            remarks=request.POST.get('resubmission_notes', 'Addressed revision remarks and resubmitted to approval chain.'),
            revision_cycle=proposal.revision_count
        )

        messages.success(request, f"Proposal updated and re-routed to Stage 1 marked as 'Revision Cycle {proposal.revision_count}'.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    return render(request, 'events/proposal_form.html', {
        'proposal': proposal,
        'units': units,
        'is_edit': True,
        'latest_log': proposal.logs.first()
    })


@login_required
def proposal_detail_view(request, proposal_id):
    """
    Requirement 2: Displays registered students and attended students section
    for the organizer and reviewing authorities.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    is_approver = proposal.is_awaiting_user(request.user)
    is_proposer = (proposal.proposer == request.user)

    logs = proposal.logs.all().order_by('-created_at')
    logistics = proposal.logistics_notifications.all()

    chain = proposal.approval_chain or []
    current_index = proposal.current_stage_index

    stages = []
    for idx, st in enumerate(chain):
        step_num = idx + 1
        if proposal.status in ['APPROVED', 'APPROVED_PENDING_PUBLISH', 'COMPLETED']:
            status = 'CLEARED'
        elif proposal.status == 'UNDER_REVIEW':
            if idx < current_index:
                status = 'CLEARED'
            elif idx == current_index:
                status = 'CURRENT'
            else:
                status = 'WAITING'
        else:
            status = 'STOPPED' if idx == current_index else 'WAITING'

        stages.append({
            'step': step_num,
            'role': st.get('role'),
            'title': st.get('title'),
            'status': status,
        })

    # Requirement 2: Fetch student participation & attendance records
    all_registrations = proposal.registrations.all().select_related('student', 'student__profile', 'feedback').order_by('-registered_at')
    attended_students = [r for r in all_registrations if r.status in ['CHECKED_IN', 'VERIFIED']]
    verified_students = [r for r in all_registrations if r.status == 'VERIFIED']

    roster_stats = {
        'total_registered': len(all_registrations),
        'total_attended': len(attended_students),
        'total_verified': len(verified_students),
        'turnout_pct': round((len(attended_students) / len(all_registrations) * 100), 1) if all_registrations else 0,
    }

    context = {
        'proposal': proposal,
        'is_approver': is_approver,
        'is_proposer': is_proposer,
        'logs': logs,
        'logistics': logistics,
        'stages': stages,
        'current_stage_num': current_index + 1,
        'total_stages': len(chain),
        'user_role': getattr(request.user.profile, 'role', 'STUDENT') if hasattr(request.user, 'profile') else 'STUDENT',
        'all_registrations': all_registrations,
        'attended_students': attended_students,
        'roster_stats': roster_stats,
    }
    return render(request, 'events/proposal_detail.html', context)


@login_required
def process_approval_view(request, proposal_id):
    if request.method != 'POST':
        return redirect('proposal_detail', proposal_id=proposal_id)

    proposal = get_object_or_404(EventProposal, id=proposal_id)
    if not proposal.is_awaiting_user(request.user):
        messages.error(request, "You do not have authorization to approve at this stage.")
        return redirect('proposal_detail', proposal_id=proposal_id)

    action = request.POST.get('action')
    remarks = request.POST.get('remarks', '').strip()
    profile = request.user.profile

    if action in ['REJECT', 'REQUEST_REVISION'] and not remarks:
        messages.error(request, "Written remarks are mandatory when requesting a revision or rejecting.")
        return redirect('proposal_detail', proposal_id=proposal_id)

    chain = proposal.approval_chain or []
    current_idx = proposal.current_stage_index
    current_stage_dict = chain[current_idx] if current_idx < len(chain) else {}
    current_stage_title = current_stage_dict.get('title', f"Stage {current_idx + 1}")

    if action == 'APPROVE':
        current_stage_dict['status'] = 'APPROVED'
        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=current_stage_title,
            action='APPROVED',
            remarks=remarks or "Approved without additional stipulations.",
            revision_cycle=proposal.revision_count
        )

        next_idx = current_idx + 1
        if next_idx >= len(chain):
            proposal.status = 'APPROVED_PENDING_PUBLISH'
            proposal.current_stage_index = next_idx
            proposal.save()
            dispatch_logistics_notifications(proposal)
            messages.success(request, f"Executive clearance granted! '{proposal.title}' is approved and logistics sections have been notified. It is now ready for the Faculty Coordinator to upload a poster and publish.")
        else:
            chain[next_idx]['status'] = 'PENDING'
            proposal.current_stage_index = next_idx
            proposal.approval_chain = chain
            proposal.save()
            next_stage_title = chain[next_idx].get('title', f"Stage {next_idx + 1}")
            messages.success(request, f"Approved! Proposal advanced to Stage {next_idx + 1}: {next_stage_title}.")

    elif action == 'REVISE_BUDGET':
        if profile.role != 'DEAN_ACCOUNTS' and current_stage_dict.get('role') != 'DEAN_ACCOUNTS':
            messages.error(request, "Only the Dean of Finance & Accounts can revise budget allocations.")
            return redirect('proposal_detail', proposal_id=proposal_id)

        try:
            new_budget = float(request.POST.get('new_budget', 0))
        except ValueError:
            messages.error(request, "Invalid budget amount provided.")
            return redirect('proposal_detail', proposal_id=proposal_id)

        old_budget = proposal.approved_budget
        proposal.approved_budget = new_budget
        proposal.budget_revision_reason = remarks

        current_stage_dict['status'] = 'APPROVED'
        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=current_stage_title,
            action='BUDGET_REVISED',
            old_budget=old_budget,
            revised_budget=new_budget,
            remarks=remarks or f"Budget adjusted from ₹{old_budget} to ₹{new_budget}.",
            revision_cycle=proposal.revision_count
        )

        next_idx = current_idx + 1
        if next_idx >= len(chain):
            proposal.status = 'APPROVED_PENDING_PUBLISH'
            proposal.current_stage_index = next_idx
            proposal.save()
            dispatch_logistics_notifications(proposal)
        else:
            chain[next_idx]['status'] = 'PENDING'
            proposal.current_stage_index = next_idx
            proposal.approval_chain = chain
            proposal.save()

        messages.success(request, f"Budget revised to ₹{new_budget:,.2f}. Proposal advanced to next stage.")

    elif action == 'REQUEST_REVISION':
        current_stage_dict['status'] = 'REVISION_REQUESTED'
        proposal.status = 'REVISION_REQUESTED'
        proposal.approval_chain = chain
        proposal.save()

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=current_stage_title,
            action='REVISION_REQUESTED',
            remarks=remarks,
            revision_cycle=proposal.revision_count
        )
        messages.warning(request, f"Proposal returned for revision to {proposal.proposer.get_full_name() or proposal.proposer.username}.")

    elif action == 'REJECT':
        current_stage_dict['status'] = 'REJECTED'
        proposal.status = 'REJECTED'
        proposal.approval_chain = chain
        proposal.save()

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=current_stage_title,
            action='REJECTED',
            remarks=remarks,
            revision_cycle=proposal.revision_count
        )
        messages.error(request, f"Proposal '{proposal.title}' was rejected.")

    return redirect('proposal_detail', proposal_id=proposal_id)


# --- Faculty Poster Upload & Final Publish View ---

@login_required
def publish_event_view(request, proposal_id):
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    if proposal.proposer != request.user and not request.user.is_superuser:
        messages.error(request, "Only the designated event coordinator can publish this event.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    if proposal.status not in ['APPROVED_PENDING_PUBLISH', 'APPROVED']:
        messages.warning(request, "This proposal has not yet cleared all administrative approval stages.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    if request.method == 'POST':
        poster_file = request.FILES.get('poster_file')
        poster_preset = request.POST.get('poster_preset', '')

        if poster_file:
            proposal.poster_image = poster_file
        elif poster_preset:
            proposal.poster_data_uri = poster_preset

        proposal.status = 'APPROVED'
        proposal.published_at = timezone.now()
        proposal.save()

        messages.success(request, f"🎉 '{proposal.title}' is now officially published! The event is now live on the Student Campus Events portal for registrations.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    return render(request, 'events/publish_event.html', {'proposal': proposal})


# --- Requirement 4: General Event Description View for Students & Other Entities ---

@login_required
def event_public_detail_view(request, proposal_id):
    """
    Requirement 4: Dedicated public/campus description view of the event.
    - Students can register (one time only) as Participant, Volunteer, or Viewer.
    - Other entities (Faculty, HODs, Deans, Director) can view specifications only.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    
    # Check if student already registered
    user_registration = EventRegistration.objects.filter(event=proposal, student=request.user).first()
    is_student = hasattr(request.user, 'profile') and request.user.profile.role == 'STUDENT'
    is_organizer = (proposal.proposer == request.user)

    context = {
        'proposal': proposal,
        'user_registration': user_registration,
        'is_student': is_student,
        'is_organizer': is_organizer,
    }
    return render(request, 'events/event_public_detail.html', context)


# --- Student Facing Views ---

@login_required
def student_events_view(request):
    """Students and campus entities browse approved & published events."""
    published_events = EventProposal.objects.filter(status__in=['APPROVED', 'COMPLETED']).order_by('start_date')

    user_registrations = {}
    if hasattr(request.user, 'event_registrations'):
        for reg in request.user.event_registrations.all():
            user_registrations[reg.event_id] = reg

    context = {
        'events': published_events,
        'user_registrations': user_registrations,
    }
    return render(request, 'events/student_events.html', context)


@login_required
def event_register_view(request, proposal_id):
    """
    Requirement 1: Students can register in an event ONLY ONE TIME as any one of the roles.
    Re-registering or duplicate entries are strictly blocked.
    Other entities are barred from registering as students.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id, status__in=['APPROVED', 'COMPLETED'])
    
    # Role check: only students register
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'STUDENT':
        messages.error(request, "Only students can register for events. Faculty and institutional heads can view details.")
        return redirect('event_public_detail', proposal_id=proposal.id)

    if request.method == 'POST':
        # Check if already registered
        existing_reg = EventRegistration.objects.filter(event=proposal, student=request.user).first()
        if existing_reg:
            messages.warning(request, f"You are already registered for '{proposal.title}' as a {existing_reg.get_role_display()}. Only one registration per student is allowed.")
            return redirect('event_public_detail', proposal_id=proposal.id)

        role = request.POST.get('role', 'PARTICIPANT')
        if role not in ['PARTICIPANT', 'VOLUNTEER', 'VIEWER']:
            role = 'PARTICIPANT'

        EventRegistration.objects.create(
            event=proposal,
            student=request.user,
            role=role,
            status='REGISTERED'
        )
        messages.success(request, f"Registration confirmed! You have registered as a {role.capitalize()} for '{proposal.title}'.")
        return redirect('event_public_detail', proposal_id=proposal.id)

    return redirect('event_public_detail', proposal_id=proposal.id)


@login_required
def my_registrations_view(request):
    registrations = EventRegistration.objects.filter(student=request.user).order_by('-registered_at')
    return render(request, 'events/my_registrations.html', {'registrations': registrations})


# --- Requirement 3: Organizer-Only Live Rotating QR Screen ---

@login_required
def live_event_view(request, proposal_id):
    """
    Requirement 3: OTHER THAN THE ORGANIZER, NO ONE HAS ACCESS TO OPEN LIVE QR.
    Strictly checks that request.user == proposal.proposer.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)

    if proposal.proposer != request.user and not request.user.is_superuser:
        messages.error(request, f"Access Denied: Only the designated event coordinator ({proposal.proposer.get_full_name() or proposal.proposer.username}) is authorized to project the live attendance QR code.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    token, seconds_left = proposal.get_rotating_qr_token()
    checkin_url = request.build_absolute_uri(f"/events/checkin/?token={token}")
    qr_data_uri = generate_qr_base64(checkin_url)

    registrations = proposal.registrations.all().order_by('-checked_in_at')
    stats = {
        'total_registered': registrations.count(),
        'checked_in': registrations.filter(status__in=['CHECKED_IN', 'VERIFIED']).count(),
        'verified': registrations.filter(status='VERIFIED').count(),
    }

    context = {
        'proposal': proposal,
        'qr_data_uri': qr_data_uri,
        'checkin_url': checkin_url,
        'current_token': token,
        'seconds_left': seconds_left,
        'interval': proposal.ROTATION_INTERVAL,
        'registrations': registrations,
        'stats': stats,
    }
    return render(request, 'events/live_checkin.html', context)


@login_required
def rotating_qr_api_view(request, proposal_id):
    """
    Requirement 3: Only the organizer can poll the rotating QR token feed.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    if proposal.proposer != request.user and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized: Only event organizer can access rotating QR code feed'}, status=403)

    token, seconds_left = proposal.get_rotating_qr_token()
    checkin_url = request.build_absolute_uri(f"/events/checkin/?token={token}")
    qr_data_uri = generate_qr_base64(checkin_url)

    registrations = proposal.registrations.all()
    data = {
        'token': token,
        'seconds_left': seconds_left,
        'interval': proposal.ROTATION_INTERVAL,
        'qr_data_uri': qr_data_uri,
        'checkin_url': checkin_url,
        'total_registered': registrations.count(),
        'checked_in': registrations.filter(status__in=['CHECKED_IN', 'VERIFIED']).count(),
        'verified': registrations.filter(status='VERIFIED').count(),
    }
    return JsonResponse(data)


@login_required
def checkin_view(request):
    """
    Validates dynamic rotating QR token against expiration window.
    """
    token = request.GET.get('token') or request.POST.get('token') or ''
    proposal = None

    if token:
        base_token = token.split('_')[0] if '_' in token else token
        proposal = EventProposal.objects.filter(qr_checkin_token=base_token).first()

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        selfie_b64 = request.POST.get('selfie_image', '')

        base_token = token.split('_')[0] if '_' in token else token
        proposal = get_object_or_404(EventProposal, qr_checkin_token=base_token)

        is_valid, reason = proposal.validate_rotating_token(token)
        if not is_valid:
            messages.error(request, f"❌ {reason}")
            return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token, 'expired': True})

        reg, _ = EventRegistration.objects.get_or_create(
            event=proposal,
            student=request.user,
            defaults={'role': 'PARTICIPANT', 'status': 'REGISTERED'}
        )

        reg.status = 'CHECKED_IN'
        reg.checked_in_at = timezone.now()
        reg.selfie_image = selfie_b64
        reg.save()

        messages.success(request, f"Check-in verified via live selfie! Please complete the quick mandatory feedback below to verify your attendance.")
        return redirect('event_feedback', registration_id=reg.id)

    context = {
        'proposal': proposal,
        'token': token,
        'expired': False,
    }
    return render(request, 'events/checkin_selfie.html', context)


@login_required
def feedback_view(request, registration_id):
    reg = get_object_or_404(EventRegistration, id=registration_id, student=request.user)

    if hasattr(reg, 'feedback'):
        messages.info(request, "You have already completed feedback for this event.")
        return redirect('dashboard')

    if request.method == 'POST':
        rating_overall = int(request.POST.get('rating_overall', 5))
        rating_content = int(request.POST.get('rating_content', 5))
        rating_speaker = int(request.POST.get('rating_speaker', 5))
        comments = request.POST.get('comments', '')

        EventFeedback.objects.create(
            registration=reg,
            rating_overall=rating_overall,
            rating_content=rating_content,
            rating_speaker=rating_speaker,
            comments=comments
        )

        reg.status = 'VERIFIED'
        reg.save()

        messages.success(request, "Dhanyavaad! Feedback received and your event attendance has been officially VERIFIED.")
        return redirect('dashboard')

    return render(request, 'events/feedback.html', {'registration': reg})


# --- Compliance & Audit Reporting ---

@login_required
def compliance_report_view(request, proposal_id):
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    registrations = proposal.registrations.all()

    total_registered = registrations.count()
    total_checked_in = registrations.filter(status__in=['CHECKED_IN', 'VERIFIED']).count()
    total_verified = registrations.filter(status='VERIFIED').count()

    feedbacks = EventFeedback.objects.filter(registration__event=proposal)
    avg_ratings = feedbacks.aggregate(
        avg_overall=Avg('rating_overall'),
        avg_content=Avg('rating_content'),
        avg_speaker=Avg('rating_speaker'),
        total_count=Count('id')
    )

    budget_variance = proposal.approved_budget - proposal.requested_budget

    context = {
        'proposal': proposal,
        'registrations': registrations,
        'feedbacks': feedbacks,
        'stats': {
            'total_registered': total_registered,
            'total_checked_in': total_checked_in,
            'total_verified': total_verified,
            'attendance_rate': round((total_verified / total_registered * 100), 1) if total_registered > 0 else 0,
            'budget_variance': budget_variance,
            'avg_overall': round(avg_ratings['avg_overall'] or 0, 1),
            'avg_content': round(avg_ratings['avg_content'] or 0, 1),
            'avg_speaker': round(avg_ratings['avg_speaker'] or 0, 1),
            'feedback_count': avg_ratings['total_count'],
        },
        'logistics': proposal.logistics_notifications.all(),
        'approval_logs': proposal.logs.all().order_by('created_at'),
    }
    return render(request, 'events/compliance_report.html', context)


# --- Superadmin User & Entity Database Manager ---

@login_required
def superadmin_users_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Access restricted to Superadministrator.")
        return redirect('dashboard')

    users = User.objects.all().select_related('profile').order_by('profile__role', 'username')
    return render(request, 'events/superadmin_users.html', {'managed_users': users})
