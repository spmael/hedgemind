"""
Management command to run portfolio daily close process.

This command orchestrates the full daily close process for a portfolio:
portfolio import → valuation → exposure computation → report generation.

Usage:
    python manage.py run_portfolio_daily_close --portfolio-id=1 --as-of=2025-01-15 --org-id=1
    python manage.py run_portfolio_daily_close --portfolio-name="Portfolio Name" --as-of=2025-01-15 --org-id=1
    python manage.py run_portfolio_daily_close --portfolio-name="Portfolio Name" --as-of=2025-01-15 --org-code=M001
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.etl.orchestration.daily_close import run_portfolio_daily_close
from libs.tenant_context import organization_context


class Command(BaseCommand):
    """
    Management command to run portfolio daily close process.

    Orchestrates the complete daily close process for a portfolio, connecting
    the chain from portfolio data to final reports.

    Usage:
        python manage.py run_portfolio_daily_close --portfolio-id=1 --as-of=2025-01-15 --org-id=1
        python manage.py run_portfolio_daily_close --portfolio-name="Portfolio Name" --as-of=2025-01-15 --org-id=1
        python manage.py run_portfolio_daily_close --portfolio-name="Portfolio Name" --as-of=2025-01-15 --org-code=M001
    """

    help = "Run portfolio daily close process (valuation → exposure → report)"

    def add_arguments(self, parser):
        """
        Add command-line arguments.

        Args:
            parser: Argument parser instance.
        """
        portfolio_group = parser.add_mutually_exclusive_group(required=True)
        portfolio_group.add_argument(
            "--portfolio-id",
            type=int,
            help="Portfolio ID to process",
        )
        portfolio_group.add_argument(
            "--portfolio-name",
            type=str,
            help="Portfolio name to process",
        )
        parser.add_argument(
            "--as-of",
            type=str,
            required=True,
            help="As-of date in ISO format (YYYY-MM-DD)",
        )
        org_group = parser.add_mutually_exclusive_group(required=True)
        org_group.add_argument(
            "--org-id",
            type=int,
            help="Organization ID",
        )
        org_group.add_argument(
            "--org-code",
            type=str,
            help="Organization code name (e.g., M001)",
        )

    def handle(self, *args, **options):
        """
        Execute the command.

        Args:
            *args: Positional arguments.
            **options: Command options.
        """
        from apps.organizations.models import Organization
        from apps.portfolios.models import Portfolio

        portfolio_id = options.get("portfolio_id")
        portfolio_name = options.get("portfolio_name")
        as_of_str = options["as_of"]
        org_id = options.get("org_id")
        org_code = options.get("org_code")

        # Parse date
        try:
            as_of_date = datetime.strptime(as_of_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(
                f"Invalid date format: {as_of_str}. Use YYYY-MM-DD format."
            )

        # Look up organization by code if org_id not provided
        if not org_id:
            try:
                organization = Organization.objects.get(
                    code_name=org_code, is_active=True
                )
                org_id = organization.id
                self.stdout.write(
                    self.style.NOTICE(f"Found organization '{org_code}' (ID: {org_id})")
                )
            except Organization.DoesNotExist:
                raise CommandError(f"Organization with code '{org_code}' not found")
            except Organization.MultipleObjectsReturned:
                raise CommandError(
                    f"Multiple organizations found with code '{org_code}'. "
                    "Please use --org-id instead."
                )

        # Set organization context and look up portfolio by name if portfolio_id not provided
        with organization_context(org_id):
            # Look up portfolio by name if portfolio_id not provided
            if not portfolio_id:
                try:
                    portfolio = Portfolio.objects.get(
                        name=portfolio_name, is_active=True
                    )
                    portfolio_id = portfolio.id
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Found portfolio '{portfolio_name}' (ID: {portfolio_id})"
                        )
                    )
                except Portfolio.DoesNotExist:
                    raise CommandError(
                        f"Portfolio '{portfolio_name}' not found in organization {org_id}"
                    )
                except Portfolio.MultipleObjectsReturned:
                    raise CommandError(
                        f"Multiple portfolios found with name '{portfolio_name}' in organization {org_id}. "
                        "Please use --portfolio-id instead."
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
