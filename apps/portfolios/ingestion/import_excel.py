"""
Excel/CSV import service for portfolio positions.

Reads portfolio position data from Excel/CSV files and creates PositionSnapshot records.
Implements immutable snapshot behavior, comprehensive validation, and provenance tracking.

Expected file format (flexible column names via mapping):
    ISIN | Quantity | Book Value | Market Value | Price | Currency | Valuation Source
    CG0000020238 | 1000 | 1000000 | 1050000 | 105.50 | XAF | custodian

Key features:
- Immutable snapshots: Never updates existing snapshots, creates new ones
- Provenance tracking: Links snapshots to PortfolioImport and source file
- Row-level error tracking: Stores errors in PortfolioImportError
- Flexible mapping: Auto-detects or uses explicit column mapping
- Validation: Business rules, reference data checks, format validation
- Bulk operations: Uses bulk_create for performance
- Idempotency: Hash-based check prevents duplicate imports
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from django.db import transaction
from django.utils import timezone

from apps.portfolios.ingestion.mapping import (
    REQUIRED_FIELDS,
    detect_column_mapping,
    validate_mapping,
)
from apps.portfolios.ingestion.utils import (
    check_duplicate_snapshot,
    compute_inputs_hash,
    extract_row_data,
    resolve_instruments,
)
from apps.portfolios.ingestion.validation import ValidationError, validate_row
from apps.portfolios.models import (
    PortfolioImport,
    PortfolioImportError,
    PositionSnapshot,
)
from apps.reference_data.models import ValuationMethod
from libs.choices import ImportStatus
from libs.tenant_context import get_current_org_id


def import_portfolio_from_file(
    portfolio_import_id: int,
    file_path: str | None = None,
    sheet_name: str | None = None,
    mapping_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Import portfolio positions from Excel/CSV file.

    This is the main entry point for portfolio ingestion. It:
    1. Reads the file (Excel or CSV)
    2. Detects or applies column mapping
    3. Validates each row
    4. Creates PositionSnapshot records (immutable)
    5. Tracks errors at row level
    6. Updates PortfolioImport status

    Args:
        portfolio_import_id: ID of PortfolioImport record.
        file_path: Path to file (if None, uses PortfolioImport.file.path).
        sheet_name: Sheet name for Excel files (default: first sheet).
        mapping_override: Explicit column mapping {standard_field: source_column}.

    Returns:
        dict: Summary with 'created', 'errors', 'total_rows', 'status'.

    Raises:
        ValueError: If file format is invalid or organization context is missing.
        RuntimeError: If not called within organization context.
    """
    # 1. Organization Context Check
    org_id = get_current_org_id()
    if org_id is None:
        raise RuntimeError(
            "Cannot import portfolio without organization context. "
            "Use organization_context() context manager."
        )

    # Get PortfolioImport record
    try:
        portfolio_import = PortfolioImport.objects.get(
            id=portfolio_import_id,
            organization_id=org_id,
        )
    except PortfolioImport.DoesNotExist:
        raise ValueError(f"PortfolioImport {portfolio_import_id} not found")

    # 2. Idempotency Check (early exit)
    if file_path is None:
        file_path = portfolio_import.file.path

    inputs_hash = compute_inputs_hash(
        file_path,
        portfolio_import.portfolio_id,
        portfolio_import.as_of_date,
    )

    # Check if this hash already exists in a successful import
    existing_import = (
        PortfolioImport.objects.filter(
            organization_id=org_id,
            portfolio_id=portfolio_import.portfolio_id,
            inputs_hash=inputs_hash,
            status=ImportStatus.SUCCESS,
        )
        .exclude(id=portfolio_import_id)
        .first()
    )

    if existing_import:
        portfolio_import.status = ImportStatus.FAILED
        portfolio_import.error_message = (
            f"Duplicate import detected. Same file was already imported successfully "
            f"on {existing_import.completed_at}."
        )
        portfolio_import.completed_at = timezone.now()
        portfolio_import.save(update_fields=["status", "error_message", "completed_at"])
        raise ValueError(portfolio_import.error_message)

    # Store hash for future checks
    portfolio_import.inputs_hash = inputs_hash

    # 3. File Reading
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0)
    except Exception as e:
        portfolio_import.status = ImportStatus.FAILED
        portfolio_import.error_message = f"Failed to read file: {str(e)}"
        portfolio_import.completed_at = timezone.now()
        portfolio_import.save(update_fields=["status", "error_message", "completed_at"])
        raise ValueError(f"Failed to read file: {str(e)}")

    # Update status: PARSING
    portfolio_import.status = ImportStatus.PARSING
    portfolio_import.save(update_fields=["status", "inputs_hash"])

    # 4. Column Mapping
    mapping = detect_column_mapping(df, mapping_override)

    # Validate mapping
    missing_fields = validate_mapping(mapping, REQUIRED_FIELDS)
    if missing_fields:
        error_msg = f"Missing required column mappings: {missing_fields}"
        portfolio_import.status = ImportStatus.FAILED
        portfolio_import.error_message = error_msg
        portfolio_import.completed_at = timezone.now()
        portfolio_import.save(update_fields=["status", "error_message", "completed_at"])
        raise ValueError(error_msg)

    # Store mapping in PortfolioImport
    portfolio_import.mapping_json = mapping
    portfolio_import.rows_total = len(df)
    portfolio_import.save(update_fields=["mapping_json", "rows_total"])

    # 5. Status: VALIDATING
    portfolio_import.status = ImportStatus.VALIDATING
    portfolio_import.save(update_fields=["status"])

    # 6. Pre-fetch Instruments (performance)
    instrument_identifiers = (
        df[mapping["instrument_identifier"]].dropna().unique().tolist()
    )
    instruments_by_identifier = resolve_instruments(org_id, instrument_identifiers)

    # 7. Row Processing Loop
    snapshots_to_create = []
    errors_to_create = []

    for idx, row in df.iterrows():
        row_number = idx + 2  # 1-indexed, +1 for header
        raw_row_data = row.to_dict()

        try:
            # Extract row data
            row_data = extract_row_data(
                row,
                mapping,
                portfolio_import.as_of_date,
                portfolio_import.portfolio.base_currency,
            )

            # Validate row
            validated_data = validate_row(
                row_data, portfolio_import.portfolio.base_currency
            )

            # Resolve instrument
            instrument_identifier = validated_data["instrument_identifier"]
            instrument = instruments_by_identifier.get(instrument_identifier)

            if not instrument:
                # Record reference_data error
                error = PortfolioImportError(
                    portfolio_import=portfolio_import,
                    row_number=row_number,
                    raw_row_data=raw_row_data,
                    error_type="reference_data",
                    error_message=(
                        f"Instrument '{instrument_identifier}' not found "
                        "(by ISIN or ticker)"
                    ),
                    error_code="INSTRUMENT_NOT_FOUND",
                )
                error.organization_id = org_id
                errors_to_create.append(error)
                continue

            # Check for duplicate snapshot
            if check_duplicate_snapshot(
                portfolio_import.portfolio_id,
                instrument.id,
                portfolio_import.as_of_date,
            ):
                # Record business_rule error
                error = PortfolioImportError(
                    portfolio_import=portfolio_import,
                    row_number=row_number,
                    raw_row_data=raw_row_data,
                    error_type="business_rule",
                    error_message=(
                        f"Position snapshot already exists for {instrument.name} "
                        f"on {portfolio_import.as_of_date}. Snapshots are immutable."
                    ),
                    error_code="DUPLICATE_SNAPSHOT",
                )
                error.organization_id = org_id
                errors_to_create.append(error)
                continue

            # Create PositionSnapshot object (don't save yet)
            snapshot = PositionSnapshot(
                portfolio=portfolio_import.portfolio,
                portfolio_import=portfolio_import,
                instrument=instrument,
                quantity=validated_data["quantity"],
                book_value=validated_data["book_value"],
                market_value=validated_data["market_value"],
                price=validated_data.get("price"),
                accrued_interest=validated_data.get("accrued_interest"),
                valuation_method=instrument.valuation_method
                or ValuationMethod.MARK_TO_MARKET,
                valuation_source=validated_data["valuation_source"],
                as_of_date=portfolio_import.as_of_date,
                last_valuation_date=portfolio_import.as_of_date,
            )
            # Set organization_id explicitly (bulk_create bypasses save())
            snapshot.organization_id = org_id
            snapshots_to_create.append(snapshot)

        except ValidationError as e:
            # Record validation error
            error = PortfolioImportError(
                portfolio_import=portfolio_import,
                row_number=row_number,
                raw_row_data=raw_row_data,
                error_type="validation",
                error_message=str(e),
                error_code=getattr(e, "code", None),
            )
            error.organization_id = org_id
            errors_to_create.append(error)
        except ValueError as e:
            # Record format error
            error = PortfolioImportError(
                portfolio_import=portfolio_import,
                row_number=row_number,
                raw_row_data=raw_row_data,
                error_type="format",
                error_message=str(e),
                error_code="FORMAT_ERROR",
            )
            error.organization_id = org_id
            errors_to_create.append(error)
        except Exception as e:
            # Record system error
            error = PortfolioImportError(
                portfolio_import=portfolio_import,
                row_number=row_number,
                raw_row_data=raw_row_data,
                error_type="system",
                error_message=f"System error: {str(e)}",
                error_code="SYSTEM_ERROR",
            )
            error.organization_id = org_id
            errors_to_create.append(error)

    # 8. Bulk Create Snapshots and Errors
    created = 0

    # Set organization_id on all snapshot objects before bulk_create
    # (bulk_create bypasses save(), so organization_id won't be auto-set)
    for snapshot in snapshots_to_create:
        if not snapshot.organization_id:
            snapshot.organization_id = org_id

    # Set organization_id on all error objects before bulk_create
    for error in errors_to_create:
        if not error.organization_id:
            error.organization_id = org_id

    with transaction.atomic():
        # Bulk create snapshots with ignore_conflicts to handle race conditions
        if snapshots_to_create:
            # Use ignore_conflicts=True to skip duplicates silently
            # We already check for duplicates before adding to list, but this handles race conditions
            PositionSnapshot.objects.bulk_create(
                snapshots_to_create, batch_size=500, ignore_conflicts=True
            )
            # Count snapshots created in this import
            # Note: We check for duplicates before adding to list, so this should match len(snapshots_to_create)
            # unless there's a race condition, in which case ignore_conflicts=True will skip them
            created = len(snapshots_to_create)

        # Bulk create errors
        if errors_to_create:
            PortfolioImportError.objects.bulk_create(errors_to_create, batch_size=500)

    # 9. Final Status Update
    error_count = len(errors_to_create)

    if error_count == 0:
        status = ImportStatus.SUCCESS
    elif created > 0:
        status = ImportStatus.PARTIAL
    else:
        status = ImportStatus.FAILED

    portfolio_import.status = status
    portfolio_import.rows_processed = created

    # Set error message (summary + first error if any)
    if error_count > 0:
        first_error = errors_to_create[0]
        portfolio_import.error_message = (
            f"{error_count} errors. First error (row {first_error.row_number}): "
            f"{first_error.error_message}"
        )
    else:
        portfolio_import.error_message = None

    portfolio_import.completed_at = timezone.now()
    portfolio_import.save(
        update_fields=["status", "rows_processed", "error_message", "completed_at"]
    )

    return {
        "created": created,
        "errors": error_count,
        "total_rows": len(df),
        "status": status,
    }
