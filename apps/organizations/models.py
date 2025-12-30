"""
Models for the organizations app.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import CurrencyField


class Organization(models.Model):
    """
    Organization model representing a multi-tenant organization.

    This is the top-level entity in the multi-tenant system. Each organization
    is isolated from others and has its own data, users, and settings.

    Note: This model does NOT use OrganizationOwnedModel because it IS the
    organization itself, not data owned by an organization.

    Attributes:
        name (str): Organization name.
        slug (str): URL-friendly unique identifier.
        abbreviation (str, optional): Short abbreviation for the organization.
        code_name (str, optional): Internal code name.
        logo (ImageField, optional): Organization logo image.
        base_currency (str): Default currency for the organization (default: XAF).
        is_active (bool): Whether the organization is active.
        created_at (datetime): When the organization was created.
    """

    name = models.CharField(_("Name"), max_length=255)
    slug = models.SlugField(_("Slug"), unique=True)
    abbreviation = models.CharField(
        _("Abbreviation"), max_length=10, blank=True, null=True
    )
    code_name = models.CharField(_("Code Name"), max_length=10, blank=True, null=True)
    logo = models.ImageField(
        _("Logo"), upload_to="organizations/logos/", blank=True, null=True
    )

    # Optional: default reporting currency
    base_currency = CurrencyField(
        _("Base Currency"), max_length=3, default=settings.DEFAULT_CURRENCY
    )

    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.name


class OrganizationRole(models.TextChoices):
    ADMIN = "admin", _("Admin")
    ANALYST = "analyst", _("Analyst")
    VIEWER = "viewer", _("Viewer")


class OrganizationMember(models.Model):
    """
    OrganizationMember model representing the relationship between users and organizations.

    This is a system-level relationship table that defines which users belong to
    which organizations and their roles. It does NOT use OrganizationOwnedModel
    because it must be queryable across organizations (e.g., in middleware to
    determine user memberships before organization context is established).

    Attributes:
        organization (Organization): The organization this membership belongs to.
        user (User): The user who is a member of the organization.
        role (str): The user's role in the organization (admin, analyst, viewer).
        is_active (bool): Whether this membership is active.
        created_at (datetime): When the membership was created.
        joined_at (datetime): When the user joined the organization.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        _("Role"),
        max_length=20,
        choices=OrganizationRole.choices,
        default=OrganizationRole.VIEWER,
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    joined_at = models.DateTimeField(_("Joined At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Organization Member")
        verbose_name_plural = _("Organization Members")
        unique_together = ["organization", "user"]
        indexes = [
            models.Index(fields=["organization", "user"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"
