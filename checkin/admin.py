from django.contrib import admin
from .models import CheckIn, EventFeedback


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ('registration', 'checked_in_at', 'is_verified')
    list_filter = ('is_verified',)
    readonly_fields = ('checked_in_at', 'qr_token')


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    list_display = ('checkin', 'rating', 'submitted_at')
    list_filter = ('rating',)
    readonly_fields = ('submitted_at',)
