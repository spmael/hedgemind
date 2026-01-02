"""
Excel import service for instrument master data.

Reads instrument data from Excel files and creates/updates Instrument records.
Works with Django FileField (supports local storage and S3/R2).

Expected Excel format:
    isin | name | ticker | instrument_group_code | instrument_type_code | currency |
    issuer_code | country | maturity_date | coupon_rate | valuation_method |
    fund_category | fund_launch_date | first_listing_date | original_offering_amount |
    units_outstanding | face_value | amortization_method | coupon_frequency |
    last_coupon_date | next_coupon_date
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from dateutil.relativedelta import relativedelta

from apps.reference_data.models import (
    FundCategory,
    Instrument,
    InstrumentGroup,
    InstrumentType,
    Issuer,
    ValuationMethod,
)
from libs.tenant_context import get_current_org_id


def import_instruments_from_file(
    file_path: str,
    sheet_name: str | None = "INSTRUMENTS",
) -> dict[str, int]:
    """
    Import instrument master data from Excel file path.

    This is the core import logic for instruments. It reads from a local file path
    and creates/updates Instrument records. Instruments are organization-scoped, so
    this function must be called within an organization context.

    Expected Excel format:
        isin | name | ticker | instrument_group_code | instrument_type_code | currency |
        issuer_code | country | maturity_date | coupon_rate | valuation_method | ...

    Validation rules:
        - name is required
        - instrument_group_code must exist in InstrumentGroup
        - instrument_type_code must exist in InstrumentType (within the group)
        - currency is required
        - issuer_code must exist in Issuer (by short_name or name)
        - valuation_method must be valid ValuationMethod choice
        - fund_category must be valid FundCategory choice (if provided)

    Args:
        file_path: Path to Excel file (local filesystem path).
        sheet_name: Sheet name to read (default: "INSTRUMENTS").

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'total_rows'.

    Raises:
        ValueError: If Excel format is invalid or organization context is missing.
        RuntimeError: If not called within organization context.

    Example:
        >>> from libs.tenant_context import organization_context
        >>> with organization_context(org_id=1):
        ...     result = import_instruments_from_file("instruments.xlsx")
        ...     print(f"Created {result['created']} instruments")
    """
    # Verify organization context
    org_id = get_current_org_id()
    if org_id is None:
        raise RuntimeError(
            "Cannot import instruments without organization context. "
            "Use organization_context() context manager or set_current_org_id()."
        )

    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate required columns
    required_columns = [
        "name",
        "instrument_group_code",
        "instrument_type_code",
        "currency",
        "issuer_code",
        "valuation_method",
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. "
            f"Found columns: {list(df.columns)}"
        )

    # Get all unique codes and resolve them to model instances
    unique_group_codes = df["instrument_group_code"].dropna().unique()
    unique_type_codes = df["instrument_type_code"].dropna().unique()
    unique_issuer_codes = df["issuer_code"].dropna().unique()

    # Resolve InstrumentGroups
    groups_by_code = {
        group.name: group
        for group in InstrumentGroup.objects.filter(name__in=unique_group_codes)
    }
    missing_groups = [code for code in unique_group_codes if code not in groups_by_code]
    if missing_groups:
        raise ValueError(
            f"InstrumentGroup codes not found: {missing_groups}. "
            f"Please create InstrumentGroup records first."
        )

    # Resolve InstrumentTypes (must match both group and type code)
    types_by_code = {}
    for group_code in unique_group_codes:
        group = groups_by_code.get(group_code)
        if group:
            types = InstrumentType.objects.filter(
                group=group, name__in=unique_type_codes
            )
            for inst_type in types:
                key = (group_code, inst_type.name)
                types_by_code[key] = inst_type

    # Check for missing types
    missing_types = []
    for _, row in df.iterrows():
        group_code = row.get("instrument_group_code")
        type_code = row.get("instrument_type_code")
        if pd.notna(group_code) and pd.notna(type_code):
            key = (group_code, type_code)
            if key not in types_by_code:
                missing_types.append(f"{group_code}/{type_code}")
    if missing_types:
        raise ValueError(
            f"InstrumentType codes not found: {list(set(missing_types))}. "
            f"Please create InstrumentType records first."
        )

    # Resolve Issuers (by issuer_code first, then short_name, then name)
    issuers_by_code = {}
    # Try by issuer_code first (new structured format)
    for issuer in Issuer.objects.filter(
        organization_id=org_id, issuer_code__in=unique_issuer_codes
    ):
        if issuer.issuer_code:
            issuers_by_code[issuer.issuer_code.upper()] = issuer
    # Then by short_name
    for issuer in Issuer.objects.filter(
        organization_id=org_id, short_name__in=unique_issuer_codes
    ):
        if issuer.short_name and issuer.short_name.upper() not in issuers_by_code:
            issuers_by_code[issuer.short_name.upper()] = issuer
    # Finally by name
    for issuer in Issuer.objects.filter(
        organization_id=org_id, name__in=unique_issuer_codes
    ):
        if issuer.name and issuer.name.upper() not in issuers_by_code:
            issuers_by_code[issuer.name.upper()] = issuer

    # Check for missing issuers
    missing_issuers = [
        code for code in unique_issuer_codes if code.upper() not in issuers_by_code
    ]
    if missing_issuers:
        raise ValueError(
            f"Issuer codes not found (by issuer_code, short_name, or name): {missing_issuers}. "
            f"Please create Issuer records first."
        )

    # Validate valuation_method values
    valid_valuation_methods = [choice[0] for choice in ValuationMethod.choices]
    invalid_valuation_methods = df[
        ~df["valuation_method"].isin(valid_valuation_methods)
    ]["valuation_method"].unique()
    if len(invalid_valuation_methods) > 0:
        raise ValueError(
            f"Invalid valuation_method values: {list(invalid_valuation_methods)}. "
            f"Valid values: {valid_valuation_methods}"
        )

    # Validate fund_category values (if column exists)
    if "fund_category" in df.columns:
        valid_fund_categories = [choice[0] for choice in FundCategory.choices]
        invalid_categories = df[
            df["fund_category"].notna()
            & ~df["fund_category"].isin(valid_fund_categories)
        ]["fund_category"].unique()
        if len(invalid_categories) > 0:
            raise ValueError(
                f"Invalid fund_category values: {list(invalid_categories)}. "
                f"Valid values: {valid_fund_categories}"
            )

    created = 0
    updated = 0
    errors = []

    # Process each row
    for idx, row in df.iterrows():
        try:
            # Required fields
            name = str(row["name"]).strip()
            if not name:
                errors.append(f"Row {idx + 2}: name is required")
                continue

            instrument_group_code = str(row["instrument_group_code"]).strip()
            instrument_type_code = str(row["instrument_type_code"]).strip()
            currency = str(row["currency"]).upper().strip()
            issuer_code = str(row["issuer_code"]).strip()
            valuation_method = str(row["valuation_method"]).lower().strip()

            # Get model instances
            group = groups_by_code.get(instrument_group_code)
            if not group:
                errors.append(
                    f"Row {idx + 2}: InstrumentGroup '{instrument_group_code}' not found"
                )
                continue

            type_key = (instrument_group_code, instrument_type_code)
            instrument_type = types_by_code.get(type_key)
            if not instrument_type:
                errors.append(
                    f"Row {idx + 2}: InstrumentType '{instrument_type_code}' not found in group '{instrument_group_code}'"
                )
                continue

            issuer = issuers_by_code.get(issuer_code.upper())
            if not issuer:
                errors.append(f"Row {idx + 2}: Issuer '{issuer_code}' not found")
                continue

            # Optional fields
            isin = None
            if pd.notna(row.get("isin")):
                isin = str(row["isin"]).strip() or None

            ticker = None
            if pd.notna(row.get("ticker")):
                ticker = str(row["ticker"]).strip() or None

            country = None
            if pd.notna(row.get("country")):
                country = str(row["country"]).upper().strip() or None

            # Date fields
            # Handle first_listing_date first (needed for maturity calculation)
            first_listing_date = None
            if pd.notna(row.get("first_listing_date")):
                try:
                    if isinstance(row["first_listing_date"], str):
                        first_listing_date = pd.to_datetime(
                            row["first_listing_date"]
                        ).date()
                    else:
                        first_listing_date = (
                            row["first_listing_date"].date()
                            if hasattr(row["first_listing_date"], "date")
                            else None
                        )
                except Exception:
                    pass  # Optional field, skip if invalid

            # Calculate maturity_date
            # Priority: 1) explicit maturity_date, 2) first_listing_date + maturity (years)
            maturity_date = None
            if pd.notna(row.get("maturity_date")):
                # If maturity_date is explicitly provided, use it
                try:
                    if isinstance(row["maturity_date"], str):
                        maturity_date = pd.to_datetime(row["maturity_date"]).date()
                    else:
                        maturity_date = (
                            row["maturity_date"].date()
                            if hasattr(row["maturity_date"], "date")
                            else None
                        )
                except Exception:
                    pass  # Optional field, skip if invalid
            elif pd.notna(row.get("maturity")) and first_listing_date:
                # Calculate maturity_date = first_listing_date + maturity (years)
                # "maturity" column contains number of years, not a date
                try:
                    maturity_years = float(row["maturity"])
                    if maturity_years > 0:
                        maturity_date = first_listing_date + relativedelta(
                            years=int(maturity_years)
                        )
                except (ValueError, TypeError):
                    pass  # Invalid maturity value, skip calculation

            fund_launch_date = None
            if pd.notna(row.get("fund_launch_date")):
                try:
                    if isinstance(row["fund_launch_date"], str):
                        fund_launch_date = pd.to_datetime(
                            row["fund_launch_date"]
                        ).date()
                    else:
                        fund_launch_date = (
                            row["fund_launch_date"].date()
                            if hasattr(row["fund_launch_date"], "date")
                            else None
                        )
                except Exception:
                    pass  # Optional field, skip if invalid

            last_coupon_date = None
            if pd.notna(row.get("last_coupon_date")):
                try:
                    if isinstance(row["last_coupon_date"], str):
                        last_coupon_date = pd.to_datetime(
                            row["last_coupon_date"]
                        ).date()
                    else:
                        last_coupon_date = (
                            row["last_coupon_date"].date()
                            if hasattr(row["last_coupon_date"], "date")
                            else None
                        )
                except Exception:
                    pass  # Optional field, skip if invalid

            next_coupon_date = None
            if pd.notna(row.get("next_coupon_date")):
                try:
                    if isinstance(row["next_coupon_date"], str):
                        next_coupon_date = pd.to_datetime(
                            row["next_coupon_date"]
                        ).date()
                    else:
                        next_coupon_date = (
                            row["next_coupon_date"].date()
                            if hasattr(row["next_coupon_date"], "date")
                            else None
                        )
                except Exception:
                    pass  # Optional field, skip if invalid

            # Decimal fields
            coupon_rate = None
            if pd.notna(row.get("coupon_rate")):
                try:
                    coupon_rate = Decimal(str(row["coupon_rate"]))
                except Exception:
                    pass  # Optional field, skip if invalid

            original_offering_amount = None
            if pd.notna(row.get("original_offering_amount")):
                try:
                    original_offering_amount = Decimal(
                        str(row["original_offering_amount"])
                    )
                except Exception:
                    pass

            units_outstanding = None
            if pd.notna(row.get("units_outstanding")):
                try:
                    units_outstanding = Decimal(str(row["units_outstanding"]))
                except Exception:
                    pass

            face_value = None
            if pd.notna(row.get("face_value")):
                try:
                    face_value = Decimal(str(row["face_value"]))
                except Exception:
                    pass

            # String fields
            sector = None
            if pd.notna(row.get("sector")):
                sector = str(row["sector"]).strip() or None

            amortization_method = None
            if pd.notna(row.get("amortization_method")):
                amortization_method = str(row["amortization_method"]).strip() or None

            coupon_frequency = None
            if pd.notna(row.get("coupon_frequency")):
                coupon_frequency = str(row["coupon_frequency"]).strip() or None

            fund_category = None
            if pd.notna(row.get("fund_category")):
                fund_category = str(row["fund_category"]).lower().strip() or None

            # Build defaults dict
            defaults = {
                "name": name,  # Always include name
                "instrument_group": group,
                "instrument_type": instrument_type,
                "currency": currency,
                "issuer": issuer,
                "valuation_method": valuation_method,
                "is_active": True,
            }

            # Add optional fields if provided
            if isin:
                defaults["isin"] = isin
            if ticker:
                defaults["ticker"] = ticker
            if country:
                defaults["country"] = country
            if sector:
                defaults["sector"] = sector
            if maturity_date:
                defaults["maturity_date"] = maturity_date
            if coupon_rate is not None:
                defaults["coupon_rate"] = coupon_rate
            if coupon_frequency:
                defaults["coupon_frequency"] = coupon_frequency
            if first_listing_date:
                defaults["first_listing_date"] = first_listing_date
            if original_offering_amount is not None:
                defaults["original_offering_amount"] = original_offering_amount
            if units_outstanding is not None:
                defaults["units_outstanding"] = units_outstanding
            if face_value is not None:
                defaults["face_value"] = face_value
            if amortization_method:
                defaults["amortization_method"] = amortization_method
            if last_coupon_date:
                defaults["last_coupon_date"] = last_coupon_date
            if next_coupon_date:
                defaults["next_coupon_date"] = next_coupon_date
            if fund_category:
                defaults["fund_category"] = fund_category
            if fund_launch_date:
                defaults["fund_launch_date"] = fund_launch_date

            # Create or update instrument
            # Note: Instruments don't have a unique constraint on name alone,
            # so we'll use (organization, isin) or (organization, ticker) if available,
            # otherwise (organization, name) as fallback
            if isin:
                lookup = {"organization_id": org_id, "isin": isin}
            elif ticker:
                lookup = {"organization_id": org_id, "ticker": ticker}
            else:
                lookup = {"organization_id": org_id, "name": name}

            instrument, was_created = Instrument.objects.update_or_create(
                **lookup,
                defaults=defaults,
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
