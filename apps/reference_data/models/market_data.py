"""
Market data source models.

Models for defining market data sources and their priority hierarchy.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class MarketDataSource(models.Model):
    """
    MarketDataSource model defining market data sources and their priority hierarchy.

    Unified source model for all market data types (prices, FX rates, yield curves).
    Defines sources and establishes a global priority hierarchy for selecting the best
    data when multiple sources are available.

    Attributes:
        code (str): Short code for the source (e.g., "BVMAC", "BEAC", "BLOOMBERG", "MANUAL").
        name (str): Full name of the source.
        priority (int): Priority rank (lower = higher priority, e.g., 1 = best, 10 = worst).
        source_type (str): Type of source (EXCHANGE, CENTRAL_BANK, VENDOR, MANUAL, CUSTODIAN).
        is_active (bool): Whether this source is currently active.
        description (str, optional): Description of the source.
        created_at (datetime): When the source record was created.
        updated_at (datetime): When the source record was last updated.

    Example:
        >>> source = MarketDataSource.objects.create(
        ...     code="BVMAC",
        ...     name="Douala Stock Exchange",
        ...     priority=1,
        ...     source_type=MarketDataSource.SourceType.EXCHANGE,
        ...     is_active=True
        ... )
    """

    class SourceType(models.TextChoices):
        """Source type choices."""

        EXCHANGE = "exchange", _("Exchange")
        CENTRAL_BANK = "central_bank", _("Central Bank")
        VENDOR = "vendor", _("Vendor")
        MANUAL = "manual", _("Manual")
        CUSTODIAN = "custodian", _("Custodian")

    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        help_text=_("Short code for the source (e.g., 'BVMAC', 'BEAC', 'BLOOMBERG')"),
    )
    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text=_("Full name of the source"),
    )
    priority = models.IntegerField(
        _("Priority"),
        default=100,
        help_text=_(
            "Priority rank (lower = higher priority, e.g., 1 = best, 10 = worst)"
        ),
    )
    source_type = models.CharField(
        _("Source Type"),
        max_length=20,
        choices=SourceType.choices,
        blank=True,
        null=True,
        help_text=_(
            "Type of source (EXCHANGE, CENTRAL_BANK, VENDOR, MANUAL, CUSTODIAN)"
        ),
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Market Data Source")
        verbose_name_plural = _("Market Data Sources")
        ordering = ["priority", "code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["priority", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
