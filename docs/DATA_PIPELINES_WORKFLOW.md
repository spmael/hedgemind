# Data Pipelines & Workflow Documentation

## Overview

This document describes the end-to-end data pipelines and workflows in Hedgemind, explaining how reference data, portfolio data, market data, and analytics components connect and flow together.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│              System Initialization (One-Time)                │
│  - Load global reference data (InstrumentGroup, Type)        │
│  - Sync market data sources (BVMAC, BEAC, etc.)             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│          Organization Setup (Per Organization)               │
│  - Create organization                                      │
│  - Load org-scoped reference data (Issuers, Instruments)    │
│  - Configure org-specific source priorities (optional)      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│         Market Data Pipeline (Ongoing, Daily)                │
│  1. Import Observations → 2. Canonicalize → 3. Store        │
│     (FX rates, prices, yield curves, indices)               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│         Portfolio Import Pipeline (Per Portfolio)            │
│  1. Upload File → 2. Preflight → 3. Import → 4. Validate   │
│     (Creates PositionSnapshot records)                      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│            Analytics Pipeline (On Demand)                    │
│  1. Valuation Run → 2. Exposure Computation → 3. Report     │
│     (Uses canonical market data + position snapshots)       │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow Components

### 1. System Initialization Pipeline

**Purpose**: Load global reference data shared across all organizations.

**Steps**:

1. **Load Instrument Taxonomy** (Static)
   ```bash
   python manage.py load_reference_data
   ```
   - Creates `InstrumentGroup` records (EQUITY, FIXED_INCOME, etc.)
   - Creates `InstrumentType` records within groups
   - **Global data**: Same for all organizations
   - **Idempotent**: Safe to re-run

2. **Sync Market Data Sources** (Deployment-Specific)
   ```bash
   python manage.py sync_market_data_sources
   ```
   - Creates baseline `MarketDataSource` records
   - Sources: BVMAC (priority 1), BEAC (priority 2), CUSTODIAN (priority 50), MANUAL (priority 100)
   - **Global data**: Shared across all organizations
   - **Deployment-specific**: Can be updated as new sources are added
   - **Idempotent**: Safe to re-run

**Output**: Global reference data foundation ready for all organizations.

---

### 2. Organization Setup Pipeline

**Purpose**: Prepare organization-specific reference data for portfolio operations.

**Steps**:

1. **Create Organization**
   - Via Django admin or API
   - Sets base currency (default: XAF)

2. **Load Organization-Scoped Reference Data**
   ```bash
   # Step 1: Load issuers
   python manage.py import_issuers_excel --file issuers.xlsx --org-id 1
   
   # Step 2: Load instruments (depends on issuers)
   python manage.py import_instruments_excel --file instruments.xlsx --org-id 1
   ```

3. **Configure Organization-Specific Source Priorities** (Optional)
   - Via Django admin: `MarketDataSourcePriority`
   - Allows org to override global source priorities for:
     - FX rates
     - Prices
     - Yield curves
     - Index values
   - Example: Org 1 prefers CUSTODIAN (priority 1) over BEAC (priority 2) for FX rates

**Dependencies**:
- ✅ Global reference data must be loaded (InstrumentGroup, InstrumentType)
- ✅ Market data sources must exist (MarketDataSource records)

**Output**: Organization ready for portfolio imports and analytics.

---

### 3. Market Data Pipeline

**Purpose**: Import and canonicalize market data observations into authoritative canonical records.

**Data Types**:
- FX Rates (FXRateObservation → FXRate)
- Instrument Prices (InstrumentPriceObservation → InstrumentPrice)
- Yield Curves (YieldCurvePointObservation → YieldCurvePoint)
- Index Values (MarketIndexValueObservation → MarketIndexValue)

#### 3.1 Import Observations

**Purpose**: Ingest raw market data from various sources.

**Process**:
1. Upload Excel file via management command
2. Service parses file and creates observation records
3. Multiple observations can exist for same instrument/date/source (revisions)
4. Observations stored in `*Observation` tables

