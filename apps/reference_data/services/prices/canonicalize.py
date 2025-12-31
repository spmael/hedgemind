"""
Canonicalization service for instrument prices.

Selects the best price observation based on source priority hierarchy
and creates canonical InstrumentPrice records.

Default policy:
- Select observation from highest priority source (lowest priority number)
- If multiple observations from same source, use most recent revision
- Store selection_reason = AUTO_POLICY
"""

from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.utils import timezone

from apps.reference_data.models import (
    Instrument,
    InstrumentPrice,
    InstrumentPriceObservation,
    SelectionReason,
)


def canonicalize_prices(
    instrument_id: str | None = None,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    price_type: str | None = None,
) -> dict[str, int]:
    """
    Canonicalize instrument price observations for given instruments and date range.

    For each (instrument, date, price_type) combination:
    1. Fetches all observations from active sources
    2. Selects best observation based on source priority (lower = higher priority)
    3. If multiple observations from same source, uses most recent revision
    4. Creates or updates canonical InstrumentPrice

    Args:
        instrument_id: Instrument identifier (ISIN or ticker). If None, processes all instruments.
        as_of_date: Single date to canonicalize (if provided, start_date/end_date ignored).
        start_date: Start date for date range (inclusive).
        end_date: End date for date range (inclusive).
        price_type: Price type to canonicalize (e.g., "close", "ask"). If None, processes all types.

    Returns:
        dict: Summary with keys 'created', 'updated', 'skipped', 'errors', 'total_groups'.

    Example:
        >>> result = canonicalize_prices(
        ...     instrument_id="CM0000020305",
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31),
        ...     price_type="close"
        ... )
        >>> print(f"Created {result['created']} canonical prices")
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

    # Build instrument filter
    instrument_filter = Q()
    if instrument_id:
        # Try to find instrument by ISIN or ticker
        # Note: Instruments are organization-scoped, so we query using the standard manager
        # which will respect organization context if set
        instrument = None
        try:
            # Try ISIN first
            instrument = Instrument.objects.filter(isin=instrument_id).first()
            if not instrument:
                # Try ticker
                instrument = Instrument.objects.filter(ticker=instrument_id).first()
        except Exception:
            pass

        if instrument:
            instrument_filter = Q(instrument=instrument)
        else:
            return {
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "errors": [
                    f"Instrument '{instrument_id}' not found (by ISIN or ticker)"
                ],
                "total_groups": 0,
            }

    # Build price_type filter
    price_type_filter = Q()
    if price_type:
        price_type_filter = Q(price_type=price_type.lower())

    # Get all observations from active sources
    observations = (
        InstrumentPriceObservation.objects.filter(
            instrument_filter & date_filter & price_type_filter
        )
        .filter(source__is_active=True)
        .select_related("source", "instrument")
        .order_by("instrument", "date", "price_type", "source__priority", "-revision")
    )

    # Group by (instrument, date, price_type)
    grouped = {}
    for obs in observations:
        key = (obs.instrument_id, obs.date, obs.price_type)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(obs)

    created = 0
    updated = 0
    skipped = 0
    errors = []

    # Process each group
    for (instrument_id_val, obs_date, price_type_val), obs_list in grouped.items():
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

            # Create or update canonical price
            canonical_price, was_created = InstrumentPrice.objects.update_or_create(
                instrument=best_obs.instrument,
                date=best_obs.date,
                price_type=best_obs.price_type,
                defaults={
                    "chosen_source": best_obs.source,
                    "observation": best_obs,
                    "price": best_obs.price,
                    "quote_convention": best_obs.quote_convention,
                    "clean_or_dirty": best_obs.clean_or_dirty,
                    "volume": best_obs.volume,
                    "currency": best_obs.currency,
                    "selection_reason": SelectionReason.AUTO_POLICY,
                    "selected_at": timezone.now(),
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors.append(
                f"Error processing instrument_id={instrument_id_val}, date={obs_date}, price_type={price_type_val}: {str(e)}"
            )

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total_groups": len(grouped),
    }
