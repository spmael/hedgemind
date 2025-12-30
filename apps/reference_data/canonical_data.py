"""
Canonical instrument group and type definitions.

This module defines the industry-standard security groups and types that
should be loaded for each organization. These definitions mirror industry
standards from Bloomberg, Aladdin, and SimCorp.

Key principles:
- Stability over completeness (don't explode the list)
- Two-level hierarchy: security_group (coarse) → security_type (granular)
- Groups used for asset allocation, risk buckets, reporting sections
- Types used for valuation logic, duration/yield logic, liquidity assumptions

Warning:
    These are canonical definitions. Do not modify lightly.
    Changes to this data structure should be versioned and migrated.
"""

from __future__ import annotations

from typing import TypedDict


class InstrumentTypeDefinition(TypedDict):
    """Definition for a single instrument type."""

    code: str  # Internal code (e.g., 'COMMON_STOCK')
    name: str  # Display name (e.g., 'Common Stock')
    description: str  # Detailed description


class InstrumentGroupDefinition(TypedDict):
    """Definition for an instrument group with its types."""

    code: str  # Internal code (e.g., 'EQUITY')
    name: str  # Display name (e.g., 'Equity')
    description: str  # Detailed description
    types: list[InstrumentTypeDefinition]  # List of types in this group


# Canonical Instrument Groups and Types
CANONICAL_INSTRUMENT_GROUPS: list[InstrumentGroupDefinition] = [
    {
        "code": "EQUITY",
        "name": "Equity",
        "description": "Equity securities including common and preferred stock, listed and unlisted equities.",
        "types": [
            {
                "code": "COMMON_STOCK",
                "name": "Common Stock",
                "description": "Common equity shares with voting rights.",
            },
            {
                "code": "PREFERRED_STOCK",
                "name": "Preferred Stock",
                "description": "Preferred equity shares with priority in dividends.",
            },
            {
                "code": "LISTED_EQUITY",
                "name": "Listed Equity",
                "description": "Equity traded on a recognized exchange (liquidity matters for pricing).",
            },
            {
                "code": "UNLISTED_EQUITY",
                "name": "Unlisted Equity",
                "description": "Equity not traded on a recognized exchange (lower liquidity).",
            },
        ],
    },
    {
        "code": "FIXED_INCOME",
        "name": "Fixed Income",
        "description": "Fixed income securities including government bonds, corporate bonds, and notes. Duration and DV01 calculations apply.",
        "types": [
            {
                "code": "GOVERNMENT_BOND",
                "name": "Government Bond",
                "description": "Bonds issued by sovereign governments.",
            },
            {
                "code": "TREASURY_BILL",
                "name": "Treasury Bill",
                "description": "Short-term government debt instruments.",
            },
            {
                "code": "CORPORATE_BOND",
                "name": "Corporate Bond",
                "description": "Bonds issued by corporations.",
            },
            {
                "code": "REGIONAL_BOND",
                "name": "Regional Bond",
                "description": "Bonds issued by regional or supranational development banks owned by a consortium of countries (e.g., development bank bonds in the CEMAC region).",
            },
            {
                "code": "SUKUK",
                "name": "Sukuk",
                "description": "Islamic fixed income securities.",
            },
            {
                "code": "NOTE",
                "name": "Note",
                "description": "Fixed income notes with specified maturity and coupon.",
            },
        ],
    },
    {
        "code": "CASH_EQUIVALENT",
        "name": "Cash Equivalent",
        "description": "Cash and cash-equivalent instruments including deposits and money market instruments. Deterministic valuation. Often large in African portfolios.",
        "types": [
            {
                "code": "DEPOSIT",
                "name": "Deposit",
                "description": "Bank deposits (don't treat as 'cash' loosely—deposits are instruments).",
            },
            {
                "code": "TIME_DEPOSIT",
                "name": "Time Deposit",
                "description": "Fixed-term bank deposits.",
            },
            {
                "code": "CALL_ACCOUNT",
                "name": "Call Account",
                "description": "Callable deposit accounts with flexible withdrawal.",
            },
            {
                "code": "MONEY_MARKET",
                "name": "Money Market",
                "description": "Short-term money market instruments.",
            },
        ],
    },
    {
        "code": "FUND",
        "name": "Fund",
        "description": "Collective investment vehicles including mutual funds and ETFs. Funds are look-through optional. Risk usually treated as single line at MVP.",
        "types": [
            {
                "code": "MUTUAL_FUND",
                "name": "Mutual Fund",
                "description": "Open-ended mutual funds with NAV-based valuation.",
            },
            {
                "code": "ETF",
                "name": "ETF",
                "description": "Exchange-traded funds.",
            },
            {
                "code": "MONEY_MARKET_FUND",
                "name": "Money Market Fund",
                "description": "Money market mutual funds.",
            },
            {
                "code": "PRIVATE_FUND",
                "name": "Private Fund",
                "description": "Private investment funds.",
            },
        ],
    },
    {
        "code": "PRIVATE_ASSET",
        "name": "Private Asset",
        "description": "Private assets including real estate, private equity, and infrastructure. Valuation = declared/appraisal. Liquidity horizon is critical metadata.",
        "types": [
            {
                "code": "REAL_ESTATE",
                "name": "Real Estate",
                "description": "Real estate investments (property, land).",
            },
            {
                "code": "PRIVATE_EQUITY",
                "name": "Private Equity",
                "description": "Private equity stakes and investments.",
            },
            {
                "code": "INFRASTRUCTURE",
                "name": "Infrastructure",
                "description": "Infrastructure project investments.",
            },
            {
                "code": "STRATEGIC_STAKE",
                "name": "Strategic Stake",
                "description": "Strategic ownership stakes in companies or projects.",
            },
            {
                "code": "JOINT_VENTURE",
                "name": "Joint Venture",
                "description": "Joint venture participations.",
            },
        ],
    },
    {
        "code": "DERIVATIVE",
        "name": "Derivative",
        "description": "Derivative instruments (future-proofing, not MVP-active).",
        "types": [
            {
                "code": "FORWARD",
                "name": "Forward",
                "description": "Forward contracts.",
            },
            {
                "code": "FUTURE",
                "name": "Future",
                "description": "Futures contracts.",
            },
            {
                "code": "OPTION",
                "name": "Option",
                "description": "Options contracts.",
            },
            {
                "code": "SWAP",
                "name": "Swap",
                "description": "Swap contracts.",
            },
        ],
    },
    {
        "code": "OTHER",
        "name": "Other",
        "description": "Other instrument types (escape hatch, discouraged but necessary for edge cases).",
        "types": [
            {
                "code": "OTHER",
                "name": "Other",
                "description": "Other instrument types not classified elsewhere.",
            },
        ],
    },
]


def get_canonical_groups() -> list[InstrumentGroupDefinition]:
    """
    Get the canonical instrument group definitions.

    Returns:
        list[InstrumentGroupDefinition]: List of canonical group definitions.
    """
    return CANONICAL_INSTRUMENT_GROUPS


def get_canonical_group_by_code(code: str) -> InstrumentGroupDefinition | None:
    """
    Get a canonical instrument group by its code.

    Args:
        code: The group code (e.g., 'EQUITY', 'FIXED_INCOME').

    Returns:
        InstrumentGroupDefinition | None: The group definition if found, None otherwise.
    """
    for group in CANONICAL_INSTRUMENT_GROUPS:
        if group["code"] == code:
            return group
    return None
