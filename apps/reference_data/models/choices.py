"""
Choice classes for reference data models.

Contains TextChoices classes used across multiple model domains.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class ValuationMethod(models.TextChoices):
    """
    Valuation method choices for instruments.

    Defines how the instrument is valued:
    - MARK_TO_MARKET: Public assets with market prices
    - MARK_TO_MODEL: Modeled valuations (future use)
    - EXTERNAL_APPRAISAL: Third-party valuation
    - MANUAL_DECLARED: Manual entry by institution
    """

    MARK_TO_MARKET = "mark_to_market", _("Mark to Market")
    MARK_TO_MODEL = "mark_to_model", _("Mark to Model")
    EXTERNAL_APPRAISAL = "external_appraisal", _("External Appraisal")
    MANUAL_DECLARED = "manual_declared", _("Manual Declared")


class SelectionReason(models.TextChoices):
    """Reason for selecting a price observation as canonical."""

    AUTO_POLICY = "auto_policy", _("Auto Policy")  # Selected by priority policy
    AUTO_POLICY_MID_FROM_BEAC = (
        "auto_policy_mid_from_beac",
        _("Auto Policy MID from BEAC"),
    )  # MID computed from BUY/SELL observations
    MANUAL_OVERRIDE = "manual_override", _("Manual Override")  # Manually selected
    ONLY_AVAILABLE = "only_available", _("Only Available")  # Only one source available


class YieldCurveType(models.TextChoices):
    """Yield curve type choices."""

    GOVT = "govt", _("Government")
    SWAP = "swap", _("Swap")
    OIS = "ois", _("OIS")
    CORPORATE = "corporate", _("Corporate")
    POLICY = "policy", _("Policy Rate")


class FundCategory(models.TextChoices):
    """
    Fund category choices indicating what asset types constitute the fund.

    Defines the primary asset class composition of a fund:
    - DIVERSIFIED: Fund holds both bonds and equities
    - MONEY_MARKET: Fund holds money market instruments (short-term, liquid)
    - BOND: Fund holds primarily bonds/fixed income
    - EQUITY: Fund holds primarily equities/stocks
    """

    DIVERSIFIED = "diversified", _("Diversified")
    MONEY_MARKET = "money_market", _("Money Market")
    BOND = "bond", _("Bond")
    EQUITY = "equity", _("Equity")
