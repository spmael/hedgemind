"""
FX rate models.

Models for foreign exchange rates, including observations, canonical rates, and imports.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.reference_data.models.choices import SelectionReason
from libs.choices import ImportStatus


class FXRateObservation(models.Model):
    """
    FXRateObservation model representing multi-source raw FX rate observations.

    This is the ETL landing zone where raw FX rate data from various sources is stored.
    Multiple observations can exist for the same currency pair/date from different
    sources. The canonicalization process selects the best observation based on source
    priority and creates a canonical FXRate record.

    Attributes:
        base_currency (str): Base currency code (e.g., "XAF").
        quote_currency (str): Quote currency code (e.g., "USD").
        rate (decimal): Exchange rate (1 base = rate quote).
        rate_type (str): Type of FX rate (BUY, SELL, MID, OFFICIAL, FIXING).
        date (date): Date for which this rate is valid.
        source (MarketDataSource): The source of this FX rate observation.
        revision (int): Revision number (0 = initial, 1+ = corrections).
        observed_at (datetime): When this observation was received/recorded.
        created_at (datetime): When the observation record was created.
        updated_at (datetime): When the observation record was last updated.

    Note:
        Rate represents how many units of quote_currency equal 1 unit of base_currency.
        For example, if base=XAF and quote=USD, rate=0.0016 means 1 XAF = 0.0016 USD.
        BUY and SELL rates can be imported and canonicalized into MID rates.

    Example:
        >>> source = MarketDataSource.objects.get(code="BEAC")
        >>> observation = FXRateObservation.objects.create(
        ...     base_currency="XAF",
        ...     quote_currency="USD",
        ...     rate=0.0016,
        ...     rate_type=FXRateObservation.RateType.BUY,
        ...     date=date.today(),
        ...     source=source,
        ...     revision=0,
        ...     observed_at=timezone.now()
        ... )
    """

    class RateType(models.TextChoices):
        """FX rate type choices."""

        BUY = "buy", _("Buy")
        SELL = "sell", _("Sell")
        MID = "mid", _("Mid")
        OFFICIAL = "official", _("Official")
        FIXING = "fixing", _("Fixing")

    base_currency = models.CharField(
        _("Base Currency"),
        max_length=3,
        help_text=_("Base currency code (e.g., 'XAF')"),
    )
    quote_currency = models.CharField(
        _("Quote Currency"),
        max_length=3,
        help_text=_("Quote currency code (e.g., 'USD')"),
    )
    rate = models.DecimalField(
        _("Rate"),
        max_digits=20,
        decimal_places=8,
        help_text=_("Exchange rate (1 base = rate quote)"),
    )
    rate_type = models.CharField(
        _("Rate Type"),
        max_length=20,
        choices=RateType.choices,
        default=RateType.MID,
        help_text=_("Type of FX rate (BUY, SELL, MID, OFFICIAL, FIXING)"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this rate is valid"),
    )
    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="fx_rate_observations",
        verbose_name=_("Source"),
    )
    revision = models.SmallIntegerField(
        _("Revision"),
        default=0,
        help_text=_("Revision number (0 = initial, 1+ = corrections)"),
    )
    observed_at = models.DateTimeField(
        _("Observed At"),
        help_text=_("When this observation was received/recorded"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("FX Rate Observation")
        verbose_name_plural = _("FX Rate Observations")
        indexes = [
            models.Index(fields=["base_currency", "quote_currency", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["source", "date"]),
            models.Index(fields=["observed_at"]),
        ]
        # Multiple observations per currency pair/date/rate_type/source/revision are allowed
        unique_together = [
            [
                "base_currency",
                "quote_currency",
                "date",
                "rate_type",
                "source",
                "revision",
            ]
        ]
        ordering = ["-date", "base_currency", "quote_currency", "-observed_at"]

    def __str__(self) -> str:
        return f"{self.base_currency}/{self.quote_currency} = {self.rate} ({self.rate_type}) from {self.source.code} ({self.date})"


class FXRate(models.Model):
    """
    FXRate model representing canonical "chosen" FX rates for currency conversion.

    This is the canonical FX rate table used for portfolio valuation and currency conversion.
    Rates are selected from FXRateObservation based on source priority hierarchy. This table
    stores one rate per currency pair/date/rate_type - the "best" rate according to the
    selection policy.

    Attributes:
        base_currency (str): Base currency code (e.g., "XAF").
        quote_currency (str): Quote currency code (e.g., "USD").
        rate (decimal): Exchange rate (1 base = rate quote).
        rate_type (str): Type of FX rate (MID, OFFICIAL, FIXING).
        date (date): Date for which this rate is valid.
        chosen_source (MarketDataSource): The source that was selected for this canonical rate.
        observation (FXRateObservation, optional): The observation that was selected.
        selection_reason (str): Why this rate was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.).
        selected_by (User, optional): User who manually selected this rate (if manual override).
        selected_at (datetime): When this rate was selected/canonicalized.
        created_at (datetime): When the canonical rate record was created.
        updated_at (datetime): When the canonical rate record was last updated.

    Note:
        - This is the single source of truth for FX conversion - only one rate per currency pair/date/rate_type.
        - Rates are selected from observations via canonicalization process.
        - Manual overrides are tracked for audit purposes.
        - Selection algorithm: filter by (base_currency, quote_currency, date, rate_type),
          keep active sources only, sort by source priority (asc), revision (desc),
          observed_at (desc), choose first.
        - Constraints: If selection_reason != MANUAL_OVERRIDE, observation must not be null.
          If selection_reason == MANUAL_OVERRIDE, selected_by must not be null.

    Example:
        >>> source = MarketDataSource.objects.get(code="BEAC")
        >>> observation = FXRateObservation.objects.get(...)
        >>> canonical_rate = FXRate.objects.create(
        ...     base_currency="XAF",
        ...     quote_currency="USD",
        ...     rate=0.0016,
        ...     rate_type=FXRate.RateType.MID,
        ...     date=date.today(),
        ...     chosen_source=source,
        ...     observation=observation,
        ...     selection_reason=SelectionReason.AUTO_POLICY,
        ...     selected_at=timezone.now()
        ... )
    """

    class RateType(models.TextChoices):
        """FX rate type choices."""

        MID = "mid", _("Mid")
        OFFICIAL = "official", _("Official")
        FIXING = "fixing", _("Fixing")

    base_currency = models.CharField(
        _("Base Currency"),
        max_length=3,
        help_text=_("Base currency code (e.g., 'XAF')"),
    )
    quote_currency = models.CharField(
        _("Quote Currency"),
        max_length=3,
        help_text=_("Quote currency code (e.g., 'USD')"),
    )
    rate = models.DecimalField(
        _("Rate"),
        max_digits=20,
        decimal_places=8,
        help_text=_("Exchange rate (1 base = rate quote)"),
    )
    rate_type = models.CharField(
        _("Rate Type"),
        max_length=20,
        choices=RateType.choices,
        default=RateType.MID,
        help_text=_("Type of FX rate (BUY, SELL, MID, OFFICIAL, FIXING)"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this rate is valid"),
    )
    chosen_source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="canonical_fx_rates",
        verbose_name=_("Chosen Source"),
        help_text=_("The source that was selected for this canonical rate"),
    )
    observation = models.ForeignKey(
        "FXRateObservation",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="canonical_fx_rates",
        verbose_name=_("Observation"),
        help_text=_("The observation that was selected (optional, for audit trail)"),
    )
    selection_reason = models.CharField(
        _("Selection Reason"),
        max_length=30,
        choices=SelectionReason.choices,
        default=SelectionReason.AUTO_POLICY,
        help_text=_("Why this rate was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.)"),
    )
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="selected_fx_rates",
        verbose_name=_("Selected By"),
        help_text=_("User who manually selected this rate (if manual override)"),
    )
    selected_at = models.DateTimeField(
        _("Selected At"),
        help_text=_("When this rate was selected/canonicalized"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("FX Rate")
        verbose_name_plural = _("FX Rates")
        indexes = [
            models.Index(fields=["base_currency", "quote_currency", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["base_currency"]),
            models.Index(fields=["quote_currency"]),
            models.Index(fields=["rate_type"]),
            models.Index(fields=["chosen_source"]),
        ]
        # One canonical rate per currency pair/date/rate_type (global, not org-scoped)
        constraints = [
            models.UniqueConstraint(
                fields=["base_currency", "quote_currency", "date", "rate_type"],
                name="uniq_fx_rate_currency_pair_date_type",
            ),
        ]
        ordering = ["-date", "base_currency", "quote_currency"]

    def clean(self):
        """
        Validate that canonical rates are always traceable unless explicitly manual override.

        Raises:
            ValidationError: If constraints are violated.
        """
        from django.core.exceptions import ValidationError

        super().clean()

        # If not manual override, observation must exist
        if (
            self.selection_reason != SelectionReason.MANUAL_OVERRIDE
            and not self.observation
        ):
            raise ValidationError(
                {
                    "observation": "Observation is required when selection_reason is not MANUAL_OVERRIDE."
                }
            )

        # If manual override, selected_by must exist
        if (
            self.selection_reason == SelectionReason.MANUAL_OVERRIDE
            and not self.selected_by
        ):
            raise ValidationError(
                {
                    "selected_by": "Selected by user is required when selection_reason is MANUAL_OVERRIDE."
                }
            )

        # If observation exists, validate source consistency
        if self.observation and self.chosen_source != self.observation.source:
            raise ValidationError(
                {
                    "chosen_source": "Chosen source must match observation source when observation is provided."
                }
            )

    def save(self, *args, **kwargs):
        """Override save to ensure clean() is called."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.base_currency}/{self.quote_currency} = {self.rate} ({self.rate_type}) from {self.chosen_source.code} ({self.date})"


