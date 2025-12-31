"""
Shared choices/constants used across multiple Django apps.

This module provides common TextChoices and constants that are used
by multiple apps to ensure consistency and avoid duplication.

Key principles:
- Only include choices that are used by 2+ apps
- Keep choices generic enough to be reusable
- Document when choices are app-specific vs shared
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class ImportStatus(models.TextChoices):
    """
    Import status choices for file imports.
    
    Used by:
    - PortfolioImport (portfolios app)
    - YieldCurveImport (reference_data app)
    - Future: FXRateImport, PriceImport, etc.
    
    Status flow:
    PENDING → PARSING → VALIDATING → PROCESSING → SUCCESS/FAILED/PARTIAL
    """
    
    PENDING = "pending", _("Pending")
    PARSING = "parsing", _("Parsing")
    VALIDATING = "validating", _("Validating")
    PROCESSING = "processing", _("Processing")
    IMPORTING = "importing", _("Importing")  # Alias for PROCESSING (for simpler workflows)
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    PARTIAL = "partial", _("Partial")  # Some rows succeeded, some failed


class ImportSourceType(models.TextChoices):
    """
    Source type choices for imports.
    
    Used by:
    - PortfolioImport (portfolios app)
    - Future: Other import types
    """
    
    CUSTODIAN = "custodian", _("Custodian")
    INTERNAL = "internal", _("Internal")
    MANUAL = "manual", _("Manual")
    EXTERNAL = "external", _("External")