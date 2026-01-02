# Excel Import Templates

This directory contains standardized Excel templates for importing data into Hedgemind. These templates serve as **guidance only** - the system's flexible column mapping will accept files with different column names, but using these templates ensures consistency and reduces errors.

## Available Templates

### 1. Portfolio Holdings Template (`portfolio_holdings_template.xlsx`)

**Purpose:** Import portfolio position data (holdings).

**Usage:**
- Upload via the portfolio import interface
- Used for daily position snapshots
- Supports CSV and Excel formats

**Required Columns:**
- `instrument_identifier` - ISIN or ticker symbol
- `quantity` - Number of units/shares
- `currency` - ISO currency code (3 letters, e.g., XAF)
- `book_value` - Book/cost value
- `valuation_source` - Source of valuation (custodian, market, internal, manual)

**Flexible Columns (at least one required):**
- `price` - Price per unit
- `market_value` - Total market value

**Optional Columns:**
- `accrued_interest` - Accrued interest (for bonds)

**Example:**
```
instrument_identifier | quantity | currency | price | market_value | book_value | valuation_source | accrued_interest
CM1234567890         | 1000     | XAF      | 105.50| 1055000     | 1000000    | custodian        | 0
```

**Notes:**
- The system will automatically map common column name variations (e.g., "ISIN", "Qty", "MV")
- At least one of `price` or `market_value` must be provided
- Instruments must exist in the reference data before importing holdings

### 2. Instrument Master Template (`instrument_master_template.xlsx`)

**Purpose:** Import instrument reference data.

**Usage:**
- Import via management command: `python manage.py import_instruments_excel --file <path> --org-id <id>`
- Must be run within organization context
- Creates or updates Instrument records

**Required Columns:**
- `name` - Full name of instrument
- `instrument_group_code` - Code of InstrumentGroup (must exist in system)
- `instrument_type_code` - Code of InstrumentType within group (must exist)
- `currency` - ISO currency code (3 letters)
- `issuer_code` - Issuer short_name or name (must exist in system)
- `valuation_method` - One of: `mark_to_market`, `mark_to_model`, `external_appraisal`, `manual_declared`

**Optional Columns:**
- `isin` - ISIN code
- `ticker` - Ticker symbol
- `country` - 2-letter country code
- `sector` - Economic sector
- `maturity_date` - Maturity date (YYYY-MM-DD format)
- `coupon_rate` - Coupon rate as percentage
- `coupon_frequency` - ANNUAL, SEMI_ANNUAL, etc.
- `first_listing_date` - First listing date
- `original_offering_amount` - Original offering amount
- `units_outstanding` - Units/shares outstanding
- `face_value` - Face/par value
- `amortization_method` - BULLET, AMORTIZING, ZERO_COUPON
- `last_coupon_date` - Last coupon date
- `next_coupon_date` - Next coupon date
- `fund_category` - DIVERSIFIED, MONEY_MARKET, BOND, EQUITY (for funds)
- `fund_launch_date` - Fund launch date

**Prerequisites:**
- InstrumentGroup records must exist
- InstrumentType records must exist (within groups)
- Issuer records must exist (import issuers first)

**Example:**
```
name                          | instrument_group_code | instrument_type_code | currency | issuer_code    | valuation_method
Cameroon 5Y Government Bond   | Government Bonds      | Bond                | XAF      | REP_CAMEROON   | mark_to_market
```

### 3. Issuer Master Template (`issuer_master_template.xlsx`)

**Purpose:** Import issuer reference data.

**Usage:**
- Import via management command: `python manage.py import_issuers_excel --file <path> --org-id <id>`
- Must be run within organization context
- Creates or updates Issuer records

**Required Columns:**
- `name` - Full legal name of issuer (unique per organization)
- `short_name` - Short name or abbreviation (used as issuer_code in instrument imports)
- `country` - 2-letter ISO country code
- `issuer_group` - Group classification (e.g., "Sovereign", "Corporate", "Asset Manager")

**Example:**
```
name                          | short_name    | country | issuer_group
Republic of Cameroon          | REP_CAMEROON  | CM      | Sovereign
Africa Bright Asset Management| ABAM         | GA      | Asset Manager
```

**Notes:**
- Issuers must be imported before instruments
- The `short_name` is used as the `issuer_code` when importing instruments
- Country codes must be valid 2-letter ISO codes

## Template Features

All templates include:
- **Header row** with canonical column names (blue background, white text)
- **Example data rows** showing proper format
- **Instructions sheet** with field descriptions and validation rules
- **Auto-sized columns** for readability

## Import Order

For new organizations, import data in this order:

1. **Issuers** - Import issuer master data first
2. **Instruments** - Import instrument master data (requires issuers)
3. **Portfolio Holdings** - Import position data (requires instruments)

## File Naming Convention

While not strictly enforced, we recommend following this naming convention for uploaded files:

**Format:** `{org_code}_{portfolio_code}_holdings_{YYYYMMDD}_{source}.xlsx`

**Example:** `CEMACBANK_TREASURY_holdings_20250131_custodian.xlsx`

**Benefits:**
- Human-readable identification without opening files
- Matches audit log patterns
- Easier reconciliation with imports
- Industry-standard practice

**Source values:** `custodian`, `internal`, `manual`, `external`, `market`

## Flexible Mapping

The system uses intelligent column mapping that accepts:
- Case variations (e.g., "ISIN", "isin", "Isin")
- Common abbreviations (e.g., "Qty" for "quantity", "MV" for "market_value")
- Underscore vs. space variations (e.g., "instrument_identifier" vs "instrument identifier")

However, using the canonical column names from templates ensures the most reliable imports.

## Error Handling

If imports fail:
- Row-level errors are recorded in `PortfolioImportError` records
- Error types include: `validation`, `mapping`, `reference_data`, `format`, `business_rule`, `system`
- Missing instruments result in `reference_data` errors (instruments are NOT auto-created)
- Users must fix reference data issues before re-importing

## Support

For questions or issues with templates:
- Check the Instructions sheet in each template
- Review import error messages in the admin interface
- Ensure all prerequisites (issuers, instrument groups/types) are in place

