"""
Excel import service for instrument price observations.

Reads instrument price data from Excel files and creates InstrumentPriceObservation records.
Works with Django FileField (supports local storage and S3/R2).

Expected Excel format:
    date | instrument_id | price | price_type | quote_convention | clean_or_dirty | Volume
    25/11/2025 | CG0000020238 | 95 | ASK | PERCENT_OF_PAR | CLEAN | 1000
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.utils import timezone

from apps.reference_data.models import (Instrument, InstrumentPriceObservation,
                                        MarketDataSource)
from libs.tenant_context import get_current_org_id


def import_prices_from_file(
    file_path: str,
    source_code: str,
    sheet_name: str | None = "PRICES",
    revision: int = 0,
) -> dict[str, int]:
    """
    Import instrument price observations from Excel file path.

    This is the core import logic for price observations. It reads from a local file path
    and creates InstrumentPriceObservation records. Instruments are organization-scoped,
    so this function must be called within an organization context.

    Expected Excel format:
        date | instrument_id | price | price_type | quote_convention | clean_or_dirty | Volume
        25/11/2025 | CG0000020238 | 95 | ASK | PERCENT_OF_PAR | CLEAN | 1000

    Validation rules:
        - date is required
        - instrument_id is required (looked up by ISIN or ticker)
        - price is required
        - price_type is required (normalized to lowercase)
        - quote_convention is required (normalized to lowercase)
        - clean_or_dirty is required (normalized to lowercase)
        - Volume is optional
        - source_code must exist in MarketDataSource

    Args:
        file_path: Path to Excel file (local filesystem path).
        source_code: Code of the MarketDataSource for these observations.
        sheet_name: Sheet name to read (default: "PRICES").
        revision: Revision number (0 = initial, 1+ = corrections).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'total_rows'.

    Raises:
        ValueError: If Excel format is invalid or organization context is missing.
        RuntimeError: If not called within organization context.

    Example:
        >>> from libs.tenant_context import organization_context
        >>> with organization_context(org_id=1):
        ...     result = import_prices_from_file("prices.xlsx", source_code="BVMAC")
        ...     print(f"Created {result['created']} price observations")
    """
    # Verify organization context
    org_id = get_current_org_id()
    if org_id is None:
        raise RuntimeError(
            "Cannot import prices without organization context. "
            "Use organization_context() context manager or set_current_org_id()."
        )

    # Get source
    try:
        source = MarketDataSource.objects.get(code=source_code)
    except MarketDataSource.DoesNotExist:
        raise ValueError(f"MarketDataSource with code '{source_code}' not found")

    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate required columns
    required_columns = [
        "date",
        "instrument_id",
        "price",
        "price_type",
        "quote_convention",
        "clean_or_dirty",
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. "
            f"Found columns: {list(df.columns)}"
        )

    # Normalize choice values (uppercase to lowercase)
    def normalize_price_type(value):
        """Normalize price_type to lowercase."""
        if pd.isna(value):
            return None
        return str(value).lower().strip()

    def normalize_quote_convention(value):
        """Normalize quote_convention to lowercase with underscores."""
        if pd.isna(value):
            return None
        return str(value).lower().replace(" ", "_").strip()

    def normalize_clean_or_dirty(value):
        """Normalize clean_or_dirty to lowercase."""
        if pd.isna(value):
            return None
        return str(value).lower().strip()

    # Validate price_type values
    valid_price_types = [choice[0] for choice in InstrumentPriceObservation.PriceType.choices]
    df["price_type_normalized"] = df["price_type"].apply(normalize_price_type)
    invalid_price_types = df[
        df["price_type_normalized"].notna()
        & ~df["price_type_normalized"].isin(valid_price_types)
    ]["price_type_normalized"].unique()
    if len(invalid_price_types) > 0:
        raise ValueError(
            f"Invalid price_type values: {list(invalid_price_types)}. "
            f"Valid values: {valid_price_types}"
        )

    # Validate quote_convention values
    valid_quote_conventions = [
        choice[0] for choice in InstrumentPriceObservation.QuoteConvention.choices
    ]
    df["quote_convention_normalized"] = df["quote_convention"].apply(
        normalize_quote_convention
    )
    invalid_quote_conventions = df[
        df["quote_convention_normalized"].notna()
        & ~df["quote_convention_normalized"].isin(valid_quote_conventions)
    ]["quote_convention_normalized"].unique()
    if len(invalid_quote_conventions) > 0:
        raise ValueError(
            f"Invalid quote_convention values: {list(invalid_quote_conventions)}. "
            f"Valid values: {valid_quote_conventions}"
        )

    # Validate clean_or_dirty values
    valid_clean_or_dirty = [
        choice[0] for choice in InstrumentPriceObservation.CleanOrDirty.choices
    ]
    df["clean_or_dirty_normalized"] = df["clean_or_dirty"].apply(
        normalize_clean_or_dirty
    )
    invalid_clean_or_dirty = df[
        df["clean_or_dirty_normalized"].notna()
        & ~df["clean_or_dirty_normalized"].isin(valid_clean_or_dirty)
    ]["clean_or_dirty_normalized"].unique()
    if len(invalid_clean_or_dirty) > 0:
        raise ValueError(
            f"Invalid clean_or_dirty values: {list(invalid_clean_or_dirty)}. "
            f"Valid values: {valid_clean_or_dirty}"
        )

    created = 0
    updated = 0
    errors = []

    # Get all unique instrument_ids and resolve them
    unique_instrument_ids = df["instrument_id"].dropna().unique()
    instruments_by_id = {}

    # Look up instruments by ISIN first, then by ticker
    # Note: Instruments are organization-scoped, so we query within org context
    for instrument_id in unique_instrument_ids:
        instrument_id_str = str(instrument_id).strip()
        # Try by ISIN first
        instrument = Instrument.objects.filter(
            organization_id=org_id, isin=instrument_id_str
        ).first()
        if not instrument:
            # Try by ticker
            instrument = Instrument.objects.filter(
                organization_id=org_id, ticker=instrument_id_str
            ).first()
        if instrument:
            instruments_by_id[instrument_id_str] = instrument

    # Check for missing instruments
    missing_instruments = [
        inst_id
        for inst_id in unique_instrument_ids
        if str(inst_id).strip() not in instruments_by_id
    ]
    if missing_instruments:
        errors.append(
            f"Instruments not found (by ISIN or ticker): {list(missing_instruments)[:10]}"
        )
        if len(missing_instruments) > 10:
            errors.append(f"... and {len(missing_instruments) - 10} more")

    # Process each row
    for idx, row in df.iterrows():
        try:
            # Required fields
            date_value = row["date"]
            if pd.isna(date_value):
                errors.append(f"Row {idx + 2}: date is required")
                continue

            # Parse date
            try:
                if isinstance(date_value, str):
                    date = pd.to_datetime(date_value).date()
                else:
                    date = date_value.date() if hasattr(date_value, "date") else None
            except Exception:
                errors.append(f"Row {idx + 2}: Invalid date format")
                continue

            instrument_id = str(row["instrument_id"]).strip()
            instrument = instruments_by_id.get(instrument_id)
            if not instrument:
                errors.append(
                    f"Row {idx + 2}: Instrument '{instrument_id}' not found (by ISIN or ticker)"
                )
                continue

            price_value = row["price"]
            if pd.isna(price_value):
                errors.append(f"Row {idx + 2}: price is required")
                continue

            try:
                price = Decimal(str(price_value))
            except Exception:
                errors.append(f"Row {idx + 2}: Invalid price value")
                continue

            price_type = df.loc[idx, "price_type_normalized"]
            quote_convention = df.loc[idx, "quote_convention_normalized"]
            clean_or_dirty = df.loc[idx, "clean_or_dirty_normalized"]

            # Optional fields
            volume = None
            if pd.notna(row.get("Volume")) or pd.notna(row.get("volume")):
                volume_value = row.get("Volume") or row.get("volume")
                try:
                    volume = Decimal(str(volume_value))
                except Exception:
                    pass  # Optional field, skip if invalid

            # Create or update observation
            # Unique constraint: (instrument, date, price_type, source, revision)
            observation, was_created = InstrumentPriceObservation.objects.update_or_create(
                instrument=instrument,
                date=date,
                price_type=price_type,
                source=source,
                revision=revision,
                defaults={
                    "price": price,
                    "quote_convention": quote_convention,
                    "clean_or_dirty": clean_or_dirty,
                    "volume": volume,
                    "observed_at": timezone.now(),
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_rows": len(df),
    }

