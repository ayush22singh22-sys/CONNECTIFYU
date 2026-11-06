import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.http import JsonResponse, HttpResponseForbidden

from .models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification
)
from .utils import generate_qr_base64, dispatch_logistics_notifications


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
    """Demo feature: seamlessly switch to any role for presentation demos."""
    user = get_object_or_404(User, username=username)
    login(request, user)
    role_name = user.profile.get_role_display() if hasattr(user, 'profile') else 'User'
    messages.info(request, f"Switched active identity to: {user.get_full_name() or user.username} ({role_name})")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


def register_student_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        roll_no = request.POST.get('roll_no')
        department = request.POST.get('department')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, 'registration/register.html')

        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password
        )
        UserProfile.objects.create(
            user=user,
            role='STUDENT',
            department=department,
            roll_or_emp_id=roll_no
        )
        login(request, user)
        messages.success(request, "Student registration successful! Welcome to CEMS.")
        return redirect('dashboard')

    return render(request, 'registration/register.html')


@login_required
def dashboard_view(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else 'STUDENT'

    if role == 'STUDENT':
        return redirect('student_events')

    # For Faculty / Proposers
    my_proposals = EventProposal.objects.filter(proposer=user).order_by('-created_at')

    # For Approvers
    pending_approvals = []
    if role == 'HOD':
        pending_approvals = EventProposal.objects.filter(
            status='STAGE_1_UNIT_HEAD',
            organizing_unit__unit_type='DEPARTMENT'
        ).order_by('-updated_at')
    elif role == 'CLUB_HEAD':
        pending_approvals = EventProposal.objects.filter(
            status='STAGE_1_UNIT_HEAD',
            organizing_unit__unit_type='CLUB'
        ).order_by('-updated_at')
    elif role == 'HR':
        pending_approvals = EventProposal.objects.filter(status='STAGE_2_HR').order_by('-updated_at')
    elif role == 'DEAN_RESEARCH':
        pending_approvals = EventProposal.objects.filter(status='STAGE_3_DEAN_RESEARCH').order_by('-updated_at')
    elif role == 'DEAN_ACCOUNTS':
        pending_approvals = EventProposal.objects.filter(status='STAGE_4_DEAN_ACCOUNTS').order_by('-updated_at')
    elif role == 'DEAN_ACADEMICS':
        pending_approvals = EventProposal.objects.filter(status='STAGE_5_DEAN_ACADEMICS').order_by('-updated_at')

    # All approved events across campus
    all_approved = EventProposal.objects.filter(status__in=['APPROVED', 'COMPLETED']).order_by('-start_date')[:6]

    context = {
        'role': role,
        'profile': profile,
        'my_proposals': my_proposals,
        'pending_approvals': pending_approvals,
        'all_approved': all_approved,
        'stats': {
            'total_proposals': EventProposal.objects.count(),
            'approved_count': EventProposal.objects.filter(status='APPROVED').count(),
            'revision_count': EventProposal.objects.filter(status='REVISION_REQUESTED').count(),
            'total_students': UserProfile.objects.filter(role='STUDENT').count(),
        }
    }
    return render(request, 'events/dashboard.html', context)


@login_required
def create_proposal_view(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role not in ['FACULTY', 'CLUB_HEAD', 'HOD', 'ADMIN', 'DEAN_ACADEMICS']:
        messages.error(request, "Only faculty and club heads can submit new event proposals.")
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
        expected_attendees = request.POST.get('expected_attendees', 50)

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
            mess_requirements=mess_req,
            transport_requirements=transport_req,
            maintenance_requirements=maint_req,
            status='STAGE_1_UNIT_HEAD'
        )

        messages.success(request, f"Event proposal '{proposal.title}' submitted! Routed to Stage 1: {unit.get_unit_type_display()} Head.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    return render(request, 'events/proposal_form.html', {'units': units, 'is_edit': False})


@login_required
def edit_proposal_view(request, proposal_id):
    """Allows proposer to fix remarks and resubmit proposal through the full chain."""
    proposal = get_object_or_404(EventProposal, id=proposal_id, proposer=request.user)
    if proposal.status != 'REVISION_REQUESTED':
        messages.warning(request, "This proposal is not currently in revision status.")
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
        proposal.expected_attendees = request.POST.get('expected_attendees', 50)
        proposal.mess_requirements = request.POST.get('mess_requirements', '')
        proposal.transport_requirements = request.POST.get('transport_requirements', '')
        proposal.maintenance_requirements = request.POST.get('maintenance_requirements', '')

        # Resubmit into Stage 1 with Revision badge
        proposal.status = 'STAGE_1_UNIT_HEAD'
        proposal.revision_count += 1
        proposal.is_revision = True
        proposal.save()

        # Log resubmission
        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=f'Resubmission (Cycle {proposal.revision_count})',
            action='APPROVED',
            remarks=request.POST.get('resubmission_notes', 'Addressed revision remarks and resubmitted to approval chain.'),
            revision_cycle=proposal.revision_count
        )

        messages.success(request, f"Proposal updated and re-routed to Stage 1 with 'Revision Cycle {proposal.revision_count}' tag.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    return render(request, 'events/proposal_form.html', {
        'proposal': proposal,
        'units': units,
        'is_edit': True,
        'latest_log': proposal.logs.first()
    })


