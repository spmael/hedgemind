"""
Tenor mapping utilities for yield curve processing.

Provides functions to map between tenor string representations (e.g., "1M", "3Y")
and tenor days (e.g., 30, 1095) for yield curve data processing.

This module defines the standard tenor conventions used throughout the yield curve
system. Tenors are normalized to uppercase for consistency.
"""

from __future__ import annotations

# Standard tenor mappings: tenor string -> days
# Based on standard financial market conventions
_TENOR_DAYS_MAP: dict[str, int] = {
    # Overnight / Very short term
    "ON": 1,  # Overnight
    "1D": 1,  # 1 day
    "TN": 2,  # Tomorrow next
    "SN": 2,  # Spot next
    # Short term
    "1W": 7,  # 1 week
    "2W": 14,  # 2 weeks
    "3W": 21,  # 3 weeks
    "1M": 30,  # 1 month (30 days)
    "2M": 60,  # 2 months
    "3M": 90,  # 3 months (quarter)
    "4M": 120,  # 4 months
    "5M": 150,  # 5 months
    "6M": 180,  # 6 months (half year)
    "7M": 210,  # 7 months
    "8M": 240,  # 8 months
    "9M": 270,  # 9 months
    "10M": 300,  # 10 months
    "11M": 330,  # 11 months
    # Medium term
    "1Y": 365,  # 1 year
    "18M": 547,  # 18 months (approx)
    "2Y": 730,  # 2 years (365 * 2)
    "3Y": 1095,  # 3 years (365 * 3)
    "3Y6M": 1315,  # 3 years 6 months (365 * 3 + 180)
    "4Y": 1460,  # 4 years (365 * 4)
    "5Y": 1825,  # 5 years (365 * 5)
    # Long term
    "6Y": 2190,  # 6 years
    "7Y": 2555,  # 7 years
    "8Y": 2920,  # 8 years
    "9Y": 3285,  # 9 years
    "10Y": 3650,  # 10 years
    "12Y": 4380,  # 12 years
    "15Y": 5475,  # 15 years
    "20Y": 7300,  # 20 years
    "25Y": 9125,  # 25 years
    "30Y": 10950,  # 30 years
}


def get_all_tenors() -> list[str]:
    """
    Get all valid tenor strings.

    Returns a list of all supported tenor strings in uppercase, sorted by
    their corresponding number of days (ascending).

    Returns:
        list[str]: List of valid tenor strings (e.g., ["ON", "1D", "1W", "1M", "3M", "1Y", "5Y", "10Y"]).

    Example:
        >>> tenors = get_all_tenors()
        >>> "1Y" in tenors
        True
        >>> "5Y" in tenors
        True
    """
    # Sort by days (ascending) to return in logical order
    return sorted(_TENOR_DAYS_MAP.keys(), key=lambda t: _TENOR_DAYS_MAP[t])


def get_tenor_days(tenor_str: str) -> int:
    """
    Convert tenor string to number of days.

    Converts a tenor string (e.g., "1M", "3Y", "5Y") to the corresponding
    number of days. The input is normalized to uppercase before lookup.

    Args:
        tenor_str: Tenor string (e.g., "1M", "3Y", "5y", "ON").

    Returns:
        int: Number of days for the tenor.

    Raises:
        ValueError: If the tenor string is not recognized.

    Example:
        >>> get_tenor_days("1M")
        30
        >>> get_tenor_days("1Y")
        365
        >>> get_tenor_days("5Y")
        1825
        >>> get_tenor_days("5y")  # Case insensitive
        1825
    """
    normalized = tenor_str.upper().strip()

    if normalized not in _TENOR_DAYS_MAP:
        valid_tenors = ", ".join(
            get_all_tenors()[:10]
        )  # Show first 10 for error message
        raise ValueError(
            f"Unrecognized tenor: '{tenor_str}'. "
            f"Valid tenors include: {valid_tenors}, ... (see get_all_tenors() for full list)"
        )

    return _TENOR_DAYS_MAP[normalized]
