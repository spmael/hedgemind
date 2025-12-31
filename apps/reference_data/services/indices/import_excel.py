"""
Excel import service for market index level observations.

Reads market index level data from Excel files and creates MarketIndexValueObservation records.
Works with Django FileField (supports local storage and S3/R2).

Expected Excel format:
    date | index_code | level | is_base | base_value | comment
    2010-01-01 | BVMAC | 100.000000 | TRUE | 100.000000 | Initial base
    2024-12-31 | BVMAC | 142.350000 | | |
"""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal

import pandas as pd
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.reference_data.models import (
    MarketDataSource,
    MarketIndex,
    MarketIndexImport,
    MarketIndexValueObservation,
)
from libs.choices import ImportStatus


def import_index_levels_from_import_record(
    import_record: MarketIndexImport,
    revision: int = 0,
) -> dict[str, int]:
    """
    Import market index level data from a MarketIndexImport record.

    This is the primary method for importing index levels. It reads from the
    stored file in media storage (works with local and S3/R2).

    Args:
        import_record: MarketIndexImport instance with file already stored.
        revision: Revision number (default: 0).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'min_date', 'max_date'.

    Raises:
        ValueError: If Excel format is invalid.
        FileNotFoundError: If file doesn't exist in storage.

    Example:
        >>> import_record = MarketIndexImport.objects.get(id=1)
        >>> result = import_index_levels_from_import_record(import_record)
        >>> print(f"Created {result['created']} observations")
    """
    # Get file path from storage
    # Works with both local storage (.path) and S3/R2 (.name)
    if hasattr(import_record.file, "path"):
        # Local storage
        file_path = import_record.file.path
    else:
        # S3/R2 storage - download to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            file_path = tmp_file.name
            # Download from storage
            with default_storage.open(import_record.file.name, "rb") as storage_file:
                tmp_file.write(storage_file.read())

    try:
        source = import_record.source

        # Import using the file path
        result = _import_index_levels_excel(
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
            os.unlink(file_path)


def _import_index_levels_excel(
    file_path: str,
    source: MarketDataSource,
    sheet_name: str | None = "INDEX_LEVELS",
    revision: int = 0,
) -> dict[str, int]:
    """
    Internal function to import market index level data from Excel file path.

    This is the core import logic. Called by import_index_levels_from_import_record
    and by the one-time backfill command.

    Expected Excel format:
        date | index_code | level | is_base | base_value | comment
        2010-01-01 | BVMAC | 100.000000 | TRUE | 100.000000 | Initial base
        2024-12-31 | BVMAC | 142.350000 | | |

    Validation rules:
        - index_code must exist in MarketIndex
        - One (index, date) only per source/revision
        - level > 0
        - If is_base = TRUE, base_value must be provided

    Args:
        file_path: Path to Excel file (local filesystem path).
        source: MarketDataSource instance (e.g., BVMAC).
        sheet_name: Sheet name to read (default: "INDEX_LEVELS").
        revision: Revision number (default: 0).

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'min_date', 'max_date'.

    Raises:
        ValueError: If Excel format is invalid.
    """
    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate required columns
    required_columns = ["date", "index_code", "level"]
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

    # Normalize index_code to uppercase and strip whitespace
    df["index_code"] = df["index_code"].str.upper().str.strip()

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

    # Validate level values are numeric and positive
    try:
        df["level"] = pd.to_numeric(df["level"])
    except Exception as e:
        raise ValueError(f"Failed to parse level column: {str(e)}")

    invalid_levels = df[df["level"] <= 0]
    if len(invalid_levels) > 0:
        raise ValueError(f"Found {len(invalid_levels)} rows with non-positive levels")

    # Validate is_base and base_value logic
    if "is_base" in df.columns:
        # Convert is_base to boolean (handles TRUE/FALSE, true/false, 1/0, etc.)
        df["is_base"] = df["is_base"].fillna(False)
        df["is_base"] = (
            df["is_base"].astype(str).str.upper().isin(["TRUE", "1", "YES", "Y"])
        )

        # If is_base is TRUE, base_value must be provided
        if "base_value" in df.columns:
            base_rows_missing_value = df[
                (df["is_base"] == True) & (df["base_value"].isna())  # noqa: E712
            ]
            if len(base_rows_missing_value) > 0:
                raise ValueError(
                    f"Found {len(base_rows_missing_value)} rows with is_base=TRUE but missing base_value"
                )
        else:
            base_rows = df[df["is_base"] == True]  # noqa: E712
            if len(base_rows) > 0:
                raise ValueError(
                    f"Found {len(base_rows)} rows with is_base=TRUE but base_value column is missing"
                )

    created = 0
    updated = 0
    errors = []
    observed_at = timezone.now()
    min_date = None
    max_date = None

    # Get all indices in one query for efficiency
    indices_by_code = {
        idx.code: idx for idx in MarketIndex.objects.filter(code__in=unique_index_codes)
    }

    # Process each row
    for idx, row in df.iterrows():
        try:
            obs_date = row["date"]
            index_code = row["index_code"]
            level = Decimal(str(row["level"]))

            # Get index
            index = indices_by_code.get(index_code)
            if not index:
                errors.append(
                    f"Row {idx + 2}: Index code '{index_code}' not found (should not happen after validation)"
                )
                continue

            # Track date range
            if min_date is None or obs_date < min_date:
                min_date = obs_date
            if max_date is None or obs_date > max_date:
                max_date = obs_date

            # Handle base/rebase if specified
            is_base = False
            base_value = None
            if "is_base" in df.columns and pd.notna(row.get("is_base")):
                is_base = bool(row["is_base"])
                if (
                    is_base
                    and "base_value" in df.columns
                    and pd.notna(row.get("base_value"))
                ):
                    base_value = Decimal(str(row["base_value"]))
                    # Update MarketIndex base_date and base_value if this is a base point
                    if index.base_date is None or obs_date < index.base_date:
                        index.base_date = obs_date
                        index.base_value = base_value
                        index.save(update_fields=["base_date", "base_value"])

            # Calculate return_pct if we have previous value (optional, can be calculated later)
            return_pct = None

            # Create or update observation
            # Use unique_together constraint: (index, date, source, revision)
            observation, was_created = (
                MarketIndexValueObservation.objects.update_or_create(
                    index=index,
                    date=obs_date,
                    source=source,
                    revision=revision,
                    defaults={
                        "value": level,
                        "return_pct": return_pct,
                        "observed_at": observed_at,
                    },
                )
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
        "min_date": min_date,
        "max_date": max_date,
    }
