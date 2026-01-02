"""
Management command to run portfolio daily close process.

This command orchestrates the full daily close process for a portfolio:
portfolio import → valuation → exposure computation → report generation.

Usage:
    python manage.py run_portfolio_daily_close --portfolio-id=1 --as-of=2025-01-15 --org-id=1
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.etl.orchestration.daily_close import run_portfolio_daily_close


class Command(BaseCommand):
    """
    Management command to run portfolio daily close process.

    Orchestrates the complete daily close process for a portfolio, connecting
    the chain from portfolio data to final reports.

    Usage:
        python manage.py run_portfolio_daily_close --portfolio-id=1 --as-of=2025-01-15 --org-id=1
    """

    help = "Run portfolio daily close process (valuation → exposure → report)"

    def add_arguments(self, parser):
        """
        Add command-line arguments.

        Args:
            parser: Argument parser instance.
        """
        parser.add_argument(
            "--portfolio-id",
            type=int,
            required=True,
            help="Portfolio ID to process",
        )
        parser.add_argument(
            "--as-of",
            type=str,
            required=True,
            help="As-of date in ISO format (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            required=True,
            help="Organization ID",
        )

    def handle(self, *args, **options):
        """
        Execute the command.

        Args:
            *args: Positional arguments.
            **options: Command options.
        """
        portfolio_id = options["portfolio_id"]
        as_of_str = options["as_of"]
        org_id = options["org_id"]

        # Parse date
        try:
            as_of_date = datetime.strptime(as_of_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(
                f"Invalid date format: {as_of_str}. Use YYYY-MM-DD format."
            )

        self.stdout.write(
            self.style.NOTICE(
                f"Running daily close for portfolio {portfolio_id} on {as_of_date} (org {org_id})..."
            )
        )

        try:
            result = run_portfolio_daily_close(
                portfolio_id=portfolio_id, as_of_date=as_of_date, org_id=org_id
            )

            # Print results
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDaily close completed for portfolio: {result['portfolio_name']}"
                )
            )
            self.stdout.write(f"  Portfolio ID: {result['portfolio_id']}")
            self.stdout.write(f"  As-of Date: {result['as_of_date']}")
            self.stdout.write(f"  Valuation Run ID: {result['valuation_run_id']}")
            self.stdout.write(f"  Valuation Status: {result['valuation_status']}")
            self.stdout.write(f"  Exposures Computed: {result['exposures_computed']}")

            if result["report_id"]:
                self.stdout.write(f"  Report ID: {result['report_id']}")
                self.stdout.write(f"  Report Status: {result['report_status']}")

            if result["errors"]:
                self.stdout.write(self.style.WARNING("\nErrors:"))
                for error in result["errors"]:
                    self.stdout.write(self.style.WARNING(f"  - {error}"))

        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f"Daily close failed: {str(e)}")
