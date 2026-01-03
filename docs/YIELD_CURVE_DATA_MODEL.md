# Yield Curve Data Model: Observations vs Canonical Points

## Overview

The yield curve system uses a **two-layer architecture** following data engineering best practices:
1. **YieldCurvePointObservation** - Raw/ETL landing zone (multiple sources)
2. **YieldCurvePoint** - Canonical "chosen" records (single source of truth)

This pattern allows the system to:
- Accept data from multiple sources (BEAC, BVMAC, manual entry, etc.)
- Store all raw observations for audit trail
- Select the "best" observation based on source priority
- Provide a single source of truth for calculations

## YieldCurvePointObservation (Raw Observations)

**Purpose**: ETL landing zone where raw yield curve data from various sources is stored.

**Key Characteristics**:
- **Multiple observations allowed** for the same curve/tenor/date from different sources
- Stores raw data exactly as imported
- Unique constraint: `(curve, tenor_days, date, source, revision)`
- This is where data is initially stored after import

**Fields**:
- `curve` - The yield curve
- `tenor` - Tenor string (e.g., "5Y")
- `tenor_days` - Tenor in days (e.g., 1825)
- `rate` - Interest rate as percentage (e.g., 5.50)
- `date` - Date for which this yield point is valid
- `source` - MarketDataSource (BEAC, BVMAC, MANUAL, etc.)
- `revision` - Revision number (0 = initial, 1+ = corrections)
- `observed_at` - When this observation was received/recorded

**Example Scenario**:
For the same curve/tenor/date, you might have:
- Observation 1: BEAC source, rate = 5.50%
- Observation 2: BVMAC source, rate = 5.48%
- Observation 3: MANUAL source, rate = 5.52%

All three observations are stored in `YieldCurvePointObservation`.

## YieldCurvePoint (Canonical Points)

**Purpose**: Single source of truth for yield curve data used in calculations and reporting.

**Key Characteristics**:
- **One point per curve/tenor/date combination** (unique constraint)
- Selected from observations via canonicalization process
- Used for fixed income valuation and duration/DV01 calculations
- Includes audit trail and selection metadata

**Fields** (includes all observation fields PLUS):
- `curve`, `tenor`, `tenor_days`, `rate`, `date` - Same as observation
- `chosen_source` - Which source was selected (the "winner")
- `observation` - Link back to the observation that was selected (optional, for audit)
- `selection_reason` - Why this point was selected (AUTO_POLICY, MANUAL_OVERRIDE, etc.)
- `selected_by` - User who manually selected (if manual override)
- `selected_at` - When this point was canonicalized
- `last_published_date` - Date when source published this data
- `published_date_assumed` - Whether publication date was assumed
- `is_official` - Whether this is official data

**Example Scenario** (continuing from above):
After canonicalization, only ONE canonical point exists:
- YieldCurvePoint: rate = 5.50%, chosen_source = BEAC (highest priority), selection_reason = AUTO_POLICY

The other observations (BVMAC, MANUAL) remain in `YieldCurvePointObservation` for audit purposes, but are not used in calculations.

## Canonicalization Process

The canonicalization process (`canonicalize_yield_curves`) selects the "best" observation based on:

1. **Source Priority** (lower number = higher priority)
   - BEAC (central bank) might have priority = 1
   - BVMAC (exchange) might have priority = 2
   - MANUAL might have priority = 10

2. **Revision Number** (higher revision = more recent correction)

3. **Observed At** (most recent observation wins if priority/revision are equal)

4. **Active Sources Only** (inactive sources are excluded)

**Process Flow**:
```
Import Excel File
    ↓
Create YieldCurvePointObservation records (multiple sources possible)
    ↓
Run Canonicalization (canonicalize_yield_curves)
    ↓
Select best observation per (curve, tenor_days, date)
    ↓
Create/Update YieldCurvePoint record (one per combination)
```

## When to Use Each

**Use YieldCurvePointObservation when**:
- Importing new data from Excel files
- Viewing all available data from all sources
- Audit trail: "What data was available from BEAC on this date?"
- Debugging: "Why was this point selected?"

**Use YieldCurvePoint when**:
- Performing calculations (valuation, duration, DV01)
- Generating reports
- Building analytics
- **This is the single source of truth for calculations**

## Data Flow Example

**Step 1: Import Data**
```python
# Import creates observations
YieldCurvePointObservation.objects.create(
    curve=cameroon_curve,
    tenor="5Y",
    tenor_days=1825,
    rate=5.50,
    date=date(2025, 1, 31),
    source=beac_source,
    revision=0
)

YieldCurvePointObservation.objects.create(
    curve=cameroon_curve,
    tenor="5Y",
    tenor_days=1825,
    rate=5.48,
    date=date(2025, 1, 31),
    source=bvmac_source,
    revision=0
)
# Now you have 2 observations for the same curve/tenor/date
```

**Step 2: Canonicalize**
```python
from apps.reference_data.services.yield_curves.canonicalize import canonicalize_yield_curves

result = canonicalize_yield_curves(
    curve=cameroon_curve,
    as_of_date=date(2025, 1, 31)
)
# Selects BEAC observation (higher priority)
# Creates ONE YieldCurvePoint record
```

**Step 3: Use in Calculations**
```python
# Use canonical points (not observations)
point = YieldCurvePoint.objects.get(
    curve=cameroon_curve,
    tenor_days=1825,
    date=date(2025, 1, 31)
)
# rate = 5.50 (from BEAC source)
# This is what gets used in calculations
```

## Summary

| Aspect | YieldCurvePointObservation | YieldCurvePoint |
|--------|---------------------------|-----------------|
| **Purpose** | Raw data storage (ETL landing zone) | Canonical data (single source of truth) |
| **Multiplicity** | Multiple per curve/tenor/date (different sources) | One per curve/tenor/date |
| **Unique Constraint** | curve + tenor_days + date + source + revision | curve + tenor_days + date |
| **Created By** | Import process | Canonicalization process |
| **Used For** | Audit trail, debugging, import storage | Calculations, reports, analytics |
| **Source Tracking** | `source` field | `chosen_source` field + `observation` link |
| **Selection Metadata** | None | `selection_reason`, `selected_by`, `selected_at` |
| **Staleness Tracking** | `observed_at` | `last_published_date`, `published_date_assumed` |

## Why This Architecture?

This two-layer architecture provides:
1. **Data Quality**: Store all raw data, then select the best
2. **Audit Trail**: Full history of what data was available
3. **Source Priority**: Configurable hierarchy (BEAC > BVMAC > MANUAL)
4. **Defensibility**: "We used BEAC data because it has highest priority"
5. **Flexibility**: Change source priorities without losing historical data
6. **Performance**: Single table for calculations (no joins needed)
7. **Industry Standard**: Same pattern used by Bloomberg, Aladdin, etc.

