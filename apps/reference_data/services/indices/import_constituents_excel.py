"""
Excel import service for market index constituents.

Reads market index constituent data from Excel files and creates MarketIndexConstituent records.
Works with Django FileField (supports local storage and S3/R2).

Expected Excel format:
    as_of_date | index_code | instrument_id | weight | shares | float_shares
    2025-03-31 | BVMAC | CM1234567890 | 12.5000 | 1000000 | 850000
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from apps.reference_data.models import (
    Instrument,
    MarketDataSource,
    MarketIndex,
    MarketIndexConstituent,
)


def import_index_constituents_from_file(
    file_path: str,
    source: MarketDataSource,
    sheet_name: str = "CONSTITUENTS",
) -> dict[str, int]:
    """
    Import market index constituent data from Excel file path.

    This is the core import logic for constituents. It reads from a local file path
    and creates MarketIndexConstituent records.

    Expected Excel format:
        as_of_date | index_code | instrument_id | weight | shares | float_shares
        2025-03-31 | BVMAC | CM1234567890 | 12.5000 | 1000000 | 850000

    Validation rules:
        - (index_code, instrument_id, as_of_date) must be unique
        - weight > 0
        - For each (index_code, as_of_date), weights should sum to ~100% (±0.5% tolerance)
        - Missing shares/float_shares allowed

    Args:
        file_path: Path to Excel file (local filesystem path).
        source: MarketDataSource instance (e.g., BVMAC).
        sheet_name: Sheet name to read (default: "CONSTITUENTS").

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'total_rows', 'weight_validation_errors'.

    Raises:
        ValueError: If Excel format is invalid or validation fails.
    """
    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate required columns
    required_columns = ["as_of_date", "index_code", "instrument_id", "weight"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. "
            f"Found columns: {list(df.columns)}"
        )

    # Convert as_of_date column to date type
    try:
        df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.date
    except Exception as e:
        raise ValueError(f"Failed to parse as_of_date column: {str(e)}")

    # Normalize index_code and instrument_id to uppercase and strip whitespace
    df["index_code"] = df["index_code"].str.upper().str.strip()
    df["instrument_id"] = df["instrument_id"].str.upper().str.strip()

    # Validate index_code values exist
    unique_index_codes = df["index_code"].unique()
    existing_indices = MarketIndex.objects.filter(
        code__in=unique_index_codes
    ).values_list("code", flat=True)
    existing_indices_set = set(existing_indices)
    missing_indices = [
        code for code in unique_index_codes if code not in existing_indices_set
    ]
    if missing_indices:
        raise ValueError(
            f"Index codes not found in MarketIndex: {missing_indices}. "
            f"Please create MarketIndex records first."
        )

    # Validate weight values are numeric and positive
    try:
        df["weight"] = pd.to_numeric(df["weight"])
    except Exception as e:
        raise ValueError(f"Failed to parse weight column: {str(e)}")

    invalid_weights = df[df["weight"] <= 0]
    if len(invalid_weights) > 0:
        raise ValueError(f"Found {len(invalid_weights)} rows with non-positive weights")

    # Validate weight sums per (index_code, as_of_date) are ~100% (±0.5% tolerance)
    weight_validation_errors = []
    for index_code in unique_index_codes:
        index_df = df[df["index_code"] == index_code]
        for as_of_date in index_df["as_of_date"].unique():
            date_df = index_df[index_df["as_of_date"] == as_of_date]
            weight_sum = date_df["weight"].sum()
            if abs(weight_sum - 100.0) > 0.5:
                weight_validation_errors.append(
                    f"Index {index_code} on {as_of_date}: weights sum to {weight_sum:.4f}% "
                    f"(expected ~100%, tolerance ±0.5%)"
                )

    if weight_validation_errors:
        # Don't fail, but report as warnings
        pass

    # Get all indices in one query for efficiency
    indices_by_code = {
        idx.code: idx for idx in MarketIndex.objects.filter(code__in=unique_index_codes)
    }

    # Get all unique instrument_ids and try to find them
    unique_instrument_ids = df["instrument_id"].unique()
    # Try to find by ISIN first, then by ticker
    # Note: Instrument is organization-scoped, but for reference data imports,
    # we search across all organizations. If multiple instruments match, we use the first one.
    instruments_by_identifier = {}

    # Find by ISIN (case-insensitive)
    instrument_ids_upper = [id.upper() for id in unique_instrument_ids]
    instruments_by_isin = {}
    for inst in Instrument.objects.filter(
        isin__in=instrument_ids_upper
    ).select_related():
        if inst.isin:
            isin_key = inst.isin.upper()
            if isin_key not in instruments_by_isin:  # Take first match if duplicates
                instruments_by_isin[isin_key] = inst

    # Find by ticker (case-insensitive)
    instruments_by_ticker = {}
    for inst in Instrument.objects.filter(
        ticker__in=instrument_ids_upper
    ).select_related():
        if inst.ticker:
            ticker_key = inst.ticker.upper()
            if (
                ticker_key not in instruments_by_ticker
            ):  # Take first match if duplicates
                instruments_by_ticker[ticker_key] = inst

    # Build mapping: instrument_id -> Instrument
    for instrument_id in unique_instrument_ids:
        if instrument_id in instruments_by_isin:
            instruments_by_identifier[instrument_id] = instruments_by_isin[
                instrument_id
            ]
        elif instrument_id in instruments_by_ticker:
            instruments_by_identifier[instrument_id] = instruments_by_ticker[
                instrument_id
            ]
        # If not found, will be reported as error during processing

    created = 0
    updated = 0
    errors = []

    # Process each row
    for idx, row in df.iterrows():
        try:
            as_of_date = row["as_of_date"]
            index_code = row["index_code"]
            instrument_id = row["instrument_id"]
            weight = Decimal(str(row["weight"]))

            # Get index
            index = indices_by_code.get(index_code)
            if not index:
                errors.append(
                    f"Row {idx + 2}: Index code '{index_code}' not found (should not happen after validation)"
                )
                continue

            # Get instrument
            instrument = instruments_by_identifier.get(instrument_id)
            if not instrument:
                errors.append(
                    f"Row {idx + 2}: Instrument '{instrument_id}' not found (by ISIN or ticker)"
                )
                continue

            # Get optional fields
            shares = None
            if "shares" in df.columns and pd.notna(row.get("shares")):
                shares = Decimal(str(row["shares"]))

            float_shares = None
            if "float_shares" in df.columns and pd.notna(row.get("float_shares")):
                float_shares = Decimal(str(row["float_shares"]))

            # Create or update constituent
            # Use unique_together constraint: (index, instrument, as_of_date)
            constituent, was_created = MarketIndexConstituent.objects.update_or_create(
                index=index,
                instrument=instrument,
                as_of_date=as_of_date,
                defaults={
                    "weight": weight,
                    "shares": shares,
                    "float_shares": float_shares,
                    "source": source,
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
        "weight_validation_errors": weight_validation_errors,
    }
