# Hedgemind

**Regional Portfolio & Risk Intelligence Platform (Institutional-first)**

A decision intelligence platform designed for institutional users to understand, analyze, and defend their portfolio risk positions. Built with Django and Python.

## Overview

Hedgemind is a **decision intelligence platform** for institutional users—asset managers, bank treasury/ALM desks, and pension & insurance investment teams. It helps organizations understand where risk sits, what can realistically break, how exposed they are, and whether their decisions are defensible to boards, regulators, and auditors.

### Core Value Proposition

- **Where risk really sits**: Concentration, liquidity, sovereign, FX exposure (not textbook volatility)
- **What can realistically break**: Fragility under stress, irreversible losses, structural weaknesses
- **How exposed they are**: Issuer, country, instrument, currency exposure
- **Defensibility**: Board-ready, regulator-ready, auditor-ready outputs

## Project Status

**Current Phase**: Exposure Engine & Report Generation (Active Development)

The project has a solid foundation with multi-tenant architecture, comprehensive reference data models, portfolio management infrastructure, valuation engine, exposure computation, and report generation. The platform now supports end-to-end portfolio analytics: valuation → exposure computation → report generation with PDF, CSV, and Excel outputs.

### ✅ Implemented

#### Core Infrastructure
- **Multi-tenant architecture**: Organization-based data isolation
- **Organization context middleware**: Automatic organization scoping for requests
- **Organization-owned model mixin**: Automatic data isolation at the model level
- **Thread-local organization context**: Context management for services and tasks
- **Celery integration**: Async task processing foundation
- **Django settings**: Environment-based configuration (dev, prod, test)
- **PostgreSQL integration**: Database setup and connection pooling
- **S3-compatible storage**: File storage configuration (via django-storages)

#### Django Apps - Implemented Features

- `apps/organizations` - Multi-tenant organization management ✅
  - Organization model with base currency support
  - OrganizationMember with role-based access (ADMIN, ANALYST, VIEWER)
  - Organization switching API endpoints
  - Organization context middleware

- `apps/reference_data` - Reference data management ✅
  - **Models**: Comprehensive reference data models organized by domain
    - `Instrument`, `InstrumentType`, `InstrumentGroup` (organization-scoped)
    - `Issuer`, `IssuerRating` (organization-scoped issuers)
    - `InstrumentPrice`, `InstrumentPriceObservation`, `InstrumentPriceImport`
    - `FXRate`, `FXRateObservation`, `FXRateImport`
    - `YieldCurve`, `YieldCurvePoint`, `YieldCurvePointObservation`, `YieldCurveImport`
    - `MarketIndex`, `MarketIndexValue`, `MarketIndexValueObservation`, `MarketIndexConstituent`, `MarketIndexImport`
    - `MarketDataSource`
  - **Management Commands**: Excel import commands for all reference data types
    - `import_instruments_excel` - Import instrument master data
    - `import_issuers_excel` - Import issuer data
    - `import_instrument_prices_excel` - Import price observations
    - `import_fx_rate_excel` - Import FX rates
    - `import_yield_curve_excel` - Import yield curve data
    - `import_index_levels_excel` - Import index level values
    - `import_index_constituents_excel` - Import index constituent data
    - `canonicalize_prices` - Canonicalize price observations
    - `load_instrument_types` - Load instrument type reference data
    - `load_instrument_groups` - Load instrument group reference data
    - `load_reference_data` - Load all reference data
  - **Services**: Import and canonicalization services for each data type
  - **Testing**: Comprehensive test coverage (327+ test functions)

- `apps/portfolios` - Portfolio management ✅
  - **Models**:
    - `PortfolioGroup` - Simple one-level grouping for portfolios
    - `Portfolio` - Investment portfolio container with base currency
    - `PortfolioImport` - Tracks file uploads and import status with row-level error tracking
    - `PortfolioImportError` - Row-level error tracking for import failures
    - `PositionSnapshot` - Time-series snapshots of positions (immutable, provenance-tracked)
  - **Ingestion** (`apps/portfolios/ingestion/`):
    - `import_excel.py` - Excel/CSV import service with comprehensive validation
    - `mapping.py` - Column mapping service with auto-detection
    - `validation.py` - Business rule and format validation
    - `utils.py` - Utility functions for instrument resolution and duplicate detection
    - **Features**:
      - Excel and CSV file support
      - Automatic column mapping with common abbreviation recognition
      - Immutable snapshots (never updates existing, creates new ones)
      - Row-level error tracking with detailed error messages
      - Idempotency checks (hash-based duplicate detection)
      - Provenance tracking (links snapshots to imports)
      - Flexible mapping (price OR market_value, validation ensures one exists)
      - Bulk operations for performance
  - All models are organization-scoped using `OrganizationOwnedModel`
  - **Testing**: Model tests implemented