**Example**:
```bash
# Import FX rates
python manage.py import_fx_rate_excel --file fx_rates.xlsx --sheet FX_RATES --source-id 2

# Import prices
python manage.py import_instrument_prices_excel --file prices.xlsx --sheet PRICES --source-id 1 --canonicalize
```

**Output**: Raw observations stored in observation tables.

#### 3.2 Canonicalization

**Purpose**: Select best observation from multiple sources/observations to create authoritative canonical record.

**Process**:
1. For each (instrument/currency_pair/curve, date) combination:
   - Gather all observations from active sources
   - Apply source priority (org-specific override if exists, else global)
   - Select best observation: highest priority (lowest number) → highest revision → most recent observed_at
   - Create/update canonical record

**Priority Resolution**:
```
1. Check MarketDataSourcePriority for org/data_type/source
2. If found → use org-specific priority
3. Else → use MarketDataSource.priority (global)
```

**Example**:
```bash
# Canonicalize prices (if not done during import)
python manage.py canonicalize_prices --as-of 2025-01-15

# Canonicalize FX rates
python manage.py canonicalize_fx_rates --base-currency XAF --quote-currency USD --as-of 2025-01-15
```

**Key Feature - Organization-Specific Priorities**:
- When canonicalization runs in org context, org-specific priorities take precedence
- Example:
  - Global: BEAC (priority 2), CUSTODIAN (priority 50)
  - Org 1 override: CUSTODIAN (priority 1) for FX rates
  - Result: Org 1 canonicalization prefers CUSTODIAN over BEAC

**Output**: Canonical records in `FXRate`, `InstrumentPrice`, `YieldCurvePoint`, `MarketIndexValue` tables.

---

### 4. Portfolio Import Pipeline

**Purpose**: Import portfolio position data and validate against reference data.

#### 4.1 Preflight Validation

**Purpose**: Check data readiness before import to catch issues early.

**Process**:
1. Read uploaded file
2. Extract identifiers (instruments, currencies)
3. Validate:
   - Missing instruments (by ISIN/ticker)
   - Missing FX rates (currencies → portfolio base currency)
   - Missing prices (if valuation policy requires)
   - Missing yield curves (if bond pricing needed)

**Example**:
```bash
python manage.py preflight_portfolio_import --portfolio-import-id 123 --org-id 1
```

**Output**: Validation report showing missing items.

**If Missing Instruments**:
```bash
# Export missing instruments
python manage.py export_missing_instruments --portfolio-import-id 123 --output-file missing.csv --org-id 1

# Fill CSV, then import
python manage.py import_instruments_excel --file missing_filled.csv --org-id 1

# Re-run preflight
python manage.py preflight_portfolio_import --portfolio-import-id 123 --org-id 1
```

#### 4.2 Portfolio Import

**Purpose**: Import position data and create immutable PositionSnapshot records.

**Process**:
1. Read Excel/CSV file
2. Detect column mapping (auto-detect or explicit)
3. Validate each row:
   - Required fields present
   - Instrument exists (by ISIN or ticker) - **NO auto-creation**
   - Data formats valid
4. Create PositionSnapshot records (immutable)
5. Track errors in PortfolioImportError records

**Example**:
```bash
python manage.py import_portfolio --portfolio-import-id 123 --org-id 1 --actor-id 5
```

**Key Validation Rules**:
- ✅ Instrument must exist in reference data
- ✅ Missing instruments create `reference_data` errors (NOT auto-created)
- ✅ Immutable snapshots: Never updates existing, creates new ones
- ✅ Idempotency: Hash-based duplicate detection

**Output**: PositionSnapshot records linked to PortfolioImport.

---

### 5. Analytics Pipeline

**Purpose**: Compute portfolio valuation and exposures from position snapshots and canonical market data.

#### 5.1 Daily Close Orchestration

**Purpose**: End-to-end pipeline: Market data → Valuation → Exposures → Reports.

**Process**:
1. **Market Data ETL** (if not already done):
   - Import and canonicalize market data for as_of_date
