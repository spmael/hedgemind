"""
Management command to export missing instruments from failed portfolio imports.

Exports missing instruments as CSV formatted for instrument import template,
enabling the operator loop: Failed import → Export missing → Fill template → Import → Retry.

Usage:
    python manage.py export_missing_instruments --portfolio-import-id 123 --output-file missing.csv
    python manage.py export_missing_instruments --portfolio-import-id 123 --output-file missing.csv --org-id 1
"""

from __future__ import annotations

import csv
import re

from django.core.management.base import BaseCommand, CommandError

from apps.portfolios.models import PortfolioImport, PortfolioImportError
from libs.tenant_context import organization_context


class Command(BaseCommand):
    """
    Management command to export missing instruments from failed portfolio imports.

    This command reads PortfolioImportError records with error_type="reference_data"
    and error_code="INSTRUMENT_NOT_FOUND", extracts instrument identifiers, and
    exports them as CSV formatted for the instrument import template.

    The exported CSV can be filled with instrument details and imported using
    import_instruments_excel command, completing the operator loop.

    Usage example:
        python manage.py export_missing_instruments --portfolio-import-id 123 --output-file missing.csv --org-id 1
    """

    help = "Export missing instruments from failed portfolio imports as CSV for instrument import template"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--portfolio-import-id",
            type=int,
            required=True,
            help="ID of PortfolioImport record to export missing instruments from",
        )
        parser.add_argument(
            "--output-file",
            type=str,
            required=True,
            help="Output CSV file path",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            required=True,
            help="Organization ID (required for organization-scoped data)",
        )

    def extract_identifier_from_error(self, error: PortfolioImportError) -> str | None:
        """
        Extract instrument identifier from error message or raw_row_data.

        Args:
            error: PortfolioImportError record.

        Returns:
            str | None: Extracted identifier, or None if not found.
        """
        # Try to extract from error message: "Instrument 'IDENTIFIER' not found (by ISIN or ticker)"
        error_message = error.error_message
        match = re.search(r"Instrument '([^']+)' not found", error_message)
        if match:
            return match.group(1).strip().upper()

        # Fallback: try to extract from raw_row_data JSON
        raw_row_data = error.raw_row_data
        if raw_row_data and isinstance(raw_row_data, dict):
            # Look for common identifier field names
            for field in ["instrument_identifier", "isin", "ticker", "ISIN", "TICKER"]:
                if field in raw_row_data and raw_row_data[field]:
                    return str(raw_row_data[field]).strip().upper()

        return None

    def handle(self, *args, **options):
        """Execute the command."""
        portfolio_import_id = options["portfolio_import_id"]
        output_file = options["output_file"]
        org_id = options["org_id"]

        # Validate PortfolioImport exists
        try:
            portfolio_import = PortfolioImport.objects.get(
                id=portfolio_import_id,
                organization_id=org_id,
            )
        except PortfolioImport.DoesNotExist:
            raise CommandError(
                f"PortfolioImport {portfolio_import_id} not found for organization {org_id}"
            )

        # Get missing instrument errors
        with organization_context(org_id):
            errors = PortfolioImportError.objects.filter(
                portfolio_import=portfolio_import,
                error_type="reference_data",
                error_code="INSTRUMENT_NOT_FOUND",
            ).order_by("row_number")

        if not errors.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"No missing instrument errors found for PortfolioImport {portfolio_import_id}"
                )
            )
            return

        # Extract unique identifiers
        identifiers = set()
        for error in errors:
            identifier = self.extract_identifier_from_error(error)
            if identifier:
                identifiers.add(identifier)

        if not identifiers:
            self.stdout.write(
                self.style.WARNING(
                    "No instrument identifiers could be extracted from error records"
                )
            )
            return

        # Write CSV file
        # Columns matching instrument import template format
        # Based on docs/templates/README.md, required columns are:
        # name, instrument_group_code, instrument_type_code, currency, issuer_code, valuation_method
        # Optional: isin, ticker, country, sector, etc.
        csv_columns = [
            "instrument_identifier",  # ISIN or ticker (from error)
            "name",  # Placeholder - user must fill
            "instrument_group_code",  # Placeholder - user must fill
            "instrument_type_code",  # Placeholder - user must fill
            "currency",  # Placeholder - user must fill
            "issuer_code",  # Placeholder - user must fill
            "valuation_method",  # Default: mark_to_market
            # Optional columns (empty, user can fill)
            "isin",
            "ticker",
            "country",
            "sector",
        ]

        try:
            # Use utf-8-sig (UTF-8 with BOM) for Excel compatibility
            with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=csv_columns)
                writer.writeheader()

                for identifier in sorted(identifiers):
                    # Determine if identifier is ISIN or ticker (basic heuristic)
                    # ISINs are typically 12 characters (alphanumeric)
                    # Tickers are typically shorter
                    is_isin = len(identifier) >= 10 and identifier[:2].isalpha()

                    row = {
                        "instrument_identifier": identifier,
                        "name": "",  # User must fill
                        "instrument_group_code": "",  # User must fill
                        "instrument_type_code": "",  # User must fill
                        "currency": "",  # User must fill
                        "issuer_code": "",  # User must fill
                        "valuation_method": "mark_to_market",  # Default
                        "isin": identifier if is_isin else "",
                        "ticker": identifier if not is_isin else "",
                        "country": "",
                        "sector": "",
                    }
                    writer.writerow(row)

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Exported {len(identifiers)} missing instruments to {output_file}"
                )
            )
            self.stdout.write("")
            self.stdout.write("Next steps:")
            self.stdout.write(f"  1. Fill missing data in {output_file}")
            self.stdout.write(
                f"  2. Import instruments: python manage.py import_instruments_excel "
                f"--file {output_file} --org-id {org_id}"
            )
            self.stdout.write(f"  3. Re-run preflight: python manage.py preflight_portfolio_import "
                            f"--portfolio-import-id {portfolio_import_id} --org-id {org_id}")
            self.stdout.write(f"  4. Retry import: python manage.py import_portfolio "
                            f"--portfolio-import-id {portfolio_import_id} --org-id {org_id}")

        except Exception as e:
            raise CommandError(f"Failed to write output file: {str(e)}")