- `apps/etl` - ETL pipelines and orchestration ✅
  - **Daily Close Orchestration**:
    - `run_portfolio_daily_close()` - Full orchestration: valuation → exposure → report
    - `run_daily_close()` - Market data ETL orchestration
    - Management command: `run_portfolio_daily_close` for triggering daily close
  - **Celery Tasks** (`apps/etl/tasks.py`):
    - `run_daily_close_task()` - Async task for daily close orchestration (requires org_id parameter)
    - `ping_etl()` - Health check task for ETL system
  - Market data FX daily pipeline (placeholder)
  - Prices daily pipeline (placeholder)

- `apps/audit` - Audit logging ✅
  - AuditEvent model implemented
  - Immutable audit log structure

- `apps/accounts` - User account management 🚧 (scaffolded)
- `apps/analytics` - Analytics engine ✅
  - **Models**:
    - `ValuationRun` - Portfolio valuation runs with policy support
    - `ValuationPositionResult` - Computed valuation results per position
    - `ExposureResult` - Stored exposure computation results (currency, issuer, country, instrument_group, instrument_type)
  - **Key Features**:
    - Valuation policy system (USE_SNAPSHOT_MV, REVALUE_FROM_MARKETDATA)
    - Official run designation with automatic unmarking
    - `inputs_hash` for data fingerprinting and idempotency
    - `run_context_id` for execution context tracking (batch operations, audit trail)
    - Stored aggregates (industry standard): total_market_value, position_count, data quality counts
    - Exposure computation and storage (stored aggregates pattern for fast queries)
    - Status tracking (PENDING → RUNNING → SUCCESS/FAILED)
    - Execution logging
  - **Engine** (`apps/analytics/engine/`):
    - `valuation.py` - Pure Python valuation computation functions
      - `compute_valuation_policy_a()` - Policy A valuation logic
    - `aggregation.py` - Pure Python aggregation and summary functions
      - `recalculate_total_market_value()` - Recalculate total from results
      - `compute_data_quality_summary()` - Aggregate data quality metrics
      - `compute_aggregates_from_results()` - Compute aggregates during execution
    - `exposures.py` - Pure Python exposure computation functions
      - `compute_exposures()` - Main entry point for all exposure types
      - `compute_currency_exposures()` - Currency exposure breakdown
      - `compute_issuer_exposures()` - Issuer concentration analysis
      - `compute_country_exposures()` - Country exposure breakdown
      - `compute_instrument_group_exposures()` - Instrument group exposure
      - `compute_instrument_type_exposures()` - Instrument type exposure
      - `compute_top_concentrations()` - Top N concentration analysis
    - **Architecture**: Separation of concerns - computation logic separate from data models
      - Models store data and provide simple getters
      - Engine functions perform all computation (pure functions, testable without Django)
      - Follows data engineering best practices (industry standard)
  - **Testing**: Comprehensive test coverage (800+ lines)
- `apps/reports` - Report generation ✅
  - **Models**:
    - `ReportTemplate` - Report template definitions (portfolio overview v1)
    - `Report` - Generated report instances with PDF, CSV, Excel outputs
  - **Renderers** (`apps/reports/renderers/`):
    - `portfolio_report.py` - Report generation functions
      - `generate_portfolio_report()` - Main entry point for report generation
      - `render_pdf_report()` - PDF generation using WeasyPrint
      - `render_csv_report()` - CSV export with exposure tables
      - `render_excel_report()` - Excel export with multiple sheets
  - **Templates** (`apps/reports/templates/`):
    - `portfolio_overview_v1.html` - HTML template for PDF reports
  - **Features**:
    - Multi-format output (PDF, CSV, Excel)
    - Portfolio overview with exposures, concentration, data quality
    - Board-ready PDF reports