@login_required
def proposal_detail_view(request, proposal_id):
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    is_approver = proposal.is_awaiting_user(request.user)
    is_proposer = (proposal.proposer == request.user)

    logs = proposal.logs.all().order_by('-created_at')
    logistics = proposal.logistics_notifications.all()

    # Stages definition for visual progress tracker
    stages = [
        {'id': 1, 'code': 'STAGE_1_UNIT_HEAD', 'title': 'Unit Head (HOD / Club)', 'approver_role': 'HOD/Club Head'},
        {'id': 2, 'code': 'STAGE_2_HR', 'title': 'Human Resources (HR)', 'approver_role': 'HR Review'},
        {'id': 3, 'code': 'STAGE_3_DEAN_RESEARCH', 'title': 'Dean of Research', 'approver_role': 'Academic Vetting'},
        {'id': 4, 'code': 'STAGE_4_DEAN_ACCOUNTS', 'title': 'Dean of Accounts', 'approver_role': 'Budget Sanction'},
        {'id': 5, 'code': 'STAGE_5_DEAN_ACADEMICS', 'title': 'Dean Academics / Director', 'approver_role': 'Executive Clearance'},
    ]

    current_stage_num = proposal.stage_number

    context = {
        'proposal': proposal,
        'is_approver': is_approver,
        'is_proposer': is_proposer,
        'logs': logs,
        'logistics': logistics,
        'stages': stages,
        'current_stage_num': current_stage_num,
        'user_role': getattr(request.user.profile, 'role', 'STUDENT') if hasattr(request.user, 'profile') else 'STUDENT',
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
        messages.error(request, "Written remarks are mandatory when rejecting or requesting a revision.")
        return redirect('proposal_detail', proposal_id=proposal_id)

    current_status = proposal.status

    if action == 'APPROVE':
        stage_names = {
            'STAGE_1_UNIT_HEAD': 'Stage 1: Organizing Unit Head',
            'STAGE_2_HR': 'Stage 2: HR Review',
            'STAGE_3_DEAN_RESEARCH': 'Stage 3: Dean of Research',
            'STAGE_4_DEAN_ACCOUNTS': 'Stage 4: Dean of Accounts',
            'STAGE_5_DEAN_ACADEMICS': 'Stage 5: Dean of Academics / Director',
        }
        next_status_map = {
            'STAGE_1_UNIT_HEAD': 'STAGE_2_HR',
            'STAGE_2_HR': 'STAGE_3_DEAN_RESEARCH',
            'STAGE_3_DEAN_RESEARCH': 'STAGE_4_DEAN_ACCOUNTS',
            'STAGE_4_DEAN_ACCOUNTS': 'STAGE_5_DEAN_ACADEMICS',
            'STAGE_5_DEAN_ACADEMICS': 'APPROVED',
        }

        next_status = next_status_map[current_status]
        proposal.status = next_status

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=stage_names[current_status],
            action='APPROVED',
            remarks=remarks or "Approved without additional conditions.",
            revision_cycle=proposal.revision_count
        )

        # If cleared Stage 5, automatically dispatch logistics emails & publish!
        if next_status == 'APPROVED':
            dispatch_logistics_notifications(proposal)
            messages.success(request, f"Proposal '{proposal.title}' cleared all 5 stages! Logistics automatically notified and event is now published to students.")
        else:
            messages.success(request, f"Proposal approved! Advanced to {proposal.get_status_display()}.")

        proposal.save()

    elif action == 'REVISE_BUDGET':
        if profile.role != 'DEAN_ACCOUNTS' and current_status != 'STAGE_4_DEAN_ACCOUNTS':
            messages.error(request, "Only the Dean of Accounts can revise budget allocations.")
            return redirect('proposal_detail', proposal_id=proposal_id)

        try:
            new_budget = float(request.POST.get('new_budget', 0))
        except ValueError:
            messages.error(request, "Invalid budget number provided.")
            return redirect('proposal_detail', proposal_id=proposal_id)

        old_budget = proposal.approved_budget
        proposal.approved_budget = new_budget
        proposal.budget_revision_reason = remarks
        proposal.status = 'STAGE_5_DEAN_ACADEMICS'
        proposal.save()

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name='Stage 4: Dean of Accounts',
            action='BUDGET_REVISED',
            old_budget=old_budget,
            revised_budget=new_budget,
            remarks=remarks or f"Budget adjusted from ${old_budget} to ${new_budget}.",
            revision_cycle=proposal.revision_count
        )
        messages.success(request, f"Budget revised to ${new_budget}. Proposal routed to Stage 5: Dean of Academics.")

    elif action == 'REQUEST_REVISION':
        proposal.status = 'REVISION_REQUESTED'
        proposal.save()

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=proposal.get_status_display(),
            action='REVISION_REQUESTED',
            remarks=remarks,
            revision_cycle=proposal.revision_count
        )
        messages.warning(request, f"Proposal sent back for revision to {proposal.proposer.get_full_name() or proposal.proposer.username}.")

    elif action == 'REJECT':
        proposal.status = 'REJECTED'
        proposal.save()

        ApprovalLog.objects.create(
            proposal=proposal,
            approver=request.user,
            stage_name=proposal.get_status_display(),
            action='REJECTED',
            remarks=remarks,
            revision_cycle=proposal.revision_count
        )
        messages.error(request, f"Proposal '{proposal.title}' was rejected.")

    return redirect('proposal_detail', proposal_id=proposal_id)


