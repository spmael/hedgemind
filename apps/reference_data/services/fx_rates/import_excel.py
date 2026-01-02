"""
Excel import service for FX rate observations.

Reads FX rate data from Excel files and creates FXRateObservation records.
Works with Django FileField (supports local storage and S3/R2).
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.reference_data.models import FXRateImport, FXRateObservation, MarketDataSource
from libs.choices import ImportStatus


def import_fx_rate_from_import_record(
    import_record: FXRateImport,
    revision: int = 0,
) -> dict[str, int]:
    """
    Import FX rate data from an FXRateImport record.

    This is the primary method for importing FX rates. It reads from the
    stored file in media storage (works with local and S3/R2).

    Args:
        import_record: FXRateImport instance with file already stored.
        revision: Revision number (default: 0).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'min_date', 'max_date'.

    Raises:
        ValueError: If Excel format is invalid.
        FileNotFoundError: If file doesn't exist in storage.

    Example:
        >>> import_record = FXRateImport.objects.get(id=1)
        >>> result = import_fx_rate_from_import_record(import_record)
        >>> print(f"Created {result['created']} observations")
    """
    # Get file path from storage
    # Works with both local storage (.path) and S3/R2 (.name)
    if hasattr(import_record.file, "path"):
        # Local storage
        file_path = import_record.file.path
    else:
        # S3/R2 storage - download to temp file
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            file_path = tmp_file.name
            # Download from storage
            with default_storage.open(import_record.file.name, "rb") as storage_file:
                tmp_file.write(storage_file.read())

    try:
        source = import_record.source

        # Import using the file path
        result = _import_fx_rate_excel(
            file_path=file_path,
            source=source,
            sheet_name=import_record.sheet_name,
            revision=revision,
        )

        # Update import record
        import_record.observations_created = result["created"]
        import_record.observations_updated = result["updated"]
        import_record.status = ImportStatus.SUCCESS
        import_record.completed_at = timezone.now()
        import_record.save()

        return result

    except Exception as e:
        # Update import record with error
        import_record.status = ImportStatus.FAILED
        import_record.error_message = str(e)
        import_record.completed_at = timezone.now()
        import_record.save()
        raise

    finally:
        # Clean up temp file if we created one
        if not hasattr(import_record.file, "path") and os.path.exists(file_path):
            import os

            os.unlink(file_path)


def _import_fx_rate_excel(
    file_path: str,
    source: MarketDataSource,
    sheet_name: str | None = None,
    revision: int = 0,
) -> dict[str, int]:
    """
    Internal function to import FX rate data from Excel file path.

    This is the core import logic. Called by import_fx_rate_from_import_record
    and by the one-time backfill command.

    Expected Excel format:
        date | base_currency | quote_currency | rate | rate_type
        2025-01-31 | XAF | EUR | 0.001520 | BUY
        2025-01-31 | XAF | EUR | 0.001528 | SELL

    Args:
        file_path: Path to Excel file (local filesystem path).
        source: MarketDataSource instance (e.g., BEAC).
        sheet_name: Sheet name to read (if None, reads first sheet).
        revision: Revision number (default: 0).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'min_date', 'max_date'.

    Raises:
        ValueError: If Excel format is invalid.
    """
    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate required columns
    required_columns = ["date", "base_currency", "quote_currency", "rate", "rate_type"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. "
            f"Found columns: {list(df.columns)}"
        )

    # Convert date column to date type
    try:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    except Exception as e:
        raise ValueError(f"Failed to parse date column: {str(e)}")

    # Validate rate_type values
    valid_rate_types = [choice[0] for choice in FXRateObservation.RateType.choices]
    invalid_rate_types = df[~df["rate_type"].isin(valid_rate_types)][
        "rate_type"
    ].unique()
    if len(invalid_rate_types) > 0:
        raise ValueError(
            f"Invalid rate_type values: {list(invalid_rate_types)}. "
            f"Valid values: {valid_rate_types}"
        )

    # Normalize currency codes to uppercase
    df["base_currency"] = df["base_currency"].str.upper().str.strip()
    df["quote_currency"] = df["quote_currency"].str.upper().str.strip()
    df["rate_type"] = df["rate_type"].str.upper().str.strip()

    # Validate currency codes are 3 characters
    invalid_base = df[df["base_currency"].str.len() != 3]["base_currency"].unique()
    invalid_quote = df[df["quote_currency"].str.len() != 3]["quote_currency"].unique()
    if len(invalid_base) > 0 or len(invalid_quote) > 0:
        errors = []
        if len(invalid_base) > 0:
            errors.append(f"Invalid base_currency codes: {list(invalid_base)}")
        if len(invalid_quote) > 0:
            errors.append(f"Invalid quote_currency codes: {list(invalid_quote)}")
        raise ValueError("; ".join(errors))

    # Validate rate values are numeric and positive
    try:
        df["rate"] = pd.to_numeric(df["rate"])
    except Exception as e:
        raise ValueError(f"Failed to parse rate column: {str(e)}")

    invalid_rates = df[df["rate"] <= 0]
    if len(invalid_rates) > 0:
        raise ValueError(f"Found {len(invalid_rates)} rows with non-positive rates")

    created = 0
    updated = 0
    errors = []
    observed_at = timezone.now()
    min_date = None
    max_date = None

    # Process each row
    for _, row in df.iterrows():
        try:
            obs_date = row["date"]
            base_currency = row["base_currency"]
            quote_currency = row["quote_currency"]
            rate = Decimal(str(row["rate"]))
            rate_type = row["rate_type"].lower()  # Convert to lowercase for enum

            # Track date range
            if min_date is None or obs_date < min_date:
                min_date = obs_date
            if max_date is None or obs_date > max_date:
                max_date = obs_date

            # Create or update observation
            # Use unique_together constraint: (base_currency, quote_currency, date, rate_type, source, revision)
            observation, was_created = FXRateObservation.objects.update_or_create(
                base_currency=base_currency,
                quote_currency=quote_currency,
                date=obs_date,
                rate_type=rate_type,
                source=source,
                revision=revision,
                defaults={
                    "rate": rate,
                    "observed_at": observed_at,
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors.append(f"Row {len(errors) + created + updated + 1}: {str(e)}")

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_rows": len(df),
        "min_date": min_date,
        "max_date": max_date,
    }
