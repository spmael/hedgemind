"""
Celery tasks for analytics operations.

This module defines Celery tasks for analytics operations, including portfolio
daily close processing. All tasks that require organization context must receive
org_id explicitly as a parameter, as middleware context is not available in Celery workers.

Key tasks:
    - run_portfolio_daily_close_task: Run portfolio daily close (valuation, exposure, report)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from celery import shared_task

from apps.etl.orchestration.daily_close import run_portfolio_daily_close
from libs.tenant_context import organization_context


@shared_task(bind=True)
def run_portfolio_daily_close_task(
    self,
    portfolio_id: Optional[int] = None,
    portfolio_name: Optional[str] = None,
    as_of_date: str = "",
    org_id: Optional[int] = None,
    org_code: Optional[str] = None,
) -> dict:
    """
    Async task to run portfolio daily close process.

    This task orchestrates the complete daily close process for a portfolio:
    valuation → exposure computation → report generation. The organization ID
    is passed explicitly as Celery workers do not have access to middleware context.

    Args:
        self: Celery task instance (from bind=True).
        portfolio_id: Portfolio ID to process (optional if portfolio_name provided).
        portfolio_name: Portfolio name to process (optional if portfolio_id provided).
        as_of_date: ISO format date string (YYYY-MM-DD) for the as-of date.
        org_id: Organization ID (explicit, not from context, optional if org_code provided).
        org_code: Organization code name (e.g., M001, optional if org_id provided).

    Returns:
        dict: Execution summary from run_portfolio_daily_close():
            - portfolio_id: Portfolio ID
            - portfolio_name: Portfolio name
            - as_of_date: As-of date string
            - valuation_run_id: ValuationRun ID
            - valuation_status: Run status
            - exposures_computed: Whether exposures were computed
            - report_id: Report ID (if generated)
            - report_status: Report status (if generated)
            - errors: List of error messages

    Raises:
        ValueError: If portfolio doesn't exist, both portfolio_id and portfolio_name are None,
                    both org_id and org_code are None, or PositionSnapshots don't exist.
    """
    from apps.organizations.models import Organization
    from apps.portfolios.models import Portfolio

    if not portfolio_id and not portfolio_name:
        raise ValueError("Either portfolio_id or portfolio_name must be provided")

    if not org_id and not org_code:
        raise ValueError("Either org_id or org_code must be provided")

    as_of = date.fromisoformat(as_of_date)

    # Look up organization by code if org_id not provided
    if not org_id:
        try:
            organization = Organization.objects.get(code_name=org_code, is_active=True)
            org_id = organization.id
        except Organization.DoesNotExist:
            raise ValueError(f"Organization with code '{org_code}' not found")
        except Organization.MultipleObjectsReturned:
            raise ValueError(
                f"Multiple organizations found with code '{org_code}'. "
                "Please use org_id instead."
            )

    with organization_context(org_id):
        # Look up portfolio by name if portfolio_id not provided
        if not portfolio_id:
            try:
                portfolio = Portfolio.objects.get(
                    name=portfolio_name, organization_id=org_id, is_active=True
                )
                portfolio_id = portfolio.id
            except Portfolio.DoesNotExist:
                raise ValueError(
                    f"Portfolio '{portfolio_name}' not found in organization {org_id}"
                )
            except Portfolio.MultipleObjectsReturned:
                raise ValueError(
                    f"Multiple portfolios found with name '{portfolio_name}' in organization {org_id}. "
                    "Please use portfolio_id instead."
                )

        return run_portfolio_daily_close(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            org_id=org_id,
        )
