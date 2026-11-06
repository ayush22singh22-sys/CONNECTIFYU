from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('faculty', 'Faculty'),
        ('hod', 'Head of Department'),
        ('club_head', 'Club Head'),
        ('hr', 'HR'),
        ('dean_research', 'Dean of Research'),
        ('dean_accounts', 'Dean of Accounts'),
        ('dean_academics', 'Dean of Academics / Director'),
        ('student', 'Student'),
        ('transport', 'Transport Staff'),
        ('mess', 'Mess Staff'),
        ('maintenance', 'Maintenance Staff'),
    ]
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='student')
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_approver(self):
        return self.role in ('hod', 'club_head', 'hr', 'dean_research', 'dean_accounts', 'dean_academics')

    @property
    def is_faculty_or_club_head(self):
        return self.role in ('faculty', 'club_head')

    @property
    def is_infra_staff(self):
        return self.role in ('transport', 'mess', 'maintenance')