#### Libraries (`libs/`)
- `libs/models.py` - `OrganizationOwnedModel` mixin for automatic organization scoping
- `libs/tenant_context.py` - Thread-local organization context management
- `libs/organization_query.py` - Organization query helpers
- `libs/storage.py` - Storage utilities
- `libs/logging.py` - Logging configuration
- `libs/choices.py` - Common choice enums (ImportStatus, ImportSourceType, etc.)

#### Testing Infrastructure
- **pytest-django**: Test framework setup
- **pytest-cov**: Code coverage reporting with HTML reports
- **Factory Boy**: Test data factories in `tests/factories.py`
- **Test organization**: Centralized test suite in `tests/` directory
  - 327+ test functions across 23 test files
  - Comprehensive coverage of reference data models and services
  - Organization isolation tests
  - Integration tests for multi-tenancy
  - ETL pipeline tests

### 🚧 In Progress / Planned

- **Stress Scenarios**: Deterministic stress scenario engine
- **Portfolio Ingestion Management Command**: CLI command for triggering imports (service is implemented)
- **Portfolio Ingestion UI**: Web interface for uploading and managing imports (backend service ready)
- **Admin Interfaces**: Django admin configuration for all models
- **Reference Data UI**: Web interfaces for managing reference data
- **ETL Pipeline Implementation**: Complete market data daily pipelines (FX, prices)
- **Duration/Rate Sensitivity**: Fixed income analytics (duration, DV01)

## Architecture

### Technical Stack

- **Framework**: Django 5.2
- **Language**: Python 3.11+
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis
- **Storage**: S3-compatible object storage (django-storages, boto3)
- **Currency**: django-money (multi-currency support)
- **Countries**: django-countries

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Web App (Django)                       │
│  - Auth, orgs, permissions                               │
│  - Uploads, portfolio views, reports listing            │
│  - Admin + configuration                                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│            Analytics Engine (Python Module)              │
│  - Pure-Python functions/classes                        │
│  - Valuation computation (valuation.py)                │
│  - Aggregation functions (aggregation.py)               │
│  - Exposure computation (exposures.py)                  │
│  - Normalized holdings + market data → exposures        │
│  - Produces report schema (JSON)                        │
│  - Separation of concerns: computation separate from    │
│    data models (data engineering best practice)        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Async Jobs (Celery)                         │
│  - File parsing, valuation, scenarios, PDF generation   │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ PostgreSQL   │  │  Redis       │  │  S3 Storage  │
│ (Source of   │  │  (Cache +    │  │  (Files +    │
│  Truth)      │  │   Queue)     │  │   PDFs)      │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Multi-Tenancy

The platform uses a **single-database, organization-scoped** multi-tenancy model:

- All organization-owned models inherit from `OrganizationOwnedModel`
- Automatic filtering by organization context in all queries
- Organization context set via middleware (requests) or explicit parameter (Celery tasks)
- Row-level security enforced at the ORM level

See `libs/README_ORGANIZATION_OWNED_MODEL.md` for detailed usage guide.

### Data Flow

**Reference Data Import** (Implemented):
1. **Import**: Admin uses management commands to import Excel files → creates observations/import records
2. **Canonicalize**: Run canonicalization to create canonical price/rate/curve records
3. **Storage**: Data stored in PostgreSQL with organization scoping where applicable

**Portfolio & Analytics Flow** (Implemented):
1. **Upload & Import** (implemented): 
   - Create `PortfolioImport` record with uploaded CSV/XLSX file
   - Call `import_portfolio_from_file()` service function
   - Service validates, maps columns, creates `PositionSnapshot` records
   - Row-level errors tracked in `PortfolioImportError` records
   - Status tracking: PENDING → PARSING → VALIDATING → SUCCESS/FAILED/PARTIAL
2. **Analytics Run** (implemented): 
   - Create `ValuationRun` → execute valuation → compute and store exposures
   - `run_portfolio_daily_close()` orchestrates: valuation → exposure → report
