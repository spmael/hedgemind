"""
Django app configuration for organizations app.

This app handles multi-tenant organization management, including:
- Organization model and settings
- Organization membership and roles
- Organization context middleware
- Organization switching endpoints
"""

from __future__ import annotations

from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    """
    App configuration for organizations app.

    Provides configuration for the organizations Django application,
    including the default auto field and app name.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.organizations"
