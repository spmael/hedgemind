"""
Django admin configuration for reference data models.

This module imports all admin classes from the admin package.
The admin classes are organized by domain in separate modules.
"""

from __future__ import annotations

# Import all admin classes to ensure they are registered
from apps.reference_data.admin import *  # noqa: F403, F401
