"""
Market index models.

Models for market indices, including observations, canonical values, constituents, and imports.

Market indices (e.g., BVMAC Index) are market indicators used for benchmarking
and performance comparison. They are NOT instrument prices and do not value
individual holdings. They follow the observation → canonical pattern similar
to FX rates and yield curves.

Index constituents track which instruments are in an index and their weights
over time. This is reference/metadata used for benchmark replication, exposure
analysis, and performance attribution. Constituents do NOT replace InstrumentPrice -
you still need prices separately to value portfolios or compute index returns.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import CurrencyField

from apps.reference_data.models.choices import SelectionReason
from libs.choices import ImportStatus


class MarketIndex(models.Model):
    """
    MarketIndex model representing a named market index.

    Market indices are market indicators used for benchmarking, performance comparison,
    and macro context. Examples include BVMAC Index, S&P 500, etc. They are NOT
    instrument prices and do not value individual holdings.

    Attributes:
        code (str): Short code for the index (e.g., "BVMAC", "SP500").
        name (str): Full name of the index (e.g., "BVMAC Index", "S&P 500").
        currency (str): Currency code for this index.
        description (str, optional): Description of the index.
        base_date (date, optional): Base date for the index (when it started or was rebased).
        base_value (decimal, optional): Base value for the index (e.g., 100.0, 1000.0).
        is_active (bool): Whether this index is currently active.
        created_at (datetime): When the index record was created.
        updated_at (datetime): When the index record was last updated.

    Example:
        >>> index = MarketIndex.objects.create(
        ...     code="BVMAC",
        ...     name="BVMAC Index",
        ...     currency="XAF",
        ...     description="Douala Stock Exchange Market Index",
        ...     base_date=date(2010, 1, 1),
        ...     base_value=100.0
        ... )

    Note:
        Indices describe the market; prices value portfolios. This separation
        avoids serious conceptual and audit mistakes later.
    """

    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        help_text=_("Short code for the index (e.g., 'BVMAC', 'SP500')"),
    )
    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text=_("Full name of the index (e.g., 'BVMAC Index', 'S&P 500')"),
    )
    currency = CurrencyField(
        _("Currency"),
        max_length=3,
        help_text=_("Currency code for this index"),
    )
    description = models.TextField(_("Description"), blank=True, null=True)
    base_date = models.DateField(
        _("Base Date"),
        blank=True,
        null=True,
        help_text=_("Base date for the index (when it started or was rebased)"),
    )
    base_value = models.DecimalField(
        _("Base Value"),
        max_digits=20,
        decimal_places=6,
        blank=True,
        null=True,
        help_text=_("Base value for the index (e.g., 100.0, 1000.0)"),
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Market Index")
        verbose_name_plural = _("Market Indices")
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["currency"]),
            models.Index(fields=["is_active"]),
        ]
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class MarketIndexConstituent(models.Model):
    """
    MarketIndexConstituent model representing time-versioned index constituents.

    Tracks which instruments are included in an index and their weights at a given point in time.
    This is reference/metadata data used for:
    - Portfolio benchmark replication / "index-like" portfolio construction
    - Sector/country exposure analysis based on index membership
    - Index weights for performance attribution
    - Understanding index composition over time

    Attributes:
        index (MarketIndex): The market index this constituent belongs to.
        instrument (Instrument): The instrument that is a constituent of the index.
        as_of_date (date): Date when this constituent/weight is effective (time-versioned).
        weight (decimal): Weight of this instrument in the index (as percentage, e.g., 5.5 for 5.5%).
        shares (decimal, optional): Number of shares/units if provided by source.
        float_shares (decimal, optional): Float-adjusted shares if provided by source.
        source (MarketDataSource, optional): Source of this constituent data.
        created_at (datetime): When the constituent record was created.
        updated_at (datetime): When the constituent record was last updated.

    Note:
        - Constituents are time-versioned: same instrument can have different weights on different dates.
        - This is reference/metadata, NOT pricing data.
        - You still need InstrumentPrice separately to value portfolios or compute index returns.
        - For MVP: store constituents monthly/quarterly (when index is rebalanced).
        - Weights are stored as percentages (e.g., 5.5 for 5.5%).

    Example:
        >>> index = MarketIndex.objects.get(code="BVMAC")
        >>> instrument = Instrument.objects.get(isin="CM1234567890")
        >>> constituent = MarketIndexConstituent.objects.create(
        ...     index=index,
        ...     instrument=instrument,
        ...     as_of_date=date(2024, 1, 1),
        ...     weight=5.5,
        ...     shares=1000000,
        ...     source=MarketDataSource.objects.get(code="BVMAC")
        ... )
    """

    index = models.ForeignKey(
        "MarketIndex",
        on_delete=models.CASCADE,
        related_name="constituents",
        verbose_name=_("Index"),
        help_text=_("The market index this constituent belongs to"),
    )
    instrument = models.ForeignKey(
        "reference_data.Instrument",
        on_delete=models.CASCADE,
        related_name="index_constituents",
        verbose_name=_("Instrument"),
        help_text=_("The instrument that is a constituent of the index"),
    )
    as_of_date = models.DateField(
        _("As Of Date"),
        help_text=_("Date when this constituent/weight is effective (time-versioned)"),
    )
    weight = models.DecimalField(
        _("Weight"),
        max_digits=10,
        decimal_places=4,
        help_text=_(
            "Weight of this instrument in the index (as percentage, e.g., 5.5 for 5.5%)"
        ),
    )
    shares = models.DecimalField(
        _("Shares"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Number of shares/units if provided by source"),
    )
    float_shares = models.DecimalField(
        _("Float Shares"),
        max_digits=20,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Float-adjusted shares if provided by source"),
    )
    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="index_constituents",
        verbose_name=_("Source"),
        help_text=_("Source of this constituent data (optional)"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Market Index Constituent")
        verbose_name_plural = _("Market Index Constituents")
        indexes = [
            models.Index(fields=["index", "as_of_date"]),
            models.Index(fields=["instrument", "as_of_date"]),
            models.Index(fields=["as_of_date"]),
        ]
        # One constituent per index/instrument/as_of_date combination
        unique_together = [["index", "instrument", "as_of_date"]]
        ordering = ["-as_of_date", "index", "-weight"]

    def __str__(self) -> str:
        return f"{self.index.code} - {self.instrument.name} ({self.weight}%) as of {self.as_of_date}"


class MarketIndexValueObservation(models.Model):
    """
    MarketIndexValueObservation model representing multi-source raw index value observations.

    This is the ETL landing zone where raw index data from various sources is stored.
    Multiple observations can exist for the same index/date from different sources.
    The canonicalization process selects the best observation based on source priority
    and creates a canonical MarketIndexValue record.

    Attributes:
        index (MarketIndex): The market index this observation applies to.
        date (date): Date for which this index value is valid.
        value (decimal): Index level/value on this date.
        return_pct (decimal, optional): Daily return as percentage (if provided by source).
        source (MarketDataSource): The source of this index observation.
        revision (int): Revision number (0 = initial, 1+ = corrections).
        observed_at (datetime): When this observation was received/recorded.
        created_at (datetime): When the observation record was created.
        updated_at (datetime): When the observation record was last updated.

    Note:
        - This is the raw ETL landing zone - multiple observations per index/date are expected.
        - Canonicalization process selects best observation based on source priority.
        - Value is the index level (e.g., 105.50, 2500.75).
        - Return percentage is optional and can be calculated from consecutive values if needed.

    Example:
        >>> index = MarketIndex.objects.get(code="BVMAC")
        >>> source = MarketDataSource.objects.get(code="BVMAC")
        >>> observation = MarketIndexValueObservation.objects.create(
        ...     index=index,
        ...     date=date.today(),
        ...     value=105.50,
        ...     return_pct=0.5,
        ...     source=source,
        ...     revision=0,
        ...     observed_at=timezone.now()
        ... )
    """

    index = models.ForeignKey(
        "MarketIndex",
        on_delete=models.CASCADE,
        related_name="value_observations",
        verbose_name=_("Index"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this index value is valid"),
    )
    value = models.DecimalField(
        _("Value"),
        max_digits=20,
        decimal_places=6,
        help_text=_("Index level/value on this date"),
    )
    return_pct = models.DecimalField(
        _("Return %"),
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        help_text=_("Daily return as percentage (if provided by source)"),
    )
    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="index_value_observations",
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
        verbose_name = _("Market Index Value Observation")
        verbose_name_plural = _("Market Index Value Observations")
        indexes = [
            models.Index(fields=["index", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["source", "date"]),
            models.Index(fields=["observed_at"]),
        ]
        # Multiple observations per index/date/source/revision are allowed
        unique_together = [["index", "date", "source", "revision"]]
        ordering = ["-date", "index", "-observed_at"]

    def __str__(self) -> str:
        return f"{self.index.code} = {self.value} from {self.source.code} ({self.date})"


class MarketIndexValue(models.Model):
    """
    MarketIndexValue model representing canonical "chosen" index values for benchmarking.

    This is the canonical index value table used for benchmarking and performance comparison.
    Values are selected from MarketIndexValueObservation based on source priority hierarchy.
    This table stores one value per index/date - the "best" value according to the
    selection policy.

    Attributes:
        index (MarketIndex): The market index this value applies to.
        date (date): Date for which this index value is valid.
        chosen_source (MarketDataSource): The source that was selected for this canonical value.
        observation (MarketIndexValueObservation, optional): The observation that was selected.
        value (decimal): Index level/value on this date (stored directly for performance).
        return_pct (decimal, optional): Daily return as percentage.
        selection_reason (str): Why this value was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.).
        selected_by (User, optional): User who manually selected this value (if manual override).
        selected_at (datetime): When this value was selected/canonicalized.
        created_at (datetime): When the canonical value record was created.
        updated_at (datetime): When the canonical value record was last updated.

    Note:
        - This is the single source of truth for benchmarking - only one value per index/date.
        - Values are selected from observations via canonicalization process.
        - Manual overrides are tracked for audit purposes.
        - Used for benchmarking, performance comparison, and macro context.
        - NOT used to value individual holdings (that's what InstrumentPrice is for).

    Example:
        >>> index = MarketIndex.objects.get(code="BVMAC")
        >>> source = MarketDataSource.objects.get(code="BVMAC")
        >>> observation = MarketIndexValueObservation.objects.get(...)
        >>> canonical_value = MarketIndexValue.objects.create(
        ...     index=index,
        ...     date=date.today(),
        ...     chosen_source=source,
        ...     observation=observation,
        ...     value=105.50,
        ...     return_pct=0.5,
        ...     selection_reason=SelectionReason.AUTO_POLICY,
        ...     selected_at=timezone.now()
        ... )
    """

    index = models.ForeignKey(
        "MarketIndex",
        on_delete=models.CASCADE,
        related_name="canonical_values",
        verbose_name=_("Index"),
    )
    date = models.DateField(
        _("Date"),
        help_text=_("Date for which this index value is valid"),
    )
    chosen_source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="canonical_index_values",
        verbose_name=_("Chosen Source"),
        help_text=_("The source that was selected for this canonical value"),
    )
    observation = models.ForeignKey(
        "MarketIndexValueObservation",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="canonical_values",
        verbose_name=_("Observation"),
        help_text=_("The observation that was selected (optional, for audit trail)"),
    )
    value = models.DecimalField(
        _("Value"),
        max_digits=20,
        decimal_places=6,
        help_text=_("Index level/value on this date (stored directly for performance)"),
    )
    return_pct = models.DecimalField(
        _("Return %"),
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        help_text=_("Daily return as percentage"),
    )
    selection_reason = models.CharField(
        _("Selection Reason"),
        max_length=30,
        choices=SelectionReason.choices,
        default=SelectionReason.AUTO_POLICY,
        help_text=_("Why this value was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.)"),
    )
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="selected_index_values",
        verbose_name=_("Selected By"),
        help_text=_("User who manually selected this value (if manual override)"),
    )
    selected_at = models.DateTimeField(
        _("Selected At"),
        help_text=_("When this value was selected/canonicalized"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Market Index Value")
        verbose_name_plural = _("Market Index Values")
        indexes = [
            models.Index(fields=["index", "date"]),
            models.Index(fields=["date"]),
            models.Index(fields=["chosen_source"]),
        ]
        # One canonical value per index/date (global, not org-scoped)
        unique_together = [["index", "date"]]
        ordering = ["-date", "index"]

    def __str__(self) -> str:
        return f"{self.index.code} = {self.value} from {self.chosen_source.code} ({self.date})"


class MarketIndexImport(models.Model):
    """
    MarketIndexImport model tracking file uploads and import status.

    Tracks the import of market index data from uploaded Excel files.
    Stores the file reference, import status, and error information.
    Files are stored in media storage (works with local and S3/R2).

    Note: This model is NOT organization-scoped because market indices
    are global reference data shared across all organizations.

    Attributes:
        index (MarketIndex): The market index being imported.
        source (MarketDataSource): The market data source (e.g., BVMAC).
        file (FileField): Uploaded Excel file.
        sheet_name (str, optional): Sheet name if file has multiple sheets.
        status (str): Current import status (pending, importing, success, failed).
        error_message (str, optional): Error message if import failed.
        observations_created (int): Number of observations created.
        observations_updated (int): Number of observations updated.
        canonical_values_created (int): Number of canonical values created (if canonicalized).
        created_at (datetime): When the import was created.
        completed_at (datetime, optional): When the import completed.
        created_by (User, optional): User who created this import.
    """

    index = models.ForeignKey(
        "MarketIndex",
        on_delete=models.CASCADE,
        related_name="imports",
        verbose_name=_("Index"),
        help_text="Market index being imported.",
    )
    source = models.ForeignKey(
        "reference_data.MarketDataSource",
        on_delete=models.PROTECT,
        related_name="market_index_imports",
        verbose_name=_("Source"),
        help_text="Market data source (e.g., BVMAC).",
    )
    file = models.FileField(
        _("File"),
        upload_to="market_data/index_values/%Y/%m/",
        help_text="Uploaded Excel file with market index data.",
    )
    sheet_name = models.CharField(
        _("Sheet Name"),
        max_length=255,
        blank=True,
        null=True,
        default="INDEX_LEVELS",
        help_text="Sheet name if file has multiple sheets. Defaults to 'INDEX_LEVELS'.",
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
    canonical_values_created = models.IntegerField(
        _("Canonical Values Created"),
        default=0,
        help_text="Number of canonical values created (if canonicalized).",
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
        related_name="market_index_imports",
        verbose_name=_("Created By"),
        help_text="User who created this import.",
    )

    class Meta:
        verbose_name = _("Market Index Import")
        verbose_name_plural = _("Market Index Imports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["index", "status"]),
            models.Index(fields=["source", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.index.code} - {self.source.code} ({self.get_status_display()})"
