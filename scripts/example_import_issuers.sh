#!/bin/bash
#
# Example script for importing issuers from Excel file.
#
# This script demonstrates how to import issuer master data for a new organization.
# Adjust the file paths and organization ID as needed.
#
# Usage:
#   ./scripts/example_import_issuers.sh
#

set -e  # Exit on error

# Configuration
ORG_ID=1
EXCEL_FILE="./scripts/data/issuers_master.xlsx"
SHEET_NAME="ISSUERS"
ACTOR_ID=1  # Optional: User ID for audit log

echo "=========================================="
echo "Importing Issuers"
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
python manage.py import_issuers_excel \
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
echo "1. Verify issuers in Django admin: /admin/reference_data/issuer/"
echo "2. Import instruments: ./scripts/example_import_instruments.sh"
echo ""

