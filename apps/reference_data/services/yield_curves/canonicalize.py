# apps/reference_data/services/yield_curve/canonicalize.py
"""
Canonicalization service for yield curves.

Selects the best yield curve observations based on source priority and creates
canonical YieldCurvePoint records.
"""

from __future__ import annotations

from datetime import date
from django.utils import timezone
from django.db.models import Q

from apps.reference_data.models import (
    YieldCurve,
    YieldCurvePointObservation,
    YieldCurvePoint,
    SelectionReason,
)


def canonicalize_yield_curves(
    curve: YieldCurve | None = None,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    """
    Canonicalize yield curve observations for a given curve and date range.
    
    For each (curve, tenor_days, date) combination:
    1. Fetches all observations from active sources
    2. Applies source priority (lower priority number = higher priority)
    3. Selects best observation (highest priority, highest revision, most recent observed_at)
    4. Creates or updates canonical YieldCurvePoint
    
    Args:
        curve: YieldCurve instance (if None, processes all curves).
        as_of_date: Single date to canonicalize (if provided, start_date/end_date ignored).
        start_date: Start date for date range (inclusive).
        end_date: End date for date range (inclusive).
    
    Returns:
        dict: Summary with keys 'created', 'updated', 'skipped', 'errors'.
    
    Example:
        >>> curve = YieldCurve.objects.get(name="Cameroon Government Curve")
        >>> result = canonicalize_yield_curves(
        ...     curve=curve,
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31)
        ... )
        >>> print(f"Created {result['created']} canonical points")
    """
    # Build date filter
    if as_of_date:
        date_filter = Q(date=as_of_date)
    elif start_date and end_date:
        date_filter = Q(date__gte=start_date, date__lte=end_date)
    elif start_date:
        date_filter = Q(date__gte=start_date)
    elif end_date:
        date_filter = Q(date__lte=end_date)
    else:
        # No date filter - process all dates
        date_filter = Q()
    
    # Build curve filter
    if curve:
        curve_filter = Q(curve=curve)
    else:
        curve_filter = Q()
    
    # Get all unique (curve, tenor_days, date) combinations
    observations = YieldCurvePointObservation.objects.filter(
        curve_filter & date_filter
    ).select_related("curve", "source")
    
    # Group by (curve, tenor_days, date)
    grouped = {}
    for obs in observations:
        key = (obs.curve_id, obs.tenor_days, obs.date)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(obs)
    
    created = 0
    updated = 0
    skipped = 0
    errors = []
    selected_at = timezone.now()
    
    # Process each group
    for (curve_id, tenor_days, obs_date), obs_list in grouped.items():
        # Filter to active sources only
        active_obs = [obs for obs in obs_list if obs.source.is_active]
        
        if not active_obs:
            skipped += 1
            continue
        
        # Sort by: priority (asc), revision (desc), observed_at (desc)
        # Lower priority number = higher priority
        active_obs.sort(
            key=lambda x: (
                x.source.priority,
                -x.revision,  # Negative for descending
                -x.observed_at.timestamp() if x.observed_at else 0,
            )
        )
        
        # Select best observation
        best_obs = active_obs[0]
        
        # Determine selection reason
        if len(active_obs) == 1:
            selection_reason = SelectionReason.ONLY_AVAILABLE
        else:
            selection_reason = SelectionReason.AUTO_POLICY
        
        try:
            # Get curve instance
            curve_instance = best_obs.curve
            
            # Create or update canonical point
            canonical_point, created_flag = YieldCurvePoint.objects.update_or_create(
                curve=curve_instance,
                tenor_days=tenor_days,
                date=obs_date,
                defaults={
                    "tenor": best_obs.tenor,
                    "rate": best_obs.rate,
                    "chosen_source": best_obs.source,
                    "observation": best_obs,
                    "selection_reason": selection_reason,
                    "selected_at": selected_at,
                },
            )
            
            if created_flag:
                created += 1
            else:
                updated += 1
                
        except Exception as e:
            errors.append(
                f"Error processing curve_id={curve_id}, tenor_days={tenor_days}, "
                f"date={obs_date}: {str(e)}"
            )
            skipped += 1
    
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total_groups": len(grouped),
    }