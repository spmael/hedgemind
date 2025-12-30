"""
Audit logging models for tracking system operations and data changes.

This module provides audit trail capabilities for tracking who performed what
actions on which objects, when. This is critical for institutional trust,
regulatory compliance, and security.

Key components:
- AuditEvent: Immutable audit log entries for all significant operations
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class AuditEvent(models.Model):
    """
    Immutable audit log entry for tracking system operations.

    Records who performed what action on which object, when, and provides
    additional context via metadata JSON. This model is append-only and
    should never be updated or deleted once created.

    Attributes:
        organization_id (int, optional): Organization context for the action.
        actor (User, optional): User who performed the action (None for system actions).
        action (str): Type of action performed (e.g., 'CREATE', 'UPDATE', 'DELETE', 'LOAD_REFERENCE_DATA').
        object_type (str): Type of object affected (e.g., 'InstrumentGroup', 'InstrumentType').
        object_id (int, optional): ID of the affected object.
        object_repr (str, optional): String representation of the affected object.
        metadata (dict): Additional context as JSON (defaults to empty dict).
        created_at (datetime): When the audit event occurred (auto-set on creation).

    Example:
        >>> AuditEvent.objects.create(
        ...     organization_id=1,
        ...     actor=user,
        ...     action='LOAD_REFERENCE_DATA',
        ...     object_type='InstrumentGroup',
        ...     object_repr='EQUITY',
        ...     metadata={'groups_created': 5, 'groups_updated': 0}
        ... )

    Note:
        This model is append-only. Never update or delete audit events.
        Use metadata JSON field for extensibility without schema changes.
    """

    organization_id = models.IntegerField(
        _("Organization ID"),
        blank=True,
        null=True,
        help_text="Organization context for this action (optional for system-wide actions).",
        db_index=True,
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="audit_events",
        verbose_name=_("Actor"),
        help_text="User who performed this action (None for system/automated actions).",
    )
    action = models.CharField(
        _("Action"),
        max_length=100,
        help_text="Type of action performed (e.g., 'CREATE', 'UPDATE', 'DELETE', 'LOAD_REFERENCE_DATA').",
        db_index=True,
    )
    object_type = models.CharField(
        _("Object Type"),
        max_length=100,
        help_text="Type of object affected (e.g., 'InstrumentGroup', 'InstrumentType').",
        db_index=True,
    )
    object_id = models.IntegerField(
        _("Object ID"),
        blank=True,
        null=True,
        help_text="ID of the affected object (optional).",
    )
    object_repr = models.CharField(
        _("Object Representation"),
        max_length=255,
        blank=True,
        null=True,
        help_text="String representation of the affected object.",
    )
    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text="Additional context as JSON (e.g., details about the operation).",
    )
    created_at = models.DateTimeField(
        _("Created At"),
        auto_now_add=True,
        help_text="When this audit event occurred.",
        db_index=True,
    )

    class Meta:
        verbose_name = _("Audit Event")
        verbose_name_plural = _("Audit Events")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization_id", "created_at"]),
            models.Index(fields=["action", "object_type"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self) -> str:
        """String representation of the audit event."""
        actor_str = self.actor.username if self.actor else "SYSTEM"
        obj_str = (
            f"{self.object_type}#{self.object_id}"
            if self.object_id
            else self.object_type
        )
        return f"{actor_str} {self.action} {obj_str} at {self.created_at}"
