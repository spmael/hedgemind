# Organization Scoping for Reference Data

## Current Architecture

### Global (Shared Across All Organizations)
- **InstrumentGroup**: Global taxonomy (EQUITY, FIXED_INCOME, etc.)
- **InstrumentType**: Global taxonomy (Bond, Stock, etc.)
- **MarketDataSource**: Global market data sources (BVMAC, BEAC, CUSTODIAN, etc.)

### Organization-Scoped (Isolated Per Organization)
- **Issuer**: Each organization has its own issuers
- **Instrument**: Each organization has its own instruments

## Current Implementation Details

### Issuer Model
- **Model**: `apps/reference_data/models/issuers.py`
- **Inheritance**: `OrganizationOwnedModel`
- **Unique Constraints**:
  - `unique_together = [["organization", "name"]]` - Same issuer name can exist in different orgs
  - `issuer_code` field has `unique=True` globally (globally unique identifier)
- **Storage**: Each organization's issuers are stored separately
- **Import**: Requires `--org-id` parameter

### Instrument Model
- **Model**: `apps/reference_data/models/instruments.py`
- **Inheritance**: `OrganizationOwnedModel`
- **Unique Constraints**: None at model level (ISIN/ticker uniqueness handled at application level)
- **Storage**: Each organization's instruments are stored separately
- **Import**: Requires `--org-id` parameter

## How It Works

### Import Process
```bash
# Step 1: Import issuers for organization 1
python manage.py import_issuers_excel --file issuers.xlsx --org-id 1

# Step 2: Import instruments for organization 1
python manage.py import_instruments_excel --file instruments.xlsx --org-id 1

# Step 3: Import issuers for organization 2 (separate data)
python manage.py import_issuers_excel --file issuers.xlsx --org-id 2
```

### Data Isolation
- Organization 1's issuers are **completely separate** from Organization 2's issuers
- Organization 1's instruments are **completely separate** from Organization 2's instruments
- All queries automatically filter by current organization context
- No cross-organization data leakage is possible

### Cross-Organization Consistency
- **issuer_code**: Globally unique field on Issuer model for cross-org consistency
- **LEI**: Legal Entity Identifier field for cross-org matching
- These fields allow future features like cross-org analytics or shared reference data

## Current Behavior vs. User Expectations

### User's Stated Requirement
> "I have instruments and issuers that are globally user agnostic of organization but later maybe organization would load their own instruments and issuers."

### Current Architecture
- **Current**: Instruments and issuers are **organization-scoped** (each org has their own)
- **Does NOT support**: Global instruments/issuers shared across all organizations

### Potential Gap
If you want to:
1. **Start with global/shared** instruments/issuers that all orgs can use
2. **Later allow** organizations to load their own custom instruments/issuers

Then the **current architecture does NOT support this**. Current design is:
- Each organization **must** load their own instruments/issuers
- No sharing mechanism exists

## Architecture Options

### Option 1: Keep Current Architecture (Recommended for MVP)
**Current Design**: Each organization loads their own instruments/issuers

**Pros**:
- ✅ Simple and clear data ownership
- ✅ Complete data isolation
- ✅ No data sharing complexity
- ✅ Matches institutional reality (orgs have different instruments)

**Cons**:
- ❌ Same issuer/instrument must be loaded separately for each org
- ❌ No global/shared reference data

**When to use**: If each organization truly has different instruments/issuers, or if duplication is acceptable.

### Option 2: Global with Organization Overrides
**Design**: Make instruments/issuers global, with optional org-specific overrides/aliases

**Implementation**:
- Remove `OrganizationOwnedModel` from Issuer/Instrument
- Add `organization` ForeignKey as nullable (global if null)
- Add organization-specific fields (aliases, custom attributes) in separate model

**Pros**:
- ✅ Shared reference data
- ✅ Reduces duplication
- ✅ Organizations can override/extend

