#!/bin/bash
#
# Example script for setting up a new organization with reference data.
#
# This script demonstrates the complete workflow for setting up reference data
# for a new organization. It includes:
#   1. Loading taxonomies (instrument groups, types, market data sources)
#   2. Importing issuers
#   3. Importing instruments
#   4. Importing initial market data
#
# Usage:
#   ./scripts/example_setup_new_organization.sh [ORG_SLUG]
#
# Example:
#   ./scripts/example_setup_new_organization.sh cemac-bank
#

set -e  # Exit on error

# Configuration
ORG_SLUG=${1:-"cemac-bank"}  # Use provided org slug or default
# Alternative: ORG_CODE="CEMACBANK"  # Organization code_name
# Alternative: ORG_ID=1  # Organization ID (numeric)
ACTOR_USERNAME="admin"  # Optional: Username for audit log
# Alternative: ACTOR_ID=1  # Optional: User ID for audit log

echo "=========================================="
echo "Setting Up New Organization"
echo "=========================================="
echo "Organization: $ORG_SLUG"
echo ""

# Step 1: Load taxonomies
echo "Step 1: Loading taxonomies..."
echo "----------------------------------------"
echo "Loading instrument groups..."
python manage.py load_instrument_groups
echo "✓ Instrument groups loaded"

echo ""
echo "Loading instrument types..."
python manage.py load_instrument_types
echo "✓ Instrument types loaded"

echo ""
echo "Syncing market data sources..."
python manage.py sync_market_data_sources
echo "✓ Market data sources synced"

echo ""
echo "=========================================="

# Step 2: Import issuers
echo "Step 2: Importing issuers..."
echo "----------------------------------------"
ISSUERS_FILE="./scripts/data/issuers_master.xlsx"
if [ -f "$ISSUERS_FILE" ]; then
    python manage.py import_issuers_excel \
        --file "$ISSUERS_FILE" \
        --sheet "ISSUERS" \
        --org-slug "$ORG_SLUG" \
        --actor-username "$ACTOR_USERNAME"
    echo "✓ Issuers imported"
else
    echo "⚠ Skipping issuers import (file not found: $ISSUERS_FILE)"
    echo "  Please create the issuers file or import manually."
fi

echo ""
echo "=========================================="

# Step 3: Import instruments
echo "Step 3: Importing instruments..."
echo "----------------------------------------"
INSTRUMENTS_FILE="./scripts/data/instruments_master.xlsx"
if [ -f "$INSTRUMENTS_FILE" ]; then
    python manage.py import_instruments_excel \
        --file "$INSTRUMENTS_FILE" \
        --sheet "INSTRUMENTS" \
        --org-slug "$ORG_SLUG" \
        --actor-username "$ACTOR_USERNAME"
    echo "✓ Instruments imported"
else
    echo "⚠ Skipping instruments import (file not found: $INSTRUMENTS_FILE)"
    echo "  Please create the instruments file or import manually."
fi

echo ""
echo "=========================================="

# Step 4: Import initial market data (optional)
echo "Step 4: Importing initial market data (optional)..."
echo "----------------------------------------"
echo "To import market data, run:"
echo "  ./scripts/example_import_market_data.sh [AS_OF_DATE]"
echo ""

echo "=========================================="
echo "Organization setup completed!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Taxonomies loaded"
echo "  ✓ Issuers imported (if file provided)"
echo "  ✓ Instruments imported (if file provided)"
echo ""
echo "Next steps:"
echo "1. Verify data in Django admin"
echo "2. Import market data: ./scripts/example_import_market_data.sh"
echo "3. Import portfolio holdings"
echo "4. Run analytics/valuation"
echo ""

