"""
Excel import service for yield curve observations.

Reads yield curve data from Excel files and creates YieldCurvePointObservation records.
Works with Django FileField (supports local storage and S3/R2).
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.reference_data.models import (
    MarketDataSource,
    YieldCurve,
    YieldCurveImport,
    YieldCurvePointObservation,
)
from apps.reference_data.services.yield_curves.tenor_mapping import (
    get_all_tenors,
    get_tenor_days,
)
from libs.choices import ImportStatus


def import_yield_curve_from_import_record(
    import_record: YieldCurveImport,
    revision: int = 0,
) -> dict[str, int]:
    """
    Import yield curve data from a YieldCurveImport record.

    This is the primary method for importing yield curves. It reads from the
    stored file in media storage (works with local and S3/R2).

    Args:
        import_record: YieldCurveImport instance with file already stored.
        revision: Revision number (default: 0).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors'.

    Raises:
        ValueError: If Excel format is invalid.
        FileNotFoundError: If file doesn't exist in storage.

    Example:
        >>> import_record = YieldCurveImport.objects.get(id=1)
        >>> result = import_yield_curve_from_import_record(import_record)
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
        # Get curve and source from import record
        curve = import_record.curve
        if not curve:
            raise ValueError("Import record must have a curve specified")

        source = import_record.source

        # Import using the file path
        result = _import_yield_curve_excel(
            file_path=file_path,
            curve=curve,
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
            os.unlink(file_path)


def _import_yield_curve_excel(
    file_path: str,
    curve: YieldCurve,
    source: MarketDataSource,
    sheet_name: str | None = None,
    date_column: str = "date",
    revision: int = 0,
) -> dict[str, int]:
    """
    Internal function to import yield curve data from Excel file path.

    This is the core import logic. Called by import_yield_curve_from_import_record
    and by the one-time backfill command.

    Args:
        file_path: Path to Excel file (local filesystem path).
        curve: YieldCurve instance to import data for.
        source: MarketDataSource instance (e.g., BEAC).
        sheet_name: Sheet name to read (if None, reads first sheet).
        date_column: Name of the date column (default: "date").
        revision: Revision number (default: 0).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors'.
    """
    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate date column exists
    if date_column not in df.columns:
        raise ValueError(
            f"Date column '{date_column}' not found in Excel. Columns: {list(df.columns)}"
        )

    # Get valid tenor columns (exclude date column)
    valid_tenors = get_all_tenors()
    tenor_columns = [
        col
        for col in df.columns
        if col != date_column and col.upper() in [t.upper() for t in valid_tenors]
    ]

    if not tenor_columns:
        raise ValueError(
            f"No valid tenor columns found. Expected columns like: {valid_tenors}. "
            f"Found columns: {list(df.columns)}"
        )

    # Normalize date column
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df = df.dropna(subset=[date_column])  # Remove rows with invalid dates

    created = 0
    updated = 0
    errors = []
    observed_at = timezone.now()
    dates_seen = []  # Track dates for date range calculation

    # Process each row
    for idx, row in df.iterrows():
        row_date = row[date_column]
        if pd.isna(row_date):
            continue

        # Convert to date object
        if isinstance(row_date, pd.Timestamp):
            as_of_date = row_date.date()
        elif isinstance(row_date, date):
            as_of_date = row_date
        else:
            errors.append(f"Row {idx + 2}: Invalid date format: {row_date}")
            continue

        # Track date for range calculation
        dates_seen.append(as_of_date)

        # Process each tenor column
        for tenor_col in tenor_columns:
            rate_value = row[tenor_col]

            # Skip NaN/empty cells
            if pd.isna(rate_value):
                continue

            try:
                # Convert to Decimal-compatible float
                rate = float(rate_value)

                # Get tenor_days
                tenor_str = tenor_col.upper().strip()
                tenor_days = get_tenor_days(tenor_str)

                # Create or update observation
                observation, created_flag = (
                    YieldCurvePointObservation.objects.update_or_create(
                        curve=curve,
                        tenor_days=tenor_days,
                        date=as_of_date,
                        source=source,
                        revision=revision,
                        defaults={
                            "tenor": tenor_str,
                            "rate": rate,
                            "observed_at": observed_at,
                        },
                    )
                )

                if created_flag:
                    created += 1
                else:
                    # Update existing observation
                    observation.rate = rate
                    observation.observed_at = observed_at
                    observation.save()
                    updated += 1

            except ValueError as e:
                errors.append(f"Row {idx + 2}, Column {tenor_col}: {str(e)}")
            except Exception as e:
                errors.append(
                    f"Row {idx + 2}, Column {tenor_col}: Unexpected error: {str(e)}"
                )

    # Calculate date range
    min_date = min(dates_seen) if dates_seen else None
    max_date = max(dates_seen) if dates_seen else None

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_rows": len(df),
        "tenor_columns_processed": len(tenor_columns),
        "min_date": min_date,
        "max_date": max_date,
    }