3. **Report** (implemented): Render PDF/CSV/Excel from computed results → persist `Report` record
4. **UI**: User views portfolio → downloads PDF/CSV/Excel (backend ready, UI to be implemented)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 12+
- Redis (for Celery)
- Poetry (for dependency management)

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd hedgemind
```

2. **Install dependencies**

```bash
poetry install
```

Or if not using Poetry:

```bash
pip install -r requirements.txt  # If you generate one
```

3. **Set up environment variables**

Create a `.env` file in the project root:

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=hedgeminddb_dev
POSTGRES_USER=hedgemind_user
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=60

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Storage (S3-compatible)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=hedgemind-storage
AWS_S3_ENDPOINT_URL=  # Optional, for S3-compatible services
```

4. **Set up the database**

```bash
# Create database (if not exists)
createdb hedgeminddb_dev

# Run migrations
python manage.py migrate
```

5. **Create a superuser**

```bash
python manage.py createsuperuser
```

6. **Run the development server**

```bash
python manage.py runserver
```

7. **Start Celery worker** (in a separate terminal)

```bash
celery -A config worker -l info
```

### Management Commands

The platform includes several management commands for importing and managing reference data:

```bash
# Import reference data
python manage.py import_instruments_excel --file path/to/file.xlsx --sheet Sheet1 --org-id 1
python manage.py import_issuers_excel --file path/to/file.xlsx --sheet Sheet1 --org-id 1
python manage.py import_instrument_prices_excel --file path/to/file.xlsx --sheet Sheet1
python manage.py import_fx_rate_excel --file path/to/file.xlsx --sheet Sheet1
python manage.py import_yield_curve_excel --file path/to/file.xlsx --sheet Sheet1
python manage.py import_index_levels_excel --file path/to/file.xlsx --sheet Sheet1
python manage.py import_index_constituents_excel --file path/to/file.xlsx --sheet Sheet1

# Load initial reference data (instrument types, groups)
python manage.py load_instrument_types
python manage.py load_instrument_groups
python manage.py load_reference_data  # Loads all initial reference data

# Canonicalize price observations
python manage.py canonicalize_prices --as-of 2024-01-01

# Run portfolio daily close (valuation → exposure → report)
python manage.py run_portfolio_daily_close --portfolio-id 1 --as-of 2025-01-15 --org-id 1
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov=libs --cov-report=html

# Run specific test file
pytest tests/organizations/test_models.py
```

## Project Structure

```
hedgemind/
├── apps/                    # Django applications
│   ├── accounts/           # User accounts management (scaffolded)
│   ├── analytics/          # Analytics and metrics ✅
│   │   ├── engine/         # Analytics engine (pure Python)
│   │   │   ├── valuation.py    # Valuation computation
│   │   │   ├── aggregation.py # Aggregation functions
│   │   │   └── exposures.py    # Exposure computation
│   ├── audit/              # Audit logging ✅
│   ├── etl/                # ETL pipelines and orchestration ✅
│   │   ├── orchestration/  # Daily close orchestration
│   │   │   └── daily_close.py  # Portfolio daily close orchestration
│   │   ├── management/     # Management commands
│   │   │   └── commands/   # ETL management commands
│   │   └── pipelines/      # Individual ETL pipelines
│   ├── organizations/      # Multi-tenant organization management ✅
│   ├── portfolios/         # Portfolio management ✅
│   │   └── ingestion/      # Portfolio ingestion logic ✅
│   │       ├── import_excel.py  # Excel/CSV import service
│   │       ├── mapping.py       # Column mapping service
│   │       ├── validation.py    # Validation logic
│   │       └── utils.py         # Utility functions
│   ├── reference_data/     # Reference data (securities, market data) ✅
│   │   ├── models/         # Model definitions by domain
│   │   ├── management/     # Management commands for data import
│   │   │   └── commands/   # Excel import commands
│   │   ├── providers/      # Market data providers
│   │   └── services/       # Reference data services (import, canonicalize)
│   └── reports/            # Report generation ✅
│       ├── renderers/      # Report renderers (PDF, CSV, Excel)
│       │   └── portfolio_report.py  # Portfolio report generation
│       └── templates/      # Report templates (HTML)
│           └── reports/    # Report template files
├── config/                 # Django project configuration
│   ├── settings/           # Environment-specific settings
│   │   ├── base.py         # Base settings
│   │   ├── dev.py          # Development overrides
│   │   ├── prod.py         # Production overrides
│   │   └── test.py         # Test-specific settings
│   ├── celery.py           # Celery configuration
│   └── urls.py             # Root URL configuration
├── libs/                   # Reusable libraries and utilities
│   ├── models.py           # Base model mixins (OrganizationOwnedModel)
│   ├── tenant_context.py   # Organization context management
│   ├── organization_query.py  # Organization query helpers
│   ├── storage.py          # Storage utilities
│   └── logging.py          # Logging configuration
├── tests/                  # Centralized test suite
│   ├── conftest.py         # Shared pytest fixtures
│   ├── factories.py        # Factory Boy factories
│   └── [app_name]/         # App-specific tests
├── scripts/                # Utility scripts
├── bugs/                   # Bug tracking documentation
├── .cursor/rules/          # Development rules and project definition
├── manage.py               # Django management script
└── pyproject.toml          # Python project configuration
```

