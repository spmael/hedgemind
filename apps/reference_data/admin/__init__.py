"""
Django admin configuration for reference data models.

This package provides admin interfaces for managing reference data, organized
by domain (market data sources, instruments, issuers, prices, FX rates, etc.).
"""

from __future__ import annotations

# Import all admin classes to ensure they are registered
from apps.reference_data.admin.fx_rates import *  # noqa: F403, F401
from apps.reference_data.admin.indices import *  # noqa: F403, F401
from apps.reference_data.admin.instruments import *  # noqa: F403, F401
from apps.reference_data.admin.issuers import *  # noqa: F403, F401
from apps.reference_data.admin.market_data_sources import *  # noqa: F403, F401
from apps.reference_data.admin.prices import * # noqa: F403, F401
from apps.reference_data.admin.yield_curves import *  # noqa: F403, F401

