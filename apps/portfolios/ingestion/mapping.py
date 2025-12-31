"""
Column mapping service for portfolio imports.

Handles mapping between source file columns and PositionSnapshot fields.
Since template is fixed, implements simple exact name matching with case-insensitive support.
"""

from __future__ import annotations

import pandas as pd

# Required fields that must be mapped
# Note: price and market_value are flexible - one can be computed from the other
REQUIRED_FIELDS = [
    "instrument_identifier",
    "quantity",
    "currency",
    "book_value",
    "valuation_source",
]

# Flexible fields - at least one of (price, market_value) must be present
# Validation will check that market_value OR (quantity + price) is available
FLEXIBLE_FIELDS = ["price", "market_value"]

# Optional fields
OPTIONAL_FIELDS = [
    "accrued_interest",
]

# All fields (for mapping detection)
ALL_FIELDS = REQUIRED_FIELDS + FLEXIBLE_FIELDS + OPTIONAL_FIELDS


def detect_column_mapping(
    df: pd.DataFrame, explicit_mapping: dict[str, str] | None = None
) -> dict[str, str]:
    """
    Detect or apply column mapping from source file to standard fields.

    Since template is fixed, matches exact column names (case-insensitive, strip whitespace).
    If explicit_mapping is provided, uses it directly.

    Args:
        df: Source DataFrame with columns to map.
        explicit_mapping: Explicit mapping dict {standard_field: source_column}.

    Returns:
        dict: Mapping {standard_field: source_column_name}.

    Example:
        >>> df = pd.DataFrame({"ISIN": [...], "Qty": [...], "MV": [...]})
        >>> mapping = detect_column_mapping(df)
        >>> # Returns: {"instrument_identifier": "ISIN", "quantity": "Qty", "market_value": "MV"}
    """
    if explicit_mapping:
        return explicit_mapping

    mapping = {}
    # Create case-insensitive lookup dict
    source_columns_lower = {col.lower().strip(): col for col in df.columns}

    # Map each standard field to source column
    for standard_field in ALL_FIELDS:
        # Try exact match first (case-insensitive)
        if standard_field.lower() in source_columns_lower:
            mapping[standard_field] = source_columns_lower[standard_field.lower()]
        else:
            # Try with underscores replaced by spaces
            field_variant = standard_field.replace("_", " ").lower()
            if field_variant in source_columns_lower:
                mapping[standard_field] = source_columns_lower[field_variant]
            else:
                # Try common abbreviations
                abbreviations = {
                    "instrument_identifier": [
                        "isin",
                        "ticker",
                        "instrument_id",
                        "security_id",
                    ],
                    "quantity": ["qty", "units", "shares", "nominal"],
                    "price": ["unit_price", "price_per_unit"],
                    "market_value": ["mv", "market_val", "current_value"],
                    "book_value": ["cost", "cost_basis", "book_cost"],
                    "valuation_source": ["val_source", "source"],
                    "accrued_interest": ["accrued", "ai"],
                }
                if standard_field in abbreviations:
                    for abbrev in abbreviations[standard_field]:
                        if abbrev in source_columns_lower:
                            mapping[standard_field] = source_columns_lower[abbrev]
                            break

    return mapping


def validate_mapping(mapping: dict[str, str], required_fields: list[str]) -> list[str]:
    """
    Validate that required fields are mapped.

    Also validates that at least one of the flexible fields (price, market_value) is present.

    Args:
        mapping: Column mapping dict {standard_field: source_column}.
        required_fields: List of required standard field names.

    Returns:
        list: List of missing required fields (empty if all present).

    Example:
        >>> mapping = {"instrument_identifier": "ISIN", "quantity": "Qty"}
        >>> missing = validate_mapping(mapping, REQUIRED_FIELDS)
        >>> # Returns: ["currency", "book_value", "valuation_source"]
    """
    missing = [field for field in required_fields if field not in mapping]

    # Check flexible fields: at least one of (price, market_value) must be present
    has_price = "price" in mapping
    has_market_value = "market_value" in mapping
    if not has_price and not has_market_value:
        missing.append("price or market_value")

    return missing
