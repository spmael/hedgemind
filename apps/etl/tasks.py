"""
Celery tasks for ETL operations.

This module defines Celery tasks for ETL processing, including daily close
orchestration and health check tasks. All tasks that require organization
context must receive org_id explicitly as a parameter, as middleware context
is not available in Celery workers.

Key tasks:
    - run_daily_close_task: Orchestrates daily market data ETL for an organization
    - ping_etl: Health check task for ETL system
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from celery import shared_task

from apps.etl.orchestration.daily_close import run_daily_close
from apps.organizations.models import Organization
from libs.tenant_context import organization_context


@shared_task(bind=True)
def run_daily_close_task(self, org_id: int, as_of_iso_date: str) -> dict[str, Any]:
    """
    Run daily close ETL orchestration for a specific organization.

    This task orchestrates all daily market data pipelines (FX, prices, etc.)
    for a given organization and as-of date. The organization ID is passed
    explicitly as Celery workers do not have access to middleware context.

    Args:
        self: Celery task instance (from bind=True).
        org_id (int): Organization ID to process data for.
        as_of_iso_date (str): ISO format date string for the as-of date.

    Returns:
        dict: Task result containing:
            - org_id: Organization object (validated and active)
            - as_of_iso_date: Original as-of date string
            - results: List of pipeline execution results

    Raises:
        DoesNotExist: If organization with given ID doesn't exist or is inactive.

    Note:
        - org_id is passed explicitly (don't rely on middleware in workers)
        - thread-local context is only for convenience inside the task execution
    """
    as_of = datetime.fromisoformat(as_of_iso_date)

    # Validate org_id exists and is active
    organization = Organization.objects.get(id=org_id, is_active=True)

    with organization_context(organization.id):
        results = run_daily_close(as_of=as_of)
        # run_daily_close returns list[dict], so use results directly
        return {
            "org_id": organization,
            "as_of_iso_date": as_of_iso_date,
            "results": results,
        }


@shared_task
def ping_etl() -> dict[str, Any]:
    """
    Health check task for ETL system.

    Returns a simple response indicating the ETL task system is operational.
    Useful for monitoring and testing Celery worker connectivity.

    Returns:
        dict: Health check response containing:
            - ok (bool): Always True if task executes successfully
            - timestamp (str): ISO format timestamp of when task executed
    """
    return {"ok": True, "timestamp": datetime.now().isoformat()}
