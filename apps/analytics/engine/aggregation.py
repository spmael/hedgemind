"""
Aggregation functions for valuation runs.

This module provides pure functions for computing aggregates and summaries
from valuation runs. These functions are separated from models to follow
data engineering best practices: computation logic separate from data storage.

Key functions:
- recalculate_total_market_value: Recalculate total from position results
- compute_data_quality_summary: Compute data quality summary from results
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import Sum
from djmoney.money import Money

if TYPE_CHECKING:
    from apps.analytics.models import ValuationRun


def recalculate_total_market_value(run: ValuationRun) -> Money:
    """
    Recalculate total market value from position results.

    Pure function that computes total from ValuationPositionResult records.
    Used for validation or when stored aggregate is missing.

    Args:
        run: ValuationRun instance to recalculate for.

    Returns:
        Money object representing recalculated total market value in portfolio base currency.

    Example:
        >>> run = ValuationRun.objects.get(id=1)
        >>> recalculated = recalculate_total_market_value(run)
        >>> stored = run.total_market_value
        >>> assert stored == recalculated  # Validation check
    """
    results = run.get_results()

    if not results.exists():
        return Money(0, run.portfolio.base_currency)

    # Sum the market_value_base_currency amounts
    total = results.aggregate(total=Sum("market_value_base_currency"))["total"]

    if total is None:
        return Money(0, run.portfolio.base_currency)

    return Money(total, run.portfolio.base_currency)


def compute_data_quality_summary(run: ValuationRun) -> dict:
    """
    Compute data quality summary from valuation position results.

    Pure function that aggregates data quality information from results.
    Uses stored aggregates where available for performance, but computes
    details on-demand.

    Args:
        run: ValuationRun instance to compute summary for.

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
        >>> summary = compute_data_quality_summary(run)
        >>> print(f"Issues: {summary['positions_with_issues']}")
    """
    # Use stored aggregates if available (fast)
    total_positions = run.position_count if run.position_count > 0 else 0
    positions_with_issues = run.positions_with_issues
    missing_fx_rates = run.missing_fx_count

    if total_positions == 0:
        # Fallback: count from results if stored aggregate is 0
        results = run.get_results()
        total_positions = results.count()

    if total_positions == 0:
        return {
            "total_positions": 0,
            "positions_with_issues": 0,
            "missing_fx_rates": 0,
            "invalid_fx_rates": 0,
            "issue_details": [],
        }

    # Compute invalid_fx_rates and issue_details on-demand (only when needed)
    # This balances performance (stored aggregates) with detail (on-demand computation)
    results = run.get_results()
    invalid_fx_rates = 0
    issue_details = []

    for result in results:
        flags = result.data_quality_flags or {}
        if flags:
            if flags.get("missing_fx_rate"):
                issue_details.append(
                    {
                        "position_snapshot_id": result.position_snapshot_id,
                        "instrument": str(result.position_snapshot.instrument),
                        "issue_type": "missing_fx_rate",
                        "currency_pair": flags.get("fx_currency_pair"),
                    }
                )

            if flags.get("invalid_fx_rate"):
                invalid_fx_rates += 1
                issue_details.append(
                    {
                        "position_snapshot_id": result.position_snapshot_id,
                        "instrument": str(result.position_snapshot.instrument),
                        "issue_type": "invalid_fx_rate",
                    }
                )

    return {
        "total_positions": total_positions,
        "positions_with_issues": positions_with_issues,
        "missing_fx_rates": missing_fx_rates,
        "invalid_fx_rates": invalid_fx_rates,
        "issue_details": issue_details,
    }


def compute_aggregates_from_results(run: ValuationRun, results: list) -> dict:
    """
    Compute aggregates from a list of ValuationPositionResult objects.

    Pure function used during run execution to compute and store aggregates.
    This is called by ValuationRun.execute() after computing results.

    Args:
        run: ValuationRun instance.
        results: List of ValuationPositionResult objects (not yet saved).

    Returns:
        Dictionary with computed aggregates:
        {
            'total_market_value': Money,
            'position_count': int,
            'positions_with_issues': int,
            'missing_fx_count': int,
        }

    Example:
        >>> run = ValuationRun.objects.get(id=1)
        >>> results = compute_valuation_policy_a(run)
        >>> aggregates = compute_aggregates_from_results(run, results)
        >>> run.total_market_value = aggregates['total_market_value']
    """
    # Calculate total market value
    total_mv = (
        sum(r.market_value_base_currency.amount for r in results)
        if results
        else Decimal("0")
    )
    total_market_value = Money(total_mv, run.portfolio.base_currency)

    # Count positions and issues
    position_count = len(results)
    positions_with_issues = sum(1 for r in results if r.data_quality_flags)
    missing_fx_count = sum(
        1
        for r in results
        if r.data_quality_flags and r.data_quality_flags.get("missing_fx_rate")
    )

    return {
        "total_market_value": total_market_value,
        "position_count": position_count,
        "positions_with_issues": positions_with_issues,
        "missing_fx_count": missing_fx_count,
    }
