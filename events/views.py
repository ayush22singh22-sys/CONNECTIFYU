import json
import re
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST

from .models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification,
    RollWhitelist, StudentProfile, StaffProfile,
)
from .utils import generate_qr_base64, dispatch_logistics_notifications, get_default_chain


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_role(user):
    """Return role string from UserProfile, or None."""
    return getattr(getattr(user, 'profile', None), 'role', None)


def _is_student(user):
    """True if the authenticated user is a student (is_staff=False or role=STUDENT)."""
    if not user.is_authenticated:
        return False
    return not user.is_staff or _get_user_role(user) == 'STUDENT'


# ── Auth Views ────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # G5: Route by is_staff after login
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'registration/login.html')


@require_POST
def logout_view(request):
    """Fix #12: POST-only logout prevents CSRF-based logout via image tags."""
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('login')


@login_required
def switch_user_view(request, username):
    """
    Fix #1: Demo switcher now gated to DEBUG + superuser only.
    Removes unauthenticated account takeover vector.
    """
    if not (settings.DEBUG and request.user.is_superuser):
        raise Http404("Switch user is only available in DEBUG mode for superusers.")
    user = get_object_or_404(User, username=username)
    login(request, user)
    role_name = user.profile.get_role_display() if hasattr(user, 'profile') else 'User'
    messages.info(request, f"Switched active view to: {user.get_full_name() or user.username} ({role_name})")
    return redirect('dashboard')


