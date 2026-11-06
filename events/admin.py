from django.contrib import admin
from .models import (
    RollWhitelist, StudentProfile, StaffProfile, UserProfile,
    OrganizingUnit, EventProposal, ApprovalLog, EventRegistration,
    EventFeedback, LogisticsNotification
)


@admin.register(RollWhitelist)
class RollWhitelistAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'name', 'department', 'year', 'is_used')
    list_filter = ('year', 'is_used', 'department')
    search_fields = ('roll_number', 'name', 'department')
    actions = ['mark_as_unused']

    @admin.action(description="Mark selected entries as unused")
    def mark_as_unused(self, request, queryset):
        queryset.update(is_used=False)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'roll_number', 'department', 'year', 'phone')
    list_filter = ('year', 'department')
    search_fields = ('roll_number', 'user__username', 'user__first_name', 'user__last_name', 'department')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'designation', 'organizing_unit')
    list_filter = ('organizing_unit',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'designation')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'roll_or_emp_id', 'phone')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'roll_or_emp_id')


@admin.register(OrganizingUnit)
class OrganizingUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_type', 'head')
    list_filter = ('unit_type',)
    search_fields = ('name', 'head__username')


@admin.register(EventProposal)
class EventProposalAdmin(admin.ModelAdmin):
    list_display = ('title', 'proposer', 'organizing_unit', 'chain_type', 'status', 'approved_budget', 'start_date')
    list_filter = ('status', 'chain_type', 'organizing_unit')
    search_fields = ('title', 'proposer__username', 'venue')


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ('proposal', 'stage_name', 'approver', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('proposal__title', 'approver__username', 'stage_name')


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'student', 'role', 'status', 'registered_at', 'checked_in_at')
    list_filter = ('status', 'role')
    search_fields = ('event__title', 'student__username')


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    list_display = ('registration', 'rating_overall', 'rating_content', 'rating_speaker', 'submitted_at')
    list_filter = ('rating_overall',)


@admin.register(LogisticsNotification)
class LogisticsNotificationAdmin(admin.ModelAdmin):
    list_display = ('proposal', 'logistics_type', 'recipient_email', 'sent_at')
    list_filter = ('logistics_type', 'sent_at')