**Cons**:
- ❌ More complex data model
- ❌ Requires migration and refactoring
- ❌ Potential for cross-org data leaks if not careful

**When to use**: If you need shared reference data across organizations.

### Option 3: Hybrid Approach (Future Enhancement)
**Design**: Keep organization-scoped, but add "reference organization" concept

**Implementation**:
- Keep current organization-scoped design
- Add concept of "reference organization" (e.g., org_id=0 for global)
- Organizations can "copy" instruments/issuers from reference org
- Or organizations can "link" to reference org's instruments

**Pros**:
- ✅ Backward compatible
- ✅ Flexibility for shared vs. custom
- ✅ Gradual migration path

**Cons**:
- ❌ More complex
- ❌ Requires new features/commands

**When to use**: If you need both shared and custom instruments/issuers.

## Recommendation

**For MVP**: **Keep Option 1** (current architecture)

**Reasons**:
1. **Institutional Reality**: Different institutions truly have different instruments/issuers
2. **Data Ownership**: Each org owns and maintains their own reference data
3. **Simplicity**: Current design is clear and works
4. **Future-Proof**: `issuer_code` and `LEI` fields allow future cross-org features

**If you need shared reference data later**, consider Option 3 (hybrid) as it maintains backward compatibility.

## Migration Path (If Changing)

If you decide to change to global/shared instruments/issuers:

1. **Data Migration**: Assign existing instruments/issuers to a "global organization" (org_id=0 or special org)
2. **Model Changes**: Remove `OrganizationOwnedModel`, make `organization` nullable
3. **Query Changes**: Update all queries to handle nullable organization
4. **Import Commands**: Update import commands to support global import (no --org-id required)
5. **Tests**: Update all tests for new model structure

**⚠️ Warning**: This is a significant architectural change that requires careful planning and migration.

## Questions to Consider

Before changing the architecture, ask:

1. **Do organizations really share the same instruments/issuers?**
   - If yes → Consider Option 2 or 3
   - If no → Keep Option 1 (current)

2. **How often do instruments/issuers change?**
   - If frequently, sharing might reduce maintenance
   - If rarely, duplication is acceptable

3. **Do organizations need to customize instrument/issuer attributes?**
   - If yes → Option 1 (current) or Option 3
   - If no → Option 2 might work

4. **What's the operational reality?**
   - Do institutions share the same data sources?
   - Or do they maintain separate reference data?

## Industry Standards & Best Practices

### Reference Data Providers (Bloomberg, Refinitiv/LSEG, S&P Capital IQ)

**Pattern**: **Global Master Data**
- Maintain centralized, global reference data (instruments, issuers, identifiers)
- Institutions subscribe and consume this master data
- Standard identifiers: ISIN, LEI, CFI codes
- **Shared foundation** across all subscribers

**Architecture**:
- Single source of truth for reference data
- Organizations consume from this master
- Organizations may have **custom mappings/extensions** but foundation is shared

### Institutional Systems (Enterprise Portfolio Management)

**Pattern**: **Hybrid - Master Data with Org Extensions**
- Start with shared/master reference data (from providers or internal master)
- Organizations can:
  - Use master data as-is
  - Add custom/organization-specific instruments
  - Override/extend master data attributes
  - Map to organization-specific classifications

**Examples**:
- **State Street, BNY Mellon (Custodian Systems)**: Shared master data, client-specific extensions
- **RiskMetrics, MSCI**: Shared reference data, client-specific portfolios/analytics
- **Bloomberg AIM, Charles River**: Shared instrument master, client-specific portfolios

### Multi-Tenant SaaS Platforms (Like Hedgemind)

**Pattern**: **Varies by Use Case**

#### Pattern A: Shared Master Data (Common for Small-Medium Institutions)
- **Global/shared** instruments and issuers
- Organizations use shared reference data
- Organizations can add custom instruments
- **Pros**: Reduces duplication, easier maintenance
- **Cons**: Requires careful data governance, potential conflicts