## Key Concepts

### Analytics Engine Architecture

The analytics engine follows **data engineering best practices** by separating computation logic from data storage:

**Design Principles**:
- **Models** (`apps/analytics/models.py`): Store data, provide simple getters for stored fields
- **Engine** (`apps/analytics/engine/`): Pure Python functions for all computation
  - `valuation.py`: Valuation computation logic
  - `aggregation.py`: Aggregation and summary functions
  - `exposures.py`: Exposure computation logic (currency, issuer, country, instrument_group, instrument_type, concentration)

**Benefits**:
- **Testability**: Engine functions are pure and testable without Django dependencies
- **Reusability**: Functions can be used in different contexts (views, tasks, scripts)
- **Maintainability**: Clear separation makes code easier to understand and modify
- **Industry Standard**: Aligns with how Aladdin, Bloomberg, and other platforms structure analytics
- **Future-Proof**: Engine can be extracted to microservice if needed without rewriting logic

**Example**:
```python
# Model: Simple getter for stored aggregate
run.get_total_market_value()  # Returns stored field (fast)

# Engine: Pure function for computation
from apps.analytics.engine.aggregation import recalculate_total_market_value
recalculated = recalculate_total_market_value(run)  # Recomputes from results
```

**Stored Aggregates** (Industry Standard):
- `total_market_value`: Total portfolio value (stored for performance)
- `position_count`: Number of positions (stored aggregate)
- `positions_with_issues`: Data quality issue count (stored aggregate)
- `missing_fx_count`: Missing FX rate count (stored aggregate)
- `ExposureResult`: Stored exposure breakdowns (currency, issuer, country, instrument_group, instrument_type) with values and percentages

These aggregates are computed during `execute()` and stored for fast queries, following the same pattern used by institutional platforms. Exposure results are persisted as `ExposureResult` records, enabling fast report generation and historical exposure analysis.

### Critical Fields for Pitch Book & Understanding

This section highlights the most important fields and concepts in Hedgemind that demonstrate the platform's institutional-grade design, auditability, and operational excellence.

#### `inputs_hash` and `run_context_id` (ValuationRun)

These two fields work together to provide both **data integrity** and **execution traceability**, following industry best practices similar to Aladdin's `run_group` concept.

**`inputs_hash`** - Data Fingerprint
- **Purpose**: Deterministic hash of position snapshots + market data + valuation policy
- **Answers**: "Did the data change?"
- **Use Cases**:
  - **Idempotency**: Prevents duplicate computation when inputs are identical
  - **Reproducibility**: Ensures same inputs produce same results
  - **Change Detection**: Quickly identify when underlying data has changed
- **Computation**: SHA256 hash of sorted position snapshot IDs + as_of_date + valuation_policy
- **Uniqueness**: Database constraint prevents duplicate runs with same inputs (when hash is set)

**`run_context_id`** - Execution Context
- **Purpose**: Identifier for execution context and configuration
- **Answers**: "Under what configuration and intent was this executed?"
- **Use Cases**:
  - **Batch Operations**: Group multiple portfolio runs executed together with same settings
  - **Audit Trail**: Track what configuration/parameters were used for each run
  - **Reproducibility**: "Re-run with same config as run_context_id X"
  - **Single & Batch**: Works for both single-portfolio and batch portfolio runs
