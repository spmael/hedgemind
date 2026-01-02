"""
Service to export missing instruments from portfolio imports.

Exports missing instruments as CSV formatted for instrument import template.
"""

from __future__ import annotations

import csv
import re
from io import StringIO

from apps.portfolios.models import PortfolioImport, PortfolioImportError
from apps.portfolios.services.preflight import preflight_portfolio_import
from libs.tenant_context import get_current_org_id


def export_missing_instruments_csv(portfolio_import_id: int) -> tuple[str, str]:
    """
    Export missing instruments as CSV string.

    Args:
        portfolio_import_id: ID of PortfolioImport record.

    Returns:
        tuple: (csv_content, filename) where csv_content is CSV string and filename is suggested filename.

    Raises:
        ValueError: If PortfolioImport not found or organization context missing.
    """
    org_id = get_current_org_id()
    if org_id is None:
        raise RuntimeError(
            "Cannot export missing instruments without organization context. "
            "Use organization_context() context manager."
        )

    # Get PortfolioImport
    try:
        portfolio_import = PortfolioImport.objects.get(
            id=portfolio_import_id,
            organization_id=org_id,
        )
    except PortfolioImport.DoesNotExist:
        raise ValueError(f"PortfolioImport {portfolio_import_id} not found")

    # Get missing instrument identifiers from error records (created during import)
    # or from preflight results (if import hasn't been attempted yet)
    identifiers = set()

    # First, try to get from PortfolioImportError records (from actual import attempts)
    errors = PortfolioImportError.objects.filter(
        portfolio_import=portfolio_import,
        error_type="reference_data",
        error_code="INSTRUMENT_NOT_FOUND",
    ).order_by("row_number")

    if errors.exists():
        # Extract identifiers from error records
        for error in errors:
            identifier = _extract_identifier_from_error(error)
            if identifier:
                identifiers.add(identifier)
    else:
        # No error records yet - try preflight to get missing instruments
        try:
            preflight_result = preflight_portfolio_import(portfolio_import.id)
            if preflight_result and preflight_result.get("missing_instruments"):
                identifiers.update(preflight_result["missing_instruments"])
        except Exception:
            # Preflight might fail (e.g., file not readable), ignore and continue
            pass

    if not identifiers:
        raise ValueError(
            "No missing instrument errors found. "
            "Run preflight validation first or attempt an import to generate error records."
        )

    # CSV columns matching instrument import template
    csv_columns = [
        "instrument_identifier",
        "name",
        "instrument_group_code",
        "instrument_type_code",
        "currency",
        "issuer_code",
        "valuation_method",
        "isin",
        "ticker",
        "country",
        "sector",
    ]

    # Write CSV to string
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_columns)
    writer.writeheader()

    for identifier in sorted(identifiers):
        # Determine if identifier is ISIN or ticker (basic heuristic)
        is_isin = len(identifier) >= 10 and identifier[:2].isalpha()

        row = {
            "instrument_identifier": identifier,
            "name": "",  # User must fill
            "instrument_group_code": "",  # User must fill
            "instrument_type_code": "",  # User must fill
            "currency": "",  # User must fill
            "issuer_code": "",  # User must fill
            "valuation_method": "mark_to_market",  # Default
            "isin": identifier if is_isin else "",
            "ticker": identifier if not is_isin else "",
            "country": "",
            "sector": "",
        }
        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    # Add UTF-8 BOM (Byte Order Mark) for Excel compatibility
    # Excel needs the BOM to properly recognize UTF-8 encoding
    csv_content = "\ufeff" + csv_content

    # Generate filename
    filename = f"missing_instruments_import_{portfolio_import_id}.csv"

    return csv_content, filename


def _extract_identifier_from_error(error: PortfolioImportError) -> str | None:
    """
    Extract instrument identifier from error message or raw_row_data.

    Args:
        error: PortfolioImportError record.

    Returns:
        str | None: Extracted identifier, or None if not found.
    """
    # Try to extract from error message: "Instrument 'IDENTIFIER' not found (by ISIN or ticker)"
    error_message = error.error_message
    match = re.search(r"Instrument '([^']+)' not found", error_message)
    if match:
        return match.group(1).strip().upper()

    # Fallback: try to extract from raw_row_data JSON
    raw_row_data = error.raw_row_data
    if raw_row_data and isinstance(raw_row_data, dict):
        # Look for common identifier field names
        for field in ["instrument_identifier", "isin", "ticker", "ISIN", "TICKER"]:
            if field in raw_row_data and raw_row_data[field]:
                return str(raw_row_data[field]).strip().upper()

    return None