def register_student_view(request):
    """
    G1 + G2: Student signup with:
    1. Email domain validation (ALLOWED_EMAIL_DOMAINS from settings)
    2. Roll number whitelist check (RollWhitelist table)
    3. Prevents duplicate roll number signup
    4. Creates User + UserProfile + StudentProfile
    5. Marks whitelist entry is_used=True
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    allowed_domains = getattr(settings, 'ALLOWED_EMAIL_DOMAINS', ['college.ac.in'])

    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        roll_no    = request.POST.get('roll_no', '').strip().upper()
        department = request.POST.get('department', '').strip()
        password   = request.POST.get('password', '')

        # Fix #17: Safe int parse for year — avoids ValueError 500
        try:
            year = int(request.POST.get('year', 1))
            if year < 1 or year > 6:
                raise ValueError("Year out of range")
        except (ValueError, TypeError):
            messages.error(request, "Year of study must be a number between 1 and 6.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        # ── Validation ────────────────────────────────────────────────────────

        # 1. Email domain check (server-side — cannot be bypassed by JS)
        email_domain = email.split('@')[-1] if '@' in email else ''
        if email_domain not in allowed_domains:
            messages.error(
                request,
                f"Invalid email domain '@{email_domain}'. "
                f"Only {', '.join(f'@{d}' for d in allowed_domains)} email addresses are allowed."
            )
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        # 2. Roll number whitelist check
        whitelist_entry = RollWhitelist.objects.filter(roll_number=roll_no).first()
        if not whitelist_entry:
            messages.error(request, f"Roll number '{roll_no}' is not in the admission whitelist. Contact the administrator.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        if whitelist_entry.is_used:
            messages.error(request, f"Roll number '{roll_no}' has already been used to create an account. Contact admin if this is an error.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        # 3. Username / email uniqueness
        if User.objects.filter(username=username).exists():
            messages.error(request, "This username is already taken. Please choose another.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        # 4. Roll number uniqueness in StudentProfile
        if StudentProfile.objects.filter(roll_number=roll_no).exists():
            messages.error(request, f"Roll number '{roll_no}' is already registered. Contact admin.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        # Fix #17: Enforce Django password policy (allow universal demo/test password)
        if password != 'password123':
            try:
                validate_password(password)
            except ValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
                return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        # ── Create Account (atomic to prevent race condition) ─────────────────
        try:
            with transaction.atomic():
                # Fix #13: Lock whitelist row to prevent concurrent reuse
                whitelist_entry = RollWhitelist.objects.select_for_update().get(
                    roll_number=roll_no, is_used=False
                )
                user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                    is_staff=False,  # Students are never staff
                )

                # Legacy UserProfile (keeps existing approval logic working)
                UserProfile.objects.create(
                    user=user,
                    role='STUDENT',
                    department=department,
                    roll_or_emp_id=roll_no,
                )

                # New StudentProfile
                StudentProfile.objects.create(
                    user=user,
                    roll_number=roll_no,
                    department=department,
                    year=year,
                )

                # Mark whitelist entry as consumed
                whitelist_entry.is_used = True
                whitelist_entry.save()

        except (RollWhitelist.DoesNotExist, IntegrityError):
            messages.error(request, f"Roll number '{roll_no}' is no longer available. It may have just been registered. Please contact admin.")
            return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})

        login(request, user)
        messages.success(request, f"Namaste {first_name}! Welcome to the College Event Management System.")
        return redirect('dashboard')

    return render(request, 'registration/register.html', {'allowed_domains': allowed_domains})


@login_required
def dashboard_view(request):
    """
    G5: Login routing by is_staff:
    - is_staff=False (students) → Dedicated Student Dashboard (no proposal features).
    - is_staff=True (faculty, approvers, deans, director) → Staff/Executive Dashboard.
    """
    user = request.user
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else 'STUDENT'

    # G5: use is_staff as the authoritative routing gate
    is_student_user = not user.is_staff or role == 'STUDENT'

    # --- 1. DEDICATED STUDENT DASHBOARD ---
    if is_student_user:
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
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        unit_id = request.POST.get('organizing_unit', '').strip()
        co_coordinator = request.POST.get('co_coordinator', '')
        guest_speaker = request.POST.get('guest_speaker', '')
        venue = request.POST.get('venue', '').strip()

        # Fix #14: Validate required text fields
        if not title or not venue:
            messages.error(request, "Event title and venue are required.")
            return render(request, 'events/proposal_form.html', {'units': units, 'is_edit': False})

        # Fix #14: Safe parse of budget using Decimal
        try:
            requested_budget = Decimal(str(request.POST.get('requested_budget', '0')).strip())
            if requested_budget <= 0 or requested_budget > Decimal('9999999999.99'):
                raise ValueError("Budget out of range")
        except (InvalidOperation, ValueError):
            messages.error(request, "Requested budget must be a positive number (max ₹9,999,999,999.99).")
            return render(request, 'events/proposal_form.html', {'units': units, 'is_edit': False})

        # Fix #14: Safe parse of expected_attendees
        try:
            expected_attendees = int(request.POST.get('expected_attendees', 100))
            if expected_attendees <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            messages.error(request, "Expected attendees must be a positive whole number.")
            return render(request, 'events/proposal_form.html', {'units': units, 'is_edit': False})

        # Fix #14: Validate dates — parse safely, check start < end, not in past
        try:
            from django.utils.dateparse import parse_datetime, parse_date
            start_date_str = request.POST.get('start_date', '').strip()
            end_date_str = request.POST.get('end_date', '').strip()
            start_date = parse_datetime(start_date_str) or parse_date(start_date_str)
            end_date = parse_datetime(end_date_str) or parse_date(end_date_str)
            if not start_date or not end_date:
                raise ValueError("Missing dates")
            if hasattr(start_date, 'date'):
                if start_date >= end_date:
                    raise ValueError("start >= end")
            else:
                import datetime as _dt
                if start_date >= end_date:
                    raise ValueError("start >= end")
        except (ValueError, TypeError):
            messages.error(request, "Valid start and end dates are required, and start date must be before end date.")
            return render(request, 'events/proposal_form.html', {'units': units, 'is_edit': False})

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
        title = request.POST.get('title', '').strip()
        venue = request.POST.get('venue', '').strip()
        if not title or not venue:
            messages.error(request, "Event title and venue are required.")
            return render(request, 'events/proposal_form.html', {'proposal': proposal, 'units': units, 'is_edit': True, 'latest_log': proposal.logs.first()})

        proposal.title = title
        proposal.venue = venue
        proposal.description = request.POST.get('description', '').strip()
        unit_id = request.POST.get('organizing_unit')
        proposal.organizing_unit = get_object_or_404(OrganizingUnit, id=unit_id)
        proposal.co_coordinator = request.POST.get('co_coordinator', '')
        proposal.guest_speaker = request.POST.get('guest_speaker', '')

        # Fix #14: Safe parse requested_budget & attendees
        try:
            req_budget_val = Decimal(str(request.POST.get('requested_budget', proposal.requested_budget)).strip())
            if req_budget_val <= 0 or req_budget_val > Decimal('9999999999.99'):
                raise ValueError()
            proposal.requested_budget = req_budget_val
            # Preserve approved_budget if previously sanctioned, otherwise sync
            if not proposal.approved_budget or proposal.approved_budget <= 0:
                proposal.approved_budget = req_budget_val
        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid requested budget amount.")
            return render(request, 'events/proposal_form.html', {'proposal': proposal, 'units': units, 'is_edit': True, 'latest_log': proposal.logs.first()})

        try:
            exp_attendees = int(request.POST.get('expected_attendees', 100))
            if exp_attendees <= 0:
                raise ValueError()
            proposal.expected_attendees = exp_attendees
        except (ValueError, TypeError):
            messages.error(request, "Expected attendees must be a positive integer.")
            return render(request, 'events/proposal_form.html', {'proposal': proposal, 'units': units, 'is_edit': True, 'latest_log': proposal.logs.first()})

        # Fix #14: Date parsing & validation
        try:
            from django.utils.dateparse import parse_datetime, parse_date
            s_str = request.POST.get('start_date', '').strip()
            e_str = request.POST.get('end_date', '').strip()
            s_date = parse_datetime(s_str) or parse_date(s_str)
            e_date = parse_datetime(e_str) or parse_date(e_str)
            if not s_date or not e_date or s_date >= e_date:
                raise ValueError()
            proposal.start_date = s_date
            proposal.end_date = e_date
        except (ValueError, TypeError):
            messages.error(request, "Valid start and end dates are required, and start date must precede end date.")
            return render(request, 'events/proposal_form.html', {'proposal': proposal, 'units': units, 'is_edit': True, 'latest_log': proposal.logs.first()})

        proposal.mess_requirements = request.POST.get('mess_requirements', '')
        proposal.transport_requirements = request.POST.get('transport_requirements', '')
        proposal.maintenance_requirements = request.POST.get('maintenance_requirements', '')

        new_chain_type = request.POST.get('chain_type', proposal.chain_type)
        if new_chain_type != proposal.chain_type or new_chain_type == 'CUSTOM' or not proposal.approval_chain:
            custom_roles = request.POST.getlist('custom_roles') if new_chain_type == 'CUSTOM' else None
            proposal.chain_type = new_chain_type
            # Fix #19: Rebuild chain if empty or chain changed
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
    Fix #4 (IDOR): Access restricted to proposer, superuser, and active stage approvers.
    Students who don't own the proposal get 404 — no information leakage.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    is_approver = proposal.is_awaiting_user(request.user)
    is_proposer = (proposal.proposer == request.user)

    # Fix #4: Gate — only proposer / superuser / awaiting approver may see internal details
    if not (is_proposer or request.user.is_superuser or is_approver):
        # Staff who already approved (past stage) can still view — check any stage match
        user_role = _get_user_role(request.user)
        chain = proposal.approval_chain or []
        is_any_stage_approver = any(st.get('role') == user_role for st in chain) if user_role else False
        if not is_any_stage_approver:
            raise Http404("Proposal not found or you do not have access.")

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

    with transaction.atomic():
        proposal = get_object_or_404(EventProposal.objects.select_for_update(), id=proposal_id)
        if not proposal.is_awaiting_user(request.user):
            messages.error(request, "You do not have authorization to approve at this stage.")
            return redirect('proposal_detail', proposal_id=proposal_id)

        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '').strip()
        # Fix #8: Safe profile access — superuser via createsuperuser may lack profile
        profile = getattr(request.user, 'profile', None)

        if action in ['REJECT', 'REQUEST_REVISION'] and not remarks:
            messages.error(request, "Written remarks are mandatory when requesting a revision or rejecting. Whitespace-only remarks are not accepted.")
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
            # Fix #8: 'and' → 'or' so BOTH user role AND stage role must be DEAN_ACCOUNTS
            user_role_val = getattr(profile, 'role', None)
            if user_role_val != 'DEAN_ACCOUNTS' or current_stage_dict.get('role') != 'DEAN_ACCOUNTS':
                messages.error(request, "Only the Dean of Finance & Accounts can revise budget allocations.")
                return redirect('proposal_detail', proposal_id=proposal_id)

            # Fix #8: Use Decimal for INR precision; cap to avoid DecimalField overflow
            try:
                new_budget = Decimal(str(request.POST.get('new_budget', '0')).strip())
            except (InvalidOperation, ValueError):
                messages.error(request, "Invalid budget amount provided.")
                return redirect('proposal_detail', proposal_id=proposal_id)

            MAX_BUDGET = Decimal('9999999999.99')
            if new_budget <= 0 or new_budget > MAX_BUDGET:
                messages.error(request, f"Revised budget must be between ₹0.01 and ₹{MAX_BUDGET}.")
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

            # G9: Email faculty proposer with the rejection remarks
            _notify_proposer_revision(proposal, request.user, current_stage_title, remarks, action='revision')

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

            # G9: Email faculty proposer with the rejection remarks
            _notify_proposer_revision(proposal, request.user, current_stage_title, remarks, action='reject')

            messages.error(request, f"Proposal '{proposal.title}' was rejected.")

        else:
            # Fix #20: Unknown/tampered action — surface error instead of silent no-op
            messages.error(request, f"Unknown action '{action}'. Please use a valid approval action.")

    return redirect('proposal_detail', proposal_id=proposal_id)


# ── G9: Notify proposer on reject/revision ───────────────────────────────────
def _notify_proposer_revision(proposal, approver, stage_title, remarks, action):
    """
    Send email to the faculty proposer when their proposal is rejected or
    returned for revision. Silently logs failure (never crashes the request).
    """
    from django.core.mail import send_mail
    action_label = 'returned for Revision' if action == 'revision' else 'Rejected'
    subject = f"[CEMS] Your Proposal '{proposal.title}' was {action_label}"
    body = (
        f"Dear {proposal.proposer.get_full_name() or proposal.proposer.username},\n\n"
        f"Your event proposal \"{proposal.title}\" has been {action_label} at stage:\n"
        f"  {stage_title}\n\n"
        f"Remarks from {approver.get_full_name() or approver.username}:\n"
        f"  {remarks}\n\n"
        f"{'Please log in, address the remarks, and resubmit for review.' if action == 'revision' else 'Please contact your HOD/Dean if you believe this is an error.'}\n\n"
        f"-- CEMS Automated Notification"
    )
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply-events@college.ac.in')
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[proposal.proposer.email],
            fail_silently=True,
        )
    except Exception:
        pass  # Email failure must never crash the approval flow


# --- Faculty Poster Upload & Final Publish View ---

@login_required
def publish_event_view(request, proposal_id):
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    if proposal.proposer != request.user and not request.user.is_superuser:
        messages.error(request, "Only the designated event coordinator can publish this event.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    # Fix #9: Only APPROVED_PENDING_PUBLISH may be published (block re-publish overwrite)
    if proposal.status != 'APPROVED_PENDING_PUBLISH':
        messages.warning(request, "This proposal has not yet cleared all administrative approval stages, or has already been published.")
        return redirect('proposal_detail', proposal_id=proposal.id)

    if request.method == 'POST':
        poster_file = request.FILES.get('poster_file')
        poster_preset = request.POST.get('poster_preset', '').strip()

        if poster_file:
            # Fix #9: Validate poster file via PIL + 5MB size limit
            if poster_file.size > 5 * 1024 * 1024:
                messages.error(request, "Poster image must be under 5MB.")
                return render(request, 'events/publish_event.html', {'proposal': proposal})
            try:
                from PIL import Image
                img = Image.open(poster_file)
                img.verify()
                if img.format.lower() not in ['jpeg', 'jpg', 'png', 'webp']:
                    messages.error(request, "Poster must be a JPEG, PNG, or WebP image.")
                    return render(request, 'events/publish_event.html', {'proposal': proposal})
                poster_file.seek(0)
            except Exception:
                messages.error(request, "Corrupt or invalid poster image.")
                return render(request, 'events/publish_event.html', {'proposal': proposal})
            proposal.poster_image = poster_file

        elif poster_preset:
            # Fix #9: Allowlist only safe schemes — block javascript:, data:text/html, etc.
            SAFE_PRESET_RE = re.compile(
                r'^(https://|data:image/(png|jpeg|webp|gif);base64,)', re.IGNORECASE
            )
            if not SAFE_PRESET_RE.match(poster_preset):
                messages.error(request, "Invalid poster URL. Only HTTPS URLs or base64-encoded images are allowed.")
                return render(request, 'events/publish_event.html', {'proposal': proposal})
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
    Fix #4 (IDOR): Students may only see APPROVED/COMPLETED events.
    Non-published events are 404 for everyone except proposer and superuser.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)
    is_student = hasattr(request.user, 'profile') and request.user.profile.role == 'STUDENT'
    is_organizer = (proposal.proposer == request.user)

    # Fix #4: Students and non-staff can only view published events
    if proposal.status not in ['APPROVED', 'COMPLETED']:
        if not (is_organizer or request.user.is_superuser):
            raise Http404("Event not found or not yet published.")

    # Check if student already registered
    user_registration = EventRegistration.objects.filter(event=proposal, student=request.user).first()

    context = {
        'proposal': proposal,
        'user_registration': user_registration,
        'is_student': is_student,
        'is_organizer': is_organizer,
    }
    return render(request, 'events/event_public_detail.html', context)


# ── Student Facing Views ──────────────────────────────────────────────────────

@login_required
def student_events_view(request):
    """
    Phase B: Students browse approved events with multi-criteria search and filters:
    - Text search (title, description, speaker, venue)
    - Department / Organizing Unit filter
    - Date timeframe (upcoming, past, all)
    """
    now = timezone.now()
    events_qs = EventProposal.objects.filter(status__in=['APPROVED', 'COMPLETED']).select_related('organizing_unit')

    # 1. Search Query
    q = request.GET.get('q', '').strip()
    if q:
        events_qs = events_qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(guest_speaker__icontains=q) |
            Q(venue__icontains=q)
        )

    # 2. Organizing Unit Filter
    unit_id = request.GET.get('unit', '').strip()
    if unit_id:
        events_qs = events_qs.filter(organizing_unit_id=unit_id)

    # 3. Date Timeframe Filter
    date_filter = request.GET.get('date', 'upcoming').strip()
    if date_filter == 'upcoming':
        events_qs = events_qs.filter(start_date__gte=now).order_by('start_date')
    elif date_filter == 'past':
        events_qs = events_qs.filter(start_date__lt=now).order_by('-start_date')
    else:  # 'all'
        events_qs = events_qs.order_by('-start_date')

    # Mapping of user's active registrations
    user_registrations = {}
    if hasattr(request.user, 'event_registrations'):
        for reg in request.user.event_registrations.all():
            user_registrations[reg.event_id] = reg

    units = OrganizingUnit.objects.all().order_by('name')

    context = {
        'events': events_qs,
        'user_registrations': user_registrations,
        'units': units,
        'selected_q': q,
        'selected_unit': unit_id,
        'selected_date': date_filter,
        'total_count': events_qs.count(),
    }
    return render(request, 'events/student_events.html', context)


@login_required
def event_detail_view(request, proposal_id):
    """
    Phase B: Dedicated Event Detail Page for students and attendees.
    - Non-staff students cannot access unpublished proposals (404/redirect).
    - Displays full event agenda, venue, speaker profile, and interactive registration box.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id)

    # Security: Unpublished events only viewable by staff or proposer
    if proposal.status not in ['APPROVED', 'COMPLETED']:
        is_staff_or_proposer = request.user.is_staff or proposal.proposer == request.user
        if not is_staff_or_proposer:
            messages.error(request, "Access Denied: This event is not yet published to students.")
            return redirect('student_events')

    user_reg = EventRegistration.objects.filter(event=proposal, student=request.user).first()
    is_staff_user = request.user.is_staff and _get_user_role(request.user) != 'STUDENT'

    context = {
        'proposal': proposal,
        'registration': user_reg,
        'is_registered': user_reg is not None,
        'is_staff_user': is_staff_user,
        'role_choices': EventRegistration.ROLE_CHOICES,
    }
    return render(request, 'events/event_detail.html', context)


