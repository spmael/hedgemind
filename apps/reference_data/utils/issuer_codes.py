"""
Issuer code generation and validation utilities.

Provides functions to generate, validate, and normalize issuer codes following
the structured format: [REGION]-[TYPE]-[IDENTIFIER]

Format:
    - REGION: 2-3 character country/region code (CM, CG, GA, TD, GQ, CF, XAF, INT)
    - TYPE: 3 character issuer type code (SOV, SUP, GRE, BNK, INS, AMC, FIN, COR)
    - IDENTIFIER: Up to 10 characters unique identifier (derived from issuer name)

Example:
    >>> from apps.reference_data.utils.issuer_codes import generate_issuer_code
    >>> code = generate_issuer_code(
    ...     name="ETAT DU CAMEROUN",
    ...     country="CM",
    ...     issuer_group_code="SOV"
    ... )
    >>> print(code)
    'CM-SOV-GOVT'
"""

from __future__ import annotations

import re
from typing import Optional

# Region code mapping: Country codes to region codes
REGION_CODE_MAP: dict[str, str] = {
    "CM": "CM",  # Cameroon
    "CG": "CG",  # Congo (Brazzaville)
    "GA": "GA",  # Gabon
    "TD": "TD",  # Chad
    "GQ": "GQ",  # Equatorial Guinea
    "CF": "CF",  # Central African Republic
    "XAF": "XAF",  # CEMAC-wide (supranational)
    "INT": "INT",  # International/unknown country
}

# Type code mapping: IssuerGroup codes to TYPE codes
TYPE_CODE_MAP: dict[str, str] = {
    "SOV": "SOV",  # Sovereign
    "SUPRA": "SUP",  # Supranational
    "GRE": "GRE",  # Government-Related Entity
    "BANK": "BNK",  # Bank
    "INS": "INS",  # Insurance
    "AM": "AMC",  # Asset Manager
    "FIN": "FIN",  # Other Financial
    "FIN_OTHER": "FIN",  # Other Financial
    "CORP": "COR",  # Corporate
    "IND": "COR",  # Industrial (Corporate)
    "CONS": "COR",  # Consumer (Corporate)
    "ENERGY": "COR",  # Energy (Corporate)
    "UTIL": "COR",  # Utilities (Corporate)
}

# Issuer code format regex pattern
ISSUER_CODE_PATTERN = re.compile(r"^[A-Z]{2,3}-[A-Z]{3}-[A-Z0-9]{1,10}$")


def get_region_code(country: Optional[str]) -> str:
    """
    Get region code from country code.

    Args:
        country: ISO 3166-1 alpha-2 country code (e.g., "CM", "CG") or None.

    Returns:
        str: Region code (defaults to "INT" if country is unknown or None).
    """
    if not country:
        return "INT"

    country_upper = country.upper().strip()
    return REGION_CODE_MAP.get(country_upper, "INT")


def get_type_code(issuer_group_code: Optional[str]) -> str:
    """
    Get type code from IssuerGroup code.

    Args:
        issuer_group_code: IssuerGroup code (e.g., "SOV", "BANK") or None.

    Returns:
        str: Type code (defaults to "COR" if issuer_group_code is unknown or None).
    """
    if not issuer_group_code:
        return "COR"

    code_upper = issuer_group_code.upper().strip()
    return TYPE_CODE_MAP.get(code_upper, "COR")


def normalize_identifier(name: str, max_length: int = 10) -> str:
    """
    Normalize issuer name to create a unique identifier.

    Converts name to uppercase, removes special characters, and truncates
    to max_length. Handles common patterns like "ETAT DU" -> "GOVT".

    Args:
        name: Issuer name to normalize.
        max_length: Maximum length of identifier (default: 10).

    Returns:
        str: Normalized identifier (uppercase, alphanumeric only).

    Example:
        >>> normalize_identifier("ETAT DU CAMEROUN")
        'GOVT'
        >>> normalize_identifier("BANQUE DE GABON")
        'BANQUEDEGAB'
    """
    if not name:
        return "UNKNOWN"

    # Handle common sovereign patterns
    name_upper = name.upper().strip()
    if name_upper.startswith("ETAT DU") or name_upper.startswith("ETAT DE"):
        return "GOVT"
    if name_upper.startswith("REPUBLIQUE DU") or name_upper.startswith("REPUBLIQUE DE"):
        return "GOVT"
    if name_upper.startswith("REPUBLIC OF"):
        return "GOVT"

    # Handle common bank patterns
    if "BANQUE" in name_upper or "BANK" in name_upper:
        # Extract key words after "BANQUE" or "BANK"
        parts = re.split(r"\b(BANQUE|BANK|DE|DU|OF)\b", name_upper, flags=re.IGNORECASE)
        # Get meaningful parts (skip common words)
        meaningful = [
            p.strip()
            for p in parts
            if p.strip() and p.upper() not in ["BANQUE", "BANK", "DE", "DU", "OF"]
        ]
        if meaningful:
            # Take first meaningful part and normalize
            identifier = "".join(meaningful[0].split())[:max_length]
            if identifier:
                return identifier

    # Remove special characters, keep only alphanumeric
    identifier = re.sub(r"[^A-Z0-9]", "", name_upper)

    # If too long, truncate (don't create acronyms - just truncate)
    if len(identifier) > max_length:
        identifier = identifier[:max_length]

    return identifier if identifier else "UNKNOWN"


