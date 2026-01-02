"""
Preflight validation service for portfolio imports.

Validates that required reference data exists before portfolio import
to catch missing data early and provide clear feedback to operators.
"""

from __future__ import annotations

import pandas as pd

from apps.portfolios.ingestion.mapping import detect_column_mapping
from apps.portfolios.ingestion.utils import resolve_instruments
from apps.portfolios.models import PortfolioImport
from apps.reference_data.models import FXRate, InstrumentPrice, YieldCurvePoint
from libs.tenant_context import get_current_org_id


def preflight_portfolio_import(portfolio_import_id: int) -> dict:
    """
    Preflight validation for portfolio import.

    Validates that required reference data exists before portfolio import:
    - Missing instruments (by identifier from file)
    - Missing FX rates (currencies → portfolio base currency)
    - Missing prices (if valuation policy requires market data)
    - Missing yield curve points (if bond pricing needed)

    Args:
        portfolio_import_id: ID of PortfolioImport record.

    Returns:
        dict: Validation results with format:
        {
            "ready": bool,
            "missing_instruments": list[str],  # Identifiers
            "missing_fx_rates": list[dict],  # [{"from": "USD", "to": "XAF", "date": "2025-01-15"}]
            "missing_prices": list[dict],  # [{"instrument_id": 1, "identifier": "CG123", "date": "2025-01-15"}]
            "missing_curves": list[dict],  # [{"currency": "XAF", "tenor": "5Y", "date": "2025-01-15"}]
            "warnings": list[str],  # Non-blocking issues
        }

    Raises:
        ValueError: If PortfolioImport not found or organization context missing.
    """
    # Organization context check
    org_id = get_current_org_id()
    if org_id is None:
        raise RuntimeError(
            "Cannot run preflight without organization context. "
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

    # Read file
    file_path = portfolio_import.file.path
    try:
        if file_path.endswith(".csv"):
            # Use utf-8-sig to handle UTF-8 BOM (Excel-compatible CSV files)
            df = pd.read_csv(file_path, encoding="utf-8-sig")
        else:
            df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Failed to read file: {str(e)}")

    # Detect column mapping
    mapping = detect_column_mapping(df, None)

    # Initialize results
    result = {
        "ready": True,
        "missing_instruments": [],
        "missing_fx_rates": [],
        "missing_prices": [],
        "missing_curves": [],
        "warnings": [],
    }

    # Extract data from file
    if "instrument_identifier" not in mapping:
        result["ready"] = False
        result["warnings"].append(
            "Cannot validate instruments: instrument_identifier column not found"
        )
        return result

    # 1. Check missing instruments
    instrument_identifiers = (
        df[mapping["instrument_identifier"]].dropna().unique().tolist()
    )
    normalized_identifiers = [
        str(ident).strip().upper() for ident in instrument_identifiers if ident
    ]

    instruments_by_identifier = {}
    if normalized_identifiers:
        instruments_by_identifier = resolve_instruments(org_id, normalized_identifiers)
        for identifier in normalized_identifiers:
            if identifier not in instruments_by_identifier:
                result["missing_instruments"].append(identifier)
                result["ready"] = False

    # 2. Check missing FX rates
    if "currency" in mapping:
        currencies = df[mapping["currency"]].dropna().unique().tolist()
        currencies = [str(c).upper().strip() for c in currencies if c]
        portfolio_base_currency = portfolio_import.portfolio.base_currency
        as_of_date = portfolio_import.as_of_date

        # Check FX rates for each unique currency (excluding base currency)
        for currency in currencies:
            if currency == portfolio_base_currency:
                continue  # No FX rate needed for base currency

            # Check if FX rate exists (canonical FXRate table)
            fx_rate_exists = FXRate.objects.filter(
                base_currency=currency,
                quote_currency=portfolio_base_currency,
                date=as_of_date,
                rate_type=FXRate.RateType.MID,  # Use MID rate for valuation
            ).exists()

            if not fx_rate_exists:
                result["missing_fx_rates"].append(
                    {
                        "from": currency,
                        "to": portfolio_base_currency,
                        "date": as_of_date.isoformat(),
                    }
                )
                result["ready"] = False

    # 3. Check missing prices (conditional - only if valuation policy requires)
    # Note: For MVP, we default to USE_SNAPSHOT_MV which doesn't require prices
    # This check is for future REVALUE_FROM_MARKETDATA policy
    # We'll check if any instruments have valuation_method requiring prices
    if (
        normalized_identifiers
        and instruments_by_identifier
        and len(instruments_by_identifier) > 0
    ):
        # Get instruments that exist
        existing_instruments = list(instruments_by_identifier.values())
        as_of_date = portfolio_import.as_of_date

        # Check prices for instruments that might need them
        # (In MVP, this is optional, but we check for completeness)
        for instrument in existing_instruments:
            # Check if price exists for this instrument/date
            price_exists = InstrumentPrice.objects.filter(
                instrument=instrument,
                date=as_of_date,
                price_type=InstrumentPrice.PriceType.CLOSE,
            ).exists()

            if not price_exists:
                # Only warn, don't block (MVP uses USE_SNAPSHOT_MV)
                identifier = instrument.isin or instrument.ticker or str(instrument.id)
                result["missing_prices"].append(
                    {
                        "instrument_id": instrument.id,
                        "identifier": identifier,
                        "date": as_of_date.isoformat(),
                    }
                )
                # Don't set ready=False for missing prices in MVP
                # (valuation policy USE_SNAPSHOT_MV doesn't require prices)

    # 4. Check missing yield curves (conditional - only if bond pricing needed)
    # This is for future bond pricing features, not required for MVP
    # We'll check if any instruments are bonds and might need yield curves
    if normalized_identifiers and instruments_by_identifier:
        existing_instruments = list(instruments_by_identifier.values())
        as_of_date = portfolio_import.as_of_date

        # Check yield curves for bond instruments
        # Filter for fixed income instruments (bonds)
        bond_instruments = [
            inst
            for inst in existing_instruments
            if inst.instrument_group and "fixed" in inst.instrument_group.name.lower()
        ]

        for instrument in bond_instruments:
            currency = instrument.currency
            # Check if yield curve exists for this currency/date
            # (We check for any tenor, as specific tenors would require maturity date analysis)
            curve_exists = YieldCurvePoint.objects.filter(
                curve__currency=currency,
                date=as_of_date,
            ).exists()

            if not curve_exists:
                # Only warn, don't block (not required for MVP)
                result["missing_curves"].append(
                    {
                        "currency": currency,
                        "date": as_of_date.isoformat(),
                    }
                )
                # Don't set ready=False for missing curves in MVP

    return result
