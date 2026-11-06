import uuid
import time
import hmac
import hashlib
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty / Event Coordinator'),
        ('HOD', 'Head of Department (HOD)'),
        ('CLUB_HEAD', 'Faculty Advisor / Club In-Charge'),
        ('REGISTRAR', 'Registrar / Establishment (HR)'),
        ('DEAN_RESEARCH', 'Dean of Research & Consultancy (R&D)'),
        ('DEAN_STUDENT_WELFARE', 'Dean of Student Welfare (DSW)'),
        ('DEAN_ACCOUNTS', 'Dean of Finance & Accounts (Mandatory)'),
        ('DEAN_ACADEMICS', 'Dean of Academic Affairs (Mandatory)'),
        ('DIRECTOR', 'Director of the Institute (Mandatory)'),
        ('LOGISTICS_STAFF', 'Campus Logistics Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='STUDENT')
    department = models.CharField(max_length=150, blank=True, help_text="e.g. Computer Science & Engineering")
    roll_or_emp_id = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class OrganizingUnit(models.Model):
    UNIT_TYPES = [
        ('DEPARTMENT', 'Academic Department'),
        ('CLUB', 'Student Club / Society / Cell'),
        ('INSTITUTE', 'Central Institute Committee'),
    ]

    name = models.CharField(max_length=150, unique=True)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES, default='DEPARTMENT')
    head = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_units')

    def __str__(self):
        return f"{self.name} ({self.get_unit_type_display()})"


