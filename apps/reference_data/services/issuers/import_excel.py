"""
Excel import service for issuer master data.

Reads issuer data from Excel files and creates/updates Issuer records.
Works with Django FileField (supports local storage and S3/R2).

Expected Excel format:
    name | short_name | country | issuer_group
    AFRICA BRIGHT ASSET MANAGEMENT | ABAM | GA | Asset Manager
"""

from __future__ import annotations

import pandas as pd

from apps.reference_data.models import Issuer
from libs.tenant_context import get_current_org_id


def import_issuers_from_file(
    file_path: str,
    sheet_name: str | None = "ISSUERS",
) -> dict[str, int]:
    """
    Import issuer master data from Excel file path.

    This is the core import logic for issuers. It reads from a local file path
    and creates/updates Issuer records. Issuers are organization-scoped, so
    this function must be called within an organization context.

    Expected Excel format:
        name | short_name | country | issuer_group
        AFRICA BRIGHT ASSET MANAGEMENT | ABAM | GA | Asset Manager

    Validation rules:
        - name is required
        - short_name is required
        - country is required (2-letter country code)
        - issuer_group is required
        - (organization, name) must be unique

    Args:
        file_path: Path to Excel file (local filesystem path).
        sheet_name: Sheet name to read (default: "ISSUERS").

    Returns:
        dict: Summary with keys 'created', 'updated', 'errors', 'total_rows'.

    Raises:
        ValueError: If Excel format is invalid or organization context is missing.
        RuntimeError: If not called within organization context.

    Example:
        >>> from libs.tenant_context import organization_context
        >>> with organization_context(org_id=1):
        ...     result = import_issuers_from_file("issuers.xlsx")
        ...     print(f"Created {result['created']} issuers")
    """
    # Verify organization context
    org_id = get_current_org_id()
    if org_id is None:
        raise RuntimeError(
            "Cannot import issuers without organization context. "
            "Use organization_context() context manager or set_current_org_id()."
        )

    # Read Excel file
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    # Validate required columns
    required_columns = ["name", "short_name", "country", "issuer_group"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. "
            f"Found columns: {list(df.columns)}"
        )

    # Normalize country codes to uppercase
    df["country"] = df["country"].str.upper().str.strip()

    # Validate country codes are 2 characters
    invalid_countries = df[df["country"].str.len() != 2]["country"].unique()
    if len(invalid_countries) > 0:
        raise ValueError(
            f"Invalid country codes (must be 2 characters): {list(invalid_countries)}"
        )

    # Normalize issuer_group
    df["issuer_group"] = df["issuer_group"].str.strip()

    created = 0
    updated = 0
    errors = []

    # Process each row
    for idx, row in df.iterrows():
        try:
            # Handle NaN values from Excel
            if pd.isna(row["name"]):
                errors.append(f"Row {idx + 2}: name is required")
                continue
            name = str(row["name"]).strip()
            short_name = str(row["short_name"]).strip()
            country = str(row["country"]).upper().strip()
            issuer_group = str(row["issuer_group"]).strip()

            # Validate required fields
            if not name:
                errors.append(f"Row {idx + 2}: name is required")
                continue
            if not short_name:
                errors.append(f"Row {idx + 2}: short_name is required")
                continue
            if not country or len(country) != 2:
                errors.append(f"Row {idx + 2}: country must be a 2-character code")
                continue
            if not issuer_group:
                errors.append(f"Row {idx + 2}: issuer_group is required")
                continue

            # Create or update issuer
            # Use unique_together constraint: (organization, name)
            issuer, was_created = Issuer.objects.update_or_create(
                organization_id=org_id,
                name=name,
                defaults={
                    "short_name": short_name,
                    "country": country,
                    "issuer_group": issuer_group,
                    "is_active": True,
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

