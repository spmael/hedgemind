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

from celery import shared_task

from apps.etl.orchestration.daily_close import run_portfolio_daily_close
from libs.tenant_context import organization_context


@shared_task(bind=True)
def run_portfolio_daily_close_task(
    self, portfolio_id: int, as_of_date: str, org_id: int
) -> dict:
    """
    Async task to run portfolio daily close process.

    This task orchestrates the complete daily close process for a portfolio:
    valuation → exposure computation → report generation. The organization ID
    is passed explicitly as Celery workers do not have access to middleware context.

    Args:
        self: Celery task instance (from bind=True).
        portfolio_id: Portfolio ID to process.
        as_of_date: ISO format date string (YYYY-MM-DD) for the as-of date.
        org_id: Organization ID (explicit, not from context).

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
        ValueError: If portfolio doesn't exist or PositionSnapshots don't exist.
    """
    as_of = date.fromisoformat(as_of_date)

    with organization_context(org_id):
        return run_portfolio_daily_close(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            org_id=org_id,
        )
