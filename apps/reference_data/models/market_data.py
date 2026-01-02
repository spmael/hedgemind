"""
Market data source models.

Models for defining market data sources and their priority hierarchy.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from libs.models import OrganizationOwnedModel


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


class MarketDataSourcePriority(OrganizationOwnedModel):
    """
    Organization-specific market data source priority override.

    Allows organizations to override the global source priority for specific data types.
    When canonicalization runs in an organization's context, org-specific priorities
    take precedence over global MarketDataSource.priority values.

    If no org-specific priority is set, the global MarketDataSource.priority is used.

    Attributes:
        organization (Organization): The organization this priority applies to.
        data_type (str): Type of market data (fx_rate, price, yield_curve).
        source (MarketDataSource): The market data source.
        priority (int): Priority rank for this org/data_type combination (lower = higher priority).

    Example:
        >>> # Org 1 prefers CUSTODIAN over BEAC for FX rates
        >>> override = MarketDataSourcePriority.objects.create(
        ...     organization_id=1,
        ...     data_type=MarketDataSourcePriority.DataType.FX_RATE,
        ...     source=custodian_source,
        ...     priority=1  # Higher priority than BEAC's global priority of 2
        ... )
    """

    class DataType(models.TextChoices):
        """Market data type choices."""

        FX_RATE = "fx_rate", _("FX Rate")
        PRICE = "price", _("Price")
        YIELD_CURVE = "yield_curve", _("Yield Curve")
        INDEX_VALUE = "index_value", _("Index Value")

    data_type = models.CharField(
        _("Data Type"),
        max_length=20,
        choices=DataType.choices,
        help_text="Type of market data this priority applies to.",
    )
    source = models.ForeignKey(
        "MarketDataSource",
        on_delete=models.CASCADE,
        related_name="org_priority_overrides",
        verbose_name=_("Source"),
        help_text="Market data source this priority applies to.",
    )
    priority = models.IntegerField(
        _("Priority"),
        help_text="Priority rank for this org/data_type combination (lower = higher priority).",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Market Data Source Priority Override")
        verbose_name_plural = _("Market Data Source Priority Overrides")
        unique_together = [["organization", "data_type", "source"]]
        indexes = [
            models.Index(fields=["organization", "data_type", "priority"]),
            models.Index(fields=["organization", "data_type", "source"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.get_data_type_display()} - {self.source.code}: {self.priority}"
