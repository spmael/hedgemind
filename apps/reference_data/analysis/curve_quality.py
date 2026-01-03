"""
Yield curve data quality and normalization analysis.

Implements Phase 0 (Data Inventory & Governance) and Phase 1 (Normalize Without Distortion).

Phase 0: Know exactly what curve data exists and its quality characteristics.
Phase 1: Make curves comparable without inventing data (no interpolation, no smoothing).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from django.db.models import Max, Min, Q

from apps.reference_data.models import YieldCurve, YieldCurvePoint


def inventory_curves() -> dict[str, Any]:
    """
    List all curves with basic metadata.
    
    Returns inventory of all yield curves including:
    - Curve name, currency, country, type
    - Basic statistics (point count, date range)
    
    Returns:
        dict: Inventory data with keys:
            - curves: List of curve metadata dictionaries
            - total_curves: Total number of curves
            - total_points: Total number of canonical points across all curves
    
    Example:
        >>> inventory = inventory_curves()
        >>> print(f"Found {inventory['total_curves']} curves")
    """
    curves = YieldCurve.objects.filter(is_active=True).select_related()
    curve_list = []
    total_points = 0
    
    for curve in curves:
        points = YieldCurvePoint.objects.filter(curve=curve)
        point_count = points.count()
        total_points += point_count
        
        # Get date range
        date_range = points.aggregate(
            min_date=Min("date"),
            max_date=Max("date")
        )
        
        curve_list.append({
            "id": curve.id,
            "name": curve.name,
            "currency": str(curve.currency),
            "country": str(curve.country),
            "curve_type": curve.curve_type,
            "point_count": point_count,
            "first_date": date_range["min_date"],
            "last_date": date_range["max_date"],
            "last_observation_date": curve.last_observation_date,
            "staleness_days": curve.staleness_days,
        })
    
    return {
        "curves": curve_list,
        "total_curves": len(curve_list),
        "total_points": total_points,
    }


def analyze_curve_coverage(
    curve: YieldCurve,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """
    Analyze curve coverage: tenors available, missing months, gaps.
    
    Args:
        curve: YieldCurve instance to analyze.
        start_date: Start date for analysis (if None, uses first point date).
        end_date: End date for analysis (if None, uses last point date).
    
    Returns:
        dict: Coverage analysis with keys:
            - available_tenors: List of tenor_days that have data
            - tenor_coverage: Dict mapping tenor_days to date coverage info
            - missing_months: List of (year, month) tuples with no data
            - total_expected_months: Total months in date range
            - total_observed_months: Months with at least one point
            - coverage_pct: Percentage of months with data
    
    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> coverage = analyze_curve_coverage(curve)
        >>> print(f"Coverage: {coverage['coverage_pct']:.1f}%")
    """
    points = YieldCurvePoint.objects.filter(curve=curve)
    
    # Determine date range
    date_range = points.aggregate(
        min_date=Min("date"),
        max_date=Max("date")
    )
    
    if not date_range["min_date"]:
        return {
            "available_tenors": [],
            "tenor_coverage": {},
            "missing_months": [],
            "total_expected_months": 0,
            "total_observed_months": 0,
            "coverage_pct": 0.0,
        }
    
    analysis_start = start_date or date_range["min_date"]
    analysis_end = end_date or date_range["max_date"]
    
    # Get all unique tenors
    tenor_days_list = points.values_list("tenor_days", flat=True).distinct()
    available_tenors = sorted(list(tenor_days_list))
    
    # Analyze coverage per tenor
    tenor_coverage = {}
    all_dates_with_data = set()
    
    for tenor_days in available_tenors:
        tenor_points = points.filter(tenor_days=tenor_days, date__gte=analysis_start, date__lte=analysis_end)
        tenor_dates = set(tenor_points.values_list("date", flat=True))
        all_dates_with_data.update(tenor_dates)
        
        tenor_date_range = tenor_points.aggregate(
            min_date=Min("date"),
            max_date=Max("date")
        )
        
        tenor_coverage[tenor_days] = {
            "point_count": tenor_points.count(),
            "first_date": tenor_date_range["min_date"],
            "last_date": tenor_date_range["max_date"],
            "dates_with_data": len(tenor_dates),
        }
    
    # Calculate missing months
    missing_months = []
    current_date = analysis_start.replace(day=1)  # Start of first month
    
    while current_date <= analysis_end:
        # Check if any point exists in this month
        month_start = current_date
        if current_date.month == 12:
            month_end = date(current_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
        
        month_end = min(month_end, analysis_end)
        
        has_data = any(
            month_start <= d <= month_end for d in all_dates_with_data
        )
        
        if not has_data:
            missing_months.append((current_date.year, current_date.month))
        
        # Move to next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)
    
    # Calculate coverage percentage
    total_months = (
        (analysis_end.year - analysis_start.year) * 12
        + (analysis_end.month - analysis_start.month)
        + 1
    )
    observed_months = total_months - len(missing_months)
    coverage_pct = (observed_months / total_months * 100) if total_months > 0 else 0.0
    
    return {
        "available_tenors": available_tenors,
        "tenor_coverage": tenor_coverage,
        "missing_months": missing_months,
        "total_expected_months": total_months,
        "total_observed_months": observed_months,
        "coverage_pct": coverage_pct,
        "analysis_start": analysis_start,
        "analysis_end": analysis_end,
    }


def calculate_publication_gaps(curve: YieldCurve) -> dict[str, Any]:
    """
    Calculate publication gaps: longest gap, frequency analysis.
    
    Args:
        curve: YieldCurve instance to analyze.
    
    Returns:
        dict: Gap analysis with keys:
            - longest_gap_days: Longest gap between observations (in days)
            - longest_gap_start: Start date of longest gap
            - longest_gap_end: End date of longest gap
            - average_gap_days: Average gap between observations
            - frequency_observed: Most common frequency (daily/weekly/monthly)
            - gap_distribution: Dict mapping gap ranges to counts
    
    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> gaps = calculate_publication_gaps(curve)
        >>> print(f"Longest gap: {gaps['longest_gap_days']} days")
    """
    points = YieldCurvePoint.objects.filter(curve=curve).order_by("date")
    
    if points.count() < 2:
        return {
            "longest_gap_days": 0,
            "longest_gap_start": None,
            "longest_gap_end": None,
            "average_gap_days": 0.0,
            "frequency_observed": "unknown",
            "gap_distribution": {},
        }
    
    # Get all unique dates (across all tenors)
    unique_dates = sorted(
        set(points.values_list("date", flat=True))
    )
    
    if len(unique_dates) < 2:
        return {
            "longest_gap_days": 0,
            "longest_gap_start": None,
            "longest_gap_end": None,
            "average_gap_days": 0.0,
            "frequency_observed": "unknown",
            "gap_distribution": {},
        }
    
    # Calculate gaps between consecutive dates
    gaps = []
    longest_gap = 0
    longest_gap_start = None
    longest_gap_end = None
    
    for i in range(len(unique_dates) - 1):
        gap_days = (unique_dates[i + 1] - unique_dates[i]).days
        gaps.append(gap_days)
        
        if gap_days > longest_gap:
            longest_gap = gap_days
            longest_gap_start = unique_dates[i]
            longest_gap_end = unique_dates[i + 1]
    
    # Calculate average gap
    average_gap = sum(gaps) / len(gaps) if gaps else 0.0
    
    # Determine frequency
    gap_counts = defaultdict(int)
    for gap in gaps:
        if gap <= 3:
            gap_counts["daily"] += 1
        elif gap <= 10:
            gap_counts["weekly"] += 1
        elif gap <= 35:
            gap_counts["monthly"] += 1
        else:
            gap_counts["irregular"] += 1
    
    frequency_observed = max(gap_counts.items(), key=lambda x: x[1])[0] if gap_counts else "unknown"
    
    # Gap distribution
    gap_distribution = {
        "1-7 days": sum(1 for g in gaps if 1 <= g <= 7),
        "8-30 days": sum(1 for g in gaps if 8 <= g <= 30),
        "31-90 days": sum(1 for g in gaps if 31 <= g <= 90),
        "91-180 days": sum(1 for g in gaps if 91 <= g <= 180),
        "181+ days": sum(1 for g in gaps if g > 180),
    }
    
    return {
        "longest_gap_days": longest_gap,
        "longest_gap_start": longest_gap_start,
        "longest_gap_end": longest_gap_end,
        "average_gap_days": average_gap,
        "frequency_observed": frequency_observed,
        "gap_distribution": gap_distribution,
        "total_gaps": len(gaps),
    }


def generate_availability_matrix() -> dict[str, Any]:
    """
    Generate curve availability matrix (country × tenor × date coverage).
    
    Returns:
        dict: Availability matrix with structure:
            - matrix: Dict mapping country_code to dict mapping tenor_days to coverage info
            - summary: Overall statistics
    
    Example:
        >>> matrix = generate_availability_matrix()
        >>> print(matrix["summary"]["total_countries"])
    """
    curves = YieldCurve.objects.filter(is_active=True)
    matrix = defaultdict(lambda: defaultdict(dict))
    
    for curve in curves:
        country_code = str(curve.country)
        coverage = analyze_curve_coverage(curve)
        
        for tenor_days in coverage["available_tenors"]:
            tenor_info = coverage["tenor_coverage"][tenor_days]
            matrix[country_code][tenor_days] = {
                "curve_name": curve.name,
                "curve_id": curve.id,
                "first_date": tenor_info["first_date"],
                "last_date": tenor_info["last_date"],
                "point_count": tenor_info["point_count"],
                "dates_with_data": tenor_info["dates_with_data"],
            }
    
    # Calculate summary
    total_countries = len(matrix)
    all_tenors = set()
    for country_data in matrix.values():
        all_tenors.update(country_data.keys())
    
    return {
        "matrix": dict(matrix),
        "summary": {
            "total_countries": total_countries,
            "total_tenors": len(all_tenors),
            "tenors": sorted(list(all_tenors)),
        },
    }


# Phase 1: Normalization functions

def select_core_tenors(curve: YieldCurve) -> list[int]:
    """
    Identify core tenors (short/medium/long) for a curve.
    
    Selects representative tenors that span the curve:
    - Short term: 3M (90 days) or closest available
    - Medium term: 1Y (365 days) or 5Y (1825 days) or closest available
    - Long term: 10Y (3650 days) or closest available
    
    Args:
        curve: YieldCurve instance.
    
    Returns:
        list[int]: List of core tenor_days values.
    
    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> core_tenors = select_core_tenors(curve)
        >>> print(f"Core tenors: {core_tenors}")
    """
    points = YieldCurvePoint.objects.filter(curve=curve)
    available_tenors = sorted(set(points.values_list("tenor_days", flat=True)))
    
    if not available_tenors:
        return []
    
    # Target tenors: 3M (90), 1Y (365), 5Y (1825), 10Y (3650)
    target_tenors = [90, 365, 1825, 3650]
    core_tenors = []
    
    for target in target_tenors:
        # Find closest available tenor to target
        closest = min(available_tenors, key=lambda x: abs(x - target))
        if closest not in core_tenors:
            core_tenors.append(closest)
    
    return sorted(core_tenors)


def extract_clean_series(
    curve: YieldCurve,
    tenor_days: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Extract clean yield series for a specific tenor (observed points only, no interpolation).
    
    Args:
        curve: YieldCurve instance.
        tenor_days: Tenor in days.
        start_date: Start date (if None, uses first point).
        end_date: End date (if None, uses last point).
    
    Returns:
        list[dict]: List of observations with keys: date, rate, last_published_date, staleness_days
    
    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> series = extract_clean_series(curve, tenor_days=1825)
        >>> print(f"Series length: {len(series)}")
    """
    points = YieldCurvePoint.objects.filter(
        curve=curve,
        tenor_days=tenor_days
    ).order_by("date")
    
    if start_date:
        points = points.filter(date__gte=start_date)
    if end_date:
        points = points.filter(date__lte=end_date)
    
    series = []
    for point in points:
        series.append({
            "date": point.date,
            "rate": float(point.rate),
            "last_published_date": point.last_published_date,
            "staleness_days": point.staleness_days,
            "published_date_assumed": point.published_date_assumed,
        })
    
    return series