def generate_issuer_code(
    name: str,
    country: Optional[str] = None,
    issuer_group_code: Optional[str] = None,
    identifier: Optional[str] = None,
) -> str:
    """
    Generate issuer code from issuer attributes.

    Creates a structured issuer code following the format:
    [REGION]-[TYPE]-[IDENTIFIER]

    Args:
        name: Issuer name (used to generate identifier if not provided).
        country: ISO 3166-1 alpha-2 country code (optional).
        issuer_group_code: IssuerGroup code (optional).
        identifier: Custom identifier (optional, will be generated from name if not provided).

    Returns:
        str: Generated issuer code in format [REGION]-[TYPE]-[IDENTIFIER].

    Example:
        >>> generate_issuer_code("ETAT DU CAMEROUN", country="CM", issuer_group_code="SOV")
        'CM-SOV-GOVT'
        >>> generate_issuer_code("BANQUE DE GABON", country="GA", issuer_group_code="BANK")
        'GA-BNK-BANQUEDEGAB'
    """
    region = get_region_code(country)
    type_code = get_type_code(issuer_group_code)

    if identifier:
        # Use provided identifier, normalize it
        normalized_id = re.sub(r"[^A-Z0-9]", "", identifier.upper())[:10]
        if not normalized_id:
            normalized_id = normalize_identifier(name)
    else:
        normalized_id = normalize_identifier(name)

    return f"{region}-{type_code}-{normalized_id}"


def validate_issuer_code(code: str) -> tuple[bool, Optional[str]]:
    """
    Validate issuer code format.

    Checks if the code matches the pattern [REGION]-[TYPE]-[IDENTIFIER].
    Codes must be uppercase - lowercase codes are considered invalid.

    Args:
        code: Issuer code to validate.

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
            - is_valid: True if code is valid, False otherwise.
            - error_message: Error message if invalid, None if valid.

    Example:
        >>> validate_issuer_code("CM-SOV-GOVT")
        (True, None)
        >>> validate_issuer_code("INVALID")
        (False, "Issuer code must match pattern [REGION]-[TYPE]-[IDENTIFIER]")
        >>> validate_issuer_code("cm-sov-govt")
        (False, "Issuer code must be uppercase")
    """
    if not code:
        return False, "Issuer code cannot be empty"

    if not isinstance(code, str):
        return False, "Issuer code must be a string"

    # Check if code is uppercase (case-sensitive validation)
    if code != code.upper():
        return False, "Issuer code must be uppercase"

    code = code.strip().upper()

    if not ISSUER_CODE_PATTERN.match(code):
        return (
            False,
            "Issuer code must match pattern [REGION]-[TYPE]-[IDENTIFIER] "
            "(e.g., CM-SOV-GOVT, GA-BNK-BANQUEDEGAB)",
        )

    # Validate region code
    parts = code.split("-")
    if len(parts) != 3:
        return False, "Issuer code must have exactly 3 parts separated by hyphens"

    region, type_code, identifier = parts

    # Check if region is valid (2-3 chars, uppercase)
    if len(region) < 2 or len(region) > 3:
        return False, "Region code must be 2-3 characters"

    # Check if type code is valid (3 chars)
    if len(type_code) != 3:
        return False, "Type code must be exactly 3 characters"

    # Check if identifier is valid (1-10 chars, alphanumeric)
    if len(identifier) < 1 or len(identifier) > 10:
        return False, "Identifier must be 1-10 characters"

    if not re.match(r"^[A-Z0-9]+$", identifier):
        return False, "Identifier must contain only uppercase letters and numbers"

    return True, None
