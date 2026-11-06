import uuid
from django.db import models
from events.models import EventRegistration


class CheckIn(models.Model):
    registration = models.OneToOneField(EventRegistration, on_delete=models.CASCADE, related_name='checkin')
    qr_token = models.UUIDField(default=uuid.uuid4)
    selfie = models.ImageField(upload_to='selfies/')
    checked_in_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)  # True after feedback submitted

    def __str__(self):
        return f"CheckIn: {self.registration.student.username} @ {self.registration.event.title}"


class EventFeedback(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    checkin = models.OneToOneField(CheckIn, on_delete=models.CASCADE, related_name='feedback')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback: {self.checkin.registration.student.username} – {self.rating}/5"