def calculate_yield_changes(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Calculate period-over-period yield changes (not fitted curves).
    
    Args:
        series: List of yield observations (from extract_clean_series).
    
    Returns:
        list[dict]: List with added 'change' and 'change_pct' keys.
    
    Example:
        >>> series = extract_clean_series(curve, 1825)
        >>> changes = calculate_yield_changes(series)
        >>> print(f"First change: {changes[1]['change']}")
    """
    if len(series) < 2:
        return series
    
    result = [series[0].copy()]  # First point has no change
    result[0]["change"] = None
    result[0]["change_pct"] = None
    
    for i in range(1, len(series)):
        point = series[i].copy()
        prev_rate = series[i - 1]["rate"]
        curr_rate = point["rate"]
        
        point["change"] = curr_rate - prev_rate
        point["change_pct"] = ((curr_rate - prev_rate) / prev_rate * 100) if prev_rate != 0 else None
        
        result.append(point)
    
    return result


def normalize_curves_for_comparison(
    curves: list[YieldCurve],
    core_tenors: list[int] | None = None,
) -> dict[str, Any]:
    """
    Normalize curves for comparison: align by date, keep only observed points.
    
    Args:
        curves: List of YieldCurve instances to compare.
        core_tenors: List of tenor_days to use (if None, uses intersection of all curves).
    
    Returns:
        dict: Normalized data with keys:
            - dates: Sorted list of dates where at least one curve has data
            - curves_data: Dict mapping curve_id to dict mapping tenor_days to series
            - common_dates: Dates where all curves have data for all core_tenors
    
    Example:
        >>> curves = YieldCurve.objects.filter(country="CM")
        >>> normalized = normalize_curves_for_comparison(list(curves))
        >>> print(f"Common dates: {len(normalized['common_dates'])}")
    """
    if not curves:
        return {
            "dates": [],
            "curves_data": {},
            "common_dates": [],
        }
    
    # Determine core tenors if not provided
    if core_tenors is None:
        all_tenors = set()
        for curve in curves:
            curve_tenors = select_core_tenors(curve)
            all_tenors.update(curve_tenors)
        core_tenors = sorted(list(all_tenors))
    
    # Extract series for each curve and tenor
    curves_data = {}
    all_dates = set()
    
    for curve in curves:
        curves_data[curve.id] = {}
        for tenor_days in core_tenors:
            series = extract_clean_series(curve, tenor_days)
            curves_data[curve.id][tenor_days] = series
            all_dates.update(point["date"] for point in series)
    
    sorted_dates = sorted(list(all_dates))
    
    # Find common dates (where all curves have data for all core_tenors)
    common_dates = []
    for date_val in sorted_dates:
        has_all_data = all(
            any(
                point["date"] == date_val
                for point in curves_data[curve.id].get(tenor_days, [])
            )
            for curve in curves
            for tenor_days in core_tenors
        )
        if has_all_data:
            common_dates.append(date_val)
    
    return {
        "dates": sorted_dates,
        "curves_data": curves_data,
        "common_dates": common_dates,
        "core_tenors": core_tenors,
    }