- **Format**: Flexible (UUIDs, custom identifiers like "batch-2025-01-15-001", "daily-close-2025-01-15")
- **Querying**: Use `ValuationRun.objects.with_run_context(run_context_id)` to find all runs in a batch

**Key Distinction**:
- `inputs_hash` = **What data** was used (data fingerprint)
- `run_context_id` = **How it was run** (execution context)
- These fields are **orthogonal** - same data can be run with different contexts, different data can share same context

**Example Scenarios**:
```python
# Scenario 1: Same data, different configs
run1 = ValuationRun.objects.create(..., inputs_hash="abc123", run_context_id="config-v1")
run2 = ValuationRun.objects.create(..., inputs_hash="abc123", run_context_id="config-v2")
# Same inputs, different execution contexts

# Scenario 2: Batch run with same config
run1 = ValuationRun.objects.create(..., inputs_hash="abc123", run_context_id="batch-001")
run2 = ValuationRun.objects.create(..., inputs_hash="def456", run_context_id="batch-001")
# Different inputs, same execution context (batch operation)

# Scenario 3: Query all runs in a batch
batch_runs = ValuationRun.objects.with_run_context("batch-001")
# Returns all runs executed together in batch-001
```

#### `is_official` (ValuationRun)

**Purpose**: Marks the authoritative valuation run for a portfolio/date combination.

**Key Features**:
- **Single Official Run**: Only one run can be marked as official per portfolio/date
- **Automatic Unmarking**: Marking a new run as official automatically unmarks the previous one
- **Status Requirement**: Only SUCCESS runs can be marked as official
- **Audit Trail**: All official marking/unmarking actions are logged in AuditEvent
- **Use Case**: Ensures clear governance - "This is the valuation we're using for reporting/decision-making"

**Example**:
```python
# Mark a successful run as official
run.mark_as_official(reason="Approved by portfolio manager", actor=user)
# Previous official run for same portfolio/date is automatically unmarked
# Audit event is created with full context
```

#### `valuation_policy` (ValuationRun)

**Purpose**: Defines the methodology used for portfolio valuation.

**Available Policies**:
- `USE_SNAPSHOT_MV`: Trust PositionSnapshot.market_value (MVP default, handles messy local data)
- `REVALUE_FROM_MARKETDATA`: Compute from prices + FX (future, for clean market data)

**Why It Matters**: Different institutions have different data quality. This policy allows the platform to handle both:
- **Messy local data**: Use custodian-provided market values directly
- **Clean market data**: Recompute from prices and FX rates

#### `as_of_date` (ValuationRun, PositionSnapshot, PortfolioImport)

**Purpose**: Time-series point-in-time snapshot identifier.

**Critical for**:
- **Historical Analysis**: Track portfolio changes over time
- **Regulatory Reporting**: "As of December 31, 2024" valuations
- **Audit Trail**: "What was the portfolio on this date?"
- **Reproducibility**: Re-run analytics for any historical date

**Design Pattern**: All time-series data uses `as_of_date` to create immutable snapshots. Never edit existing snapshots - create new ones for new dates.

#### `valuation_method` and `valuation_source` (PositionSnapshot)

**Purpose**: Explicit valuation provenance tracking for defensibility.

**Valuation Methods** (from reference_data.ValuationMethod):
- `MARK_TO_MARKET`: Public market prices
- `MARK_TO_MODEL`: Model-based valuation
- `EXTERNAL_APPRAISAL`: Third-party valuation
- `MANUAL_DECLARED`: Manual entry

**Valuation Sources**:
- `CUSTODIAN`: Custodian-provided values
- `MARKET`: Market data provider
- `INTERNAL`: Internal valuation team
- `EXTERNAL`: External valuation firm
- `MANUAL`: Manual entry

**Why Critical**: Institutional users must defend valuations to boards, regulators, and auditors. These fields provide explicit provenance: "This position was valued using [method] from [source] on [date]."

#### `status` Fields (ValuationRun, PortfolioImport)

**Purpose**: Track execution state through lifecycle.

**ValuationRun Status Flow**:
- `PENDING` → `RUNNING` → `SUCCESS` / `FAILED`

