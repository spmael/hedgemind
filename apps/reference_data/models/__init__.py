"""
Reference data models package.

This package contains all reference data models organized by domain:
- choices: TextChoices classes used across models
- issuers: Issuer and IssuerRating models
- instruments: Instrument, InstrumentGroup, InstrumentType models
- market_data: MarketDataSource and MarketDataSourcePriority models
- prices: InstrumentPrice, InstrumentPriceObservation, and InstrumentPriceImport models
- yield_curves: YieldCurve, YieldCurvePoint, and related models
- fx_rates: FXRate, FXRateObservation, and FXRateImport models
- indices: MarketIndex, MarketIndexValue, MarketIndexValueObservation, and MarketIndexImport models

All models are exported here for backward compatibility with existing imports.
"""

from apps.reference_data.models.choices import (
    FundCategory,
    SelectionReason,
    ValuationMethod,
    YieldCurveType,
)
from apps.reference_data.models.fx_rates import FXRate, FXRateImport, FXRateObservation
from apps.reference_data.models.indices import (
    MarketIndex,
    MarketIndexConstituent,
    MarketIndexImport,
    MarketIndexValue,
    MarketIndexValueObservation,
)
from apps.reference_data.models.instruments import (
    Instrument,
    InstrumentGroup,
    InstrumentType,
)
from apps.reference_data.models.issuers import Issuer, IssuerGroup, IssuerRating
from apps.reference_data.models.market_data import (
    MarketDataSource,
    MarketDataSourcePriority,
)
from apps.reference_data.models.prices import (
    InstrumentPrice,
    InstrumentPriceImport,
    InstrumentPriceObservation,
)
from apps.reference_data.models.yield_curves import (
    YieldCurve,
    YieldCurveImport,
    YieldCurvePoint,
    YieldCurvePointObservation,
    YieldCurveStressProfile,
)

__all__ = [
    # Choices
    "FundCategory",
    "SelectionReason",
    "ValuationMethod",
    "YieldCurveType",
    # Issuers
    "Issuer",
    "IssuerGroup",
    "IssuerRating",
    # Instruments
    "Instrument",
    "InstrumentGroup",
    "InstrumentType",
    # Market Data
    "MarketDataSource",
    "MarketDataSourcePriority",
    # Prices
    "InstrumentPrice",
    "InstrumentPriceImport",
    "InstrumentPriceObservation",
    # Yield Curves
    "YieldCurve",
    "YieldCurveImport",
    "YieldCurvePoint",
    "YieldCurvePointObservation",
    "YieldCurveStressProfile",
    # FX Rates
    "FXRate",
    "FXRateImport",
    "FXRateObservation",
    # Market Indices
    "MarketIndex",
    "MarketIndexConstituent",
    "MarketIndexImport",
    "MarketIndexValue",
    "MarketIndexValueObservation",
]
