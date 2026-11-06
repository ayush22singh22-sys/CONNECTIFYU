import uuid
from django.db import models
from django.conf import settings


class Event(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('revision_required', 'Revision Required'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('completed', 'Completed'),
    ]
    EVENT_TYPE_CHOICES = [
        ('department', 'Department'),
        ('club', 'Club'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='proposed_events', on_delete=models.CASCADE)
    co_coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='co_coordinated_events',
        on_delete=models.SET_NULL, null=True, blank=True
    )
    guest_speaker = models.CharField(max_length=200, blank=True)
    guest_speaker_bio = models.TextField(blank=True)
    venue = models.CharField(max_length=200)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    expected_attendees = models.PositiveIntegerField()
    requested_budget = models.DecimalField(max_digits=10, decimal_places=2)
    approved_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    is_revision = models.BooleanField(default=False)
    revision_number = models.PositiveIntegerField(default=0)
    department = models.CharField(max_length=100, blank=True)
    club_name = models.CharField(max_length=100, blank=True)
    transport_required = models.BooleanField(default=False)
    mess_required = models.BooleanField(default=False)
    maintenance_required = models.BooleanField(default=False)
    transport_details = models.TextField(blank=True)
    mess_details = models.TextField(blank=True)
    maintenance_details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def get_current_stage(self):
        """Returns the latest pending ApprovalStage number, or None."""
        stage = self.approval_stages.filter(action='pending').order_by('stage_number').first()
        return stage.stage_number if stage else None

    def get_latest_stage(self):
        return self.approval_stages.order_by('-stage_number').first()


class ApprovalStage(models.Model):
    STAGE_CHOICES = [
        (1, 'Organizing Unit Head'),
        (2, 'HR'),
        (3, 'Dean of Research'),
        (4, 'Dean of Accounts'),
        (5, 'Dean of Academics / Director'),
    ]
    ACTION_CHOICES = [
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('revision_required', 'Revision Required'),
        ('pending', 'Pending'),
    ]
    event = models.ForeignKey(Event, related_name='approval_stages', on_delete=models.CASCADE)
    stage_number = models.PositiveIntegerField(choices=STAGE_CHOICES)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='pending')
    remark = models.TextField(blank=True)
    revised_budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_revision_reason = models.TextField(blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['stage_number']

    def __str__(self):
        return f"Stage {self.stage_number} – {self.event.title} ({self.action})"


class EventRegistration(models.Model):
    ROLE_CHOICES = [
        ('participant', 'Participant'),
        ('volunteer', 'Volunteer'),
        ('viewer', 'Viewer'),
    ]
    event = models.ForeignKey(Event, related_name='registrations', on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'student')

    def __str__(self):
        return f"{self.student.username} → {self.event.title} ({self.role})"


class EventQRCode(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='qr_code')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    qr_image = models.ImageField(upload_to='qrcodes/')
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR for {self.event.title}"
