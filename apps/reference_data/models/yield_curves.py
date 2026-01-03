"""
Yield curve models.

Models for yield curves, yield curve points, and yield curve imports.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from djmoney.models.fields import CurrencyField

from apps.reference_data.models.choices import SelectionReason, YieldCurveType
from libs.choices import ImportStatus


class YieldCurve(models.Model):
    """
    YieldCurve model representing a named yield curve.

    Groups yield curve points into named curves (e.g., "Government Curve", "Swap Curve").
    Each curve has a type (GOVT, SWAP, etc.) and a currency. Points reference the curve,
    not the currency directly, to ensure consistency.

    Attributes:
        name (str): Human-readable name of the yield curve (e.g., "XAF Government Curve").
        curve_type (str): Type of curve (GOVT, SWAP, OIS, CORPORATE, POLICY).
        currency (str): Currency code for this curve.
        description (str, optional): Description of the curve.
        is_active (bool): Whether this curve is currently active.
        last_observation_date (date, optional): Date of the most recent observation for this curve.
            Automatically maintained during canonicalization as max(point.date) for all canonical points.
        staleness_days (int, optional): Number of days since last_observation_date (computed property).
            This is the primary indicator for curve staleness in stress narratives.
        created_at (datetime): When the curve record was created.
        updated_at (datetime): When the curve record was last updated.

    Example:
        >>> curve = YieldCurve.objects.create(
        ...     name="XAF Government Curve",
        ...     curve_type=YieldCurveType.GOVT,
        ...     currency="XAF",
        ...     description="Government bond yield curve"
        ... )
    """

    name = models.CharField(
        _("Name"),
        max_length=100,
        help_text=_(
            "Human-readable name of the yield curve (e.g., 'XAF Government Curve')"
        ),
    )
    curve_type = models.CharField(
        _("Curve Type"),
        max_length=20,
        choices=YieldCurveType.choices,
        help_text=_("Type of curve (GOVT, SWAP, OIS, CORPORATE, POLICY)"),
    )
    currency = CurrencyField(
        _("Currency"),
        max_length=3,
        help_text=_("Currency code for this curve"),
    )
    country = CountryField(
        _("Country"),
        help_text=_("Country for this curve"),
    )
    description = models.TextField(_("Description"), blank=True, null=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    last_observation_date = models.DateField(
        _("Last Observation Date"),
        blank=True,
        null=True,
        help_text=_("Date of the most recent observation for this curve"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Yield Curve")
        verbose_name_plural = _("Yield Curves")
        indexes = [
            models.Index(fields=["currency", "curve_type"]),
            models.Index(fields=["currency"]),
            models.Index(fields=["curve_type"]),
        ]
        unique_together = [["currency", "name"]]

    def __str__(self) -> str:
        return f"{self.name} ({self.currency})"

    @property
    def staleness_days(self) -> int | None:
        """
        Compute staleness in days from last_observation_date.

        Returns:
            int: Number of days since last_observation_date, or None if last_observation_date is None.
        """
        if self.last_observation_date is None:
            return None
        today = date.today()
        delta = today - self.last_observation_date
        return delta.days


class YieldCurvePointObservation(models.Model):
    """
    YieldCurvePointObservation model representing multi-source raw yield curve observations.

    This is the ETL landing zone where raw yield curve data from various sources is stored.
    Multiple observations can exist for the same curve/tenor/date from different sources.
    The canonicalization process selects the best observation based on source priority
    and creates a canonical YieldCurvePoint record.

    Attributes:
        curve (YieldCurve): The yield curve this observation belongs to.
        tenor (str): Tenor description for display (e.g., "1M", "3M", "1Y", "5Y", "10Y").
        tenor_days (int): Tenor in days (e.g., 30 for 1M, 365 for 1Y, 1825 for 5Y) - REQUIRED.
        rate (decimal): Interest rate as percentage (e.g., 5.50 for 5.5%).
        date (date): Date for which this yield point is valid.
        source (MarketDataSource): The source of this yield curve observation.
        revision (int): Revision number (0 = initial, 1+ = corrections).
        observed_at (datetime): When this observation was received/recorded.
        created_at (datetime): When the observation record was created.
        updated_at (datetime): When the observation record was last updated.

    Note:
        - Currency comes from curve.currency, not stored here to avoid inconsistency.
        - tenor_days is the key field for uniqueness and indexing (not tenor string).
        - Rate is stored as a percentage (e.g., 5.50 for 5.5%). For calculations, divide by 100.

    Example:
        >>> curve = YieldCurve.objects.get(name="XAF Government Curve")
        >>> source = MarketDataSource.objects.get(code="BEAC")
        >>> observation = YieldCurvePointObservation.objects.create(
        ...     curve=curve,
        ...     tenor="5Y",
        ...     tenor_days=1825,
        ...     rate=5.50,
        ...     date=date.today(),
        ...     source=source,
        ...     revision=0,
        ...     observed_at=timezone.now()
        ... )
    """

    curve = models.ForeignKey(
        "YieldCurve",
        on_delete=models.CASCADE,
        related_name="point_observations",
        verbose_name=_("Curve"),
        help_text=_("The yield curve this observation belongs to"),
    )
    tenor = models.CharField(
        _("Tenor"),
        max_length=10,
        help_text=_(
            "Tenor description for display (e.g., '1M', '3M', '1Y', '5Y', '10Y')"
        ),
    )
    tenor_days = models.IntegerField(
        _("Tenor Days"),
        help_text=_(
            "Tenor in days (e.g., 30 for 1M, 365 for 1Y, 1825 for 5Y) - REQUIRED"
        ),
    )
    rate = models.DecimalField(
        _("Rate"),
        max_digits=8,
        decimal_places=4,
        help_text=_("Interest rate as percentage (e.g., 5.50 for 5.5%)"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this yield point is valid"),
    )
    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="yield_curve_observations",
        verbose_name=_("Source"),
    )
    revision = models.SmallIntegerField(
        _("Revision"),
        default=0,
        help_text=_("Revision number (0 = initial, 1+ = corrections)"),
    )
    observed_at = models.DateTimeField(
        _("Observed At"),
        blank=True,
        null=True,
        help_text=_("When this observation was received/recorded (optional)"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Yield Curve Point Observation")
        verbose_name_plural = _("Yield Curve Point Observations")
        indexes = [
            models.Index(fields=["curve", "tenor_days", "date"]),
            models.Index(fields=["curve", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["source", "date"]),
            models.Index(fields=["observed_at"]),
        ]
        # Multiple observations per curve/tenor_days/date/source/revision are allowed
        unique_together = [["curve", "tenor_days", "date", "source", "revision"]]
        ordering = ["-date", "curve", "tenor_days", "-observed_at"]

    def __str__(self) -> str:
        return f"{self.curve.name} {self.tenor} = {self.rate}% from {self.source.code} ({self.date})"


class YieldCurvePoint(models.Model):
    """
    YieldCurvePoint model representing canonical "chosen" yield curve points.

    This is the canonical yield curve table used for fixed income valuation and duration/DV01
    calculations. Points are selected from YieldCurvePointObservation based on source priority
    hierarchy. This table stores one point per curve/tenor_days/date - the "best" point according
    to the selection policy.

    Attributes:
        curve (YieldCurve): The yield curve this point belongs to (REQUIRED).
        tenor (str): Tenor description for display (e.g., "1M", "3M", "1Y", "5Y", "10Y").
        tenor_days (int): Tenor in days (e.g., 30 for 1M, 365 for 1Y, 1825 for 5Y) - REQUIRED.
        rate (decimal): Interest rate as percentage (e.g., 5.50 for 5.5%).
        date (date): Date for which this yield point is valid (curve_date).
        chosen_source (MarketDataSource): The source that was selected for this canonical point.
        observation (YieldCurvePointObservation, optional): The observation that was selected.
        selection_reason (str): Why this point was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.).
        selected_by (User, optional): User who manually selected this point (if manual override).
        selected_at (datetime): When this point was selected/canonicalized.
        last_published_date (date, optional): Date when the source published this data.
            If not provided, defaults to curve_date (date) and published_date_assumed is set to True.
        published_date_assumed (bool): Whether last_published_date was assumed to equal curve_date
            because publication date was not provided by the source.
        is_official (bool): Whether this is official data (e.g., from BEAC central bank).
        staleness_days (int, optional): Number of days since last_published_date (computed property).
        created_at (datetime): When the canonical point record was created.
        updated_at (datetime): When the canonical point record was last updated.

    Note:
        - Currency comes from curve.currency, not stored here to avoid inconsistency.
        - This is the single source of truth for yield curves - only one point per curve/tenor_days/date.
        - Points are selected from observations via canonicalization process.
        - Manual overrides are tracked for audit purposes.
        - Rate is stored as a percentage (e.g., 5.50 for 5.5%). For calculations, divide by 100.
        - Selection algorithm: filter by (curve, tenor_days, date), keep active sources only,
          sort by source priority (asc), revision (desc), observed_at (desc), choose first.
        - Published date assumption: If source does not provide publication date, last_published_date
          defaults to curve_date (date) and published_date_assumed is set to True. This is explicit,
          not implicit - the assumption is always recorded.
        - For data quality narratives, use curve-level staleness (YieldCurve.staleness_days) as the
          primary indicator. Point-level last_published_date is for audit/detail purposes.

    Example:
        >>> curve = YieldCurve.objects.get(name="XAF Government Curve")
        >>> source = MarketDataSource.objects.get(code="BEAC")
        >>> observation = YieldCurvePointObservation.objects.get(...)
        >>> canonical_point = YieldCurvePoint.objects.create(
        ...     curve=curve,
        ...     tenor="5Y",
        ...     tenor_days=1825,
        ...     rate=5.50,
        ...     date=date.today(),
        ...     chosen_source=source,
        ...     observation=observation,
        ...     selection_reason=SelectionReason.AUTO_POLICY,
        ...     selected_at=timezone.now()
        ... )
    """

    curve = models.ForeignKey(
        "YieldCurve",
        on_delete=models.CASCADE,
        related_name="points",
        verbose_name=_("Curve"),
        help_text=_("The yield curve this point belongs to (REQUIRED)"),
    )
    tenor = models.CharField(
        _("Tenor"),
        max_length=10,
        help_text=_(
            "Tenor description for display (e.g., '1M', '3M', '1Y', '5Y', '10Y')"
        ),
    )
    tenor_days = models.IntegerField(
        _("Tenor Days"),
        help_text=_(
            "Tenor in days (e.g., 30 for 1M, 365 for 1Y, 1825 for 5Y) - REQUIRED"
        ),
    )
    rate = models.DecimalField(
        _("Rate"),
        max_digits=8,
        decimal_places=4,
        help_text=_("Interest rate as percentage (e.g., 5.50 for 5.5%)"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this yield point is valid"),
    )
    chosen_source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="canonical_yield_curve_points",
        verbose_name=_("Source"),
        help_text=_("The source that was selected for this canonical point"),
    )
    observation = models.ForeignKey(
        "YieldCurvePointObservation",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="canonical_points",
        verbose_name=_("Observation"),
        help_text=_("The observation that was selected (optional, for audit trail)"),
    )
    selection_reason = models.CharField(
        _("Selection Reason"),
        max_length=30,
        choices=SelectionReason.choices,
        default=SelectionReason.AUTO_POLICY,
        help_text=_("Why this point was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.)"),
    )
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="selected_yield_curve_points",
        verbose_name=_("Selected By"),
        help_text=_("User who manually selected this point (if manual override)"),
    )
    selected_at = models.DateTimeField(
        _("Selected At"),
        help_text=_("When this point was selected/canonicalized"),
    )
    last_published_date = models.DateField(
        _("Last Published Date"),
        blank=True,
        null=True,
        help_text=_(
            "Date when the source published this data (for staleness tracking). "
            "If not provided, defaults to curve_date (date) and published_date_assumed is set to True."
        ),
    )
    published_date_assumed = models.BooleanField(
        _("Published Date Assumed"),
        default=False,
        help_text=_(
            "Whether last_published_date was assumed to equal curve_date (date) "
            "because publication date was not provided by the source."
        ),
    )
    is_official = models.BooleanField(
        _("Is Official"),
        default=True,
        help_text=_("Whether this is official data (e.g., from BEAC central bank)"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Yield Curve Point")
        verbose_name_plural = _("Yield Curve Points")
        indexes = [
            models.Index(fields=["curve", "tenor_days", "date"]),
            models.Index(fields=["curve", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["chosen_source"]),
            models.Index(fields=["last_published_date"]),
            models.Index(fields=["is_official", "last_published_date"]),
            models.Index(fields=["published_date_assumed"]),
        ]
        # One canonical point per curve/tenor_days/date (global, not org-scoped)
        constraints = [
            models.UniqueConstraint(
                fields=["curve", "tenor_days", "date"],
                name="uniq_curve_tenor_days_date",
            ),
        ]
        ordering = ["-date", "curve", "tenor_days"]

    def __str__(self) -> str:
        return f"{self.curve.name} {self.tenor} = {self.rate}% from {self.chosen_source.code} ({self.date})"

    @property
    def curve_date(self) -> date:
        """
        Alias for date field (curve_date for clarity in stress narratives).

        Returns:
            date: The date for which this yield point is valid.
        """
        return self.date

    @property
    def staleness_days(self) -> int | None:
        """
        Compute staleness in days from last_published_date.

        This enables data-quality-aware stress narratives by tracking how stale
        the curve data is when used in stress scenarios.

        Returns:
            int: Number of days since last_published_date, or None if last_published_date is None.
        """
        if self.last_published_date is None:
            return None
        today = date.today()
        delta = today - self.last_published_date
        return delta.days


class YieldCurveImport(models.Model):
    """
    YieldCurveImport model tracking file uploads and import status.

    Tracks the import of yield curve data from uploaded Excel files.
    Stores the file reference, import status, and error information.
    Files are stored in media storage (works with local and S3/R2).

    Note: This model is NOT organization-scoped because yield curves
    are global reference data shared across all organizations.

    Attributes:
        source (MarketDataSource): The market data source (e.g., BEAC).
        curve (YieldCurve, optional): Specific curve to import (if None, imports all curves in file).
        file (FileField): Uploaded Excel file.
        sheet_name (str, optional): Sheet name if file has multiple sheets.
        status (str): Current import status (pending, importing, success, failed).
        error_message (str, optional): Error message if import failed.
        observations_created (int): Number of observations created.
        observations_updated (int): Number of observations updated.
        canonical_points_created (int): Number of canonical points created (if canonicalized).
        created_at (datetime): When the import was created.
        completed_at (datetime, optional): When the import completed.
        created_by (User, optional): User who created this import.
    """

    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="yield_curve_imports",
        verbose_name=_("Source"),
        help_text="Market data source (e.g., BEAC).",
    )
    curve = models.ForeignKey(
        "YieldCurve",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="imports",
        verbose_name=_("Curve"),
        help_text="Specific curve to import (if None, imports all curves in file).",
    )
    file = models.FileField(
        _("File"),
        upload_to="market_data/yield_curves/%Y/%m/",
        help_text="Uploaded Excel file with yield curve data.",
    )
    sheet_name = models.CharField(
        _("Sheet Name"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Sheet name if file has multiple sheets (e.g., 'CM', 'GA', 'CG').",
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
    canonical_points_created = models.IntegerField(
        _("Canonical Points Created"),
        default=0,
        help_text="Number of canonical points created (if canonicalized).",
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
        related_name="yield_curve_imports",
        verbose_name=_("Created By"),
        help_text="User who created this import.",
    )

    class Meta:
        verbose_name = _("Yield Curve Import")
        verbose_name_plural = _("Yield Curve Imports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["curve", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        curve_name = self.curve.name if self.curve else "All Curves"
        return f"{self.source.code} - {curve_name} ({self.get_status_display()})"


class YieldCurveStressProfile(models.Model):
    """
    Yield curve stress profile for stress testing.

    Stores calibrated stress inputs (haircut bands) derived from historical
    stress narratives. These profiles are used by the stress engine to apply
    haircuts to portfolio holdings during stress scenarios.

    Attributes:
        curve: YieldCurve this profile applies to.
        narrative: Narrative type (e.g., "gradual_deterioration", "acute_sovereign_stress").
        period_start: Start date of historical period this profile is based on.
        period_end: End date of historical period.
        regime_type: Regime classification (normal, rising_stress, high_stress, etc.).
        sovereign_haircut_pct: Haircut percentage for sovereign issuers.
        corporate_haircut_pct: Haircut percentage for corporate issuers.
        supra_haircut_pct: Haircut percentage for supranational issuers.
        calibration_rationale: Explanation of how haircuts were calibrated.
        last_observation_date: Last observation date from YieldCurve (for staleness tracking).
        staleness_days: Computed staleness in days.
        is_active: Whether this profile is currently active.

    Note:
        This is derived reference data, not portfolio-specific. Profiles are
        reusable across stress runs, reports, and future pricing work.
    """

    curve = models.ForeignKey(
        "YieldCurve",
        on_delete=models.CASCADE,
        related_name="stress_profiles",
        verbose_name=_("Curve"),
        help_text=_("Yield curve this stress profile applies to."),
    )
    narrative = models.CharField(
        _("Narrative"),
        max_length=50,
        help_text=_(
            "Stress narrative type (e.g., 'gradual_deterioration', 'acute_sovereign_stress')."
        ),
    )
    period_start = models.DateField(
        _("Period Start"),
        help_text=_("Start date of historical period this profile is based on."),
    )
    period_end = models.DateField(
        _("Period End"),
        help_text=_("End date of historical period."),
    )
    regime_type = models.CharField(
        _("Regime Type"),
        max_length=30,
        help_text=_(
            "Regime classification (normal, rising_stress, high_stress, etc.)."
        ),
    )
    sovereign_haircut_pct = models.DecimalField(
        _("Sovereign Haircut %"),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_("Haircut percentage for sovereign issuers (0-100)."),
    )
    corporate_haircut_pct = models.DecimalField(
        _("Corporate Haircut %"),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_("Haircut percentage for corporate issuers (0-100)."),
    )
    supra_haircut_pct = models.DecimalField(
        _("Supranational Haircut %"),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_("Haircut percentage for supranational issuers (0-100)."),
    )
    calibration_rationale = models.TextField(
        _("Calibration Rationale"),
        help_text=_(
            "Explanation of how haircuts were calibrated from historical narrative."
        ),
    )
    last_observation_date = models.DateField(
        _("Last Observation Date"),
        blank=True,
        null=True,
        help_text=_("Last observation date from YieldCurve (for staleness tracking)."),
    )
    staleness_days = models.IntegerField(
        _("Staleness Days"),
        blank=True,
        null=True,
        help_text=_("Computed staleness in days (from last_observation_date)."),
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_("Whether this profile is currently active for stress testing."),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Yield Curve Stress Profile")
        verbose_name_plural = _("Yield Curve Stress Profiles")
        ordering = ["-period_end", "-created_at"]
        indexes = [
            models.Index(fields=["curve", "is_active"]),
            models.Index(fields=["narrative", "is_active"]),
            models.Index(fields=["regime_type"]),
            models.Index(fields=["period_start", "period_end"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    sovereign_haircut_pct__gte=0, sovereign_haircut_pct__lte=100
                ),
                name="valid_sovereign_haircut",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    corporate_haircut_pct__gte=0, corporate_haircut_pct__lte=100
                ),
                name="valid_corporate_haircut",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    supra_haircut_pct__gte=0, supra_haircut_pct__lte=100
                ),
                name="valid_supra_haircut",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.curve.name} - {self.narrative} ({self.period_start} to {self.period_end})"

    def save(self, *args, **kwargs):
        """Update staleness_days from curve's last_observation_date."""
        if self.curve and self.curve.last_observation_date:
            self.last_observation_date = self.curve.last_observation_date
            if self.last_observation_date:
                from datetime import date

                self.staleness_days = (date.today() - self.last_observation_date).days
        super().save(*args, **kwargs)
