"""
Canonicalization service for FX rates.

For BEAC FX data, BUY and SELL rates are ingested as observations;
the canonical FX rate used for valuation is the MID computed from BUY/SELL
unless explicitly overridden.

Default policy:
- Use MID = (BUY + SELL) / 2 when both are available
- Use the available one if only one side exists (with flag for incomplete spread)
- Store selection_reason = AUTO_POLICY_MID_FROM_BEAC
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.reference_data.models import FXRate, FXRateObservation, SelectionReason
from apps.reference_data.utils.priority import get_effective_priority


def canonicalize_fx_rates(
    base_currency: str | None = None,
    quote_currency: str | None = None,
    as_of_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    """
    Canonicalize FX rate observations for a given currency pair and date range.

    For each (base_currency, quote_currency, date) combination:
    1. Fetches BUY and SELL observations from active sources
    2. Computes MID = (BUY + SELL) / 2 if both exist
    3. Uses the available one if only one side exists
    4. Creates or updates canonical FXRate with rate_type=MID

    Args:
        base_currency: Base currency code (e.g., "XAF"). If None, processes all base currencies.
        quote_currency: Quote currency code (e.g., "USD"). If None, processes all quote currencies.
        as_of_date: Single date to canonicalize (if provided, start_date/end_date ignored).
        start_date: Start date for date range (inclusive).
        end_date: End date for date range (inclusive).

    Returns:
        dict: Summary with keys 'created', 'updated', 'skipped', 'errors', 'total_groups'.

    Example:
        >>> result = canonicalize_fx_rates(
        ...     base_currency="XAF",
        ...     quote_currency="EUR",
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 12, 31)
        ... )
        >>> print(f"Created {result['created']} canonical rates")
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

    # Build currency filters
    currency_filter = Q()
    if base_currency:
        currency_filter &= Q(base_currency=base_currency.upper())
    if quote_currency:
        currency_filter &= Q(quote_currency=quote_currency.upper())

    # Get all BUY and SELL observations from active sources
    observations = (
        FXRateObservation.objects.filter(
            currency_filter & date_filter & Q(rate_type__in=["buy", "sell"])
        )
        .filter(source__is_active=True)
        .select_related("source")
    )

    # Group by (base_currency, quote_currency, date)
    grouped = {}
    for obs in observations:
        key = (obs.base_currency, obs.quote_currency, obs.date)
        if key not in grouped:
            grouped[key] = {"buy": [], "sell": []}
        if obs.rate_type == "buy":
            grouped[key]["buy"].append(obs)
        elif obs.rate_type == "sell":
            grouped[key]["sell"].append(obs)

    created = 0
    updated = 0
    skipped = 0
    errors = []
    selected_at = timezone.now()

    # Process each group
    for (base_ccy, quote_ccy, obs_date), obs_dict in grouped.items():
        buy_obs_list = obs_dict["buy"]
        sell_obs_list = obs_dict["sell"]

        # Sort by: priority (asc), revision (desc), observed_at (desc)
        # Lower priority number = higher priority
        # Use effective priority (org-specific override or global)
        buy_obs_list.sort(
            key=lambda x: (
                get_effective_priority(x.source, "fx_rate"),
                -x.revision,
                -x.observed_at.timestamp() if x.observed_at else 0,
            )
        )
        sell_obs_list.sort(
            key=lambda x: (
                get_effective_priority(x.source, "fx_rate"),
                -x.revision,
                -x.observed_at.timestamp() if x.observed_at else 0,
            )
        )

        # Select best BUY and SELL observations
        best_buy = buy_obs_list[0] if buy_obs_list else None
        best_sell = sell_obs_list[0] if sell_obs_list else None

        # Determine canonical rate and selection logic
        if best_buy and best_sell:
            # Both sides available: compute MID
            mid_rate = (best_buy.rate + best_sell.rate) / Decimal("2")
            canonical_rate = mid_rate
            chosen_source = (
                best_buy.source
            )  # Use BUY source (or could use SELL, preference is BUY)
            observation = best_buy  # Link to BUY observation
            selection_reason = SelectionReason.AUTO_POLICY_MID_FROM_BEAC
        elif best_buy:
            # Only BUY available
            canonical_rate = best_buy.rate
            chosen_source = best_buy.source
            observation = best_buy
            selection_reason = SelectionReason.ONLY_AVAILABLE
            # Note: In future, could add is_spread_incomplete flag
        elif best_sell:
            # Only SELL available
            canonical_rate = best_sell.rate
            chosen_source = best_sell.source
            observation = best_sell
            selection_reason = SelectionReason.ONLY_AVAILABLE
            # Note: In future, could add is_spread_incomplete flag
        else:
            # This shouldn't happen given our grouping, but handle it
            skipped += 1
            continue

        try:
            # Create or update canonical FXRate with rate_type=MID
            canonical_fx_rate, created_flag = FXRate.objects.update_or_create(
                base_currency=base_ccy,
                quote_currency=quote_ccy,
                date=obs_date,
                rate_type=FXRate.RateType.MID,  # Canonical rates are always MID
                defaults={
                    "rate": canonical_rate,
                    "chosen_source": chosen_source,
                    "observation": observation,
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
                f"Error processing {base_ccy}/{quote_ccy} on {obs_date}: {str(e)}"
            )
            skipped += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total_groups": len(grouped),
    }
