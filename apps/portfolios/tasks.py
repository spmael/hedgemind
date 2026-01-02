"""
Celery tasks for portfolio operations.

This module defines Celery tasks for portfolio-related operations, including
file imports. All tasks that require organization context must receive org_id
explicitly as a parameter, as middleware context is not available in Celery workers.

Key tasks:
    - import_portfolio_task: Import portfolio positions from file (async)
"""

from __future__ import annotations

from celery import shared_task

from apps.portfolios.ingestion.import_excel import import_portfolio_from_file
from libs.tenant_context import organization_context


@shared_task(bind=True)
def import_portfolio_task(self, portfolio_import_id: int, org_id: int) -> dict:
    """
    Async task to import portfolio positions from file.

    This task wraps the synchronous import_portfolio_from_file() function to
    run it asynchronously in a Celery worker. The organization ID is passed
    explicitly as Celery workers do not have access to middleware context.

    Args:
        self: Celery task instance (from bind=True).
        portfolio_import_id: ID of PortfolioImport record to process.
        org_id: Organization ID (explicit, not from context).

    Returns:
        dict: Result dictionary from import_portfolio_from_file() containing:
            - created: Number of positions created
            - errors: Number of errors encountered
            - total_rows: Total rows processed
            - status: Import status (success/partial/failed)

    Raises:
        Exception: Re-raises any exception from import_portfolio_from_file().
    """
    from django.utils import timezone

    from apps.portfolios.models import PortfolioImport
    from libs.choices import ImportStatus

    with organization_context(org_id):
        try:
            # Update status to processing
            try:
                portfolio_import = PortfolioImport.objects.get(
                    id=portfolio_import_id, organization_id=org_id
                )
                portfolio_import.status = ImportStatus.PROCESSING
                portfolio_import.save(update_fields=["status"])
            except PortfolioImport.DoesNotExist:
                # PortfolioImport doesn't exist, let import function handle error
                pass

            # Run import
            result = import_portfolio_from_file(portfolio_import_id)
            return result
        except Exception as e:
            # Update status to failed if not already updated
            try:
                portfolio_import = PortfolioImport.objects.get(
                    id=portfolio_import_id, organization_id=org_id
                )
                portfolio_import.status = ImportStatus.FAILED
                portfolio_import.error_message = str(e)
                portfolio_import.completed_at = timezone.now()
                portfolio_import.save(
                    update_fields=["status", "error_message", "completed_at"]
                )
            except PortfolioImport.DoesNotExist:
                pass
            raise  # Re-raise the exception