**PortfolioImport Status Flow**:
- `PENDING` → `PARSING` → `SUCCESS` / `FAILED` / `PARTIAL`

**Why Important**: 
- **User Experience**: Clear feedback on operation progress
- **Error Handling**: Failed operations can be retried
- **Monitoring**: Track system health and success rates
- **Audit**: Historical record of what succeeded/failed

#### Organization Scoping (All Business Data)

**Purpose**: Multi-tenant data isolation at the database level.

**Implementation**: All business data models inherit from `OrganizationOwnedModel`, which:
- Automatically adds `organization` ForeignKey
- Filters all queries by current organization context
- Prevents accidental cross-organization data access
- Auto-sets organization_id from thread-local context

**Why Critical for Institutions**:
- **Data Security**: Complete isolation between clients
- **Compliance**: Ensures data cannot leak across organizations
- **Scalability**: Single database, organization-scoped (can scale to schema-per-tenant later)

#### Audit Trail (AuditEvent)

**Purpose**: Immutable append-only log of all significant operations.

**Tracks**:
- **Who**: User (actor) who performed the action
- **What**: Action type (CREATE, UPDATE, DELETE, MARK_VALUATION_OFFICIAL, etc.)
- **What Object**: Object type and ID affected
- **When**: Timestamp of the action
- **Context**: Additional metadata as JSON

**Why Critical**:
- **Regulatory Compliance**: Required for institutional trust
- **Forensics**: "Who changed what and when?"
- **Governance**: Track official valuation approvals, data imports, etc.
- **Non-Repudiation**: Immutable log cannot be altered

**Example**:
```python
# Marking valuation as official creates audit event
run.mark_as_official(reason="Board approval", actor=user)
# Creates AuditEvent with:
# - action: "MARK_VALUATION_OFFICIAL"
# - object_type: "ValuationRun"
# - metadata: {reason, portfolio_id, as_of_date, previous_official_run_id, ...}
```

### Organization Context

The platform uses thread-local organization context to scope all operations. In Django views, this is set automatically by `OrganizationContextMiddleware`. In Celery tasks, you must pass `org_id` explicitly and use the `organization_context()` context manager.

```python
# In views (automatic via middleware)
portfolio = Portfolio.objects.create(name="My Portfolio")  # Uses current org

# In Celery tasks (explicit)
from libs.tenant_context import organization_context

@shared_task(bind=True)
def process_portfolio(self, org_id: int):
    with organization_context(org_id):
        portfolio = Portfolio.objects.create(name="My Portfolio")
```

### Organization-Owned Models

Models that belong to an organization should inherit from `OrganizationOwnedModel`:

```python
from libs.models import OrganizationOwnedModel

class Portfolio(OrganizationOwnedModel):
    name = models.CharField(max_length=255)
    # organization field is automatically added
```

This ensures:
- All queries are automatically filtered by current organization
- `organization_id` is auto-set from context on save
- Data cannot leak across organizations

### Reference Data Models

The platform includes comprehensive reference data models organized by domain:

**Instruments** (Organization-scoped):
- `Instrument` - Securities master data (bonds, equities, funds, deposits, private assets)
- `InstrumentType` - Instrument classification types
- `InstrumentGroup` - Instrument grouping/categorization

**Issuers** (Organization-scoped):
- `Issuer` - Issuer master data
- `IssuerRating` - Credit ratings for issuers

**Market Data**:
- `MarketDataSource` - Source tracking for market data
- `InstrumentPrice` / `InstrumentPriceObservation` - Security prices (with import tracking)
- `FXRate` / `FXRateObservation` - Foreign exchange rates (with import tracking)
- `YieldCurve` / `YieldCurvePoint` / `YieldCurvePointObservation` - Yield curve data (with import tracking)
- `MarketIndex` / `MarketIndexValue` / `MarketIndexValueObservation` - Market index levels (with import tracking)
- `MarketIndexConstituent` - Index constituent tracking

**Import Tracking**:
All market data types support import tracking with `*Import` models that track:
- Source files
- Import timestamps
- Data quality metrics
- Selection reasons (for rate/price selection)

**Canonicalization**:
Market data follows an observation → canonical pattern:
- Raw observations are imported and stored
- Canonicalization process creates consolidated records for a given date
- Supports multiple data sources with selection logic

