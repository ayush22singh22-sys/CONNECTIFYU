from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    UserProfile, OrganizingUnit, EventProposal,
    ApprovalLog, EventRegistration, EventFeedback, LogisticsNotification
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Institutional Profile (Role & Dept)'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_dept', 'get_roll', 'is_staff')
    list_filter = ('profile__role', 'profile__department', 'is_staff', 'is_superuser')

    @admin.display(description='Role')
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else '-'

    @admin.display(description='Department / Office')
    def get_dept(self, obj):
        return obj.profile.department if hasattr(obj, 'profile') else '-'

    @admin.display(description='Roll / Emp ID')
    def get_roll(self, obj):
        return obj.profile.roll_or_emp_id if hasattr(obj, 'profile') else '-'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'roll_or_emp_id', 'phone')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'roll_or_emp_id', 'department')


@admin.register(OrganizingUnit)
class OrganizingUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_type', 'head')
    list_filter = ('unit_type',)
    search_fields = ('name', 'head__username')


@admin.register(EventProposal)
class EventProposalAdmin(admin.ModelAdmin):
    list_display = ('title', 'proposer', 'organizing_unit', 'chain_type', 'approved_budget', 'status', 'published_at', 'start_date')
    list_filter = ('status', 'chain_type', 'organizing_unit')
    search_fields = ('title', 'description', 'proposer__username', 'guest_speaker')
    readonly_fields = ('qr_checkin_token', 'qr_rotation_secret', 'created_at', 'updated_at')


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ('proposal', 'approver', 'stage_name', 'action', 'revision_cycle', 'created_at')
    list_filter = ('action', 'revision_cycle')
    search_fields = ('proposal__title', 'approver__username', 'remarks')


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'student', 'role', 'status', 'registered_at', 'checked_in_at')
    list_filter = ('status', 'role')
    search_fields = ('event__title', 'student__username')


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    list_display = ('registration', 'rating_overall', 'rating_content', 'rating_speaker', 'submitted_at')
    list_filter = ('rating_overall',)
    search_fields = ('registration__event__title', 'registration__student__username', 'comments')


@admin.register(LogisticsNotification)
class LogisticsNotificationAdmin(admin.ModelAdmin):
    list_display = ('proposal', 'logistics_type', 'recipient_email', 'sent_at')
    list_filter = ('logistics_type',)
    search_fields = ('proposal__title', 'recipient_email', 'subject')
