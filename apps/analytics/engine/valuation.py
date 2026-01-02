"""
Valuation engine for computing portfolio valuations.

This module provides functions to compute portfolio valuations according to
different valuation policies. Each policy function takes a ValuationRun and
returns a list of ValuationPositionResult objects.

Key functions:
- compute_valuation_policy_a: Policy A (USE_SNAPSHOT_MV) - trusts snapshot market values
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from djmoney.money import Money

from apps.analytics.models import ValuationPositionResult, ValuationRun
from apps.portfolios.models import PositionSnapshot
from apps.reference_data.models import FXRate

if TYPE_CHECKING:
    pass


def compute_valuation_policy_a(run: ValuationRun) -> list[ValuationPositionResult]:
    """
    Compute valuation using Policy A: USE_SNAPSHOT_MV.

    Policy A trusts the market_value stored in PositionSnapshot (typically from
    custodian or manual input). This policy:
    1. Loads all PositionSnapshot records for portfolio/date
    2. For each snapshot:
       - Uses snapshot.market_value (already in snapshot's currency)
       - Converts to portfolio.base_currency using FXRate if needed
       - Flags missing FX rates as data quality issues (but continues)
    3. Returns list of ValuationPositionResult objects (not yet saved)

    Args:
        run: ValuationRun instance to compute valuation for.

    Returns:
        List of ValuationPositionResult objects (not yet saved to database).

    Note:
        This function does NOT save results to database. Caller is responsible
        for saving results. This enables transaction control and error handling.

    Example:
        >>> run = ValuationRun.objects.get(id=1)
        >>> results = compute_valuation_policy_a(run)
        >>> for result in results:
        ...     result.save()
    """
    # Get all position snapshots for this portfolio/date
    snapshots = PositionSnapshot.objects.filter(
        portfolio=run.portfolio,
        as_of_date=run.as_of_date,
    ).select_related("instrument")

    if not snapshots.exists():
        return []

    results = []
    base_currency = run.portfolio.base_currency

    for snapshot in snapshots:
        # Get original market value (already in snapshot's currency)
        original_mv = snapshot.market_value
        # Ensure currency is a string (Money.currency returns str, but normalize for safety)
        original_currency = str(original_mv.currency) if original_mv.currency else None
        original_amount = original_mv.amount

        # Initialize data quality flags
        data_quality_flags = {}
        fx_rate_used = None
        fx_rate_source = None

        # Ensure base_currency is a string for comparison
        base_currency_str = str(base_currency) if base_currency else None

        # Convert to base currency if needed
        if original_currency == base_currency_str:
            # No conversion needed, use snapshot value directly
            base_amount = original_amount
        else:
            # Need FX conversion
            fx_rate = _get_fx_rate(
                from_currency=original_currency,
                to_currency=base_currency_str,
                as_of_date=run.as_of_date,
            )

            if fx_rate is None:
                # Missing FX rate - flag as data quality issue
                data_quality_flags["missing_fx_rate"] = True
                data_quality_flags["fx_currency_pair"] = (
                    f"{original_currency}/{base_currency_str}"
                )
                # Set base amount to None or zero? We'll use 0 for now but flag it
                base_amount = Decimal("0")
                # Note: In production, you might want to raise an exception or
                # use a fallback rate. For MVP, we flag and continue.
            else:
                # Apply FX conversion
                # FXRate stores: 1 base_currency = rate quote_currency
                # We need to check direction of the rate
                # Normalize FX rate currencies to strings for comparison
                fx_base_currency = (
                    str(fx_rate.base_currency) if fx_rate.base_currency else None
                )

                if fx_base_currency == original_currency:
                    # Direct rate: 1 original = rate base
                    # So: base_amount = original_amount * rate
                    fx_rate_used = fx_rate.rate
                    base_amount = original_amount * fx_rate.rate
                elif fx_base_currency == base_currency_str:
                    # Inverted rate: 1 base = rate original
                    # So: base_amount = original_amount / rate
                    fx_rate_used = Decimal("1") / fx_rate.rate
                    base_amount = original_amount / fx_rate.rate
                else:
                    # This shouldn't happen, but handle gracefully
                    data_quality_flags["invalid_fx_rate"] = True
                    base_amount = Decimal("0")
                    fx_rate = None

                if fx_rate:
                    fx_rate_source = fx_rate.chosen_source.code

        # Create result object (not yet saved)
        result = ValuationPositionResult(
            valuation_run=run,
            position_snapshot=snapshot,
            market_value_original_currency=Money(original_amount, original_currency),
            market_value_base_currency=Money(base_amount, base_currency),
            fx_rate_used=fx_rate_used,
            fx_rate_source=fx_rate_source,
            data_quality_flags=data_quality_flags,
            organization=run.organization,  # Set organization for OrganizationOwnedModel
        )
        results.append(result)

    return results


def _get_fx_rate(
    from_currency: str,
    to_currency: str,
    as_of_date,
) -> FXRate | None:
    """
    Get FX rate for currency conversion.

    Looks up canonical FXRate for converting from_currency to to_currency on as_of_date.
    Tries both directions (from/to and to/from) since rates can be stored either way.

    Args:
        from_currency: Source currency code.
        to_currency: Target currency code.
        as_of_date: Date for the FX rate.

    Returns:
        FXRate instance if found, None otherwise.
    """
    # Try direct direction: from_currency/base to to_currency/quote
    fx_rate = FXRate.objects.filter(
        base_currency=from_currency,
        quote_currency=to_currency,
        date=as_of_date,
        rate_type=FXRate.RateType.MID,
    ).first()

    if fx_rate:
        return fx_rate

    # Try inverted direction: to_currency/base to from_currency/quote
    fx_rate = FXRate.objects.filter(
        base_currency=to_currency,
        quote_currency=from_currency,
        date=as_of_date,
        rate_type=FXRate.RateType.MID,
    ).first()

    return fx_rate  # Returns None if not found
