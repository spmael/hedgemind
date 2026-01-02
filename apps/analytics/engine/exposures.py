"""
Exposure computation engine for portfolio analytics.

This module provides pure Python functions to compute portfolio exposures from
ValuationPositionResult data. Exposures are computed by aggregating position
values across different dimensions (currency, issuer, country, instrument_group,
instrument_type) to identify concentration risk and portfolio composition.

Key functions:
- compute_exposures: Main entry point for computing all exposure types
- compute_currency_exposures: Currency exposure breakdown
- compute_issuer_exposures: Issuer concentration analysis
- compute_country_exposures: Country exposure breakdown
- compute_instrument_group_exposures: Instrument group exposure
- compute_instrument_type_exposures: Instrument type exposure
- compute_top_concentrations: Top N concentration analysis
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django_countries import countries
from djmoney.money import Money

if TYPE_CHECKING:
    from apps.analytics.models import ValuationRun


def compute_exposures(run: ValuationRun) -> dict:
    """
    Compute all exposure types for a valuation run.

    Main entry point that computes exposures across all dimensions and returns
    a structured dictionary with exposure breakdowns. All values are in portfolio
    base currency.

    Args:
        run: ValuationRun instance to compute exposures for.

    Returns:
        Dictionary with exposure breakdowns:
        {
            'currency': list[dict],  # Currency exposures
            'issuer': list[dict],    # Issuer exposures
            'country': list[dict],   # Country exposures
            'instrument_group': list[dict],  # Instrument group exposures
            'instrument_type': list[dict],   # Instrument type exposures
            'total_market_value': Money,  # Total portfolio value (for pct calculations)
        }

    Example:
        >>> run = ValuationRun.objects.get(id=1)
        >>> exposures = compute_exposures(run)
        >>> print(exposures['currency'])
        [{'currency': 'XAF', 'value_base': Money(1000000, 'XAF'), 'pct_total': Decimal('50.00')}, ...]
    """
    results = run.get_results().select_related(
        "position_snapshot__instrument__issuer",
        "position_snapshot__instrument__instrument_group",
        "position_snapshot__instrument__instrument_type",
    )

    if not results.exists():
        total_mv = Money(0, run.portfolio.base_currency)
        return {
            "currency": [],
            "issuer": [],
            "country": [],
            "instrument_group": [],
            "instrument_type": [],
            "total_market_value": total_mv,
        }

    # Get total market value for percentage calculations
    total_mv = run.get_total_market_value()

    return {
        "currency": compute_currency_exposures(results, total_mv),
        "issuer": compute_issuer_exposures(results, total_mv),
        "country": compute_country_exposures(results, total_mv),
        "instrument_group": compute_instrument_group_exposures(results, total_mv),
        "instrument_type": compute_instrument_type_exposures(results, total_mv),
        "total_market_value": total_mv,
    }


def compute_currency_exposures(
    results: QuerySet, total_market_value: Money
) -> list[dict]:
    """
    Compute currency exposures from valuation results.

    Groups positions by instrument currency and sums market values in base currency.
    Returns sorted list (descending by value).

    Args:
        results: QuerySet of ValuationPositionResult objects.
        total_market_value: Total portfolio value in base currency (for pct calculation).

    Returns:
        List of dictionaries with currency exposure data:
        [
            {
                'currency': str,  # Currency code (e.g., 'USD', 'XAF')
                'value_base': Money,  # Total exposure in base currency
                'pct_total': Decimal,  # Percentage of total portfolio
            },
            ...
        ]

    Example:
        >>> results = run.get_results()
        >>> total = run.get_total_market_value()
        >>> currency_exposures = compute_currency_exposures(results, total)
        >>> print(currency_exposures[0]['currency'])
        'USD'
    """
    currency_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for result in results:
        instrument = result.position_snapshot.instrument
        currency = str(instrument.currency) if instrument.currency else "UNKNOWN"
        value = result.market_value_base_currency.amount
        currency_totals[currency] += value

    # Convert to list of dicts and calculate percentages
    base_currency = total_market_value.currency
    total_amount = total_market_value.amount

    exposures = []
    for currency, value_amount in sorted(
        currency_totals.items(), key=lambda x: x[1], reverse=True
    ):
        pct_total = (
            (value_amount / total_amount * 100) if total_amount > 0 else Decimal("0")
        )
        exposures.append(
            {
                "currency": currency,
                "value_base": Money(value_amount, base_currency),
                "pct_total": pct_total,
            }
        )

    return exposures


def compute_issuer_exposures(
    results: QuerySet, total_market_value: Money
) -> list[dict]:
    """
    Compute issuer exposures from valuation results.

    Groups positions by issuer and sums market values. Handles NULL issuers gracefully.
    Returns sorted list (descending by value).

    Args:
        results: QuerySet of ValuationPositionResult objects.
        total_market_value: Total portfolio value in base currency (for pct calculation).

    Returns:
        List of dictionaries with issuer exposure data:
        [
            {
                'issuer_id': int | None,  # Issuer ID (None if no issuer)
                'issuer_name': str,  # Issuer name or 'Unknown'
                'value_base': Money,  # Total exposure in base currency
                'pct_total': Decimal,  # Percentage of total portfolio
            },
            ...
        ]

    Example:
        >>> results = run.get_results()
        >>> total = run.get_total_market_value()
        >>> issuer_exposures = compute_issuer_exposures(results, total)
        >>> print(issuer_exposures[0]['issuer_name'])
        'Republic of Cameroon'
    """
    issuer_totals: dict[int | None, Decimal] = defaultdict(lambda: Decimal("0"))
    issuer_names: dict[int | None, str] = {}

    for result in results:
        instrument = result.position_snapshot.instrument
        issuer = instrument.issuer
        issuer_id = issuer.id if issuer else None
        issuer_name = issuer.name if issuer else "Unknown"
        value = result.market_value_base_currency.amount

        issuer_totals[issuer_id] += value
        if issuer_id not in issuer_names:
            issuer_names[issuer_id] = issuer_name

    # Convert to list of dicts and calculate percentages
    base_currency = total_market_value.currency
    total_amount = total_market_value.amount

    exposures = []
    for issuer_id, value_amount in sorted(
        issuer_totals.items(), key=lambda x: x[1], reverse=True
    ):
        pct_total = (
            (value_amount / total_amount * 100) if total_amount > 0 else Decimal("0")
        )
        exposures.append(
            {
                "issuer_id": issuer_id,
                "issuer_name": issuer_names[issuer_id],
                "value_base": Money(value_amount, base_currency),
                "pct_total": pct_total,
            }
        )

    return exposures


def compute_country_exposures(
    results: QuerySet, total_market_value: Money
) -> list[dict]:
    """
    Compute country exposures from valuation results.

    Groups positions by instrument country and sums market values. Handles NULL countries
    gracefully. Returns sorted list (descending by value).

    Args:
        results: QuerySet of ValuationPositionResult objects.
        total_market_value: Total portfolio value in base currency (for pct calculation).

    Returns:
        List of dictionaries with country exposure data:
        [
            {
                'country': str | None,  # Country code (e.g., 'CM', 'US') or None
                'country_name': str,  # Country name or 'Unknown'
                'value_base': Money,  # Total exposure in base currency
                'pct_total': Decimal,  # Percentage of total portfolio
            },
            ...
        ]

    Example:
        >>> results = run.get_results()
        >>> total = run.get_total_market_value()
        >>> country_exposures = compute_country_exposures(results, total)
        >>> print(country_exposures[0]['country_name'])
        'Cameroon'
    """
    country_totals: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    country_names: dict[str | None, str] = {}

    for result in results:
        instrument = result.position_snapshot.instrument
        country_code = str(instrument.country) if instrument.country else None
        country_name = countries.name(country_code) if country_code else "Unknown"
        value = result.market_value_base_currency.amount

        country_totals[country_code] += value
        if country_code not in country_names:
            country_names[country_code] = country_name

    # Convert to list of dicts and calculate percentages
    base_currency = total_market_value.currency
    total_amount = total_market_value.amount

    exposures = []
    for country_code, value_amount in sorted(
        country_totals.items(), key=lambda x: x[1], reverse=True
    ):
        pct_total = (
            (value_amount / total_amount * 100) if total_amount > 0 else Decimal("0")
        )
        exposures.append(
            {
                "country": country_code,
                "country_name": country_names[country_code],
                "value_base": Money(value_amount, base_currency),
                "pct_total": pct_total,
            }
        )

    return exposures


def compute_instrument_group_exposures(
    results: QuerySet, total_market_value: Money
) -> list[dict]:
    """
    Compute instrument group exposures from valuation results.

    Groups positions by instrument_group and sums market values. Returns sorted list
    (descending by value).

    Args:
        results: QuerySet of ValuationPositionResult objects.
        total_market_value: Total portfolio value in base currency (for pct calculation).

    Returns:
        List of dictionaries with instrument group exposure data:
        [
            {
                'instrument_group_id': int,  # Instrument group ID
                'instrument_group_name': str,  # Instrument group name
                'value_base': Money,  # Total exposure in base currency
                'pct_total': Decimal,  # Percentage of total portfolio
            },
            ...
        ]

    Example:
        >>> results = run.get_results()
        >>> total = run.get_total_market_value()
        >>> group_exposures = compute_instrument_group_exposures(results, total)
        >>> print(group_exposures[0]['instrument_group_name'])
        'Government Bonds'
    """
    group_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    group_names: dict[int, str] = {}

    for result in results:
        instrument = result.position_snapshot.instrument
        group = instrument.instrument_group
        group_id = group.id
        group_name = group.name
        value = result.market_value_base_currency.amount

        group_totals[group_id] += value
        if group_id not in group_names:
            group_names[group_id] = group_name

    # Convert to list of dicts and calculate percentages
    base_currency = total_market_value.currency
    total_amount = total_market_value.amount

    exposures = []
    for group_id, value_amount in sorted(
        group_totals.items(), key=lambda x: x[1], reverse=True
    ):
        pct_total = (
            (value_amount / total_amount * 100) if total_amount > 0 else Decimal("0")
        )
        exposures.append(
            {
                "instrument_group_id": group_id,
                "instrument_group_name": group_names[group_id],
                "value_base": Money(value_amount, base_currency),
                "pct_total": pct_total,
            }
        )

    return exposures


def compute_instrument_type_exposures(
    results: QuerySet, total_market_value: Money
) -> list[dict]:
    """
    Compute instrument type exposures from valuation results.

    Groups positions by instrument_type and sums market values. Returns sorted list
    (descending by value).

    Args:
        results: QuerySet of ValuationPositionResult objects.
        total_market_value: Total portfolio value in base currency (for pct calculation).

    Returns:
        List of dictionaries with instrument type exposure data:
        [
            {
                'instrument_type_id': int,  # Instrument type ID
                'instrument_type_name': str,  # Instrument type name
                'value_base': Money,  # Total exposure in base currency
                'pct_total': Decimal,  # Percentage of total portfolio
            },
            ...
        ]

    Example:
        >>> results = run.get_results()
        >>> total = run.get_total_market_value()
        >>> type_exposures = compute_instrument_type_exposures(results, total)
        >>> print(type_exposures[0]['instrument_type_name'])
        'Bond'
    """
    type_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    type_names: dict[int, str] = {}

    for result in results:
        instrument = result.position_snapshot.instrument
        instr_type = instrument.instrument_type
        type_id = instr_type.id
        type_name = instr_type.name
        value = result.market_value_base_currency.amount

        type_totals[type_id] += value
        if type_id not in type_names:
            type_names[type_id] = type_name

    # Convert to list of dicts and calculate percentages
    base_currency = total_market_value.currency
    total_amount = total_market_value.amount

    exposures = []
    for type_id, value_amount in sorted(
        type_totals.items(), key=lambda x: x[1], reverse=True
    ):
        pct_total = (
            (value_amount / total_amount * 100) if total_amount > 0 else Decimal("0")
        )
        exposures.append(
            {
                "instrument_type_id": type_id,
                "instrument_type_name": type_names[type_id],
                "value_base": Money(value_amount, base_currency),
                "pct_total": pct_total,
            }
        )

    return exposures


def compute_top_concentrations(
    results: QuerySet,
    dimension: str,
    total_market_value: Money,
    top_n: int = 5,
) -> list[dict]:
    """
    Compute top N concentrations for a given dimension.

    Generic function for computing top N concentrations. Supports 'issuer', 'country',
    and 'instrument' dimensions. Returns sorted list (descending by value).

    Args:
        results: QuerySet of ValuationPositionResult objects.
        dimension: Dimension to compute concentrations for ('issuer', 'country', 'instrument').
        total_market_value: Total portfolio value in base currency (for pct calculation).
        top_n: Number of top items to return (default: 5).

    Returns:
        List of dictionaries with concentration data (up to top_n items):
        [
            {
                'key': str | int,  # Dimension key (issuer_id, country_code, instrument_id)
                'label': str,  # Human-readable label
                'value_base': Money,  # Total exposure in base currency
                'pct_total': Decimal,  # Percentage of total portfolio
            },
            ...
        ]

    Raises:
        ValueError: If dimension is not supported.

    Example:
        >>> results = run.get_results()
        >>> total = run.get_total_market_value()
        >>> top_issuers = compute_top_concentrations(results, 'issuer', total, top_n=5)
        >>> print(top_issuers[0]['label'])
        'Republic of Cameroon'
    """
    if dimension == "issuer":
        exposures = compute_issuer_exposures(results, total_market_value)
        return [
            {
                "key": exp["issuer_id"],
                "label": exp["issuer_name"],
                "value_base": exp["value_base"],
                "pct_total": exp["pct_total"],
            }
            for exp in exposures[:top_n]
        ]
    elif dimension == "country":
        exposures = compute_country_exposures(results, total_market_value)
        return [
            {
                "key": exp["country"],
                "label": exp["country_name"],
                "value_base": exp["value_base"],
                "pct_total": exp["pct_total"],
            }
            for exp in exposures[:top_n]
        ]
    elif dimension == "instrument":
        # Instrument-level concentration (individual instruments)
        instrument_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        instrument_labels: dict[int, str] = {}

        for result in results:
            instrument = result.position_snapshot.instrument
            instrument_id = instrument.id
            instrument_name = instrument.name
            value = result.market_value_base_currency.amount

            instrument_totals[instrument_id] += value
            if instrument_id not in instrument_labels:
                instrument_labels[instrument_id] = instrument_name

        base_currency = total_market_value.currency
        total_amount = total_market_value.amount

        concentrations = []
        for instrument_id, value_amount in sorted(
            instrument_totals.items(), key=lambda x: x[1], reverse=True
        )[:top_n]:
            pct_total = (
                (value_amount / total_amount * 100)
                if total_amount > 0
                else Decimal("0")
            )
            concentrations.append(
                {
                    "key": instrument_id,
                    "label": instrument_labels[instrument_id],
                    "value_base": Money(value_amount, base_currency),
                    "pct_total": pct_total,
                }
            )

        return concentrations
    else:
        raise ValueError(
            f"Unsupported dimension: {dimension}. Must be 'issuer', 'country', or 'instrument'."
        )
