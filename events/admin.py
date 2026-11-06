from django.contrib import admin
from .models import Event, ApprovalStage, EventRegistration, EventQRCode


class ApprovalStageInline(admin.TabularInline):
    model = ApprovalStage
    extra = 0
    readonly_fields = ('acted_at', 'created_at')


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    readonly_fields = ('registered_at',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'proposed_by', 'status', 'start_datetime', 'venue')
    list_filter = ('status', 'event_type', 'department')
    search_fields = ('title', 'proposed_by__username', 'venue')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ApprovalStageInline, EventRegistrationInline]


@admin.register(ApprovalStage)
class ApprovalStageAdmin(admin.ModelAdmin):
    list_display = ('event', 'stage_number', 'approver', 'action', 'acted_at')
    list_filter = ('stage_number', 'action')
    search_fields = ('event__title', 'approver__username')


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'student', 'role', 'registered_at')
    list_filter = ('role',)


@admin.register(EventQRCode)
class EventQRCodeAdmin(admin.ModelAdmin):
    list_display = ('event', 'token', 'generated_at')
    readonly_fields = ('generated_at',)
