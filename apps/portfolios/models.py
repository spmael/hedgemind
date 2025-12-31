"""
Portfolio management models.

This module provides models for portfolio management, including portfolios,
position snapshots, and portfolio import tracking. All portfolio data is scoped to
organizations to support multi-tenant isolation.

Key components:
- PortfolioGroup: Simple one-level grouping for portfolios
- Portfolio: Investment portfolio container
- PortfolioImport: Tracks file uploads and import status
- PositionSnapshot: Time-series snapshots of positions (immutable)

All models use OrganizationOwnedModel to ensure automatic organization scoping.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import CurrencyField, MoneyField

from apps.reference_data.models import Instrument, ValuationMethod
from libs.choices import ImportSourceType, ImportStatus
from libs.models import OrganizationOwnedModel


class PortfolioGroup(OrganizationOwnedModel):
    """
    PortfolioGroup model for simple one-level grouping of portfolios.

    Provides grouping capability for portfolios without complex tree structures.
    Useful for organizing portfolios by fund family, client, desk, or strategy.

    Attributes:
        name (str): Group name (max 10 characters, unique per organization).
        description (str, optional): Detailed description.
        created_at (datetime): When the group was created.
        updated_at (datetime): When the group was last updated.

    Example:
        >>> group = PortfolioGroup.objects.create(
        ...     name="TREAS",
        ...     description="Treasury Portfolios"
        ... )
    """

    name = models.CharField(
        _("Name"), max_length=10, help_text="Short name of the group."
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        null=True,
        help_text="Detailed description of the group.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Portfolio Group")
        verbose_name_plural = _("Portfolio Groups")
        indexes = [
            models.Index(fields=["organization", "name"]),
        ]
        unique_together = [("organization", "name")]

    def __str__(self) -> str:
        return self.name


class Portfolio(OrganizationOwnedModel):
    """
    Portfolio model representing an investment portfolio.

    A portfolio is a collection of position snapshots that belong to an
    organization. Portfolios can represent different mandates, strategies, or
    reporting entities within an organization.

    Attributes:
        name (str): Portfolio name.
        full_name (str, optional): Full name of the portfolio.
        base_currency (str): Base currency for reporting and valuation.
        group (PortfolioGroup, optional): Group this portfolio belongs to.
        mandate_type (str, optional): Type of mandate or strategy.
        is_active (bool): Whether this portfolio is currently active.
        created_at (datetime): When the portfolio was created.
        updated_at (datetime): When the portfolio was last updated.

    Example:
        >>> group = PortfolioGroup.objects.get(name="Treasury Portfolios")
        >>> portfolio = Portfolio.objects.create(
        ...     name="Treasury Portfolio A",
        ...     base_currency="XAF",
        ...     group=group,
        ...     mandate_type="Liquidity Management"
        ... )
    """

    name = models.CharField(
        _("Name"), max_length=10, help_text="Short name of the portfolio."
    )
    full_name = models.TextField(
        _("Full Name"),
        blank=True,
        null=True,
        help_text="Full name of the portfolio.",
    )
    base_currency = CurrencyField(
        _("Base Currency"), max_length=3, default=settings.DEFAULT_CURRENCY
    )
    group = models.ForeignKey(
        PortfolioGroup,
        on_delete=models.CASCADE,
        related_name="portfolios",
        help_text="Group this portfolio belongs to.",
    )
    mandate_type = models.CharField(
        _("Mandate Type"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Type of mandate or strategy.",
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text="Whether this portfolio is currently active.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Portfolio")
        verbose_name_plural = _("Portfolios")
        indexes = [
            models.Index(fields=["organization", "name"]),
            models.Index(fields=["organization", "group"]),
            models.Index(fields=["organization", "is_active"]),
        ]
        unique_together = [("organization", "name")]

    def __str__(self) -> str:
        return self.name


class PortfolioImport(OrganizationOwnedModel):
    """
    PortfolioImport model tracking file uploads and import status.

    Tracks the import of portfolio positions from uploaded files (CSV/Excel).
    Stores the file reference, import status, mapping configuration, and
    error information for debugging and user feedback.

    Attributes:
        portfolio (Portfolio): The portfolio being imported into.
        file (FileField): Uploaded file (CSV or Excel).
        as_of_date (date): As-of date for the holdings in this import (required).
        mapping_json (JSONField, optional): Column mapping configuration.
        source_type (str): Source of the import (custodian, internal, manual, external).
        status (str): Current import status (pending, parsing, success, failed, etc.).
        error_message (str, optional): Error message if import failed.
        rows_processed (int): Number of rows successfully processed.
        rows_total (int): Total number of rows in the file.
        inputs_hash (str, optional): Hash of inputs for idempotency checks.
        created_at (datetime): When the import was created.
        completed_at (datetime, optional): When the import completed.

    Example:
        >>> portfolio = Portfolio.objects.get(name="Treasury Portfolio A")
        >>> import_record = PortfolioImport.objects.create(
        ...     portfolio=portfolio,
        ...     file=uploaded_file,
        ...     as_of_date=date.today(),
        ...     source_type=ImportSourceType.CUSTODIAN,
        ...     status=ImportStatus.PENDING
        ... )
    """

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="imports",
        help_text="Portfolio being imported into.",
    )
    file = models.FileField(
        _("File"),
        upload_to="portfolios/imports/%Y/%m/%d/",
        help_text="Uploaded file (CSV or Excel).",
    )
    as_of_date = models.DateField(
        _("As Of Date"), help_text="As-of date for the holdings in this import."
    )
    mapping_json = models.JSONField(
        _("Mapping JSON"),
        blank=True,
        null=True,
        help_text="Column mapping configuration.",
    )
    source_type = models.CharField(
        _("Source Type"),
        max_length=255,
        choices=ImportSourceType.choices,
        default=ImportSourceType.MANUAL,
        help_text="Source of the import.",
    )
    status = models.CharField(
        _("Status"),
        max_length=255,
        choices=ImportStatus.choices,
        default=ImportStatus.PENDING,
        help_text="Current import status.",
    )
    error_message = models.TextField(
        _("Error Message"),
        blank=True,
        null=True,
        help_text="Error message if import failed.",
    )
    rows_processed = models.IntegerField(
        _("Rows Processed"),
        default=0,
        help_text="Number of rows successfully processed.",
    )
    rows_total = models.IntegerField(
        _("Rows Total"), default=0, help_text="Total number of rows in the file."
    )
    inputs_hash = models.CharField(
        _("Inputs Hash"),
        max_length=64,
        blank=True,
        null=True,
        help_text="Hash of inputs for idempotency checks.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    completed_at = models.DateTimeField(
        _("Completed At"), blank=True, null=True, help_text="When the import completed."
    )

    class Meta:
        verbose_name = _("Portfolio Import")
        verbose_name_plural = _("Portfolio Imports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "portfolio"]),
            models.Index(fields=["organization", "as_of_date"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.portfolio.name} - {self.get_status_display()} ({self.as_of_date})"
        )


class ValuationSource(models.TextChoices):
    """Valuation source choices for position snapshots."""

    INTERNAL = "internal", _("Internal")
    EXTERNAL = "external", _("External")
    CUSTODIAN = "custodian", _("Custodian")
    MANUAL = "manual", _("Manual")
    MARKET = "market", _("Market")


class PositionSnapshot(OrganizationOwnedModel):
    """
    PositionSnapshot model representing an immutable time-series snapshot of a position.

    A position snapshot represents a single position (quantity of an instrument) held
    in a portfolio at a specific point in time. Snapshots are immutable and should
    never be edited - new snapshots are created for new dates.

    This model explicitly tracks valuation provenance to support defensible reporting
    to boards, regulators, and auditors. Market value can be stored directly (for messy
    local data) but valuation method and source must be recorded.

    Attributes:
        portfolio (Portfolio): The portfolio this position belongs to.
        portfolio_import (PortfolioImport, optional): The import that created this snapshot.
        instrument (Instrument): The financial instrument being held.
        quantity (decimal): Quantity or number of units held.
        book_value (Money): Book value or cost basis.
        market_value (Money): Market value (may be from messy data, but provenance tracked).
        price (decimal, optional): Price per unit used for valuation.
        accrued_interest (Money, optional): Accrued interest for fixed income instruments.
        valuation_method (str): How this position is valued (from reference_data.ValuationMethod).
        valuation_source (str): Source of the valuation (internal, external, custodian, etc.).
        as_of_date (date): As-of date for this position snapshot.
        last_valuation_date (date, optional): Last date this position was actually valued.
        stale_after_days (int, optional): Number of days after which this is considered stale.
        created_at (datetime): When the snapshot record was created.
        updated_at (datetime): When the snapshot record was last updated.

    Note:
        - Snapshots are immutable - never edit existing snapshots, create new ones.
        - Market value can be stored directly for messy local data, but valuation_method
          and valuation_source must be recorded for defensibility.
        - For deterministic valuation, store price and compute market_value = quantity * price.
        - For manual/external valuations, store market_value directly and record source.

    Example:
        >>> portfolio = Portfolio.objects.get(name="Treasury Portfolio A")
        >>> instrument = Instrument.objects.get(isin="CM1234567890")
        >>> snapshot = PositionSnapshot.objects.create(
        ...     portfolio=portfolio,
        ...     instrument=instrument,
        ...     quantity=1000,
        ...     book_value=Money(1000000, "XAF"),
        ...     market_value=Money(1050000, "XAF"),
        ...     price=105.50,
        ...     valuation_method="mark_to_market",
        ...     valuation_source=ValuationSource.MARKET,
        ...     as_of_date=date.today(),
        ...     last_valuation_date=date.today()
        ... )
    """

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="position_snapshots",
        help_text="Portfolio this position belongs to.",
    )
    portfolio_import = models.ForeignKey(
        PortfolioImport,
        on_delete=models.SET_NULL,
        related_name="position_snapshots",
        help_text="Import that created this snapshot.",
        null=True,
        blank=True,
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="position_snapshots",
        help_text="Instrument this position belongs to.",
    )
    quantity = models.DecimalField(
        _("Quantity"),
        max_digits=20,
        decimal_places=6,
        help_text="Quantity or number of units held.",
    )
    book_price = models.DecimalField(
        _("Book Price"),
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Price per unit used for book value calculation.",
    )
    book_value = MoneyField(
        _("Book Value"),
        max_digits=20,
        decimal_places=6,
        help_text="Book value or cost basis.",
    )
    market_value = MoneyField(
        _("Market Value"), max_digits=20, decimal_places=6, help_text="Market value."
    )
    price = models.DecimalField(
        _("Price"),
        max_digits=20,
        decimal_places=6,
        help_text="Price per unit used for valuation.",
    )
    accrued_interest = MoneyField(
        _("Accrued Interest"),
        max_digits=20,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Accrued interest for fixed income instruments.",
    )
    valuation_method = models.CharField(
        _("Valuation Method"),
        max_length=255,
        choices=ValuationMethod.choices,
        default=ValuationMethod.MARK_TO_MARKET,
        help_text="How this position is valued.",
    )
    valuation_source = models.CharField(
        _("Valuation Source"),
        max_length=20,
        choices=ValuationSource.choices,
        help_text=_("Source of the valuation (internal, external, custodian, etc.)"),
    )
    as_of_date = models.DateField(
        _("As Of Date"),
        help_text=_("As-of date for this position snapshot"),
    )
    last_valuation_date = models.DateField(
        _("Last Valuation Date"),
        blank=True,
        null=True,
        help_text=_(
            "Last date this position was actually valued (useful for private assets & stale NAVs)"
        ),
    )
    stale_after_days = models.IntegerField(
        _("Stale After Days"),
        blank=True,
        null=True,
        help_text=_("Number of days after which this is considered stale (for alerts)"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Position Snapshot")
        verbose_name_plural = _("Position Snapshots")
        indexes = [
            models.Index(fields=["organization", "portfolio", "as_of_date"]),
            models.Index(fields=["organization", "instrument", "as_of_date"]),
            models.Index(fields=["organization", "as_of_date"]),
            models.Index(fields=["portfolio", "as_of_date"]),
        ]
        # Prevent duplicate snapshots - include organization for safety and performance
        constraints = [
            UniqueConstraint(
                fields=["organization", "portfolio", "instrument", "as_of_date"],
                name="uniq_pos_snapshot_org_port_instr_date",
            ),
        ]
        ordering = ["-as_of_date", "portfolio", "instrument"]

    def __str__(self) -> str:
        return f"{self.portfolio.name} - {self.instrument.name} ({self.as_of_date})"
