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

**Current Phase**: Reference Data & Portfolio Foundation (Active Development)

The project has a solid foundation with multi-tenant architecture, comprehensive reference data models, and portfolio management infrastructure. Reference data import capabilities are fully implemented, and the platform is ready for analytics engine development.

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
    - `PortfolioImport` - Tracks file uploads and import status
    - `PositionSnapshot` - Time-series snapshots of positions (immutable)
  - All models are organization-scoped using `OrganizationOwnedModel`
  - **Testing**: Model tests implemented

- `apps/etl` - ETL pipelines and orchestration 🚧
  - Daily close orchestration framework
  - Market data FX daily pipeline (placeholder)
  - Prices daily pipeline (placeholder)
  - Celery tasks for async processing

- `apps/audit` - Audit logging ✅
  - AuditEvent model implemented
  - Immutable audit log structure

- `apps/accounts` - User account management 🚧 (scaffolded)
- `apps/analytics` - Analytics engine 🚧 (scaffolded)
- `apps/reports` - Report generation 🚧 (scaffolded, templates directory exists)

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

- **Analytics Engine**: Exposure calculation, risk analytics (concentration, FX, duration)
- **Stress Scenarios**: Deterministic stress scenario engine
- **Portfolio Ingestion**: CSV/Excel upload and parsing services
- **PDF Report Generation**: Report templates and renderers
- **Admin Interfaces**: Django admin configuration for all models
- **Reference Data UI**: Web interfaces for managing reference data
- **ETL Pipeline Implementation**: Complete market data daily pipelines

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
│  - Normalized holdings + market data → exposures        │
│  - Produces report schema (JSON)                        │
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

**Portfolio & Analytics Flow** (Planned):
1. **Upload**: User uploads CSV/XLSX → stored in object storage → `PortfolioImport` record created
2. **Parse & Normalize** (async): Job validates → maps columns → creates `PositionSnapshot` records
3. **Analytics Run** (async): Load market data → compute exposures → persist `AnalyticsRun` results
4. **Report** (async): Render PDF from JSON results → persist `Report` record
5. **UI**: User views portfolio → downloads PDF

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
│   ├── analytics/          # Analytics and metrics (scaffolded)
│   │   └── engine/         # Analytics engine (pure Python)
│   ├── audit/              # Audit logging ✅
│   ├── etl/                # ETL pipelines and orchestration 🚧
│   │   ├── orchestration/  # Daily close orchestration
│   │   └── pipelines/      # Individual ETL pipelines
│   ├── organizations/      # Multi-tenant organization management ✅
│   ├── portfolios/         # Portfolio management ✅
│   │   └── ingestion/      # Portfolio ingestion logic
│   ├── reference_data/     # Reference data (securities, market data) ✅
│   │   ├── models/         # Model definitions by domain
│   │   ├── management/     # Management commands for data import
│   │   │   └── commands/   # Excel import commands
│   │   ├── providers/      # Market data providers
│   │   └── services/       # Reference data services (import, canonicalize)
│   └── reports/            # Report generation (scaffolded)
│       ├── renderers/      # PDF renderers
│       └── templates/      # Report templates
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

