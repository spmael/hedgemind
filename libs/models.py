"""
Base model mixins for multi-tenant organization scoping.

Provides OrganizationOwnedModel mixin that:
- Adds organization ForeignKey to models
- Provides custom manager that auto-filters by current org context
- Auto-sets organization_id on save from thread-local context
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet

from libs.tenant_context import get_current_org_id


class OrganizationQuerySet(QuerySet):
    """
    Custom QuerySet that automatically filters by the current organization context.

    This ensures that all queries are scoped to the active organization,
    preventing accidental data leaks across organizations.
    """

    def _filter_by_org(self):
        """Filter queryset by current organization context."""
        org_id = get_current_org_id()
        if org_id is None:
            return self.none()
        return self.filter(organization_id=org_id)

    def all(self):
        """Override all() to filter by current organization."""
        return self._filter_by_org()

    def filter(self, *args, **kwargs):
        """Override filter() to always include organization filter."""
        queryset = super().filter(*args, **kwargs)
        return queryset._filter_by_org()

    def get(self, *args, **kwargs):
        """Override get() to always include organization filter."""
        # Apply organization filter first, then call parent get()
        filtered = self._filter_by_org()
        return super(OrganizationQuerySet, filtered).get(*args, **kwargs)

    def create(self, **kwargs):
        """Override create() to auto-set organization_id from context."""
        org_id = get_current_org_id()
        if org_id is not None and "organization_id" not in kwargs:
            kwargs["organization_id"] = org_id
        return super().create(**kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        """Override get_or_create() to auto-set organization_id."""
        org_id = get_current_org_id()
        if org_id is not None and "organization_id" not in kwargs:
            kwargs["organization_id"] = org_id
        return super().get_or_create(defaults=defaults, **kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        """Override update_or_create() to auto-set organization_id."""
        org_id = get_current_org_id()
        if org_id is not None and "organization_id" not in kwargs:
            kwargs["organization_id"] = org_id
        return super().update_or_create(defaults=defaults, **kwargs)


class OrganizationManager(models.Manager):
    """
    Custom manager for organization-owned models.

    Provides automatic filtering by current organization context.
    """

    def get_queryset(self):
        """Return QuerySet filtered by current organization."""
        return OrganizationQuerySet(self.model, using=self._db)

    def all(self):
        """Return all objects for current organization."""
        return self.get_queryset().all()

    def filter(self, *args, **kwargs):
        """Filter objects for current organization."""
        return self.get_queryset().filter(*args, **kwargs)

    def get(self, *args, **kwargs):
        """Get object for current organization."""
        return self.get_queryset().get(*args, **kwargs)

    def create(self, **kwargs):
        """Create object with organization_id from context."""
        return self.get_queryset().create(**kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        """Get or create object with organization_id from context."""
        return self.get_queryset().get_or_create(defaults=defaults, **kwargs)

    def update_or_create(self, defaults=None, **kwargs):
        """Update or create object with organization_id from context."""
        return self.get_queryset().update_or_create(defaults=defaults, **kwargs)


class OrganizationOwnedModel(models.Model):
    """
    Abstract base model mixin for models that belong to an organization.

    Usage:
        class Portfolio(OrganizationOwnedModel):
            name = models.CharField(max_length=255)
            # organization field is automatically added

    Benefits:
        - Automatic organization scoping in all queries
        - Auto-sets organization_id on save from thread-local context
        - Prevents accidental cross-organization data access
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        verbose_name="Organization",
    )

    objects = OrganizationManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Auto-set organization_id from context if not already set."""
        if not self.organization_id:
            org_id = get_current_org_id()
            if org_id is None:
                raise ValidationError(
                    "Cannot save organization-owned model without organization context. "
                    "Set organization_id explicitly or ensure organization context is set."
                )
            self.organization_id = org_id
        super().save(*args, **kwargs)

    def clean(self):
        """Validate that organization_id is set."""
        super().clean()
        if not self.organization_id:
            org_id = get_current_org_id()
            if org_id:
                self.organization_id = org_id
            else:
                raise ValidationError(
                    "Organization is required. Set organization_id explicitly "
                    "or ensure organization context is set."
                )
