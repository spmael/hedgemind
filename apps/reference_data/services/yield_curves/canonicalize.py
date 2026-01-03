# apps/reference_data/services/yield_curve/canonicalize.py
"""
Canonicalization service for yield curves.

Selects the best yield curve observations based on source priority and creates
canonical YieldCurvePoint records.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Max, Q
from django.utils import timezone

from apps.reference_data.models import (
    SelectionReason,
    YieldCurve,
    YieldCurvePoint,
    YieldCurvePointObservation,
)
from apps.reference_data.models.market_data import MarketDataSource
from apps.reference_data.utils.priority import get_effective_priority


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
        dict: Summary with keys 'created', 'updated', 'skipped', 'errors', 'total_groups', 'curves_updated'.
            - curves_updated: Number of curves whose last_observation_date was automatically updated.

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
    curves_processed = set()  # Track curves for staleness update

    # Process each group
    for (curve_id, tenor_days, obs_date), obs_list in grouped.items():
        # Filter to active sources only
        active_obs = [obs for obs in obs_list if obs.source.is_active]

        if not active_obs:
            skipped += 1
            continue

        # Sort by: priority (asc), revision (desc), observed_at (desc)
        # Lower priority number = higher priority
        # Use effective priority (org-specific override or global)
        active_obs.sort(
            key=lambda x: (
                get_effective_priority(x.source, "yield_curve"),
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

            # Determine metadata for data-quality-aware stress narratives
            # Explicit assumption: if publication date not provided, assume it equals curve_date
            if best_obs.observed_at:
                # Use observed_at date as last_published_date (when source published the data)
                last_published_date = best_obs.observed_at.date()
                published_date_assumed = False
            else:
                # Explicit assumption: published_date = curve_date when not provided
                last_published_date = obs_date  # curve_date
                published_date_assumed = True

            # Mark as official if source is BEAC or central bank type
            is_official = (
                best_obs.source.code == "BEAC"
                or best_obs.source.source_type
                == MarketDataSource.SourceType.CENTRAL_BANK
            )

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
                    "last_published_date": last_published_date,
                    "published_date_assumed": published_date_assumed,
                    "is_official": is_official,
                },
            )

            if created_flag:
                created += 1
            else:
                updated += 1

            # Track curve for staleness update
            curves_processed.add(curve_instance.id)

        except Exception as e:
            errors.append(
                f"Error processing curve_id={curve_id}, tenor_days={tenor_days}, "
                f"date={obs_date}: {str(e)}"
            )
            skipped += 1

    # Automatically maintain curve-level staleness: update last_observation_date
    # This is the primary indicator for curve staleness in stress narratives
    curves_updated = 0
    for curve_id in curves_processed:
        try:
            curve = YieldCurve.objects.get(id=curve_id)
            # Get max date from all canonical points for this curve
            max_date_result = YieldCurvePoint.objects.filter(curve=curve).aggregate(
                max_date=Max("date")
            )
            max_date = max_date_result.get("max_date")
            if max_date:
                curve.last_observation_date = max_date
                curve.save(update_fields=["last_observation_date", "updated_at"])
                curves_updated += 1
        except YieldCurve.DoesNotExist:
            errors.append(f"Curve with id={curve_id} not found for staleness update")
        except Exception as e:
            errors.append(f"Error updating staleness for curve_id={curve_id}: {str(e)}")

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total_groups": len(grouped),
        "curves_updated": curves_updated,
    }