class FXRateImport(models.Model):
    """
    FXRateImport model tracking file uploads and import status.

    Tracks the import of FX rate data from uploaded Excel files.
    Stores the file reference, import status, and error information.
    Files are stored in media storage (works with local and S3/R2).

    Note: This model is NOT organization-scoped because FX rates
    are global reference data shared across all organizations.

    Attributes:
        source (MarketDataSource): The market data source (e.g., BEAC).
        file (FileField): Uploaded Excel file.
        sheet_name (str, optional): Sheet name if file has multiple sheets.
        status (str): Current import status (pending, importing, success, failed).
        error_message (str, optional): Error message if import failed.
        observations_created (int): Number of observations created.
        observations_updated (int): Number of observations updated.
        canonical_rates_created (int): Number of canonical rates created (if canonicalized).
        created_at (datetime): When the import was created.
        completed_at (datetime, optional): When the import completed.
        created_by (User, optional): User who created this import.
    """

    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="fx_rate_imports",
        verbose_name=_("Source"),
        help_text="Market data source (e.g., BEAC).",
    )
    file = models.FileField(
        _("File"),
        upload_to="market_data/fx_rates/%Y/%m/",
        help_text="Uploaded Excel file with FX rate data.",
    )
    sheet_name = models.CharField(
        _("Sheet Name"),
        max_length=255,
        blank=True,
        null=True,
        default="FX_RATES",
        help_text="Sheet name if file has multiple sheets. Defaults to 'FX_RATES'.",
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
    canonical_rates_created = models.IntegerField(
        _("Canonical Rates Created"),
        default=0,
        help_text="Number of canonical rates created (if canonicalized).",
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
        related_name="fx_rate_imports",
        verbose_name=_("Created By"),
        help_text="User who created this import.",
    )

    class Meta:
        verbose_name = _("FX Rate Import")
        verbose_name_plural = _("FX Rate Imports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source.code} - FX Rates ({self.get_status_display()})"
