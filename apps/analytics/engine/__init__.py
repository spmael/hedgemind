"""
Analytics engine module.

This package contains pure Python computation logic for portfolio analytics,
separate from Django models and views. This design allows:
- Unit testing without Django dependencies
- Future extraction to microservice if needed
- Clear separation of computation from data persistence

Key modules:
- valuation: Portfolio valuation computation
- aggregation: Aggregation and summary computation functions
- exposures: Exposure computation functions
"""

from apps.analytics.engine.aggregation import (
    compute_aggregates_from_results,
    compute_data_quality_summary,
    recalculate_total_market_value,
)
from apps.analytics.engine.exposures import (
    compute_country_exposures,
    compute_currency_exposures,
    compute_exposures,
    compute_instrument_group_exposures,
    compute_instrument_type_exposures,
    compute_issuer_exposures,
    compute_top_concentrations,
)
from apps.analytics.engine.valuation import compute_valuation_policy_a

__all__ = [
    "compute_valuation_policy_a",
    "compute_aggregates_from_results",
    "compute_data_quality_summary",
    "recalculate_total_market_value",
    "compute_exposures",
    "compute_currency_exposures",
    "compute_issuer_exposures",
    "compute_country_exposures",
    "compute_instrument_group_exposures",
    "compute_instrument_type_exposures",
    "compute_top_concentrations",
]
