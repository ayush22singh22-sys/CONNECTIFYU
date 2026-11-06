import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty / Organizer'),
        ('HOD', 'Department Head (HOD)'),
        ('CLUB_HEAD', 'Club President / Head'),
        ('HR', 'Human Resources (HR)'),
        ('DEAN_RESEARCH', 'Dean of Research'),
        ('DEAN_ACCOUNTS', 'Dean of Accounts'),
        ('DEAN_ACADEMICS', 'Dean of Academics / Director'),
        ('LOGISTICS_STAFF', 'Logistics Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='STUDENT')
    department = models.CharField(max_length=100, blank=True, help_text="e.g. Computer Science, Mechanical, etc.")
    roll_or_emp_id = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class OrganizingUnit(models.Model):
    UNIT_TYPES = [
        ('DEPARTMENT', 'Academic Department'),
        ('CLUB', 'Student Club / Society'),
    ]

    name = models.CharField(max_length=150, unique=True)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES, default='DEPARTMENT')
    head = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_units')

    def __str__(self):
        return f"{self.name} ({self.get_unit_type_display()})"


class EventProposal(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('STAGE_1_UNIT_HEAD', 'Stage 1: Organizing Unit Head Review'),
        ('STAGE_2_HR', 'Stage 2: HR Review'),
        ('STAGE_3_DEAN_RESEARCH', 'Stage 3: Dean of Research Review'),
        ('STAGE_4_DEAN_ACCOUNTS', 'Stage 4: Dean of Accounts Review'),
        ('STAGE_5_DEAN_ACADEMICS', 'Stage 5: Dean of Academics / Director Review'),
        ('APPROVED', 'Approved & Published'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]

    title = models.CharField(max_length=250)
    description = models.TextField()
    proposer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proposals')
    co_coordinator = models.CharField(max_length=200, help_text="Name, department, contact")
    guest_speaker = models.CharField(max_length=250, help_text="Name, Designation, Organization")

    organizing_unit = models.ForeignKey(OrganizingUnit, on_delete=models.CASCADE, related_name='events')

    requested_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    approved_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    budget_revision_reason = models.TextField(blank=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    expected_attendees = models.PositiveIntegerField(default=50)

    # Logistics Requirements
    mess_requirements = models.TextField(blank=True, help_text="Refreshments, meals, tea/coffee counts")
    transport_requirements = models.TextField(blank=True, help_text="Bus pickup, guest car arrangement")
    maintenance_requirements = models.TextField(blank=True, help_text="Projector, mic, AC, auditorium seating")

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='STAGE_1_UNIT_HEAD')
    revision_count = models.PositiveIntegerField(default=0)
    is_revision = models.BooleanField(default=False)

    qr_checkin_token = models.CharField(max_length=64, default=uuid.uuid4, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.approved_budget or self.approved_budget == 0:
            self.approved_budget = self.requested_budget
        if not self.qr_checkin_token:
            self.qr_checkin_token = str(uuid.uuid4())
        super().save(*args, **kwargs)

    @property
    def stage_number(self):
        stage_map = {
            'STAGE_1_UNIT_HEAD': 1,
            'STAGE_2_HR': 2,
            'STAGE_3_DEAN_RESEARCH': 3,
            'STAGE_4_DEAN_ACCOUNTS': 4,
            'STAGE_5_DEAN_ACADEMICS': 5,
            'APPROVED': 6,
            'COMPLETED': 6,
        }
        return stage_map.get(self.status, 0)

    def is_awaiting_user(self, user):
        """Checks if this proposal is currently waiting for the given user's approval."""
        if not hasattr(user, 'profile'):
            return False
        role = user.profile.role

        if self.status == 'STAGE_1_UNIT_HEAD':
            # Dynamically check if user is head of the organizing unit
            return self.organizing_unit.head == user or (role == 'HOD' and self.organizing_unit.unit_type == 'DEPARTMENT') or (role == 'CLUB_HEAD' and self.organizing_unit.unit_type == 'CLUB')
        elif self.status == 'STAGE_2_HR':
            return role == 'HR'
        elif self.status == 'STAGE_3_DEAN_RESEARCH':
            return role == 'DEAN_RESEARCH'
        elif self.status == 'STAGE_4_DEAN_ACCOUNTS':
            return role == 'DEAN_ACCOUNTS'
        elif self.status == 'STAGE_5_DEAN_ACADEMICS':
            return role == 'DEAN_ACADEMICS'
        return False

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"


class ApprovalLog(models.Model):
    ACTION_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REVISION_REQUESTED', 'Revision Requested'),
        ('REJECTED', 'Rejected'),
        ('BUDGET_REVISED', 'Budget Revised & Approved'),
    ]

    proposal = models.ForeignKey(EventProposal, on_delete=models.CASCADE, related_name='logs')
    approver = models.ForeignKey(User, on_delete=models.CASCADE)
    stage_name = models.CharField(max_length=100)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    remarks = models.TextField()

    old_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    revised_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    revision_cycle = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.proposal.title} - {self.stage_name}: {self.action} by {self.approver.username}"


class EventRegistration(models.Model):
    ROLE_CHOICES = [
        ('PARTICIPANT', 'Participant'),
        ('VOLUNTEER', 'Volunteer'),
        ('VIEWER', 'Viewer / Audience'),
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
    selfie_image = models.TextField(blank=True, help_text="Base64 Data URI or Image URL of attendance selfie")

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
        ('MESS', 'Mess / Catering Services'),
        ('TRANSPORT', 'Transport & Fleet Management'),
        ('MAINTENANCE', 'Auditorium & AV Maintenance'),
    ]

    proposal = models.ForeignKey(EventProposal, on_delete=models.CASCADE, related_name='logistics_notifications')
    logistics_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_logistics_type_display()} - {self.proposal.title}"
