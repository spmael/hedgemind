"""
Django admin configuration for audit models.

This module provides admin interface for viewing audit events.
Note: AuditEvent is append-only and should never be editable or deletable.
"""

from __future__ import annotations

from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """
    Admin interface for AuditEvent model.

    Provides read-only interface for viewing audit trail events.
    Audit events are immutable and should never be edited or deleted.
    """

    list_display = [
        "actor",
        "action",
        "object_type",
        "object_id",
        "organization_id",
        "created_at",
    ]
    list_filter = ["action", "object_type", "created_at", "organization_id"]
    search_fields = ["actor__username", "action", "object_type", "object_repr"]
    readonly_fields = [
        "organization_id",
        "actor",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "metadata",
        "created_at",
    ]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        """Disable adding audit events through admin (they should be created programmatically)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing audit events (they are immutable)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deleting audit events (they are append-only)."""
        return False