2. **Portfolio Valuation**:
   - Create ValuationRun
   - Compute valuation for each position
   - Store ValuationPositionResult records
3. **Exposure Computation**:
   - Compute exposures (currency, issuer, country, instrument_group, instrument_type)
   - Store ExposureResult records
4. **Report Generation**:
   - Generate PDF/CSV/Excel reports
   - Store Report records

**Example**:
```bash
python manage.py run_portfolio_daily_close --portfolio-id 1 --as-of 2025-01-15 --org-id 1
```

**Or via Celery Task**:
```python
from apps.etl.tasks import run_portfolio_daily_close_task
run_portfolio_daily_close_task.delay(org_id=1, as_of_iso_date="2025-01-15")
```

#### 5.2 Valuation

**Purpose**: Compute portfolio market values using canonical market data.

**Valuation Policies**:
- `USE_SNAPSHOT_MV`: Trust PositionSnapshot.market_value (MVP default)
- `REVALUE_FROM_MARKETDATA`: Compute from prices + FX (future)

**Process**:
1. Load PositionSnapshot records for portfolio/as_of_date
2. For each position:
   - Apply valuation policy
   - If REVALUE_FROM_MARKETDATA:
     - Look up canonical InstrumentPrice
     - Look up canonical FXRate (if currency != base currency)
     - Compute market_value = quantity * price * fx_rate
   - Store ValuationPositionResult

**Output**: ValuationPositionResult records with computed values.

#### 5.3 Exposure Computation

**Purpose**: Compute exposure breakdowns and concentration metrics.

**Exposure Types**:
- Currency exposure
- Issuer concentration
- Country exposure
- Instrument group/type exposure

**Process**:
1. Load ValuationPositionResult records
2. Group and aggregate by dimension
3. Compute percentages and totals
4. Store ExposureResult records

**Output**: ExposureResult records with aggregated exposure data.

#### 5.4 Report Generation

**Purpose**: Generate board-ready reports from analytics results.

**Formats**: PDF, CSV, Excel

**Process**:
1. Load ValuationRun and ExposureResult records
2. Render report template (HTML for PDF, structured data for CSV/Excel)
3. Store Report record with file references

**Output**: Report records with PDF/CSV/Excel files.

---

## Data Dependencies

### Dependency Graph

```
System Initialization
  ├─→ InstrumentGroup (global)
  ├─→ InstrumentType (global)
  └─→ MarketDataSource (global)

Organization Setup
  ├─→ Depends on: InstrumentGroup, InstrumentType
  ├─→ Creates: Issuer (org-scoped)
  ├─→ Creates: Instrument (org-scoped, depends on Issuer)
  └─→ Creates: MarketDataSourcePriority (org-scoped, optional, depends on MarketDataSource)

Market Data Pipeline
  ├─→ Depends on: MarketDataSource
  ├─→ Creates: *Observation records
  ├─→ Uses: MarketDataSourcePriority (if org context set)
  └─→ Creates: Canonical records (FXRate, InstrumentPrice, etc.)

Portfolio Import
  ├─→ Depends on: Instrument (must exist, org-scoped)
  ├─→ Depends on: InstrumentGroup, InstrumentType (for validation)
  ├─→ Creates: PositionSnapshot (org-scoped)
  └─→ Creates: PortfolioImportError (org-scoped, for missing instruments)

Analytics Pipeline
  ├─→ Depends on: PositionSnapshot (org-scoped)
  ├─→ Depends on: Canonical market data (FXRate, InstrumentPrice, etc.)
  ├─→ Depends on: Instrument (for issuer/country/exposure data)
  ├─→ Creates: ValuationRun (org-scoped)
  ├─→ Creates: ValuationPositionResult (org-scoped)
  ├─→ Creates: ExposureResult (org-scoped)
  └─→ Creates: Report (org-scoped)
```

### Critical Dependencies

**Before Portfolio Import**:
- ✅ Global reference data loaded (InstrumentGroup, InstrumentType)
- ✅ Organization has Issuers
- ✅ Organization has Instruments (matching portfolio holdings)