class EventProposal(models.Model):
    CHAIN_TYPES = [
        ('ACADEMIC', 'Academic & Research Event Chain (HOD → Dean R&D → Dean Finance → Dean Academics → Director)'),
        ('CLUB_FEST', 'Student Club & Cultural Fest Chain (Club Advisor → Dean Student Welfare → Dean Finance → Dean Academics → Director)'),
        ('INSTITUTE_MEGA', 'Institute Mega Event / Conclave Chain (Registrar/HR → Dean R&D → Dean Finance → Dean Academics → Director)'),
        ('CUSTOM', 'Custom Multi-Stage Approval Chain (Custom Selected Stages with Mandatory Deans & Director)'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('UNDER_REVIEW', 'Under Multi-Stage Review'),
        ('APPROVED_PENDING_PUBLISH', 'Approved by Director (Awaiting Faculty Poster & Publish)'),
        ('APPROVED', 'Approved & Published to Campus'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]

    title = models.CharField(max_length=250)
    description = models.TextField()
    proposer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proposals')
    co_coordinator = models.CharField(max_length=200, help_text="Name, Department, Contact")
    guest_speaker = models.CharField(max_length=250, help_text="Chief Guest / Keynote Speaker Profile")

    organizing_unit = models.ForeignKey(OrganizingUnit, on_delete=models.CASCADE, related_name='events')

    # Approval Chain configuration
    chain_type = models.CharField(max_length=30, choices=CHAIN_TYPES, default='ACADEMIC')
    approval_chain = models.JSONField(
        default=list,
        help_text="Ordered list of stages: [{'role': 'HOD', 'title': 'Head of Department', 'status': 'PENDING', ...}]"
    )
    current_stage_index = models.PositiveIntegerField(default=0)

    # Budget in Indian Rupees (₹)
    requested_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    approved_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    budget_revision_reason = models.TextField(blank=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    expected_attendees = models.PositiveIntegerField(default=100)

    # Poster & Faculty Publishing Gate
    poster_image = models.ImageField(upload_to='event_posters/', blank=True, null=True)
    poster_data_uri = models.TextField(blank=True, help_text="Base64 or image URL for event poster")
    published_at = models.DateTimeField(null=True, blank=True)

    # Campus Logistics Requirements
    mess_requirements = models.TextField(blank=True, help_text="Catering & refreshment arrangements")
    transport_requirements = models.TextField(blank=True, help_text="Vehicle fleet & airport/station pickup")
    maintenance_requirements = models.TextField(blank=True, help_text="Auditorium AC, PA system, audio/visual setup")

    status = models.CharField(max_length=35, choices=STATUS_CHOICES, default='UNDER_REVIEW')
    revision_count = models.PositiveIntegerField(default=0)
    is_revision = models.BooleanField(default=False)

    qr_checkin_token = models.CharField(max_length=64, default=uuid.uuid4, unique=True)
    qr_rotation_secret = models.CharField(max_length=64, default=uuid.uuid4)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    ROTATION_INTERVAL = 20  # seconds per QR rotation

    def save(self, *args, **kwargs):
        if not self.approved_budget or self.approved_budget == 0:
            self.approved_budget = self.requested_budget
        if not self.qr_checkin_token:
            self.qr_checkin_token = str(uuid.uuid4())
        else:
            self.qr_checkin_token = str(self.qr_checkin_token)

        if not self.qr_rotation_secret:
            self.qr_rotation_secret = str(uuid.uuid4())
        else:
            self.qr_rotation_secret = str(self.qr_rotation_secret)

        super().save(*args, **kwargs)

    def get_rotating_qr_token(self):
        """
        Generates a time-synced dynamic token that rotates every ROTATION_INTERVAL seconds.
        Prevents students from sharing photos of QR code with absent friends.
        """
        now_ts = int(time.time())
        window = now_ts // self.ROTATION_INTERVAL
        seconds_left = self.ROTATION_INTERVAL - (now_ts % self.ROTATION_INTERVAL)
        
        base_tok = str(self.qr_checkin_token)
        secret = str(self.qr_rotation_secret)

        # Compute HMAC signature for this window
        msg = f"{base_tok}:{window}".encode('utf-8')
        sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()[:10]
        token = f"{base_tok}_{window}_{sig}"
        return token, seconds_left

    def validate_rotating_token(self, token_string):
        """
        Validates if the provided token belongs to the current or immediate previous time window
        (allows 20-40s grace period for camera capture / network transit).
        Also accepts static qr_checkin_token as fallback for manual check-in testing.
        """
        if not token_string:
            return False, "Token is required"

        token_string = token_string.strip()
        base_tok = str(self.qr_checkin_token)
        secret = str(self.qr_rotation_secret)

        # Fallback exact static token check
        if token_string == base_tok:
            return True, "Valid token"

        parts = token_string.split('_')
        if len(parts) != 3:
            return False, "Invalid QR code format."

        base_token, window_str, sig = parts
        if base_token != base_tok:
            return False, "QR code does not match this event."

        try:
            window = int(window_str)
        except ValueError:
            return False, "Invalid QR rotation timestamp."

        current_window = int(time.time()) // self.ROTATION_INTERVAL
        
        # Check signature
        msg = f"{base_tok}:{window}".encode('utf-8')
        expected_sig = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()[:10]
        if not hmac.compare_digest(sig, expected_sig):
            return False, "Tampered or forged QR code."

        # Allow current window and 1 past window
        if window < (current_window - 1):
            return False, "QR Code Expired: This code has expired! Please scan the live rotating QR on the auditorium screen."
        if window > (current_window + 1):
            return False, "Invalid forward timestamp on QR code."

        return True, "Valid rotating token"

    @property
    def current_stage(self):
        """Returns the current pending stage dictionary or None if finished."""
        if self.status != 'UNDER_REVIEW':
            return None
        if self.approval_chain and self.current_stage_index < len(self.approval_chain):
            return self.approval_chain[self.current_stage_index]
        return None

    @property
    def current_stage_role(self):
        stage = self.current_stage
        return stage.get('role') if stage else None

    @property
    def current_stage_title(self):
        stage = self.current_stage
        return stage.get('title') if stage else self.get_status_display()

    @property
    def stage_number(self):
        return self.current_stage_index + 1

    @property
    def total_stages(self):
        return len(self.approval_chain) if self.approval_chain else 5

    def is_awaiting_user(self, user):
        """Checks if proposal is currently waiting for the given user's approval."""
        if self.status != 'UNDER_REVIEW' or not hasattr(user, 'profile'):
            return False
        
        current_role = self.current_stage_role
        if not current_role:
            return False

        user_role = user.profile.role

        if current_role == 'HOD':
            return (user_role == 'HOD' and (self.organizing_unit.head == user or self.organizing_unit.unit_type == 'DEPARTMENT'))
        elif current_role == 'CLUB_HEAD':
            return (user_role in ['CLUB_HEAD', 'FACULTY'] and (self.organizing_unit.head == user or self.organizing_unit.unit_type == 'CLUB'))
        elif current_role == 'REGISTRAR':
            return user_role == 'REGISTRAR'
        elif current_role == 'DEAN_RESEARCH':
            return user_role == 'DEAN_RESEARCH'
        elif current_role == 'DEAN_STUDENT_WELFARE':
            return user_role == 'DEAN_STUDENT_WELFARE'
        elif current_role == 'DEAN_ACCOUNTS':
            return user_role == 'DEAN_ACCOUNTS'
        elif current_role == 'DEAN_ACADEMICS':
            return user_role == 'DEAN_ACADEMICS'
        elif current_role == 'DIRECTOR':
            return user_role == 'DIRECTOR'

        return user_role == current_role

    def __str__(self):
        return f"{self.title} [₹{self.approved_budget} - {self.get_status_display()}]"


class ApprovalLog(models.Model):
    ACTION_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('REJECTED', 'Rejected'),
        ('BUDGET_REVISED', 'Budget Revised & Sanctioned'),
    ]

    proposal = models.ForeignKey(EventProposal, on_delete=models.CASCADE, related_name='logs')
    approver = models.ForeignKey(User, on_delete=models.CASCADE)
    stage_name = models.CharField(max_length=120)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    remarks = models.TextField()

    old_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    revised_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    revision_cycle = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.proposal.title} - {self.stage_name}: {self.action} by {self.approver.username}"


class EventRegistration(models.Model):
    ROLE_CHOICES = [
        ('PARTICIPANT', 'Student Participant'),
        ('VOLUNTEER', 'Student Volunteer'),
        ('VIEWER', 'Audience / Viewer'),
    ]

    STATUS_CHOICES = [
        ('REGISTERED', 'Registered'),
        ('CHECKED_IN', 'Checked-In (Pending Feedback)'),
        ('VERIFIED', 'Verified Attendee (Attendance Confirmed)'),
    ]

    event = models.ForeignKey(EventProposal, on_delete=models.CASCADE, related_name='registrations')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_registrations')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='PARTICIPANT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REGISTERED')
    registered_at = models.DateTimeField(auto_now_add=True)

    checked_in_at = models.DateTimeField(null=True, blank=True)
    selfie_image = models.TextField(blank=True, help_text="Base64 Data URI of anti-proxy selfie")

    class Meta:
        unique_together = ('event', 'student')

    def __str__(self):
        return f"{self.student.username} -> {self.event.title} ({self.role})"


class EventFeedback(models.Model):
    registration = models.OneToOneField(EventRegistration, on_delete=models.CASCADE, related_name='feedback')
    rating_overall = models.PositiveSmallIntegerField(default=5)
    rating_content = models.PositiveSmallIntegerField(default=5)
    rating_speaker = models.PositiveSmallIntegerField(default=5)
    comments = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for {self.registration.event.title} by {self.registration.student.username} ({self.rating_overall}★)"


class LogisticsNotification(models.Model):
    TYPE_CHOICES = [
        ('MESS', 'Hostel Mess & Catering Services'),
        ('TRANSPORT', 'Transport & Institute Fleet Management'),
        ('MAINTENANCE', 'Estate & AV Maintenance Section'),
    ]

    proposal = models.ForeignKey(EventProposal, on_delete=models.CASCADE, related_name='logistics_notifications')
    logistics_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_logistics_type_display()} - {self.proposal.title}"
