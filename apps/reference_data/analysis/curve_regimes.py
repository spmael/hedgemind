"""
Yield curve stress regime detection.

Implements Phase 2: Identify Stress Regimes.

Detects when markets were "normal", "stressed", or "broken" using simple,
explainable rules (percentiles, jumps, gaps).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.reference_data.analysis.curve_quality import (
    extract_clean_series,
    select_core_tenors,
)
from apps.reference_data.models import YieldCurve, YieldCurvePoint


class RegimeType:
    """Regime type constants."""

    NORMAL = "normal"
    RISING_STRESS = "rising_stress"
    HIGH_STRESS = "high_stress"
    PUBLICATION_BREAKDOWN = "publication_breakdown"


def classify_regime(
    yield_level: float,
    yield_change: float | None,
    gap_days: int,
    percentile_thresholds: dict[str, float],
) -> str:
    """
    Classify regime using simple rules-based approach.

    Args:
        yield_level: Current yield level.
        yield_change: Period-over-period change (None if first observation).
        gap_days: Days since last observation.
        percentile_thresholds: Dict with keys 'low', 'medium', 'high' for yield level thresholds.

    Returns:
        str: Regime type (NORMAL, RISING_STRESS, HIGH_STRESS, PUBLICATION_BREAKDOWN).

    Example:
        >>> thresholds = {'low': 2.0, 'medium': 5.0, 'high': 8.0}
        >>> regime = classify_regime(6.5, 0.5, 5, thresholds)
        >>> print(regime)  # "rising_stress"
    """
    # Publication breakdown: gap > 90 days
    if gap_days > 90:
        return RegimeType.PUBLICATION_BREAKDOWN

    # High stress: yield above high threshold
    if yield_level >= percentile_thresholds.get("high", 8.0):
        return RegimeType.HIGH_STRESS

    # Rising stress: yield rising and above medium threshold, or large positive change
    if yield_change is not None:
        if (
            yield_level >= percentile_thresholds.get("medium", 5.0)
            and yield_change > 0.2
        ):
            return RegimeType.RISING_STRESS
        if yield_change > 0.5:  # Large jump
            return RegimeType.RISING_STRESS

    # Normal: everything else
    return RegimeType.NORMAL


def calculate_percentile_thresholds(
    series: list[dict[str, Any]],
    low_pct: float = 25.0,
    medium_pct: float = 75.0,
    high_pct: float = 90.0,
) -> dict[str, float]:
    """
    Calculate percentile thresholds for yield levels.

    Args:
        series: List of yield observations (from extract_clean_series).
        low_pct: Low percentile (default: 25th).
        medium_pct: Medium percentile (default: 75th).
        high_pct: High percentile (default: 90th).

    Returns:
        dict: Thresholds with keys 'low', 'medium', 'high'.

    Example:
        >>> series = extract_clean_series(curve, 1825)
        >>> thresholds = calculate_percentile_thresholds(series)
    """
    if not series:
        return {"low": 0.0, "medium": 5.0, "high": 8.0}

    rates = sorted([point["rate"] for point in series])
    n = len(rates)

    def percentile(pct: float) -> float:
        idx = int((pct / 100.0) * (n - 1))
        return rates[idx]

    return {
        "low": percentile(low_pct),
        "medium": percentile(medium_pct),
        "high": percentile(high_pct),
    }


def detect_regime_periods(
    curve: YieldCurve,
    core_tenors: list[int] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Identify regime boundaries for a curve.

    Args:
        curve: YieldCurve instance.
        core_tenors: List of tenor_days to analyze (if None, uses select_core_tenors).
        start_date: Start date for analysis.
        end_date: End date for analysis.

    Returns:
        list[dict]: List of regime periods with keys:
            - start_date: Period start
            - end_date: Period end
            - regime_type: Regime classification
            - representative_yield: Representative yield level for period
            - affected_tenors: List of tenors analyzed

    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> regimes = detect_regime_periods(curve)
        >>> print(f"Found {len(regimes)} regime periods")
    """
    if core_tenors is None:
        core_tenors = select_core_tenors(curve)

    if not core_tenors:
        return []

    # Get series for primary tenor (use longest available as representative)
    primary_tenor = max(core_tenors)
    series = extract_clean_series(curve, primary_tenor, start_date, end_date)

    if len(series) < 2:
        return []

    # Calculate thresholds
    thresholds = calculate_percentile_thresholds(series)

    # Calculate changes
    from apps.reference_data.analysis.curve_quality import calculate_yield_changes

    series_with_changes = calculate_yield_changes(series)

    # Detect regime periods
    regime_periods = []
    current_regime = None
    period_start = None

    for i, point in enumerate(series_with_changes):
        # Calculate gap from previous observation
        if i > 0:
            gap_days = (point["date"] - series_with_changes[i - 1]["date"]).days
        else:
            gap_days = 0

        # Classify regime for this point
        regime = classify_regime(
            yield_level=point["rate"],
            yield_change=point.get("change"),
            gap_days=gap_days,
            percentile_thresholds=thresholds,
        )

        # Start new period or continue current
        if regime != current_regime:
            # End previous period
            if current_regime is not None and period_start is not None:
                regime_periods.append(
                    {
                        "start_date": period_start,
                        "end_date": series_with_changes[i - 1]["date"],
                        "regime_type": current_regime,
                        "representative_yield": series_with_changes[i - 1]["rate"],
                        "affected_tenors": core_tenors,
                    }
                )

            # Start new period
            current_regime = regime
            period_start = point["date"]

    # Close final period
    if current_regime is not None and period_start is not None:
        regime_periods.append(
            {
                "start_date": period_start,
                "end_date": series_with_changes[-1]["date"],
                "regime_type": current_regime,
                "representative_yield": series_with_changes[-1]["rate"],
                "affected_tenors": core_tenors,
            }
        )

    return regime_periods