**Before Analytics/Valuation**:
- ✅ PositionSnapshot records exist
- ✅ Canonical market data available (if valuation policy requires):
  - FX rates (if multi-currency positions)
  - Prices (if REVALUE_FROM_MARKETDATA policy)
  - Yield curves (if bond pricing needed)

---

## Organization Context Flow

### How Organization Context Works

**In Django Views** (Automatic):
- `OrganizationContextMiddleware` sets org context from request
- All organization-scoped queries automatically filtered
- No explicit org_id needed

**In Celery Tasks** (Explicit):
- Must pass `org_id` as parameter
- Use `organization_context()` context manager
- All queries within context are scoped to that org

**In Canonicalization** (Context-Aware):
- Checks for org context (if set)
- Uses org-specific priorities if available
- Falls back to global priorities if no org context or no override

### Example: Organization-Specific Priority Override

**Scenario**: Organization 1 wants to prefer CUSTODIAN over BEAC for FX rates.

**Setup**:
```python
from apps.reference_data.models import MarketDataSource, MarketDataSourcePriority

# Get sources
beac = MarketDataSource.objects.get(code="BEAC")  # Global priority: 2
custodian = MarketDataSource.objects.get(code="CUSTODIAN")  # Global priority: 50

# Create org-specific override
with organization_context(org_id=1):
    MarketDataSourcePriority.objects.create(
        organization_id=1,
        data_type=MarketDataSourcePriority.DataType.FX_RATE,
        source=custodian,
        priority=1  # Higher priority than BEAC for org 1
    )
```

**Result**:
- Global canonicalization: Uses BEAC (priority 2 < 50)
- Org 1 canonicalization: Uses CUSTODIAN (priority 1 < 2)
- Org 2 canonicalization: Uses BEAC (no override, uses global priority 2)

---

## Workflow Examples

### Example 1: First-Time Portfolio Import

**Scenario**: New organization setting up first portfolio.

**Steps**:

1. **System Initialization** (one-time, admin):
   ```bash
   python manage.py load_reference_data
   python manage.py sync_market_data_sources
   ```

2. **Organization Setup**:
   ```bash
   # Create organization (via admin)
   # Load issuers
   python manage.py import_issuers_excel --file issuers.xlsx --org-id 1
   
   # Load instruments
   python manage.py import_instruments_excel --file instruments.xlsx --org-id 1
   ```

3. **Preflight Check**:
   ```bash
   # Create PortfolioImport record (via UI or admin)
   # Run preflight
   python manage.py preflight_portfolio_import --portfolio-import-id 123 --org-id 1
   # Output: Missing 5 instruments
   ```

4. **Fix Missing Instruments**:
   ```bash
   # Export missing
   python manage.py export_missing_instruments --portfolio-import-id 123 --output-file missing.csv --org-id 1
   
   # Fill CSV with instrument details
   # Import instruments
   python manage.py import_instruments_excel --file missing_filled.csv --org-id 1
   
   # Re-run preflight (should pass now)
   python manage.py preflight_portfolio_import --portfolio-import-id 123 --org-id 1
   ```

5. **Import Portfolio**:
   ```bash
   python manage.py import_portfolio --portfolio-import-id 123 --org-id 1 --actor-id 5
   # Creates PositionSnapshot records
   ```

6. **Run Analytics**:
   ```bash
   python manage.py run_portfolio_daily_close --portfolio-id 1 --as-of 2025-01-15 --org-id 1
   # Creates ValuationRun, ExposureResult, Report
   ```

### Example 2: Daily Market Data Refresh

**Scenario**: Daily update of market data and portfolio analytics.

**Steps**:

1. **Import Market Data Observations**:
   ```bash
   # FX rates from BEAC
   python manage.py import_fx_rate_excel --file beac_fx_20250115.xlsx --source-id 2
   
   # Prices from BVMAC
   python manage.py import_instrument_prices_excel --file bvmac_prices_20250115.xlsx --source-id 1
   ```