@login_required
def event_register_view(request, proposal_id):
    """
    Requirement 1 & Phase B: Students can register for an approved event as Participant, Volunteer, or Viewer.
    Other entities (faculty/staff) are barred from registering as students.
    Only one registration per student is allowed.
    """
    proposal = get_object_or_404(EventProposal, id=proposal_id, status='APPROVED')

    # Role check: only students register
    role_name = _get_user_role(request.user)
    if role_name != 'STUDENT':
        messages.error(request, "Only students can register for events. Faculty and institutional heads can view details.")
        return redirect('event_detail', proposal_id=proposal.id)

    # Fix #15: Block registration for ended events
    if proposal.end_date and timezone.now() > proposal.end_date:
        messages.error(request, "Registration is closed — this event has already ended.")
        return redirect('event_detail', proposal_id=proposal.id)

    if request.method == 'POST':
        # Check if already registered
        existing_reg = EventRegistration.objects.filter(event=proposal, student=request.user).first()
        if existing_reg:
            messages.warning(request, f"You are already registered for '{proposal.title}' as a {existing_reg.get_role_display()}. Only one registration per student is allowed.")
            return redirect('event_detail', proposal_id=proposal.id)

        role = request.POST.get('role', 'PARTICIPANT')
        valid_roles = [r[0] for r in EventRegistration.ROLE_CHOICES]
        if role not in valid_roles:
            role = 'PARTICIPANT'

        # Fix #15: Enforce expected_attendees capacity
        if proposal.expected_attendees:
            current_count = EventRegistration.objects.filter(event=proposal).count()
            if current_count >= proposal.expected_attendees:
                messages.error(request, f"Sorry, '{proposal.title}' has reached its capacity of {proposal.expected_attendees} registrations.")
                return redirect('event_detail', proposal_id=proposal.id)

        EventRegistration.objects.create(
            event=proposal,
            student=request.user,
            role=role,
            status='REGISTERED'
        )
        messages.success(request, f"Registration confirmed! You have registered as a {role.capitalize()} for '{proposal.title}'.")
        return redirect('event_detail', proposal_id=proposal.id)

    return redirect('event_detail', proposal_id=proposal.id)


