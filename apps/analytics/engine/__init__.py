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
"""

from apps.analytics.engine.aggregation import (
    compute_aggregates_from_results,
    compute_data_quality_summary,
    recalculate_total_market_value,
)
from apps.analytics.engine.valuation import compute_valuation_policy_a

__all__ = [
    "compute_valuation_policy_a",
    "compute_aggregates_from_results",
    "compute_data_quality_summary",
    "recalculate_total_market_value",
]