### Portfolio Models

The platform includes comprehensive portfolio management models:

**Portfolio Structure**:
- `PortfolioGroup` - Simple one-level grouping for portfolios
- `Portfolio` - Investment portfolio container with base currency and mandate type

**Portfolio Import & Tracking**:
- `PortfolioImport` - Tracks file uploads and import status
  - Status flow: `PENDING` → `PARSING` → `VALIDATING` → `SUCCESS` / `FAILED` / `PARTIAL`
  - Stores mapping configuration, row counts, error summaries
  - Idempotency via `inputs_hash` (prevents duplicate imports)
- `PortfolioImportError` - Row-level error tracking
  - Stores individual row errors with error type, message, and raw row data
  - Error types: validation, mapping, reference_data, format, business_rule, system
  - Enables detailed error reporting and debugging

**Position Snapshots**:
- `PositionSnapshot` - Immutable time-series snapshots of positions
  - **Immutability**: Snapshots are never edited - new snapshots created for new dates
  - **Provenance Tracking**: Links to PortfolioImport, valuation_method, valuation_source
  - **Unique Constraint**: One snapshot per (portfolio, instrument, as_of_date)
  - **Fields**: quantity, book_value, market_value, price, accrued_interest
  - **Valuation Metadata**: valuation_method, valuation_source, last_valuation_date

**Portfolio Ingestion Workflow**:
1. Create `PortfolioImport` record with uploaded file (CSV/Excel)
2. Call `import_portfolio_from_file(portfolio_import_id)` service function
3. Service auto-detects column mapping or uses explicit mapping
4. Each row is validated and instrument is resolved (by ISIN or ticker)
5. Valid rows create `PositionSnapshot` records (bulk insert for performance)
6. Invalid rows create `PortfolioImportError` records with detailed error info
7. `PortfolioImport` status updated based on results (SUCCESS/FAILED/PARTIAL)
8. Duplicate snapshots are prevented (immutability enforced)

**Example Usage**:
```python
from apps.portfolios.models import Portfolio, PortfolioImport
from apps.portfolios.ingestion.import_excel import import_portfolio_from_file
from libs.tenant_context import organization_context

# Within organization context
with organization_context(org_id=1):
    portfolio = Portfolio.objects.get(name="My Portfolio")
    
    # Create import record (typically done via file upload in UI)
    portfolio_import = PortfolioImport.objects.create(
        portfolio=portfolio,
        file=uploaded_file,  # FileField
        as_of_date=date.today(),
        source_type=ImportSourceType.CUSTODIAN,
    )
    
    # Run import
    result = import_portfolio_from_file(portfolio_import.id)
    # Returns: {'created': 100, 'errors': 5, 'total_rows': 105, 'status': 'PARTIAL'}
    
    # Check errors
    errors = portfolio_import.errors.all()
    for error in errors:
        print(f"Row {error.row_number}: {error.error_message}")
```

## Development Guidelines

See `.cursor/rules/development.mdc` for comprehensive development rules covering:
- Code documentation requirements
- Model design patterns
- Testing guidelines
- Code quality standards
- Multi-tenancy best practices

See `.cursor/rules/project_definition.mdc` for:
- Product vision and scope
- Technical architecture decisions
- What the platform is and is not
- Design principles

## Design Principles

1. **Honesty over sophistication**: Simple, defensible analytics over complex black-box models
2. **Stress before optimization**: Focus on understanding fragility under stress
3. **Explainability over black boxes**: All outputs must be explainable to boards, regulators, auditors
4. **PDF > Dashboard**: Printable, exportable outputs are the product

## MVP Scope (Planned)

### Included

- Portfolio ingestion via Excel/CSV
- Exposure engine (issuer, country, asset class, currency)
- Concentration risk analysis
- FX exposure
- Duration/rate sensitivity
- Deterministic stress scenarios
- PDF report generation

### Explicitly Excluded

- Retail onboarding
- Execution/trading
- Real-time pricing
- AI positioning
- Monte Carlo simulations
- Complex VaR models
- Mobile-first UX

## Contributing

This project is in early development. Please refer to the development rules in `.cursor/rules/` before contributing.

## License

[To be determined]

## Contact

For questions or issues, please contact the development team.