def compare_curves_divergence(
    curve1: YieldCurve,
    curve2: YieldCurve,
    date_range: tuple[date, date] | None = None,
) -> dict[str, Any]:
    """
    Compare two curves for divergence (e.g., CM vs GA vs CG).

    Args:
        curve1: First YieldCurve instance.
        curve2: Second YieldCurve instance.
        date_range: Tuple of (start_date, end_date) or None for all dates.

    Returns:
        dict: Divergence analysis with keys:
            - common_dates: Dates where both curves have data
            - divergence_points: List of dates with significant divergence
            - average_divergence: Average absolute yield difference
            - max_divergence: Maximum divergence observed

    Example:
        >>> cm_curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> ga_curve = YieldCurve.objects.get(name="Gabon Government Curve")
        >>> divergence = compare_curves_divergence(cm_curve, ga_curve)
    """
    # Use common core tenors
    core_tenors1 = select_core_tenors(curve1)
    core_tenors2 = select_core_tenors(curve2)
    common_tenors = sorted(list(set(core_tenors1) & set(core_tenors2)))

    if not common_tenors:
        return {
            "common_dates": [],
            "divergence_points": [],
            "average_divergence": 0.0,
            "max_divergence": 0.0,
        }

    # Use primary tenor for comparison
    primary_tenor = max(common_tenors)

    start_date, end_date = date_range if date_range else (None, None)
    series1 = extract_clean_series(curve1, primary_tenor, start_date, end_date)
    series2 = extract_clean_series(curve2, primary_tenor, start_date, end_date)

    # Build date maps
    series1_map = {point["date"]: point["rate"] for point in series1}
    series2_map = {point["date"]: point["rate"] for point in series2}

    # Find common dates
    common_dates = sorted(list(set(series1_map.keys()) & set(series2_map.keys())))

    if not common_dates:
        return {
            "common_dates": [],
            "divergence_points": [],
            "average_divergence": 0.0,
            "max_divergence": 0.0,
        }

    # Calculate divergences
    divergences = []
    divergence_points = []
    max_divergence = 0.0

    for date_val in common_dates:
        rate1 = series1_map[date_val]
        rate2 = series2_map[date_val]
        divergence = abs(rate1 - rate2)
        divergences.append(divergence)

        if divergence > max_divergence:
            max_divergence = divergence

        # Flag significant divergence (> 1.0% or > 20% relative)
        avg_rate = (rate1 + rate2) / 2
        relative_divergence = (divergence / avg_rate * 100) if avg_rate > 0 else 0

        if divergence > 1.0 or relative_divergence > 20:
            divergence_points.append(
                {
                    "date": date_val,
                    "curve1_rate": rate1,
                    "curve2_rate": rate2,
                    "absolute_divergence": divergence,
                    "relative_divergence_pct": relative_divergence,
                }
            )

    average_divergence = sum(divergences) / len(divergences) if divergences else 0.0

    return {
        "common_dates": common_dates,
        "divergence_points": divergence_points,
        "average_divergence": average_divergence,
        "max_divergence": max_divergence,
        "primary_tenor_days": primary_tenor,
    }


def identify_publication_breakdown(curve: YieldCurve) -> list[dict[str, Any]]:
    """
    Identify periods where data is missing or stale (publication breakdown).

    Args:
        curve: YieldCurve instance.

    Returns:
        list[dict]: List of breakdown periods with keys:
            - start_date: Breakdown start
            - end_date: Breakdown end
            - gap_days: Length of gap
            - staleness_at_start: Staleness days at start of gap

    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> breakdowns = identify_publication_breakdown(curve)
        >>> print(f"Found {len(breakdowns)} publication breakdown periods")
    """
    points = YieldCurvePoint.objects.filter(curve=curve).order_by("date")

    if points.count() < 2:
        return []

    # Get unique dates
    unique_dates = sorted(set(points.values_list("date", flat=True)))

    if len(unique_dates) < 2:
        return []

    breakdowns = []

    for i in range(len(unique_dates) - 1):
        gap_days = (unique_dates[i + 1] - unique_dates[i]).days

        # Flag gaps > 90 days as publication breakdown
        if gap_days > 90:
            # Check staleness at start of gap
            start_point = points.filter(date=unique_dates[i]).first()
            staleness_at_start = start_point.staleness_days if start_point else None

            breakdowns.append(
                {
                    "start_date": unique_dates[i],
                    "end_date": unique_dates[i + 1],
                    "gap_days": gap_days,
                    "staleness_at_start": staleness_at_start,
                }
            )

    # Also check if curve itself is stale
    if curve.last_observation_date:
        days_since_last = (date.today() - curve.last_observation_date).days
        if days_since_last > 90:
            breakdowns.append(
                {
                    "start_date": curve.last_observation_date,
                    "end_date": date.today(),
                    "gap_days": days_since_last,
                    "staleness_at_start": curve.staleness_days,
                    "is_current": True,
                }
            )

    return breakdowns