2. **Canonicalize** (if not done during import):
   ```bash
   # Canonicalize FX rates
   python manage.py canonicalize_fx_rates --as-of 2025-01-15
   
   # Canonicalize prices
   python manage.py canonicalize_prices --as-of 2025-01-15
   ```

3. **Run Daily Close** (orchestrates everything):
   ```bash
   python manage.py run_portfolio_daily_close --portfolio-id 1 --as-of 2025-01-15 --org-id 1
   ```

**Note**: `run_portfolio_daily_close` can include market data ETL steps, or they can be run separately.

### Example 3: Organization-Specific Source Priority

**Scenario**: Organization wants to use their custodian's FX rates instead of BEAC.

**Steps**:

1. **Create Priority Override** (via admin or programmatically):
   ```python
   from apps.reference_data.models import MarketDataSource, MarketDataSourcePriority
   from libs.tenant_context import organization_context
   
   custodian = MarketDataSource.objects.get(code="CUSTODIAN")
   
   with organization_context(org_id=1):
       MarketDataSourcePriority.objects.create(
           organization_id=1,
           data_type=MarketDataSourcePriority.DataType.FX_RATE,
           source=custodian,
           priority=1  # Higher than BEAC's global priority of 2
       )
   ```

2. **Canonicalize with Org Context**:
   ```python
   from apps.reference_data.services.fx_rates.canonicalize import canonicalize_fx_rates
   from libs.tenant_context import organization_context
   
   with organization_context(org_id=1):
       result = canonicalize_fx_rates(as_of_date=date(2025, 1, 15))
   # Uses CUSTODIAN (priority 1) instead of BEAC (priority 2) for org 1
   ```

**Result**: Organization 1's canonical FX rates prefer CUSTODIAN, while other orgs use BEAC (global default).

---

## Data Quality & Error Handling

### Error Tracking

**Portfolio Import Errors**:
- Stored in `PortfolioImportError` records
- Row-level error tracking
- Error types: validation, mapping, reference_data, format, business_rule, system
- Can export missing instruments from errors

**Market Data Import Errors**:
- Tracked in `*Import` model status fields
- Error messages stored in import records

### Data Validation

**Preflight Validation**:
- Runs before import
- Checks missing instruments, FX rates, prices, curves
- Provides actionable feedback

**Import Validation**:
- Format validation (data types, required fields)
- Business rule validation (positive quantities, valid dates)
- Reference data validation (instruments exist)
- No auto-creation: Missing data creates errors, not records

---

## Performance Considerations

### Bulk Operations

- Portfolio import uses `bulk_create` for PositionSnapshot records
- Canonicalization processes observations in batches
- Exposure computation aggregates from ValuationPositionResult records

### Caching

- Canonical records serve as "cache" of best observations
- Avoids re-computing priority selection on every query
- Organization-specific priorities resolved during canonicalization

### Database Indexes

- All foreign keys indexed
- Organization scoping indexes on org-scoped models
- Date indexes on time-series data (snapshots, market data)
- Source priority indexes for canonicalization queries

---

## Future Enhancements

### Planned

- Real-time market data feeds (API integrations)
- Automated daily close scheduling (Celery Beat)
- Look-through fund analysis (fund constituent breakdown)
- Duration/DV01 calculations for fixed income

### Architecture Scalability

- Current: Single database, organization-scoped
- Future: Can scale to schema-per-tenant or separate databases if needed
- Analytics engine designed for potential microservice extraction

---

## Summary

The data pipeline architecture follows these principles:

1. **Separation of Concerns**: Observation → Canonical → Analytics layers
2. **Organization Isolation**: Org-scoped data with automatic filtering
3. **Flexible Prioritization**: Global defaults with org-specific overrides
4. **Immutable Snapshots**: Time-series data never updated, only appended
5. **Operator-Friendly**: Preflight checks, error exports, clear dependencies
6. **Auditable**: Full provenance tracking, immutable audit logs

This design supports institutional requirements for data governance, auditability, and operational control while maintaining flexibility for organization-specific configurations.

