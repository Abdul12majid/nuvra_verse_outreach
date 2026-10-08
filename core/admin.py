from django.contrib import admin
from .models import (
    Lead,
    Signal,
    ContactMethod,
    ContactPreference,
    OutreachLog,
    Response,
    SendQueue,
)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "display_name", "status", "signal_score", "signal_count", "last_seen_at")
    list_filter = ("source", "status")
    search_fields = ("display_name", "source_uid", "headline", "bio")
    ordering = ("-signal_score", "-last_seen_at")


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "source", "signal_type", "confidence", "detected_at")
    list_filter = ("source", "signal_type", "confidence")
    search_fields = ("summary", "evidence", "external_id")
    ordering = ("-detected_at",)


@admin.register(ContactMethod)
class ContactMethodAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "channel", "identifier", "is_primary", "verified")
    list_filter = ("channel", "is_primary", "verified")
    search_fields = ("identifier",)


@admin.register(ContactPreference)
class ContactPreferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "identifier", "opted_out", "opted_out_at")
    list_filter = ("channel", "opted_out")
    search_fields = ("identifier",)


@admin.register(OutreachLog)
class OutreachLogAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "channel", "send_method", "status", "sent_at", "created_at")
    list_filter = ("channel", "send_method", "status")
    search_fields = ("subject", "body", "external_id")
    ordering = ("-created_at",)


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "channel", "is_positive", "received_at")
    list_filter = ("channel", "is_positive")
    ordering = ("-received_at",)


@admin.register(SendQueue)
class SendQueueAdmin(admin.ModelAdmin):
    list_display = ("id", "outreach", "run_after", "attempts", "max_attempts", "locked_at")
    list_filter = ("locked_at",)
    ordering = ("run_after",)