#### Pattern B: Organization-Scoped (Common for Large Institutions)
- **Organization-specific** instruments and issuers
- Each organization maintains their own reference data
- **Pros**: Complete data isolation, no conflicts, matches institutional reality
- **Cons**: Potential duplication, each org must load data
- **Used by**: Systems serving large institutions with different data sources

#### Pattern C: Hybrid (Most Flexible)
- **Shared master data** for common instruments/issuers
- **Organization-specific** for custom/proprietary instruments
- Organizations can "adopt" from master or create custom
- **Pros**: Best of both worlds
- **Cons**: More complex implementation

### Industry Standards Compliance

**Identification Standards** (From search results):
- **ISIN (ISO 6166)**: Unique 12-character identifier for instruments
- **LEI (ISO 17442)**: Unique 20-character identifier for legal entities (issuers)
- **CFI Code (ISO 10962)**: 6-letter classification code for instruments
- **FISN (ISO 18774)**: Standardized short names for instruments

**Key Insight**: Industry standards focus on **identification**, not necessarily on **data ownership/scoping**. The architecture (shared vs. org-scoped) is an implementation choice.

### Recommendation Based on Industry Standards

**For Hedgemind (Regional Institutional Platform)**:

1. **Current Architecture (Organization-Scoped) is Industry Standard** for:
   - Systems serving large institutions
   - Systems where organizations have different data sources
   - Systems requiring complete data isolation
   - Regional/institutional focus (like Hedgemind)

2. **Shared Master Data is Industry Standard** for:
   - Systems serving many small-medium institutions
   - Systems with single data source/provider
   - Retail-focused platforms

3. **Hybrid Approach is Industry Standard** for:
   - Enterprise platforms (Bloomberg AIM, Charles River)
   - Systems needing maximum flexibility

### Why Current Architecture Matches Industry Standards

**Hedgemind's context** (from project rules):
- **Institutional-first** platform
- Regional focus (Central Africa)
- Different institutions likely have different data sources
- Need for data isolation and governance

**Matches Pattern B (Organization-Scoped)** which is standard for:
- ✅ Institutional systems
- ✅ Regional/custom data sources
- ✅ Organizations with proprietary instruments
- ✅ Regulatory/compliance requirements for data isolation

**However**, industry standards also emphasize:
- **Standard identifiers** (ISIN, LEI) - ✅ Already implemented (`issuer_code`, `lei` fields)
- **Master data concepts** - ⚠️ Not implemented, but `issuer_code` enables future cross-org features

## Summary

**Current State**: Instruments and issuers are **organization-scoped**. Each organization loads and maintains their own reference data.

**Storage Location**: 
- Issuers: `reference_data_issuer` table with `organization_id` foreign key
- Instruments: `reference_data_instrument` table with `organization_id` foreign key

**Import Process**: 
- Requires `--org-id` parameter
- Data is scoped to that organization
- No sharing mechanism exists

**Industry Standards Alignment**:
- ✅ **Matches industry standard** for institutional systems (Pattern B)
- ✅ **Complies with identification standards** (ISIN, LEI via `issuer_code`, `lei` fields)
- ✅ **Aligns with regional/institutional platforms** requiring data isolation
- ⚠️ **Different from** shared master data pattern (Pattern A), but that's appropriate for this use case

**Is this properly handled?** 
- ✅ **Yes** - Current architecture matches industry standards for institutional platforms
- ✅ **Yes** - Standard identifiers (`issuer_code`, `lei`) enable future cross-org features
- ⚠️ **Consider for future** - Hybrid approach (Pattern C) if you need shared master data

**Final Recommendation**: 
- **Keep current architecture** - It aligns with industry standards for institutional systems
- **Maintain standard identifiers** (`issuer_code`, `lei`) - Already implemented correctly
- **Consider hybrid approach later** - Only if you need shared master data across organizations

