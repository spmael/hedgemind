"""
Utility functions for Django management commands.

Provides helpers for resolving organizations and users from human-readable
identifiers (slug, code_name, username) instead of requiring numeric IDs.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from apps.organizations.models import Organization

User = get_user_model()


def resolve_organization(
    org_id: int | None = None,
    org_slug: str | None = None,
    org_code: str | None = None,
) -> Organization:
    """
    Resolve an Organization from various identifier types.

    Resolution priority:
        1. org_id (if provided)
        2. org_slug (if provided)
        3. org_code (code_name, if provided)

    Args:
        org_id: Organization ID (numeric).
        org_slug: Organization slug (unique identifier).
        org_code: Organization code_name (optional internal code).

    Returns:
        Organization: The resolved organization.

    Raises:
        CommandError: If no identifier provided or organization not found.
    """
    if org_id:
        try:
            return Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization with id={org_id} not found")

    if org_slug:
        try:
            return Organization.objects.get(slug=org_slug)
        except Organization.DoesNotExist:
            raise CommandError(
                f"Organization with slug='{org_slug}' not found. "
                f"Available slugs: {', '.join(Organization.objects.values_list('slug', flat=True))}"
            )

    if org_code:
        try:
            return Organization.objects.get(code_name=org_code)
        except Organization.DoesNotExist:
            raise CommandError(
                f"Organization with code_name='{org_code}' not found. "
                f"Available code_names: {', '.join(Organization.objects.exclude(code_name__isnull=True).exclude(code_name='').values_list('code_name', flat=True))}"
            )

    raise CommandError(
        "Organization identifier required. Provide one of: --org-id, --org-slug, or --org-code"
    )


def resolve_user(
    user_id: int | None = None,
    username: str | None = None,
) -> User | None:
    """
    Resolve a User from various identifier types.

    Resolution priority:
        1. user_id (if provided)
        2. username (if provided)

    Args:
        user_id: User ID (numeric).
        username: Username (unique identifier).

    Returns:
        User | None: The resolved user, or None if no identifier provided.

    Raises:
        CommandError: If identifier provided but user not found.
    """
    if user_id:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise CommandError(f"User with id={user_id} not found")

    if username:
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User with username='{username}' not found")

    return None

