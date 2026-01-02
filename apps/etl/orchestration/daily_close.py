"""
Orchestration logic for daily close ETL processing.

This module provides the orchestration entrypoint to run all required market data ETL
pipelines for the daily "close-of-business" cycle. Here, you can coordinate execution
of FX, security prices, and other market data pipeline tasks for a given as-of date.
Extend this file whenever new daily ETL pipelines or dependencies are needed.
"""

from __future__ import annotations

from datetime import date

from apps.analytics.models import RunStatus, ValuationPolicy, ValuationRun
from apps.etl.pipelines.market_data_fx_daily import run_fx_daily
from apps.etl.pipelines.prices_daily import run_prices_daily
from apps.organizations.models import Organization
from apps.portfolios.models import Portfolio, PositionSnapshot
from libs.tenant_context import organization_context


def run_daily_close(as_of: date) -> list[dict]:
    """
    Runs the daily close orchestration for market data pipelines for a given as-of date.

    This function coordinates the execution of multiple ETL pipelines required for daily "close-of-business"
    processing, ensuring that all key market data sources (such as FX rates and security prices) are refreshed
    for the specified date. Additional market data pipelines (e.g., curves_daily, fund_navs_daily/weekly,
    corporate_actions) should be added as needed in the future.

    Args:
        as_of (date): The as-of date for which all market data pipelines should be run.

    Returns:
        list[dict]: A list of result dictionaries from each invoked pipeline containing status, metadata, etc.
    """
    results = []
    results.append(run_fx_daily(as_of=as_of))
    results.append(run_prices_daily(as_of=as_of))
    return results


def run_portfolio_daily_close(portfolio_id: int, as_of_date: date, org_id: int) -> dict:
    """
    Run full daily close process for a portfolio: valuation → exposure → report.

    Orchestrates the complete daily close process for a portfolio:
    1. Validates portfolio exists and belongs to organization
    2. Checks if PositionSnapshots exist for portfolio/date
    3. Creates or gets existing ValuationRun for portfolio/date
    4. Executes valuation run
    5. Computes and stores exposures
    6. Generates report

    Args:
        portfolio_id: Portfolio ID to process.
        as_of_date: As-of date for the processing.
        org_id: Organization ID (explicit, not from context).

    Returns:
        Dictionary with execution summary:
        {
            'portfolio_id': int,
            'portfolio_name': str,
            'as_of_date': str,
            'valuation_run_id': int,
            'valuation_status': str,
            'exposures_computed': bool,
            'report_id': int | None,
            'report_status': str | None,
            'errors': list[str],
        }

    Raises:
        Portfolio.DoesNotExist: If portfolio doesn't exist or doesn't belong to org.
        ValueError: If PositionSnapshots don't exist for portfolio/date.
    """
    errors = []

    with organization_context(org_id):
        # Validate organization
        try:
            _org = Organization.objects.get(id=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise ValueError(f"Organization {org_id} does not exist or is not active")

        # Validate portfolio
        try:
            portfolio = Portfolio.objects.get(id=portfolio_id, organization_id=org_id)
        except Portfolio.DoesNotExist:
            raise ValueError(
                f"Portfolio {portfolio_id} does not exist or does not belong to organization {org_id}"
            )

        # Check if PositionSnapshots exist
        snapshots_count = PositionSnapshot.objects.filter(
            portfolio=portfolio, as_of_date=as_of_date
        ).count()

        if snapshots_count == 0:
            raise ValueError(
                f"No PositionSnapshots found for portfolio {portfolio_id} on date {as_of_date}. "
                "Please import portfolio data first."
            )

        # Get or create ValuationRun
        valuation_run, created = ValuationRun.objects.get_or_create(
            portfolio=portfolio,
            as_of_date=as_of_date,
            valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
            defaults={
                "status": RunStatus.PENDING,
                "organization": portfolio.organization,
            },
        )

        # Execute valuation if not already successful
        if valuation_run.status != RunStatus.SUCCESS:
            try:
                valuation_run.execute()
                # Refresh from database to get updated status
                valuation_run.refresh_from_db()
            except Exception as e:
                errors.append(f"Valuation execution failed: {str(e)}")
                valuation_run.refresh_from_db()  # Get latest status (may be FAILED)
                return {
                    "portfolio_id": portfolio_id,
                    "portfolio_name": portfolio.name,
                    "as_of_date": str(as_of_date),
                    "valuation_run_id": valuation_run.id,
                    "valuation_status": valuation_run.status,
                    "exposures_computed": False,
                    "report_id": None,
                    "report_status": None,
                    "errors": errors,
                }

        # Compute and store exposures
        exposures_computed = False
        try:
            valuation_run.compute_and_store_exposures()
            exposures_computed = True
        except Exception as e:
            errors.append(f"Exposure computation failed: {str(e)}")

        # Generate report (will be implemented in report renderer)
        report_id = None
        report_status = None
        if exposures_computed:
            try:
                from apps.reports.renderers.portfolio_report import (
                    generate_portfolio_report,
                )

                report = generate_portfolio_report(valuation_run.id)
                report_id = report.id
                report_status = report.status
            except ImportError:
                # Report renderer not yet implemented, skip for now
                pass
            except Exception as e:
                errors.append(f"Report generation failed: {str(e)}")

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "as_of_date": str(as_of_date),
            "valuation_run_id": valuation_run.id,
            "valuation_status": valuation_run.status,
            "exposures_computed": exposures_computed,
            "report_id": report_id,
            "report_status": report_status,
            "errors": errors,
        }