# --- Student Facing Views ---

@login_required
def student_events_view(request):
    """Students browse approved events and register."""
    published_events = EventProposal.objects.filter(status__in=['APPROVED', 'COMPLETED']).order_by('start_date')
    
    # Check registration status for current student
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
    proposal = get_object_or_404(EventProposal, id=proposal_id, status__in=['APPROVED', 'COMPLETED'])
    if request.method == 'POST':
        role = request.POST.get('role', 'PARTICIPANT')
        reg, created = EventRegistration.objects.get_or_create(
            event=proposal,
            student=request.user,
            defaults={'role': role, 'status': 'REGISTERED'}
        )
        if not created:
            reg.role = role
            reg.save()
            messages.info(request, f"Your registration role for '{proposal.title}' was updated to {reg.get_role_display()}.")
        else:
            messages.success(request, f"Successfully registered for '{proposal.title}' as {reg.get_role_display()}!")
        return redirect('my_registrations')

    return redirect('student_events')


@login_required
def my_registrations_view(request):
    registrations = EventRegistration.objects.filter(student=request.user).order_by('-registered_at')
    return render(request, 'events/my_registrations.html', {'registrations': registrations})


# --- Live Presentation & QR / Selfie Check-In ---

@login_required
def live_event_view(request, proposal_id):
    """Faculty / Organizer screen to project QR code on auditorium screen."""
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    
    # Base URL for check-in
    checkin_url = request.build_absolute_uri(f"/events/checkin/?token={proposal.qr_checkin_token}")
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
        'registrations': registrations,
        'stats': stats,
    }
    return render(request, 'events/live_checkin.html', context)


@login_required
def checkin_view(request):
    """
    Step 7 in lifecycle:
    Student scans projected QR code on phone, immediately followed by
    front-camera selfie to prevent attendance proxy fraud.
    """
    token = request.GET.get('token') or request.POST.get('token')
    proposal = None
    if token:
        proposal = EventProposal.objects.filter(qr_checkin_token=token).first()

    if request.method == 'POST':
        token = request.POST.get('token')
        selfie_b64 = request.POST.get('selfie_image', '')
        proposal = get_object_or_404(EventProposal, qr_checkin_token=token)

        # Get or auto-register student
        reg, _ = EventRegistration.objects.get_or_create(
            event=proposal,
            student=request.user,
            defaults={'role': 'PARTICIPANT', 'status': 'REGISTERED'}
        )

        reg.status = 'CHECKED_IN'
        reg.checked_in_at = timezone.now()
        reg.selfie_image = selfie_b64
        reg.save()

        messages.success(request, f"Check-in verified via selfie! Please complete the quick mandatory feedback below to finalize your attendance.")
        return redirect('event_feedback', registration_id=reg.id)

    context = {
        'proposal': proposal,
        'token': token or '',
    }
    return render(request, 'events/checkin_selfie.html', context)


@login_required
def feedback_view(request, registration_id):
    """
    Step 8 in lifecycle:
    Attendance is only marked 'VERIFIED' once student submits feedback!
    Guarantees 100% feedback collection.
    """
    reg = get_object_or_404(EventRegistration, id=registration_id, student=request.user)

    if hasattr(reg, 'feedback'):
        messages.info(request, "You have already completed feedback for this event.")
        return redirect('my_registrations')

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

        # Transition to fully VERIFIED attendance!
        reg.status = 'VERIFIED'
        reg.save()

        messages.success(request, "Feedback received! Your official event attendance has been VERIFIED.")
        return redirect('my_registrations')

    return render(request, 'events/feedback.html', {'registration': reg})


# --- Compliance & Audit Reporting ---

@login_required
def compliance_report_view(request, proposal_id):
    """
    Step 9 in lifecycle:
    System automatically compiles compliance report combining final budget,
    actual verified attendance, and student feedback ratings.
    """
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
            'avg_content': round(avg_content := avg_ratings['avg_content'] or 0, 1),
            'avg_speaker': round(avg_ratings['avg_speaker'] or 0, 1),
            'feedback_count': avg_ratings['total_count'],
        },
        'logistics': proposal.logistics_notifications.all(),
        'approval_logs': proposal.logs.all().order_by('created_at'),
    }
    return render(request, 'events/compliance_report.html', context)
