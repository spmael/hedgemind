"""
Canonicalization service for market index values.

Selects the best index value observation based on source priority hierarchy
and creates canonical MarketIndexValue records.

Default policy:
- Select observation from highest priority source (lowest priority number)
- If multiple observations from same source, use most recent revision
- Store selection_reason = AUTO_POLICY
"""

from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.utils import timezone

from apps.reference_data.models import (MarketIndex, MarketIndexValue,
                                        MarketIndexValueObservation,
                                        SelectionReason)


def canonicalize_index_values(
    index_code: str | None = None,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    """
    Canonicalize market index value observations for a given index and date range.

    For each (index, date) combination:
    1. Fetches all observations from active sources
    2. Selects best observation based on source priority (lower = higher priority)
    3. If multiple observations from same source, uses most recent revision
    4. Creates or updates canonical MarketIndexValue

    Args:
        index_code: Index code (e.g., "BVMAC"). If None, processes all indices.
        as_of_date: Single date to canonicalize (if provided, start_date/end_date ignored).
        start_date: Start date for date range (inclusive).
        end_date: End date for date range (inclusive).

    Returns:
        dict: Summary with keys 'created', 'updated', 'skipped', 'errors', 'total_groups'.

    Example:
        >>> result = canonicalize_index_values(
        ...     index_code="BVMAC",
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31)
        ... )
        >>> print(f"Created {result['created']} canonical values")
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

    # Build index filter
    index_filter = Q()
    if index_code:
        try:
            index = MarketIndex.objects.get(code=index_code.upper())
            index_filter = Q(index=index)
        except MarketIndex.DoesNotExist:
            return {
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [f"Index code '{index_code}' not found"],
                "total_groups": 0,
            }

    # Get all observations from active sources
    observations = (
        MarketIndexValueObservation.objects.filter(index_filter & date_filter)
        .filter(source__is_active=True)
        .select_related("source", "index")
        .order_by("index", "date", "source__priority", "-revision")
    )

    # Group by (index, date)
    grouped = {}
    for obs in observations:
        key = (obs.index_id, obs.date)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(obs)

    created = 0
    updated = 0
    skipped = 0
    errors = []

    # Process each group
    for (index_id, obs_date), obs_list in grouped.items():
        try:
            # Select best observation: highest priority (lowest priority number),
            # then most recent revision
            best_obs = None
            best_priority = None
            best_revision = -1

            for obs in obs_list:
                priority = obs.source.priority
                revision = obs.revision

                if best_obs is None:
                    best_obs = obs
                    best_priority = priority
                    best_revision = revision
                elif priority < best_priority:
                    # Lower priority number = higher priority
                    best_obs = obs
                    best_priority = priority
                    best_revision = revision
                elif priority == best_priority and revision > best_revision:
                    # Same priority, use most recent revision
                    best_obs = obs
                    best_revision = revision

            if not best_obs:
                skipped += 1
                continue

            # Create or update canonical value
            canonical_value, was_created = MarketIndexValue.objects.update_or_create(
                index=best_obs.index,
                date=best_obs.date,
                defaults={
                    "chosen_source": best_obs.source,
                    "observation": best_obs,
                    "value": best_obs.value,
                    "return_pct": best_obs.return_pct,
                    "selection_reason": SelectionReason.AUTO_POLICY,
                    "selected_at": timezone.now(),
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors.append(f"Error processing index_id={index_id}, date={obs_date}: {str(e)}")

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total_groups": len(grouped),
    }

