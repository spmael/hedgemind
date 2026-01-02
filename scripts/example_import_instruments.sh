#!/bin/bash
#
# Example script for importing instruments from Excel file.
#
# This script demonstrates how to import instrument master data for an organization.
# Adjust the file paths and organization ID as needed.
#
# Prerequisites:
#   - Issuers must be imported first (run example_import_issuers.sh)
#   - Instrument groups and types must be loaded
#
# Usage:
#   ./scripts/example_import_instruments.sh
#

set -e  # Exit on error

# Configuration
ORG_ID=1
EXCEL_FILE="./scripts/data/instruments_master.xlsx"
SHEET_NAME="INSTRUMENTS"
ACTOR_ID=1  # Optional: User ID for audit log

echo "=========================================="
echo "Importing Instruments"
echo "=========================================="
echo "Organization ID: $ORG_ID"
echo "Excel File: $EXCEL_FILE"
echo "Sheet: $SHEET_NAME"
echo ""

# Check if file exists
if [ ! -f "$EXCEL_FILE" ]; then
    echo "ERROR: File not found: $EXCEL_FILE"
    echo "Please ensure the Excel file exists and the path is correct."
    exit 1
fi

# Run import command
echo "Running import command..."
python manage.py import_instruments_excel \
    --file "$EXCEL_FILE" \
    --sheet "$SHEET_NAME" \
    --org-id "$ORG_ID" \
    --actor-id "$ACTOR_ID"

echo ""
echo "=========================================="
echo "Import completed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Verify instruments in Django admin: /admin/reference_data/instrument/"
echo "2. Import market data (prices, FX rates, yield curves)"
echo "3. Import portfolio holdings"
echo ""

