"""
Price models.

Models for instrument prices, including observations and canonical prices.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import CurrencyField

from apps.reference_data.models.choices import SelectionReason
from libs.choices import ImportStatus


class InstrumentPriceObservation(models.Model):
    """
    InstrumentPriceObservation model representing multi-source raw price observations.

    This is the ETL landing zone where raw price data from various sources is stored.
    Multiple observations can exist for the same instrument/date/price_type from different
    sources. The canonicalization process selects the best observation based on source
    priority and creates a canonical InstrumentPrice record.

    Attributes:
        instrument (Instrument): The instrument this price applies to.
        date (date): Date for which this price is valid.
        price_type (str): Type of price (close, bid, ask, mid, NAV, etc.).
        source (MarketDataSource): The source of this price observation.
        price (decimal): Market price per unit (interpretation depends on quote_convention).
        quote_convention (str): How to interpret the price (PRICE, PERCENT_OF_PAR, YIELD).
        clean_or_dirty (str): Whether price includes accrued interest (CLEAN, DIRTY, NA).
        revision (int): Revision number (0 = initial, 1+ = corrections).
        volume (decimal, optional): Trading volume for the date.
        currency (str, optional): Currency override (if different from instrument currency).
        observed_at (datetime): When this observation was received/recorded.
        created_at (datetime): When the observation record was created.
        updated_at (datetime): When the observation record was last updated.

    Note:
        - This is the raw ETL landing zone - multiple observations per instrument/date are expected.
        - Canonicalization process selects best observation based on source priority.
        - For bonds: typically PERCENT_OF_PAR with CLEAN or DIRTY.
        - For equities: typically PRICE with NA for clean_or_dirty.
        - For mutual funds: typically NAV price_type with PRICE convention.

    Example:
        >>> instrument = Instrument.objects.get(isin="CM1234567890")
        >>> source = MarketDataSource.objects.get(code="BVMAC")
        >>> observation = InstrumentPriceObservation.objects.create(
        ...     instrument=instrument,
        ...     date=date.today(),
        ...     price_type=InstrumentPriceObservation.PriceType.CLOSE,
        ...     source=source,
        ...     price=105.50,
        ...     quote_convention=InstrumentPriceObservation.QuoteConvention.PERCENT_OF_PAR,
        ...     clean_or_dirty=InstrumentPriceObservation.CleanOrDirty.CLEAN,
        ...     revision=0,
        ...     observed_at=timezone.now()
        ... )
    """

    class PriceType(models.TextChoices):
        """Price type choices."""

        CLOSE = "close", _("Close")
        BID = "bid", _("Bid")
        ASK = "ask", _("Ask")
        MID = "mid", _("Mid")
        OPEN = "open", _("Open")
        HIGH = "high", _("High")
        LOW = "low", _("Low")
        NAV = "nav", _("NAV")  # For mutual funds

    class QuoteConvention(models.TextChoices):
        """Quote convention choices - how to interpret the price value."""

        PRICE = "price", _("Price")  # Absolute price (equities, some bonds)
        PERCENT_OF_PAR = "percent_of_par", _(
            "Percent of Par"
        )  # Common for bonds (e.g., 105.50 = 105.5%)
        YIELD = "yield", _(
            "Yield"
        )  # Yield-to-maturity (sometimes provided instead of price)

    class CleanOrDirty(models.TextChoices):
        """Clean or dirty price indicator."""

        CLEAN = "clean", _("Clean")  # Price excludes accrued interest
        DIRTY = "dirty", _("Dirty")  # Price includes accrued interest
        NA = "na", _("N/A")  # Not applicable (equities, funds, deposits)

    instrument = models.ForeignKey(
        "reference_data.Instrument",
        on_delete=models.CASCADE,
        related_name="price_observations",
        verbose_name=_("Instrument"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this price is valid"),
    )
    price_type = models.CharField(
        _("Price Type"),
        max_length=10,
        choices=PriceType.choices,
        default=PriceType.CLOSE,
        help_text=_("Type of price (close, bid, ask, etc.)"),
    )
    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="market_data_observations",
        verbose_name=_("Source"),
    )
    price = models.DecimalField(
        _("Price"),
        max_digits=20,
        decimal_places=6,
        help_text=_(
            "Market price per unit (interpretation depends on quote_convention)"
        ),
    )
    quote_convention = models.CharField(
        _("Quote Convention"),
        max_length=20,
        choices=QuoteConvention.choices,
        default=QuoteConvention.PRICE,
        help_text=_("How to interpret the price (PRICE, PERCENT_OF_PAR, YIELD)"),
    )
    clean_or_dirty = models.CharField(
        _("Clean or Dirty"),
        max_length=10,
        choices=CleanOrDirty.choices,
        default=CleanOrDirty.NA,
        help_text=_("Whether price includes accrued interest (CLEAN, DIRTY, NA)"),
    )
    revision = models.SmallIntegerField(
        _("Revision"),
        default=0,
        help_text=_("Revision number (0 = initial, 1+ = corrections)"),
    )
    volume = models.DecimalField(
        _("Volume"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Trading volume for the date"),
    )
    currency = CurrencyField(
        _("Currency Override"),
        max_length=3,
        blank=True,
        null=True,
        help_text=_("Currency override if different from instrument currency (rare)"),
    )
    observed_at = models.DateTimeField(
        _("Observed At"),
        help_text=_("When this observation was received/recorded"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Instrument Price Observation")
        verbose_name_plural = _("Instrument Price Observations")
        indexes = [
            models.Index(fields=["instrument", "date", "price_type"]),
            models.Index(fields=["date"]),
            models.Index(fields=["source", "date"]),
            models.Index(fields=["observed_at"]),
        ]
        # Multiple observations per instrument/date/price_type/source/revision are allowed
        unique_together = [["instrument", "date", "price_type", "source", "revision"]]
        ordering = ["-date", "instrument", "-observed_at"]

    def __str__(self) -> str:
        return f"{self.instrument.name} - {self.price} from {self.source.code} ({self.date})"


class InstrumentPrice(models.Model):
    """
    InstrumentPrice model representing canonical "chosen" prices for valuation.

    This is the canonical price table used for portfolio valuation. Prices are selected
    from InstrumentPriceObservation based on source priority hierarchy. This table
    stores one price per instrument/date/price_type - the "best" price according to
    the selection policy.

    Attributes:
        instrument (Instrument): The instrument this price applies to.
        date (date): Date for which this price is valid.
        price_type (str): Type of price (close, bid, ask, mid, NAV, etc.).
        chosen_source (MarketDataSource): The source that was selected for this canonical price.
        observation (InstrumentPriceObservation, optional): The observation that was selected.
        price (decimal): Market price per unit (stored directly for performance).
        quote_convention (str): How to interpret the price (PRICE, PERCENT_OF_PAR, YIELD).
        clean_or_dirty (str): Whether price includes accrued interest (CLEAN, DIRTY, NA).
        volume (decimal, optional): Trading volume for the date.
        currency (str, optional): Currency override (if different from instrument currency).
        selection_reason (str): Why this price was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.).
        selected_by (User, optional): User who manually selected this price (if manual override).
        selected_at (datetime): When this price was selected/canonicalized.
        created_at (datetime): When the canonical price record was created.
        updated_at (datetime): When the canonical price record was last updated.

    Note:
        - This is the single source of truth for valuation - only one price per instrument/date/price_type.
        - Prices are selected from observations via canonicalization process.
        - Manual overrides are tracked for audit purposes.
        - For bonds: typically PERCENT_OF_PAR with CLEAN or DIRTY.
        - For equities: typically PRICE with NA for clean_or_dirty.
        - For mutual funds: typically NAV price_type with PRICE convention.
        - Deposits do not use this model (they have principal + accrued interest, not prices).

    Example:
        >>> instrument = Instrument.objects.get(isin="CM1234567890")
        >>> source = MarketDataSource.objects.get(code="BVMAC")
        >>> observation = InstrumentPriceObservation.objects.get(...)
        >>> canonical_price = InstrumentPrice.objects.create(
        ...     instrument=instrument,
        ...     date=date.today(),
        ...     price_type=InstrumentPrice.PriceType.CLOSE,
        ...     chosen_source=source,
        ...     observation=observation,
        ...     price=105.50,
        ...     quote_convention=InstrumentPrice.QuoteConvention.PERCENT_OF_PAR,
        ...     clean_or_dirty=InstrumentPrice.CleanOrDirty.CLEAN,
        ...     selection_reason=SelectionReason.AUTO_POLICY,
        ...     selected_at=timezone.now()
        ... )
    """

    class PriceType(models.TextChoices):
        """Price type choices."""

        CLOSE = "close", _("Close")
        BID = "bid", _("Bid")
        ASK = "ask", _("Ask")
        MID = "mid", _("Mid")
        OPEN = "open", _("Open")
        HIGH = "high", _("High")
        LOW = "low", _("Low")
        NAV = "nav", _("NAV")  # For mutual funds

    class QuoteConvention(models.TextChoices):
        """Quote convention choices - how to interpret the price value."""

        PRICE = "price", _("Price")  # Absolute price (equities, some bonds)
        PERCENT_OF_PAR = "percent_of_par", _(
            "Percent of Par"
        )  # Common for bonds (e.g., 105.50 = 105.5%)
        YIELD = "yield", _(
            "Yield"
        )  # Yield-to-maturity (sometimes provided instead of price)

    class CleanOrDirty(models.TextChoices):
        """Clean or dirty price indicator."""

        CLEAN = "clean", _("Clean")  # Price excludes accrued interest
        DIRTY = "dirty", _("Dirty")  # Price includes accrued interest
        NA = "na", _("N/A")  # Not applicable (equities, funds, deposits)

    instrument = models.ForeignKey(
        "reference_data.Instrument",
        on_delete=models.CASCADE,
        related_name="canonical_prices",
        verbose_name=_("Instrument"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this price is valid"),
    )
    price_type = models.CharField(
        _("Price Type"),
        max_length=10,
        choices=PriceType.choices,
        default=PriceType.CLOSE,
        help_text=_("Type of price (close, bid, ask, etc.)"),
    )
    chosen_source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="canonical_market_data",
        verbose_name=_("Chosen Source"),
        help_text=_("The source that was selected for this canonical price"),
    )
    observation = models.ForeignKey(
        "InstrumentPriceObservation",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="canonical_prices",
        verbose_name=_("Observation"),
        help_text=_("The observation that was selected (optional, for audit trail)"),
    )
    price = models.DecimalField(
        _("Price"),
        max_digits=20,
        decimal_places=6,
        help_text=_("Market price per unit (stored directly for performance)"),
    )
    quote_convention = models.CharField(
        _("Quote Convention"),
        max_length=20,
        choices=QuoteConvention.choices,
        default=QuoteConvention.PRICE,
        help_text=_("How to interpret the price (PRICE, PERCENT_OF_PAR, YIELD)"),
    )
    clean_or_dirty = models.CharField(
        _("Clean or Dirty"),
        max_length=10,
        choices=CleanOrDirty.choices,
        default=CleanOrDirty.NA,
        help_text=_("Whether price includes accrued interest (CLEAN, DIRTY, NA)"),
    )
    volume = models.DecimalField(
        _("Volume"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Trading volume for the date"),
    )
    currency = CurrencyField(
        _("Currency Override"),
        max_length=3,
        blank=True,
        null=True,
        help_text=_("Currency override if different from instrument currency (rare)"),
    )
    selection_reason = models.CharField(
        _("Selection Reason"),
        max_length=30,
        choices=SelectionReason.choices,
        default=SelectionReason.AUTO_POLICY,
        help_text=_("Why this price was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.)"),
    )
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="selected_prices",
        verbose_name=_("Selected By"),
        help_text=_("User who manually selected this price (if manual override)"),
    )
    selected_at = models.DateTimeField(
        _("Selected At"),
        help_text=_("When this price was selected/canonicalized"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Instrument Price")
        verbose_name_plural = _("Instrument Prices")
        indexes = [
            models.Index(fields=["instrument", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["instrument", "date", "price_type"]),
            models.Index(fields=["chosen_source"]),
        ]
        # One canonical price per instrument/date/price_type (global, not org-scoped)
        unique_together = [["instrument", "date", "price_type"]]
        ordering = ["-date", "instrument"]

    def __str__(self) -> str:
        return f"{self.instrument.name} - {self.price} from {self.chosen_source.code} ({self.date})"


class InstrumentPriceImport(models.Model):
    """
    InstrumentPriceImport model tracking file uploads and import status.

    Tracks the import of instrument price data from uploaded Excel files.
    Stores the file reference, import status, and error information.
    Files are stored in media storage (works with local and S3/R2).

    Note: This model is NOT organization-scoped because instrument prices
    are global reference data shared across all organizations.

    Attributes:
        source (MarketDataSource): The market data source (e.g., BVMAC).
        file (FileField): Uploaded Excel file.
        sheet_name (str, optional): Sheet name if file has multiple sheets.
        status (str): Current import status (pending, importing, success, failed).
        error_message (str, optional): Error message if import failed.
        observations_created (int): Number of observations created.
        observations_updated (int): Number of observations updated.
        canonical_prices_created (int): Number of canonical prices created (if canonicalized).
        created_at (datetime): When the import was created.
        completed_at (datetime, optional): When the import completed.
        created_by (User, optional): User who created this import.
    """

    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="instrument_price_imports",
        verbose_name=_("Source"),
        help_text="Market data source (e.g., BVMAC).",
    )
    file = models.FileField(
        _("File"),
        upload_to="market_data/instrument_prices/%Y/%m/",
        help_text="Uploaded Excel file with instrument price data.",
    )
    sheet_name = models.CharField(
        _("Sheet Name"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Sheet name if file has multiple sheets.",
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
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
    observations_created = models.IntegerField(
        _("Observations Created"),
        default=0,
        help_text="Number of observations created.",
    )
    observations_updated = models.IntegerField(
        _("Observations Updated"),
        default=0,
        help_text="Number of observations updated.",
    )
    canonical_prices_created = models.IntegerField(
        _("Canonical Prices Created"),
        default=0,
        help_text="Number of canonical prices created (if canonicalized).",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    completed_at = models.DateTimeField(
        _("Completed At"),
        blank=True,
        null=True,
        help_text="When the import completed.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="instrument_price_imports",
        verbose_name=_("Created By"),
        help_text="User who created this import.",
    )

    class Meta:
        verbose_name = _("Instrument Price Import")
        verbose_name_plural = _("Instrument Price Imports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source.code} - Instrument Prices ({self.get_status_display()})"
