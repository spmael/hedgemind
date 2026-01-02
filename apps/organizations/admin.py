"""
Django admin configuration for organization models.

This module provides admin interfaces for managing organizations and organization memberships.
"""

from __future__ import annotations

from django.contrib import admin

from apps.organizations.models import Organization, OrganizationMember


class OrganizationMemberInline(admin.TabularInline):
    """
    Inline admin for OrganizationMember model.

    Allows managing organization members directly from the organization admin page.
    """

    model = OrganizationMember
    extra = 0
    fields = ["user", "role", "is_active", "joined_at"]
    readonly_fields = ["joined_at", "created_at"]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """
    Admin interface for Organization model.

    Provides management interface for multi-tenant organizations.
    """

    list_display = [
        "name",
        "slug",
        "abbreviation",
        "base_currency",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "base_currency", "created_at"]
    search_fields = ["name", "slug", "abbreviation", "code_name"]
    readonly_fields = ["created_at"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [OrganizationMemberInline]


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    """
    Admin interface for OrganizationMember model.

    Provides management interface for user-organization memberships.
    """

    list_display = [
        "user",
        "organization",
        "role",
        "is_active",
        "joined_at",
        "created_at",
    ]
    list_filter = ["organization", "role", "is_active", "created_at"]
    search_fields = ["user__username", "user__email", "organization__name"]
    readonly_fields = ["created_at", "joined_at"]
