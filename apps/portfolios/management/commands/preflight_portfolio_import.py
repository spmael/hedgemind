"""
Management command for preflight validation of portfolio imports.

Validates that required reference data exists before portfolio import
to catch missing data early and provide clear feedback to operators.

Usage:
    python manage.py preflight_portfolio_import --portfolio-import-id 123
    python manage.py preflight_portfolio_import --portfolio-import-id 123 --org-id 1
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.portfolios.models import PortfolioImport
from apps.portfolios.services.preflight import preflight_portfolio_import
from libs.tenant_context import organization_context


class Command(BaseCommand):
    """
    Management command for preflight validation of portfolio imports.

    This command validates that required reference data exists before
    portfolio import, providing early feedback on missing instruments,
    FX rates, prices, and yield curves.

    Usage example:
        python manage.py preflight_portfolio_import --portfolio-import-id 123 --org-id 1
    """

    help = "Preflight validation for portfolio import (checks missing reference data)"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--portfolio-import-id",
            type=int,
            required=True,
            help="ID of PortfolioImport record to validate",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            required=True,
            help="Organization ID (required for organization-scoped data)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        portfolio_import_id = options["portfolio_import_id"]
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

        self.stdout.write(
            f"Preflight validation for PortfolioImport {portfolio_import_id}"
        )
        self.stdout.write(f"Portfolio: {portfolio_import.portfolio.name}")
        self.stdout.write(f"As-of date: {portfolio_import.as_of_date}")
        self.stdout.write("")

        # Run preflight validation within organization context
        with organization_context(org_id):
            try:
                result = preflight_portfolio_import(portfolio_import_id)
            except Exception as e:
                raise CommandError(f"Preflight validation failed: {str(e)}")

        # Output results
        if result["ready"]:
            self.stdout.write(self.style.SUCCESS("✓ Preflight validation PASSED"))
            self.stdout.write("All required reference data is available.")
        else:
            self.stdout.write(self.style.ERROR("✗ Preflight validation FAILED"))
            self.stdout.write("Missing reference data detected:")
            self.stdout.write("")

        # Missing instruments
        if result["missing_instruments"]:
            self.stdout.write(
                self.style.ERROR(
                    f"Missing Instruments ({len(result['missing_instruments'])}):"
                )
            )
            for identifier in result["missing_instruments"]:
                self.stdout.write(f"  - {identifier}")
            self.stdout.write("")
            self.stdout.write(
                "  → Export missing instruments: "
                f"python manage.py export_missing_instruments "
                f"--portfolio-import-id {portfolio_import_id} --output-file missing.csv"
            )
            self.stdout.write("")

        # Missing FX rates
        if result["missing_fx_rates"]:
            self.stdout.write(
                self.style.ERROR(
                    f"Missing FX Rates ({len(result['missing_fx_rates'])}):"
                )
            )
            for fx_rate in result["missing_fx_rates"]:
                self.stdout.write(
                    f"  - {fx_rate['from']}/{fx_rate['to']} for date {fx_rate['date']}"
                )
            self.stdout.write("")

        # Missing prices (warnings only, not blocking for MVP)
        if result["missing_prices"]:
            self.stdout.write(
                self.style.WARNING(f"Missing Prices ({len(result['missing_prices'])}):")
            )
            for price in result["missing_prices"][:10]:  # Show first 10
                self.stdout.write(
                    f"  - {price['identifier']} (instrument_id: {price['instrument_id']}) "
                    f"for date {price['date']}"
                )
            if len(result["missing_prices"]) > 10:
                self.stdout.write(
                    f"  ... and {len(result['missing_prices']) - 10} more"
                )
            self.stdout.write(
                "  (Note: Not required for MVP valuation policy USE_SNAPSHOT_MV)"
            )
            self.stdout.write("")

        # Missing yield curves (warnings only, not blocking for MVP)
        if result["missing_curves"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Missing Yield Curves ({len(result['missing_curves'])}):"
                )
            )
            for curve in result["missing_curves"]:
                self.stdout.write(f"  - {curve['currency']} for date {curve['date']}")
            self.stdout.write("  (Note: Not required for MVP)")
            self.stdout.write("")

        # Warnings
        if result["warnings"]:
            self.stdout.write(self.style.WARNING("Warnings:"))
            for warning in result["warnings"]:
                self.stdout.write(f"  - {warning}")
            self.stdout.write("")

        # Exit code: 0 if ready, 1 if not ready
        if not result["ready"]:
            self.stdout.write(
                self.style.ERROR(
                    "Import is NOT ready. Please resolve missing reference data and re-run preflight."
                )
            )
            raise SystemExit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Import is ready. You can proceed with portfolio import."
                )
            )
