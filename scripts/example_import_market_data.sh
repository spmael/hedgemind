#!/bin/bash
#
# Example script for importing market data (prices, FX rates, yield curves).
#
# This script demonstrates how to import daily market data for an organization.
# Adjust the file paths, dates, and organization ID as needed.
#
# Prerequisites:
#   - Instruments must be imported first
#   - Market data sources must be configured
#
# Usage:
#   ./scripts/example_import_market_data.sh [AS_OF_DATE]
#
# Example:
#   ./scripts/example_import_market_data.sh 2025-01-31
#

set -e  # Exit on error

# Configuration
ORG_SLUG="cemac-bank"  # Organization slug (e.g., 'cemac-bank')
# Alternative: ORG_CODE="CEMACBANK"  # Organization code_name
# Alternative: ORG_ID=1  # Organization ID (numeric)
AS_OF_DATE=${1:-$(date +%Y-%m-%d)}  # Use provided date or today's date
ACTOR_USERNAME="admin"  # Optional: Username for audit log
# Alternative: ACTOR_ID=1  # Optional: User ID for audit log

# File paths (adjust as needed)
PRICES_FILE="./scripts/data/prices_${AS_OF_DATE//-/_}.xlsx"
FX_RATES_FILE="./scripts/data/fx_rates_${AS_OF_DATE//-/_}.xlsx"
YIELD_CURVES_FILE="./scripts/data/yield_curves_${AS_OF_DATE//-/_}.xlsx"

# Market data source codes (adjust as needed)
PRICES_SOURCE="BVMAC"
FX_SOURCE="BEAC"
YIELD_CURVE_SOURCE="BEAC"
YIELD_CURVE_NAME="XAF_SOVEREIGN"

echo "=========================================="
echo "Importing Market Data"
echo "=========================================="
echo "Organization: $ORG_SLUG"
echo "As-of Date: $AS_OF_DATE"
echo ""

# Import Prices
if [ -f "$PRICES_FILE" ]; then
    echo "Importing instrument prices..."
    python manage.py import_instrument_prices_excel \
        --file "$PRICES_FILE" \
        --source-code "$PRICES_SOURCE" \
        --sheet "PRICES" \
        --org-slug "$ORG_SLUG" \
        --revision 0 \
        --actor-username "$ACTOR_USERNAME" \
        --canonicalize
    echo "✓ Prices imported"
else
    echo "⚠ Skipping prices import (file not found: $PRICES_FILE)"
fi

echo ""

# Import FX Rates
if [ -f "$FX_RATES_FILE" ]; then
    echo "Importing FX rates..."
    python manage.py import_fx_rate_excel \
        --file "$FX_RATES_FILE" \
        --source-code "$FX_SOURCE" \
        --sheet "FX_RATES" \
        --org-slug "$ORG_SLUG" \
        --revision 0 \
        --actor-username "$ACTOR_USERNAME" \
        --canonicalize
    echo "✓ FX rates imported"
else
    echo "⚠ Skipping FX rates import (file not found: $FX_RATES_FILE)"
fi

echo ""

# Import Yield Curves
if [ -f "$YIELD_CURVES_FILE" ]; then
    echo "Importing yield curves..."
    python manage.py import_yield_curve_excel \
        --file "$YIELD_CURVES_FILE" \
        --source-code "$YIELD_CURVE_SOURCE" \
        --yield-curve-name "$YIELD_CURVE_NAME" \
        --sheet "YIELD_CURVES" \
        --org-slug "$ORG_SLUG" \
        --revision 0 \
        --actor-username "$ACTOR_USERNAME" \
        --canonicalize
    echo "✓ Yield curves imported"
else
    echo "⚠ Skipping yield curves import (file not found: $YIELD_CURVES_FILE)"
fi

echo ""
echo "=========================================="
echo "Market data import completed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Verify market data in Django admin"
echo "2. Import portfolio holdings"
echo "3. Run analytics/valuation"
echo ""

