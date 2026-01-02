"""
Analytics models for valuation runs and results.

This module provides models for portfolio valuation runs, which represent
valuation decisions for portfolios on specific dates using specific policies.
All valuation data is scoped to organizations to support multi-tenant isolation.

Key components:
- ValuationPolicy: Policy choices for valuation methods
- RunStatus: Status choices for valuation runs
- ValuationRun: Main model representing a valuation run decision
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from apps.portfolios.models import Portfolio, PositionSnapshot
from libs.models import (
    OrganizationManager,
    OrganizationOwnedModel,
    OrganizationQuerySet,
)


class ValuationPolicy(models.TextChoices):
    """
    Valuation policy choices for valuation runs.

    Defines the method used to compute portfolio valuation:
    - USE_SNAPSHOT_MV: Trust PositionSnapshot.market_value (MVP default)
    - REVALUE_FROM_MARKETDATA: Compute from prices + FX (future)
    """

    USE_SNAPSHOT_MV = "use_snapshot_mv", _("Use Snapshot Market Value")
    REVALUE_FROM_MARKETDATA = "revalue_from_marketdata", _("Revalue from Market Data")


class RunStatus(models.TextChoices):
    """
    Run status choices for valuation runs.

    Status flow: PENDING → RUNNING → SUCCESS/FAILED
    """

    PENDING = "pending", _("Pending")
    RUNNING = "running", _("Running")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")


class ValuationRunQuerySet(OrganizationQuerySet):
    """
    Custom QuerySet for ValuationRun with additional query methods.
    """

    def official(self):
        """Filter for official runs (is_official=True)."""
        return self.filter(is_official=True)

    def for_portfolio_date(self, portfolio, as_of_date):
        """
        Filter for runs for a specific portfolio and date.

        Args:
            portfolio: Portfolio instance or ID.
            as_of_date: Date object.

        Returns:
            QuerySet filtered to the specified portfolio and date.
        """
        portfolio_id = portfolio.id if hasattr(portfolio, "id") else portfolio
        return self.filter(portfolio_id=portfolio_id, as_of_date=as_of_date)

    def latest_official(self, portfolio, as_of_date):
        """
        Get the latest official run for a portfolio/date.

        Args:
            portfolio: Portfolio instance or ID.
            as_of_date: Date object.

        Returns:
            ValuationRun instance or None if no official run exists.
        """
        return (
            self.for_portfolio_date(portfolio, as_of_date)
            .official()
            .order_by("-created_at")
            .first()
        )

    def with_run_context(self, run_context_id: str):
        """
        Filter runs by run_context_id.

        Args:
            run_context_id: The run context identifier to filter by.

        Returns:
            QuerySet filtered to runs with the specified run_context_id.

        Example:
            >>> runs = ValuationRun.objects.with_run_context("batch-2025-01-15-001")
            >>> for run in runs:
            ...     print(run.portfolio.name)
        """
        return self.filter(run_context_id=run_context_id)


class ValuationRunManager(OrganizationManager):
    """
    Custom Manager for ValuationRun with additional query methods.
    """

    def get_queryset(self):
        """Return custom QuerySet."""
        return ValuationRunQuerySet(self.model, using=self._db)

    def official(self):
        """Filter for official runs."""
        return self.get_queryset().official()

    def for_portfolio_date(self, portfolio, as_of_date):
        """Filter for runs for a specific portfolio and date."""
        return self.get_queryset().for_portfolio_date(portfolio, as_of_date)

    def latest_official(self, portfolio, as_of_date):
        """Get the latest official run for a portfolio/date."""
        return self.get_queryset().latest_official(portfolio, as_of_date)

    def with_run_context(self, run_context_id: str):
        """Filter runs by run_context_id."""
        return self.get_queryset().with_run_context(run_context_id)


class ValuationRun(OrganizationOwnedModel):
    """
    ValuationRun model representing a valuation decision for a portfolio.

    A valuation run represents a valuation computation for a portfolio on a specific
    date using a specific policy. The policy determines how market values are computed
    (trust custodian values vs. revalue from market data). Multiple runs can exist
    for the same portfolio/date, but only one can be marked as official.

    Attributes:
        portfolio (Portfolio): The portfolio being valued.
        as_of_date (date): As-of date for this valuation run.
        valuation_policy (str): Policy used for valuation (USE_SNAPSHOT_MV, etc.).
        is_official (bool): Whether this is the official valuation for the date.
        created_by (User, optional): User who created this run.
        status (str): Current run status (PENDING, RUNNING, SUCCESS, FAILED).
        inputs_hash (str, optional): Hash of position snapshots + market data for idempotency.
        run_context_id (str, optional): Identifier for execution context and configuration.
        total_market_value (Money, optional): Stored total market value in base currency.
        position_count (int): Number of positions (stored aggregate).
        positions_with_issues (int): Number of positions with data quality issues (stored aggregate).
        missing_fx_count (int): Number of positions with missing FX rates (stored aggregate).
        log (str, optional): Execution log for debugging.
        created_at (datetime): When the run was created.

    Example:
        >>> portfolio = Portfolio.objects.get(name="Treasury Portfolio A")
        >>> run = ValuationRun.objects.create(
        ...     portfolio=portfolio,
        ...     as_of_date=date.today(),
        ...     valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
        ...     status=RunStatus.PENDING,
        ...     run_context_id="batch-2025-01-15-001"  # Optional: group related runs
        ... )

    Note:
        - inputs_hash: Data fingerprint ("Did the data change?")
        - run_context_id: Execution context ("Under what configuration was this executed?")
        - These fields are orthogonal and serve different purposes.
    """

    # Override default manager with custom one
    objects = ValuationRunManager()

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="valuation_runs",
        help_text="Portfolio being valued.",
    )
    as_of_date = models.DateField(
        _("As Of Date"),
        help_text="As-of date for this valuation run.",
    )
    valuation_policy = models.CharField(
        _("Valuation Policy"),
        max_length=30,
        choices=ValuationPolicy.choices,
        default=ValuationPolicy.USE_SNAPSHOT_MV,
        help_text="Policy used for valuation.",
    )
    is_official = models.BooleanField(
        _("Is Official"),
        default=False,
        help_text="Whether this is the official valuation for this portfolio/date.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="valuation_runs",
        verbose_name=_("Created By"),
        help_text="User who created this valuation run.",
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.PENDING,
        help_text="Current run status.",
    )
    inputs_hash = models.CharField(
        _("Inputs Hash"),
        max_length=64,
        blank=True,
        null=True,
        help_text="Hash of position snapshots + market data for idempotency checks.",
        db_index=True,
    )
    run_context_id = models.CharField(
        _("Run Context ID"),
        max_length=64,
        blank=True,
        null=True,
        help_text="Identifier for execution context and configuration. Groups runs executed with the same settings (single or batch). Used for audit trail and reproducibility.",
        db_index=True,
    )
    # Stored aggregates (computed during execute() for performance and auditability)
    total_market_value = MoneyField(
        _("Total Market Value"),
        max_digits=20,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Total market value of all positions in portfolio base currency (stored aggregate).",
    )
    position_count = models.IntegerField(
        _("Position Count"),
        default=0,
        help_text="Number of positions in this valuation run (stored aggregate).",
    )
    positions_with_issues = models.IntegerField(
        _("Positions With Issues"),
        default=0,
        help_text="Number of positions with data quality issues (stored aggregate).",
    )
    missing_fx_count = models.IntegerField(
        _("Missing FX Count"),
        default=0,
        help_text="Number of positions with missing FX rates (stored aggregate).",
    )
    log = models.TextField(
        _("Log"),
        blank=True,
        null=True,
        help_text="Execution log for debugging.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Valuation Run")
        verbose_name_plural = _("Valuation Runs")
        ordering = ["-as_of_date", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "portfolio", "as_of_date"]),
            models.Index(
                fields=["organization", "portfolio", "as_of_date", "is_official"]
            ),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["organization", "run_context_id"]),
        ]
        # Prevent duplicate runs with same inputs
        constraints = [
            UniqueConstraint(
                fields=["organization", "portfolio", "as_of_date", "inputs_hash"],
                name="uniq_valuation_run_org_port_date_inputs",
                condition=models.Q(inputs_hash__isnull=False),
            ),
        ]

    def compute_inputs_hash(self) -> str:
        """
        Compute hash of position snapshots + market data date.

        Returns:
            str: SHA256 hash (hex) of position snapshot IDs and as_of_date.

        The hash is computed from:
        - Sorted list of position snapshot IDs for portfolio/date
        - As-of date
        - Valuation policy (to differentiate runs with same inputs but different policies)

        This ensures that runs with identical inputs have the same hash, enabling
        idempotency checks and preventing duplicate computation.
        """

        # Get all position snapshots for this portfolio/date
        snapshots = PositionSnapshot.objects.filter(
            portfolio=self.portfolio,
            as_of_date=self.as_of_date,
        ).order_by("id")

        # Build hash input: sorted snapshot IDs + date + policy
        snapshot_ids = sorted(str(snapshot.id) for snapshot in snapshots)
        hash_input = "|".join(
            [
                ",".join(snapshot_ids),
                str(self.as_of_date.isoformat()),
                self.valuation_policy,
            ]
        )

        # Compute SHA256 hash
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    def execute(self) -> None:
        """
        Execute the valuation run.

        Runs the valuation computation according to the valuation_policy, saves
        results to ValuationPositionResult, and updates the run status.

        Raises:
            ValueError: If valuation_policy is not recognized.
            Exception: Any exception during computation (status set to FAILED).
        """
        from apps.analytics.engine.valuation import compute_valuation_policy_a

        self.status = RunStatus.RUNNING
        self.save(update_fields=["status"])

        log_entries = []

        try:
            # Select appropriate policy function
            if self.valuation_policy == ValuationPolicy.USE_SNAPSHOT_MV:
                log_entries.append(
                    f"Starting valuation with Policy A: {self.get_valuation_policy_display()}"
                )
                results = compute_valuation_policy_a(self)
            elif self.valuation_policy == ValuationPolicy.REVALUE_FROM_MARKETDATA:
                raise ValueError(
                    f"Policy {self.valuation_policy} not yet implemented. "
                    "Only USE_SNAPSHOT_MV is supported."
                )
            else:
                raise ValueError(f"Unknown valuation policy: {self.valuation_policy}")

            # Save results in transaction
            with transaction.atomic():
                # Delete existing results (if re-running)
                ValuationPositionResult.objects.filter(valuation_run=self).delete()

                # Save new results
                for result in results:
                    result.save()

                log_entries.append(f"Computed {len(results)} position results")

            # Compute and store aggregates (industry standard: store for performance/auditability)
            from apps.analytics.engine.aggregation import (
                compute_aggregates_from_results,
            )

            aggregates = compute_aggregates_from_results(self, results)
            self.total_market_value = aggregates["total_market_value"]
            self.position_count = aggregates["position_count"]
            self.positions_with_issues = aggregates["positions_with_issues"]
            self.missing_fx_count = aggregates["missing_fx_count"]

            # Log data quality issues
            if self.positions_with_issues > 0:
                log_entries.append(
                    f"Warning: {self.positions_with_issues} positions have data quality flags "
                    f"({self.missing_fx_count} missing FX rates)"
                )

            self.status = RunStatus.SUCCESS
            log_entries.append("Valuation completed successfully")

        except Exception as e:
            self.status = RunStatus.FAILED
            log_entries.append(f"Error: {str(e)}")
            raise  # Re-raise to let caller handle

        finally:
            self.log = "\n".join(log_entries)
            # Save status, log, and aggregates
            update_fields = [
                "status",
                "log",
                "total_market_value",
                "position_count",
                "positions_with_issues",
                "missing_fx_count",
            ]
            self.save(update_fields=update_fields)

    def clean(self) -> None:
        """
        Validate model fields.

        Raises:
            ValidationError: If validation fails.
        """
        super().clean()

        # Validate that portfolio belongs to same organization
        if self.portfolio_id and self.organization_id:
            if self.portfolio.organization_id != self.organization_id:
                raise ValidationError(
                    {
                        "portfolio": "Portfolio must belong to the same organization as the valuation run."
                    }
                )

        # Warn if marking as official but status is not SUCCESS
        if self.is_official and self.status != RunStatus.SUCCESS:
            # Note: We allow this in clean() but mark_as_official() will enforce it
            # This is just a warning for early detection
            pass  # Could add a warning here if desired

        # Auto-compute inputs_hash if not set (will be set on save)
        if not self.inputs_hash and self.portfolio_id and self.as_of_date:
            # This will be computed in save() method, just validate we have required fields
            pass

    def save(self, *args, **kwargs) -> None:
        """
        Override save to auto-compute inputs_hash and enforce official run constraint.

        The inputs_hash is computed from position snapshots and is used for
        idempotency checks. It's computed before save to ensure uniqueness
        constraints can be checked.

        Also enforces that only one run can be marked as official per portfolio/date.
        If this run is being marked as official, any existing official run for the
        same portfolio/date will be unmarked.
        """
        # Compute inputs_hash if we have portfolio and date
        if self.portfolio_id and self.as_of_date and not self.inputs_hash:
            self.inputs_hash = self.compute_inputs_hash()

        # Track if is_official is being set to True
        is_being_marked_official = False
        if self.pk is None:
            # New object - check if is_official is True
            is_being_marked_official = self.is_official
        else:
            # Existing object - check if is_official is changing to True
            try:
                old_instance = ValuationRun.objects.get(pk=self.pk)
                is_being_marked_official = (
                    not old_instance.is_official and self.is_official
                )
            except ValuationRun.DoesNotExist:
                # Object doesn't exist yet (shouldn't happen, but handle gracefully)
                is_being_marked_official = self.is_official

        # If being marked as official, unmark any existing official run
        if is_being_marked_official and self.portfolio_id and self.as_of_date:
            # Unmark existing official runs for same portfolio/date
            ValuationRun.objects.filter(
                organization=self.organization,
                portfolio=self.portfolio,
                as_of_date=self.as_of_date,
                is_official=True,
            ).exclude(pk=self.pk if self.pk else None).update(is_official=False)

        super().save(*args, **kwargs)

    def mark_as_official(self, reason: str, actor=None) -> None:
        """
        Mark this valuation run as the official run for its portfolio/date.

        This method:
        1. Unmarks any existing official run for the same portfolio/date
        2. Marks this run as official
        3. Creates an audit event recording the change

        Args:
            reason: Reason for marking as official (required for audit trail).
            actor: User performing the action (optional, defaults to self.created_by).

        Raises:
            ValidationError: If run is not in SUCCESS status.

        Example:
            >>> run = ValuationRun.objects.get(id=1)
            >>> run.mark_as_official(
            ...     reason="Approved by portfolio manager",
            ...     actor=request.user
            ... )
        """
        from apps.audit.models import AuditEvent

        # Validate that run is successful
        if self.status != RunStatus.SUCCESS:
            raise ValidationError(
                f"Cannot mark run as official when status is {self.get_status_display()}. "
                "Run must be in SUCCESS status."
            )

        # Get previous official run before unmarking
        previous_official = (
            ValuationRun.objects.filter(
                organization=self.organization,
                portfolio=self.portfolio,
                as_of_date=self.as_of_date,
                is_official=True,
            )
            .exclude(pk=self.pk if self.pk else None)
            .first()
        )

        previous_official_id = previous_official.id if previous_official else None

        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Unmark existing official run
            if previous_official:
                previous_official.is_official = False
                previous_official.save(update_fields=["is_official"])

            # Mark this run as official
            self.is_official = True
            self.save(update_fields=["is_official"])

            # Create audit event
            AuditEvent.objects.create(
                organization_id=self.organization_id,
                actor=actor or self.created_by,
                action="MARK_VALUATION_OFFICIAL",
                object_type="ValuationRun",
                object_id=self.id,
                object_repr=str(self),
                metadata={
                    "reason": reason,
                    "portfolio_id": self.portfolio_id,
                    "portfolio_name": self.portfolio.name,
                    "as_of_date": str(self.as_of_date),
                    "valuation_policy": self.valuation_policy,
                    "previous_official_run_id": previous_official_id,
                },
            )

    def unmark_as_official(self, reason: str, actor=None) -> None:
        """
        Unmark this valuation run as official.

        This method:
        1. Sets is_official to False
        2. Creates an audit event recording the change

        Args:
            reason: Reason for unmarking (required for audit trail).
            actor: User performing the action (optional, defaults to self.created_by).

        Example:
            >>> run = ValuationRun.objects.get(id=1)
            >>> run.unmark_as_official(
            ...     reason="New valuation run approved",
            ...     actor=request.user
            ... )
        """
        from apps.audit.models import AuditEvent

        # Only unmark if currently official
        if not self.is_official:
            return  # Nothing to do

        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Unmark this run
            self.is_official = False
            self.save(update_fields=["is_official"])

            # Create audit event
            AuditEvent.objects.create(
                organization_id=self.organization_id,
                actor=actor or self.created_by,
                action="UNMARK_VALUATION_OFFICIAL",
                object_type="ValuationRun",
                object_id=self.id,
                object_repr=str(self),
                metadata={
                    "reason": reason,
                    "portfolio_id": self.portfolio_id,
                    "portfolio_name": self.portfolio.name,
                    "as_of_date": str(self.as_of_date),
                    "valuation_policy": self.valuation_policy,
                },
            )

    def get_results(self):
        """
        Get QuerySet of ValuationPositionResult for this run.

        Returns:
            QuerySet of ValuationPositionResult objects.

        Example:
            >>> run = ValuationRun.objects.get(id=1)
            >>> results = run.get_results()
            >>> for result in results:
            ...     print(result.market_value_base_currency)
        """
        return ValuationPositionResult.objects.filter(valuation_run=self)

    def get_total_market_value(self):
        """
        Get total market value of all positions in base currency.

        Returns the stored aggregate value (industry standard: fast, auditable).
        This is a simple getter - computation logic is in engine/aggregation.py.

        Returns:
            Money object representing total market value in portfolio base currency.
            Returns Money(0, base_currency) if stored value is None.

        Example:
            >>> run = ValuationRun.objects.get(id=1)
            >>> total = run.get_total_market_value()
            >>> print(f"Total: {total}")
        """
        # Return stored aggregate (industry standard: fast, auditable)
        if self.total_market_value is not None:
            return self.total_market_value

        # Fallback: return zero if not computed yet
        from djmoney.money import Money

        return Money(0, self.portfolio.base_currency)

    def get_data_quality_summary(self) -> dict:
        """
        Get summary of data quality issues across all position results.

        Delegates to engine function for computation (separation of concerns).
        Uses stored aggregates where available for performance.

        Returns:
            Dictionary with counts of various data quality issues:
            {
                'total_positions': int,
                'positions_with_issues': int,
                'missing_fx_rates': int,
                'invalid_fx_rates': int,
                'issue_details': list[dict],  # Detailed list of issues
            }

        Example:
            >>> run = ValuationRun.objects.get(id=1)
            >>> summary = run.get_data_quality_summary()
            >>> print(f"Issues: {summary['positions_with_issues']}")
        """
        from apps.analytics.engine.aggregation import compute_data_quality_summary

        return compute_data_quality_summary(self)

    def __str__(self) -> str:
        """String representation of the valuation run."""
        policy_display = self.get_valuation_policy_display()
        official_str = " [OFFICIAL]" if self.is_official else ""
        return f"{self.portfolio.name} - {self.as_of_date} ({policy_display}){official_str}"


class ValuationPositionResult(OrganizationOwnedModel):
    """
    ValuationPositionResult model storing computed valuation results for a position.

    Stores the result of valuation computation for a single position snapshot within
    a valuation run. Contains both the original market value (in position currency)
    and the converted market value (in portfolio base currency), along with FX
    conversion details and data quality flags.

    Attributes:
        valuation_run (ValuationRun): The valuation run this result belongs to.
        position_snapshot (PositionSnapshot): The position snapshot being valued.
        market_value_original_currency (Money): Original MV from snapshot (in snapshot currency).
        market_value_base_currency (Money): Converted MV in portfolio base currency.
        fx_rate_used (decimal, optional): FX rate applied (if conversion needed).
        fx_rate_source (str, optional): Source code of FX rate used (if conversion needed).
        data_quality_flags (dict): JSON field tracking missing data issues.
        created_at (datetime): When the result record was created.

    Example:
        >>> run = ValuationRun.objects.get(id=1)
        >>> snapshot = PositionSnapshot.objects.get(id=1)
        >>> result = ValuationPositionResult.objects.create(
        ...     valuation_run=run,
        ...     position_snapshot=snapshot,
        ...     market_value_original_currency=Money(1000, "USD"),
        ...     market_value_base_currency=Money(625000, "XAF"),
        ...     fx_rate_used=Decimal("0.0016"),
        ...     fx_rate_source="BEAC"
        ... )
    """

    valuation_run = models.ForeignKey(
        ValuationRun,
        on_delete=models.CASCADE,
        related_name="position_results",
        help_text="Valuation run this result belongs to.",
    )
    position_snapshot = models.ForeignKey(
        "portfolios.PositionSnapshot",
        on_delete=models.CASCADE,
        related_name="valuation_results",
        help_text="Position snapshot being valued.",
    )
    market_value_original_currency = MoneyField(
        _("Market Value (Original Currency)"),
        max_digits=20,
        decimal_places=6,
        help_text="Original market value from snapshot (in snapshot currency).",
    )
    market_value_base_currency = MoneyField(
        _("Market Value (Base Currency)"),
        max_digits=20,
        decimal_places=6,
        help_text="Converted market value in portfolio base currency.",
    )
    fx_rate_used = models.DecimalField(
        _("FX Rate Used"),
        max_digits=20,
        decimal_places=8,
        blank=True,
        null=True,
        help_text="FX rate applied for conversion (if conversion was needed).",
    )
    fx_rate_source = models.CharField(
        _("FX Rate Source"),
        max_length=50,
        blank=True,
        null=True,
        help_text="Source code of FX rate used (e.g., 'BEAC', 'BVMAC').",
    )
    data_quality_flags = models.JSONField(
        _("Data Quality Flags"),
        default=dict,
        blank=True,
        help_text="JSON object tracking data quality issues (missing FX, etc.).",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Valuation Position Result")
        verbose_name_plural = _("Valuation Position Results")
        ordering = ["valuation_run", "position_snapshot"]
        indexes = [
            models.Index(fields=["organization", "valuation_run"]),
            models.Index(fields=["organization", "position_snapshot"]),
        ]
        # One result per run per snapshot
        constraints = [
            UniqueConstraint(
                fields=["organization", "valuation_run", "position_snapshot"],
                name="uniq_valuation_result_run_snapshot",
            ),
        ]

    def __str__(self) -> str:
        """String representation of the valuation result."""
        return f"{self.valuation_run} - {self.position_snapshot.instrument.name}"

    def get_data_quality_flags_display(self) -> str:
        """
        Get human-readable representation of data quality flags.

        Returns:
            String describing data quality issues, or empty string if none.

        Example:
            >>> result = ValuationPositionResult.objects.get(id=1)
            >>> flags_str = result.get_data_quality_flags_display()
            >>> print(flags_str)  # "Missing FX rate for USD/XAF"
        """
        flags = self.data_quality_flags or {}
        if not flags:
            return ""

        issues = []

        if flags.get("missing_fx_rate"):
            currency_pair = flags.get("fx_currency_pair", "N/A")
            issues.append(f"Missing FX rate for {currency_pair}")

        if flags.get("invalid_fx_rate"):
            issues.append("Invalid FX rate")

        return "; ".join(issues) if issues else ""
