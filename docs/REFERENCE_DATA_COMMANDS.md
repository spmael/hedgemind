# Reference Data Management Commands

This document provides comprehensive documentation for all reference data import and management commands in Hedgemind.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Command Reference](#command-reference)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

## Overview

Reference data commands are used to import and manage master data (instruments, issuers) and market data (prices, FX rates, yield curves, indices) from Excel files. All commands support organization-scoped data and require an organization context.

### Key Principles

- **Organization Context Required**: Most commands require `--org-id` to specify which organization's data you're working with
- **Excel Templates**: Use standardized templates from `docs/templates/` for consistent data format
- **File Naming**: Follow naming conventions: `{org_code}_{type}_{YYYYMMDD}_{source}.xlsx`
- **No Auto-Creation**: Reference data (instruments, issuers) must be imported before portfolio holdings

## Prerequisites

### Required Setup

1. **Organization Context**: Ensure you know the organization ID you're working with
   ```bash
   # List organizations
   python manage.py shell
   >>> from apps.organizations.models import Organization
   >>> for org in Organization.objects.all():
   ...     print(f"{org.id}: {org.name}")
   ```

2. **Market Data Sources**: Ensure market data sources are configured
   ```bash
   python manage.py shell
   >>> from apps.reference_data.models import MarketDataSource
   >>> MarketDataSource.objects.all()
   ```

3. **Excel Templates**: Download templates from `docs/templates/` directory

### Required Python Packages

- `pandas` - For Excel file reading
- `openpyxl` - For Excel file support
- `django` - Framework dependencies

## Command Reference

### Master Data Commands

#### Import Issuers

**Command**: `import_issuers_excel`

**Description**: Import issuer master data from Excel file. Creates or updates Issuer records within an organization context.

**Usage**:
```bash
python manage.py import_issuers_excel \
    --file ./data/issuers_master.xlsx \
    --sheet ISSUERS \
    --org-id 1
```

**Arguments**:
- `--file` (required): Path to Excel file
- `--sheet` (optional): Sheet name (default: "ISSUERS")
- `--org-id` (required): Organization ID
- `--actor-id` (optional): User ID for audit log

**Excel Format**:
| name | short_name | country | issuer_group |
|------|------------|---------|--------------|
| Government of Cameroon | GOC | CM | SOVEREIGN |
| Bank of Central African States | BEAC | CM | CENTRAL_BANK |

**Example**:
```bash
python manage.py import_issuers_excel \
    --file ./scripts/data/issuers_master.xlsx \
    --sheet Sheet1 \
    --org-id 1 \
    --actor-id 1
```

**Output**:
- Creates/updates Issuer records
- Returns summary: created count, updated count, errors

---

#### Import Instruments

**Command**: `import_instruments_excel`

**Description**: Import instrument master data from Excel file. Creates or updates Instrument records within an organization context.

**Usage**:
```bash
python manage.py import_instruments_excel \
    --file ./data/instruments_master.xlsx \
    --sheet INSTRUMENTS \
    --org-id 1
```

**Arguments**:
- `--file` (required): Path to Excel file
- `--sheet` (optional): Sheet name (default: "INSTRUMENTS")
- `--org-id` (required): Organization ID
- `--actor-id` (optional): User ID for audit log

**Excel Format**:
| instrument_identifier | name | instrument_group_code | instrument_type_code | currency | issuer_code | valuation_method | isin | ticker | country | sector |
|----------------------|------|----------------------|---------------------|----------|-------------|------------------|------|--------|---------|--------|
| CM1234567890 | Cameroon Treasury Bond 2025 | BOND | TREASURY_BOND | XAF | GOC | MARK_TO_MARKET | CM1234567890 | TREAS2025 | CM | SOVEREIGN |

**Example**:
```bash
python manage.py import_instruments_excel \
    --file ./scripts/data/instruments_master.xlsx \
    --sheet Sheet1 \
    --org-id 1 \
    --actor-id 1
```

**Output**:
- Creates/updates Instrument records
- Returns summary: created count, updated count, errors

**Important Notes**:
- `instrument_group_code` and `instrument_type_code` must exist in the system
- `issuer_code` must match an existing issuer's `short_name`
- `instrument_identifier` can be ISIN, ticker, or custom identifier

---

### Market Data Commands

#### Import Instrument Prices

**Command**: `import_instrument_prices_excel`

**Description**: Import instrument price observations from Excel file. Creates InstrumentPriceObservation records within an organization context.

**Usage**:
```bash
python manage.py import_instrument_prices_excel \
    --file ./data/prices.xlsx \
    --source-code BVMAC \
    --sheet PRICES \
    --org-id 1
```

**Arguments**:
- `--file` (required): Path to Excel file
- `--source-code` (required): MarketDataSource code (e.g., "BVMAC", "BEAC", "MANUAL")
- `--sheet` (optional): Sheet name (default: "PRICES")
- `--org-id` (required): Organization ID
- `--revision` (optional): Revision number (default: 0)
- `--actor-id` (optional): User ID for audit log
- `--canonicalize` (optional): Run canonicalization after import

**Excel Format**:
| date | instrument_id | price | price_type | quote_convention | clean_or_dirty | Volume |
|------|-----------------|-------|------------|------------------|----------------|--------|
| 2025-01-31 | CM1234567890 | 95.50 | close | PERCENT_OF_PAR | CLEAN | 1000 |

**Example**:
```bash
python manage.py import_instrument_prices_excel \
    --file ./scripts/data/prices_20250131.xlsx \
    --source-code BVMAC \
    --sheet PRICES \
    --org-id 1 \
    --revision 0 \
    --canonicalize
```

**Output**:
- Creates InstrumentPriceObservation records
- Optionally runs canonicalization to create InstrumentPrice records
- Returns summary: created count, updated count, errors

---

#### Import FX Rates

**Command**: `import_fx_rate_excel`

**Description**: Import foreign exchange rate observations from Excel file. Creates FXRateObservation records.

**Usage**:
```bash
python manage.py import_fx_rate_excel \
    --file ./data/fx_rates.xlsx \
    --source-code BEAC \
    --sheet FX_RATES \
    --org-id 1
```

**Arguments**:
- `--file` (required): Path to Excel file
- `--source-code` (required): MarketDataSource code
- `--sheet` (optional): Sheet name (default: "FX_RATES")
- `--org-id` (required): Organization ID
- `--revision` (optional): Revision number (default: 0)
- `--actor-id` (optional): User ID for audit log
- `--canonicalize` (optional): Run canonicalization after import

**Excel Format**:
| date | base_currency | quote_currency | rate | rate_type |
|------|---------------|----------------|------|-----------|
| 2025-01-31 | USD | XAF | 600.50 | SPOT |

**Example**:
```bash
python manage.py import_fx_rate_excel \
    --file ./scripts/data/fx_rates_20250131.xlsx \
    --source-code BEAC \
    --sheet FX_RATES \
    --org-id 1 \
    --canonicalize
```

---

#### Import Yield Curves

**Command**: `import_yield_curve_excel`

**Description**: Import yield curve point observations from Excel file. Creates YieldCurvePointObservation records.

**Usage**:
```bash
python manage.py import_yield_curve_excel \
    --file ./data/yield_curves.xlsx \
    --source-code BEAC \
    --yield-curve-name XAF_SOVEREIGN \
    --sheet YIELD_CURVES \
    --org-id 1
```

**Arguments**:
- `--file` (required): Path to Excel file
- `--source-code` (required): MarketDataSource code
- `--yield-curve-name` (required): YieldCurve name
- `--sheet` (optional): Sheet name (default: "YIELD_CURVES")
- `--org-id` (required): Organization ID
- `--revision` (optional): Revision number (default: 0)
- `--actor-id` (optional): User ID for audit log
- `--canonicalize` (optional): Run canonicalization after import

**Excel Format**:
| date | tenor | rate |
|------|-------|------|
| 2025-01-31 | 1M | 2.50 |
| 2025-01-31 | 3M | 2.75 |
| 2025-01-31 | 6M | 3.00 |

**Example**:
```bash
python manage.py import_yield_curve_excel \
    --file ./scripts/data/yield_curves_20250131.xlsx \
    --source-code BEAC \
    --yield-curve-name XAF_SOVEREIGN \
    --sheet YIELD_CURVES \
    --org-id 1 \
    --canonicalize
```

---

#### Import Market Index Levels

**Command**: `import_index_levels_excel`

**Description**: Import market index value observations from Excel file. Creates MarketIndexValueObservation records.

**Usage**:
```bash
python manage.py import_index_levels_excel \
    --file ./data/index_levels.xlsx \
    --source-code BVMAC \
    --index-code BVMAC_INDEX \
    --sheet INDEX_LEVELS \
    --org-id 1
```

**Arguments**:
- `--file` (required): Path to Excel file
- `--source-code` (required): MarketDataSource code
- `--index-code` (required): MarketIndex code
- `--sheet` (optional): Sheet name (default: "INDEX_LEVELS")
- `--org-id` (required): Organization ID
- `--revision` (optional): Revision number (default: 0)
- `--actor-id` (optional): User ID for audit log
- `--canonicalize` (optional): Run canonicalization after import

**Excel Format**:
| date | value |
|------|-------|
| 2025-01-31 | 1250.50 |

**Example**:
```bash
python manage.py import_index_levels_excel \
    --file ./scripts/data/index_levels_20250131.xlsx \
    --source-code BVMAC \
    --index-code BVMAC_INDEX \
    --sheet INDEX_LEVELS \
    --org-id 1 \
    --canonicalize
```

---

### Canonicalization Commands

#### Canonicalize Prices

**Command**: `canonicalize_prices`

**Description**: Run canonicalization process to select best price observations and create canonical InstrumentPrice records.

**Usage**:
```bash
python manage.py canonicalize_prices \
    --as-of-date 2025-01-31 \
    --org-id 1
```

**Arguments**:
- `--as-of-date` (required): Date to canonicalize (YYYY-MM-DD)
- `--org-id` (required): Organization ID
- `--actor-id` (optional): User ID for audit log

**Example**:
```bash
python manage.py canonicalize_prices \
    --as-of-date 2025-01-31 \
    --org-id 1 \
    --actor-id 1
```

**Output**:
- Creates/updates InstrumentPrice records based on source priority
- Returns summary: prices created, prices updated

---

### Setup Commands

#### Load Instrument Groups

**Command**: `load_instrument_groups`

**Description**: Load predefined instrument groups (global taxonomy).

**Usage**:
```bash
python manage.py load_instrument_groups
```

**Example**:
```bash
python manage.py load_instrument_groups
```

---

#### Load Instrument Types

**Command**: `load_instrument_types`

**Description**: Load predefined instrument types within groups.

**Usage**:
```bash
python manage.py load_instrument_types
```

**Example**:
```bash
python manage.py load_instrument_types
```

---

#### Sync Market Data Sources

**Command**: `sync_market_data_sources`

**Description**: Sync market data sources from configuration.

**Usage**:
```bash
python manage.py sync_market_data_sources
```

**Example**:
```bash
python manage.py sync_market_data_sources
```

---

## Common Workflows

### Workflow 1: Setting Up a New Organization

**Step 1**: Load reference data taxonomies
```bash
python manage.py load_instrument_groups
python manage.py load_instrument_types
python manage.py sync_market_data_sources
```

**Step 2**: Import issuers
```bash
python manage.py import_issuers_excel \
    --file ./data/issuers_master.xlsx \
    --org-id 1
```

**Step 3**: Import instruments
```bash
python manage.py import_instruments_excel \
    --file ./data/instruments_master.xlsx \
    --org-id 1
```

**Step 4**: Import market data (prices, FX rates, yield curves)
```bash
python manage.py import_instrument_prices_excel \
    --file ./data/prices.xlsx \
    --source-code BVMAC \
    --org-id 1 \
    --canonicalize

python manage.py import_fx_rate_excel \
    --file ./data/fx_rates.xlsx \
    --source-code BEAC \
    --org-id 1 \
    --canonicalize

python manage.py import_yield_curve_excel \
    --file ./data/yield_curves.xlsx \
    --source-code BEAC \
    --yield-curve-name XAF_SOVEREIGN \
    --org-id 1 \
    --canonicalize
```

### Workflow 2: Daily Market Data Import

**Step 1**: Import prices
```bash
python manage.py import_instrument_prices_excel \
    --file ./data/prices_20250131.xlsx \
    --source-code BVMAC \
    --org-id 1 \
    --canonicalize
```

**Step 2**: Import FX rates
```bash
python manage.py import_fx_rate_excel \
    --file ./data/fx_rates_20250131.xlsx \
    --source-code BEAC \
    --org-id 1 \
    --canonicalize
```

**Step 3**: Import yield curves
```bash
python manage.py import_yield_curve_excel \
    --file ./data/yield_curves_20250131.xlsx \
    --source-code BEAC \
    --yield-curve-name XAF_SOVEREIGN \
    --org-id 1 \
    --canonicalize
```

**Step 4**: (Optional) Re-run canonicalization if needed
```bash
python manage.py canonicalize_prices \
    --as-of-date 2025-01-31 \
    --org-id 1
```

### Workflow 3: Adding New Instruments

**Step 1**: Export existing instruments (optional, for reference)
```bash
# Use Django admin export action or query directly
```

**Step 2**: Prepare Excel file with new instruments using template
```bash
# Use docs/templates/instrument_master_template.xlsx
```

**Step 3**: Import new instruments
```bash
python manage.py import_instruments_excel \
    --file ./data/new_instruments.xlsx \
    --org-id 1
```

**Step 4**: Verify import
```bash
python manage.py shell
>>> from apps.reference_data.models import Instrument
>>> Instrument.objects.filter(organization_id=1).count()
```

## Troubleshooting

### Common Errors

#### Error: "Organization context required"

**Cause**: Command was run without `--org-id` parameter.

**Solution**: Always provide `--org-id` parameter:
```bash
python manage.py import_instruments_excel \
    --file ./data/instruments.xlsx \
    --org-id 1
```

---

#### Error: "MarketDataSource with code 'XXX' not found"

**Cause**: Market data source doesn't exist in the system.

**Solution**: Create the source or use an existing one:
```bash
python manage.py sync_market_data_sources
# Or create manually in Django admin
```

---

#### Error: "InstrumentGroup with code 'XXX' not found"

**Cause**: Instrument group doesn't exist.

**Solution**: Load instrument groups:
```bash
python manage.py load_instrument_groups
```

---

#### Error: "Issuer with short_name 'XXX' not found"

**Cause**: Issuer doesn't exist in the organization.

**Solution**: Import issuers first:
```bash
python manage.py import_issuers_excel \
    --file ./data/issuers.xlsx \
    --org-id 1
```

---

#### Error: "Failed to read Excel file"

**Cause**: File path is incorrect or file is corrupted.

**Solution**: 
- Verify file path is correct
- Ensure file is a valid Excel file (.xlsx)
- Check file permissions

---

#### Error: "Missing required columns"

**Cause**: Excel file doesn't have required columns.

**Solution**: 
- Use templates from `docs/templates/`
- Verify column names match exactly (case-sensitive)
- Check for typos in column headers

---

### Best Practices

1. **Always use templates**: Use standardized templates from `docs/templates/` to ensure correct format

2. **File naming**: Follow naming convention: `{org_code}_{type}_{YYYYMMDD}_{source}.xlsx`

3. **Import order**: 
   - Issuers first
   - Instruments second
   - Market data last

4. **Validate before import**: Check Excel file format and data quality before importing

5. **Use canonicalization**: Run `--canonicalize` flag after market data imports to create canonical records

6. **Audit logging**: Use `--actor-id` to track who performed the import

7. **Revision tracking**: Use `--revision` parameter for corrections (0 = initial, 1+ = corrections)

---

### Getting Help

- Check command help: `python manage.py <command> --help`
- Review templates: `docs/templates/README.md`
- Check Django admin: Import models show status and errors
- Review logs: Check application logs for detailed error messages

---

## Additional Resources

- **Templates**: `docs/templates/` - Excel templates for all data types
- **Admin Interface**: Django admin provides visual interface for viewing imports and errors
- **API Documentation**: See main README.md for API endpoints (if available)

