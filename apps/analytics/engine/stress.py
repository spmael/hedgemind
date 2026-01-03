"""
Portfolio stress testing engine.

Implements Phase 5: Apply to Portfolios.

Applies yield curve stress profiles to portfolios and computes stress impacts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.analytics.models import ValuationRun
from apps.portfolios.models import Portfolio, PositionSnapshot
from apps.reference_data.models import YieldCurveStressProfile


def load_stress_profile(
    curve_id: int | None = None,
    narrative: str | None = None,
    profile_id: int | None = None,
) -> YieldCurveStressProfile | None:
    """
    Load a stress profile for use in stress testing.

    Args:
        curve_id: YieldCurve ID to filter by.
        narrative: Narrative type to filter by.
        profile_id: Specific profile ID to load.

    Returns:
        YieldCurveStressProfile instance or None if not found.

    Example:
        >>> profile = load_stress_profile(curve_id=1, narrative="acute_sovereign_stress")
        >>> if profile:
        ...     print(f"Haircut: {profile.sovereign_haircut_pct}%")
    """
    profiles = YieldCurveStressProfile.objects.filter(is_active=True)

    if profile_id:
        profiles = profiles.filter(id=profile_id)
    else:
        if curve_id:
            profiles = profiles.filter(curve_id=curve_id)
        if narrative:
            profiles = profiles.filter(narrative=narrative)

    # Return most recent profile
    return profiles.order_by("-period_end", "-created_at").first()


def apply_haircuts_to_portfolio(
    portfolio: Portfolio,
    stress_profile: YieldCurveStressProfile,
    as_of_date: Any,
) -> dict[str, Any]:
    """
    Apply haircuts to portfolio holdings based on issuer type.

    Args:
        portfolio: Portfolio instance.
        stress_profile: YieldCurveStressProfile to apply.
        as_of_date: Date for stress test.

    Returns:
        dict: Stress results with keys:
            - positions_stressed: List of position stress results
            - total_baseline_mv: Total baseline market value
            - total_stressed_mv: Total stressed market value
            - capital_loss: Absolute capital loss
            - capital_loss_pct: Percentage capital loss

    Example:
        >>> portfolio = Portfolio.objects.get(id=1)
        >>> profile = load_stress_profile(curve_id=1)
        >>> results = apply_haircuts_to_portfolio(portfolio, profile, date.today())
        >>> print(f"Capital loss: {results['capital_loss']}")
    """
    # Get position snapshot for date
    snapshot = PositionSnapshot.objects.filter(
        portfolio=portfolio,
        as_of_date=as_of_date,
    ).first()

    if not snapshot:
        return {
            "positions_stressed": [],
            "total_baseline_mv": Decimal("0.00"),
            "total_stressed_mv": Decimal("0.00"),
            "capital_loss": Decimal("0.00"),
            "capital_loss_pct": Decimal("0.00"),
        }

    positions = snapshot.positions.all()
    positions_stressed = []
    total_baseline_mv = Decimal("0.00")
    total_stressed_mv = Decimal("0.00")

    for position in positions:
        # Get baseline market value
        baseline_mv = position.market_value or Decimal("0.00")
        total_baseline_mv += baseline_mv

        # Determine issuer type and haircut
        instrument = position.instrument
        issuer = instrument.issuer if instrument else None

        if issuer:
            issuer_type = issuer.issuer_type if hasattr(issuer, "issuer_type") else None
        else:
            issuer_type = None

        # Select haircut based on issuer type
        if issuer_type == "SOVEREIGN" or (
            issuer and "sovereign" in str(issuer.issuer_group).lower()
        ):
            haircut_pct = stress_profile.sovereign_haircut_pct
        elif issuer_type == "SUPRANATIONAL" or (
            issuer and "supra" in str(issuer.issuer_group).lower()
        ):
            haircut_pct = stress_profile.supra_haircut_pct
        else:
            # Default to corporate
            haircut_pct = stress_profile.corporate_haircut_pct

        # Apply haircut
        haircut_factor = Decimal("1.00") - (haircut_pct / Decimal("100.00"))
        stressed_mv = baseline_mv * haircut_factor
        total_stressed_mv += stressed_mv

        positions_stressed.append(
            {
                "position_id": position.id,
                "instrument_id": instrument.id if instrument else None,
                "issuer_type": issuer_type,
                "baseline_mv": baseline_mv,
                "stressed_mv": stressed_mv,
                "haircut_pct": haircut_pct,
                "capital_loss": baseline_mv - stressed_mv,
            }
        )

    # Calculate total capital loss
    capital_loss = total_baseline_mv - total_stressed_mv
    capital_loss_pct = (
        (capital_loss / total_baseline_mv * Decimal("100.00"))
        if total_baseline_mv > 0
        else Decimal("0.00")
    )

    return {
        "positions_stressed": positions_stressed,
        "total_baseline_mv": total_baseline_mv,
        "total_stressed_mv": total_stressed_mv,
        "capital_loss": capital_loss,
        "capital_loss_pct": capital_loss_pct,
    }


def recompute_valuation_stress(
    portfolio: Portfolio,
    stress_profile: YieldCurveStressProfile,
    as_of_date: Any,
) -> dict[str, Any]:
    """
    Recalculate portfolio valuation under stress.

    Uses baseline valuation and applies stress haircuts.

    Args:
        portfolio: Portfolio instance.
        stress_profile: YieldCurveStressProfile to apply.
        as_of_date: Date for stress test.

    Returns:
        dict: Stressed valuation results.

    Example:
        >>> portfolio = Portfolio.objects.get(id=1)
        >>> profile = load_stress_profile(curve_id=1)
        >>> stressed_valuation = recompute_valuation_stress(portfolio, profile, date.today())
    """
    # Get baseline valuation
    baseline_run = (
        ValuationRun.objects.filter(
            portfolio=portfolio,
            as_of_date=as_of_date,
            is_official=True,
        )
        .order_by("-created_at")
        .first()
    )

    if not baseline_run:
        # Fallback: compute from snapshot
        baseline_results = apply_haircuts_to_portfolio(
            portfolio, stress_profile, as_of_date
        )
        return {
            "baseline_mv": baseline_results["total_baseline_mv"],
            "stressed_mv": baseline_results["total_stressed_mv"],
            "capital_loss": baseline_results["capital_loss"],
            "capital_loss_pct": baseline_results["capital_loss_pct"],
        }

    # Apply stress to baseline
    stress_results = apply_haircuts_to_portfolio(portfolio, stress_profile, as_of_date)

    return {
        "baseline_mv": baseline_run.total_market_value or Decimal("0.00"),
        "stressed_mv": stress_results["total_stressed_mv"],
        "capital_loss": stress_results["capital_loss"],
        "capital_loss_pct": stress_results["capital_loss_pct"],
        "baseline_run_id": baseline_run.id,
    }


def recompute_exposures_stress(
    portfolio: Portfolio,
    stress_profile: YieldCurveStressProfile,
    as_of_date: Any,
) -> dict[str, Any]:
    """
    Recalculate exposures under stress.

    Args:
        portfolio: Portfolio instance.
        stress_profile: YieldCurveStressProfile to apply.
        as_of_date: Date for stress test.

    Returns:
        dict: Stressed exposure results by dimension (currency, issuer, country, etc.).

    Example:
        >>> portfolio = Portfolio.objects.get(id=1)
        >>> profile = load_stress_profile(curve_id=1)
        >>> stressed_exposures = recompute_exposures_stress(portfolio, profile, date.today())
    """
    # Get stressed positions
    stress_results = apply_haircuts_to_portfolio(portfolio, stress_profile, as_of_date)

    # Recompute exposures using stressed market values
    # This is a simplified version - full implementation would recompute from positions
    exposures = {
        "by_currency": {},
        "by_issuer": {},
        "by_country": {},
        "by_asset_class": {},
    }

    # Aggregate from stressed positions
    for pos_result in stress_results["positions_stressed"]:
        # This is simplified - full implementation would query positions and aggregate
        # For now, return structure
        pass

    return {
        "exposures": exposures,
        "total_stressed_mv": stress_results["total_stressed_mv"],
    }


def compare_baseline_vs_stress(
    baseline_results: dict[str, Any],
    stress_results: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate comparison between baseline and stress results.

    Args:
        baseline_results: Baseline valuation/exposure results.
        stress_results: Stress results.

    Returns:
        dict: Comparison with deltas and percentage changes.

    Example:
        >>> baseline = {"total_mv": 1000000, ...}
        >>> stress = {"total_stressed_mv": 850000, ...}
        >>> comparison = compare_baseline_vs_stress(baseline, stress)
    """
    baseline_mv = (
        baseline_results.get("total_mv")
        or baseline_results.get("total_market_value")
        or Decimal("0.00")
    )
    stressed_mv = stress_results.get("total_stressed_mv") or Decimal("0.00")

    capital_loss = baseline_mv - stressed_mv
    capital_loss_pct = (
        (capital_loss / baseline_mv * Decimal("100.00"))
        if baseline_mv > 0
        else Decimal("0.00")
    )

    return {
        "baseline_mv": baseline_mv,
        "stressed_mv": stressed_mv,
        "capital_loss": capital_loss,
        "capital_loss_pct": capital_loss_pct,
        "delta": capital_loss,
        "delta_pct": capital_loss_pct,
    }
