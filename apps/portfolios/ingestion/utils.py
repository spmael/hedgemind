"""
Helper utilities for portfolio ingestion.

Provides instrument resolution, idempotency hashing, row data extraction,
and duplicate snapshot checking.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from djmoney.money import Money

from apps.portfolios.models import PositionSnapshot
from apps.reference_data.models import Instrument


def resolve_instruments(org_id: int, identifiers: list[str]) -> dict[str, Instrument]:
    """
    Resolve instrument identifiers to Instrument objects.

    Normalizes identifiers (strip, upper) and queries by ISIN first, then ticker.
    Returns dict mapping normalized identifier to Instrument.

    Args:
        org_id: Organization ID for scoping.
        identifiers: List of instrument identifiers (ISINs or tickers).

    Returns:
        dict: Mapping {normalized_identifier: Instrument}.

    Example:
        >>> instruments = resolve_instruments(1, ["CG0000020238", "TICKER1"])
        >>> # Returns: {"CG0000020238": Instrument(...), "TICKER1": Instrument(...)}
    """
    instruments_by_identifier = {}

    # Normalize identifiers
    normalized_identifiers = [
        str(ident).strip().upper() for ident in identifiers if ident
    ]

    if not normalized_identifiers:
        return instruments_by_identifier

    # Try by ISIN first
    for instrument in Instrument.objects.filter(
        organization_id=org_id,
        isin__in=normalized_identifiers,
    ):
        if instrument.isin:
            instruments_by_identifier[instrument.isin.upper()] = instrument

    # Then by ticker (only if not already found)
    for instrument in Instrument.objects.filter(
        organization_id=org_id,
        ticker__in=normalized_identifiers,
    ):
        if instrument.ticker:
            ticker_upper = instrument.ticker.upper()
            if ticker_upper not in instruments_by_identifier:
                instruments_by_identifier[ticker_upper] = instrument

    return instruments_by_identifier


def compute_inputs_hash(file_path: str, portfolio_id: int, as_of_date: date) -> str:
    """
    Compute hash of inputs for idempotency checks.

    Hash is computed from: file bytes + portfolio_id + as_of_date.
    Uses SHA256 for collision resistance.

    Args:
        file_path: Path to the file to hash.
        portfolio_id: Portfolio ID.
        as_of_date: As-of date for the import.

    Returns:
        str: Hex digest of the hash (64 characters).

    Example:
        >>> hash_value = compute_inputs_hash("file.xlsx", 1, date(2025, 1, 15))
        >>> # Returns: "a1b2c3d4e5f6..."
    """
    # Read file bytes
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    # Create hash input: file_bytes + portfolio_id + as_of_date
    hash_input = (
        file_bytes + str(portfolio_id).encode() + as_of_date.isoformat().encode()
    )

    # Compute SHA256 hash
    hash_obj = hashlib.sha256(hash_input)
    return hash_obj.hexdigest()


def extract_row_data(
    row: pd.Series,
    mapping: dict[str, str],
    default_as_of_date: date,
    portfolio_base_currency: str,
) -> dict[str, Any]:
    """
    Extract and normalize row data from DataFrame row.

    Converts values to proper types (Decimal, Money, date) and handles missing optional fields.

    Args:
        row: Pandas Series representing a row from the DataFrame.
        mapping: Column mapping {standard_field: source_column}.
        default_as_of_date: Default as_of_date if not in row.
        portfolio_base_currency: Base currency for Money fields.

    Returns:
        dict: Normalized row data with proper types.

    Raises:
        ValueError: If required fields cannot be extracted or converted.
    """
    data = {}

    # Extract instrument_identifier
    if "instrument_identifier" in mapping:
        value = row[mapping["instrument_identifier"]]
        data["instrument_identifier"] = (
            str(value).strip().upper() if pd.notna(value) else None
        )

    # Extract quantity
    if "quantity" in mapping:
        value = row[mapping["quantity"]]
        if pd.isna(value):
            raise ValueError("quantity is required")
        try:
            data["quantity"] = Decimal(str(value))
        except (ValueError, InvalidOperation) as e:
            raise ValueError(f"Invalid quantity: {str(e)}")

    # Extract currency
    if "currency" in mapping:
        value = row[mapping["currency"]]
        if pd.isna(value):
            raise ValueError("currency is required")
        data["currency"] = str(value).upper().strip()
    else:
        # Default to portfolio base currency
        data["currency"] = portfolio_base_currency

    currency = data["currency"]

    # Extract price (optional)
    if "price" in mapping:
        value = row[mapping["price"]]
        if pd.notna(value):
            try:
                data["price"] = Decimal(str(value))
            except (ValueError, InvalidOperation):
                data["price"] = None
        else:
            data["price"] = None
    else:
        data["price"] = None

    # Extract market_value
    if "market_value" in mapping:
        value = row[mapping["market_value"]]
        if pd.notna(value):
            try:
                amount = Decimal(str(value))
                data["market_value"] = Money(amount, currency)
            except (ValueError, InvalidOperation):
                data["market_value"] = None
        else:
            data["market_value"] = None
    else:
        data["market_value"] = None

    # Extract book_value
    if "book_value" in mapping:
        value = row[mapping["book_value"]]
        if pd.isna(value):
            raise ValueError("book_value is required")
        try:
            amount = Decimal(str(value))
            data["book_value"] = Money(amount, currency)
        except (ValueError, InvalidOperation) as e:
            raise ValueError(f"Invalid book_value: {str(e)}")

    # Extract valuation_source
    if "valuation_source" in mapping:
        value = row[mapping["valuation_source"]]
        if pd.isna(value):
            raise ValueError("valuation_source is required")
        data["valuation_source"] = str(value).strip()
    else:
        raise ValueError("valuation_source is required")

    # Extract accrued_interest (optional)
    if "accrued_interest" in mapping:
        value = row[mapping["accrued_interest"]]
        if pd.notna(value):
            try:
                amount = Decimal(str(value))
                data["accrued_interest"] = Money(amount, currency)
            except (ValueError, InvalidOperation):
                data["accrued_interest"] = None
        else:
            data["accrued_interest"] = None
    else:
        data["accrued_interest"] = None

    # Extract as_of_date (optional, defaults to portfolio_import.as_of_date)
    if "as_of_date" in mapping:
        value = row[mapping["as_of_date"]]
        if pd.notna(value):
            try:
                if isinstance(value, str):
                    data["as_of_date"] = pd.to_datetime(value).date()
                else:
                    data["as_of_date"] = (
                        value.date() if hasattr(value, "date") else default_as_of_date
                    )
            except Exception:
                data["as_of_date"] = default_as_of_date
        else:
            data["as_of_date"] = default_as_of_date
    else:
        data["as_of_date"] = default_as_of_date

    return data


def check_duplicate_snapshot(
    portfolio_id: int, instrument_id: int, as_of_date: date
) -> bool:
    """
    Check if a PositionSnapshot already exists for the given combination.

    Args:
        portfolio_id: Portfolio ID.
        instrument_id: Instrument ID.
        as_of_date: As-of date.

    Returns:
        bool: True if snapshot exists, False otherwise.

    Example:
        >>> exists = check_duplicate_snapshot(1, 5, date(2025, 1, 15))
        >>> # Returns: True if snapshot exists, False otherwise
    """
    return PositionSnapshot.objects.filter(
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        as_of_date=as_of_date,
    ).exists()