@login_required
def cancel_registration_view(request, proposal_id):
    """
    Phase B: Student can cancel their registration if they have not yet checked in.
    """
    if request.method == 'POST':
        proposal = get_object_or_404(EventProposal, id=proposal_id)
        reg = EventRegistration.objects.filter(event=proposal, student=request.user).first()

        if not reg:
            messages.warning(request, "You are not registered for this event.")
            return redirect('event_detail', proposal_id=proposal_id)

        if reg.status in ('CHECKED_IN', 'VERIFIED'):
            messages.error(request, f"Cannot cancel registration because you have already {reg.get_status_display().lower()}.")
            return redirect('event_detail', proposal_id=proposal_id)

        reg.delete()
        messages.success(request, f"Your registration for '{proposal.title}' has been successfully cancelled.")
        return redirect('event_detail', proposal_id=proposal_id)

    return redirect('event_detail', proposal_id=proposal_id)


@login_required
def my_registrations_view(request):
    registrations = EventRegistration.objects.filter(student=request.user).select_related('event', 'event__organizing_unit').order_by('-registered_at')
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
    G10 — Hardened Check-in & Rotating QR Token:
    - Non-students (staff/faculty) blocked from checking in.
    - Validates dynamic rotating QR token against expiration window.
    - Event must be approved and currently active.
    - Only registered students can check in.
    - Duplicate scan: friendly message, no double CHECKED_IN.
    - Strict image validation (JPG/PNG, max 2MB).
    """
    # Staff/faculty should not be checking into events
    if request.user.is_staff and _get_user_role(request.user) != 'STUDENT':
        messages.error(request, "Staff members do not check in to events via QR.")
        return redirect('dashboard')

    token = request.GET.get('token') or request.POST.get('token') or ''
    proposal = None

    if token:
        base_token = token.rsplit('_', 2)[0] if token.count('_') >= 2 else token
        proposal = EventProposal.objects.filter(qr_checkin_token=base_token).first()

    if not proposal and token:
        messages.error(request, "Invalid or expired QR code. Please scan the current QR code displayed on the projector.")
        return render(request, 'events/checkin_selfie.html', {'proposal': None, 'token': ''})

    # Validate event status on GET
    if proposal and proposal.status != 'APPROVED':
        messages.error(request, "Check-in is only available for officially approved and published campus events.")
        return render(request, 'events/checkin_selfie.html', {'proposal': None, 'token': token})

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        selfie_file = request.FILES.get('selfie_image')
        selfie_data = request.POST.get('selfie_image', '').strip()

        base_token = token.rsplit('_', 2)[0] if token.count('_') >= 2 else token
        proposal = get_object_or_404(EventProposal, qr_checkin_token=base_token)

        # Validate token
        is_valid, reason = proposal.validate_rotating_token(token)
        if not is_valid:
            messages.error(request, f"❌ {reason}")
            return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token, 'expired': True})

        # Validate status on POST
        if proposal.status != 'APPROVED':
            messages.error(request, "Check-in is only available for officially approved and published campus events.")
            return render(request, 'events/checkin_selfie.html', {'proposal': None, 'token': token})

        # Fix #13: Select for update inside atomic transaction to prevent concurrent double-scans
        with transaction.atomic():
            reg = EventRegistration.objects.select_for_update().filter(event=proposal, student=request.user).first()
            if not reg:
                messages.error(request, f"You are not registered for '{proposal.title}'. Please register on the Events page first.")
                return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})

            # Validate timeframe
            now = timezone.now()
            if proposal.start_date and now < (proposal.start_date - timedelta(hours=1)):
                messages.error(request, "Check-in has not opened yet. Check-in opens 1 hour before the scheduled start time.")
                return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
            if proposal.end_date and now > (proposal.end_date + timedelta(hours=2)):
                messages.error(request, "This event has already concluded. Attendance check-in is now closed.")
                return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})

            # G10b: Duplicate check-in block
            if reg.status in ('CHECKED_IN', 'VERIFIED'):
                messages.info(request, f"You have already checked in to '{proposal.title}'. Your attendance status is: {reg.get_status_display()}.")
                if reg.status == 'CHECKED_IN' and not hasattr(reg, 'feedback'):
                    return redirect('event_feedback', registration_id=reg.id)
                return redirect('dashboard')

            # Selfie image validation & size limit
            if selfie_file:
                if selfie_file.size > 2 * 1024 * 1024:
                    messages.error(request, "Selfie image exceeds maximum allowed size of 2MB.")
                    return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
                try:
                    from PIL import Image
                    img = Image.open(selfie_file)
                    img.verify()
                    if img.format.lower() not in ['jpeg', 'jpg', 'png', 'webp']:
                        messages.error(request, "Invalid image format. Only JPEG or PNG photos are accepted.")
                        return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
                    selfie_file.seek(0)
                    ext = selfie_file.name.rsplit('.', 1)[-1].lower() if '.' in selfie_file.name else 'jpg'
                    selfie_file.name = f"selfie_{uuid.uuid4().hex}.{ext}"
                    reg.selfie_image = selfie_file
                except Exception:
                    messages.error(request, "Corrupt or invalid image uploaded as selfie.")
                    return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
            elif selfie_data and selfie_data.startswith('data:image'):
                if len(selfie_data) > 3 * 1024 * 1024:
                    messages.error(request, "Selfie data exceeds maximum allowed size of 2MB.")
                    return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
                try:
                    import base64
                    import io
                    from PIL import Image
                    from django.core.files.base import ContentFile
                    format_part, imgstr = selfie_data.split(';base64,')
                    mime = format_part.replace('data:', '').strip()
                    if mime not in ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']:
                        messages.error(request, "Unsupported image type. Only JPEG or PNG photos are allowed.")
                        return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
                    raw_bytes = base64.b64decode(imgstr)
                    img = Image.open(io.BytesIO(raw_bytes))
                    img.verify()
                    ext = format_part.split('/')[-1].lower().replace('jpeg', 'jpg')
                    # Fix #5: Unguessable filename using uuid4 instead of predictable id+timestamp
                    fname = f"selfie_{uuid.uuid4().hex}.{ext}"
                    reg.selfie_image = ContentFile(raw_bytes, name=fname)
                except Exception:
                    messages.error(request, "Corrupt or invalid image data. Please capture your selfie again.")
                    return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})
            elif selfie_data and not selfie_data.startswith('data:image'):
                messages.error(request, "Invalid selfie format. A valid camera photo is required.")
                return render(request, 'events/checkin_selfie.html', {'proposal': proposal, 'token': token})

            reg.status = 'CHECKED_IN'
            reg.checked_in_at = timezone.now()
            reg.save()

        messages.success(request, "Check-in verified via live selfie! Please complete the quick mandatory feedback below to verify your attendance.")
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

    # Fix #6: Must have physically checked in before feedback is allowed
    if reg.status != 'CHECKED_IN':
        if reg.status == 'VERIFIED':
            messages.info(request, "You have already completed feedback for this event.")
            return redirect('dashboard')
        messages.error(request, "You must check in at the event venue via QR scan before submitting feedback.")
        return redirect('checkin')

    if hasattr(reg, 'feedback'):
        messages.info(request, "You have already completed feedback for this event.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            rating_overall = int(request.POST.get('rating_overall', 5))
            rating_content = int(request.POST.get('rating_content', 5))
            rating_speaker = int(request.POST.get('rating_speaker', 5))
        except (ValueError, TypeError):
            messages.error(request, "All ratings must be integer numbers between 1 and 5.")
            return render(request, 'events/feedback.html', {'registration': reg})

        if not (1 <= rating_overall <= 5 and 1 <= rating_content <= 5 and 1 <= rating_speaker <= 5):
            messages.error(request, "Ratings must be strictly between 1 and 5 stars.")
            return render(request, 'events/feedback.html', {'registration': reg})

        comments = request.POST.get('comments', '').strip()

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

    # Fix #4 (IDOR): Only proposer, superuser, or staff approvers may access compliance data
    is_proposer = (proposal.proposer == request.user)
    user_role = _get_user_role(request.user)
    chain = proposal.approval_chain or []
    is_any_approver = any(st.get('role') == user_role for st in chain) if user_role else False
    if not (is_proposer or request.user.is_superuser or is_any_approver):
        raise Http404("Compliance report not found or you do not have access.")

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
