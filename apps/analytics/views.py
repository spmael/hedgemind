"""
Views for analytics operations.

This module provides views for analytics operations, including daily close
execution and valuation run management.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.analytics.models import RunStatus, ValuationPolicy, ValuationRun
from apps.analytics.tasks import run_portfolio_daily_close_task
from apps.portfolios.models import Portfolio


@login_required
@require_http_methods(["GET", "POST"])
def run_daily_close(request):
    """
    Run daily close for a portfolio.

    GET: Display form to select portfolio and as-of date.
    POST: Trigger async daily close task and redirect to status page.
    """
    if request.method == "GET":
        # Get portfolios for current organization
        portfolios = Portfolio.objects.filter(is_active=True).order_by("name")
        return render(
            request,
            "analytics/run_daily_close.html",
            {
                "portfolios": portfolios,
            },
        )

    # POST: Trigger daily close
    if not hasattr(request, "org_id") or request.org_id is None:
        messages.error(request, "No organization context available.")
        return HttpResponseRedirect(reverse("analytics:run_daily_close"))

    portfolio_id = request.POST.get("portfolio")
    as_of_date_str = request.POST.get("as_of_date")

    # Validate required fields
    errors = []
    if not portfolio_id:
        errors.append("Portfolio is required.")
    if not as_of_date_str:
        errors.append("As-of date is required.")

    if errors:
        for error in errors:
            messages.error(request, error)
        portfolios = Portfolio.objects.filter(is_active=True).order_by("name")
        return render(
            request,
            "analytics/run_daily_close.html",
            {
                "portfolios": portfolios,
            },
        )

    # Get portfolio
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        messages.error(request, "Invalid portfolio selected.")
        portfolios = Portfolio.objects.filter(is_active=True).order_by("name")
        return render(
            request,
            "analytics/run_daily_close.html",
            {
                "portfolios": portfolios,
            },
        )

    # Parse date
    from datetime import datetime

    try:
        as_of_date = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Invalid date format.")
        portfolios = Portfolio.objects.filter(is_active=True).order_by("name")
        return render(
            request,
            "analytics/run_daily_close.html",
            {
                "portfolios": portfolios,
            },
        )

    # Create or get ValuationRun (task will use get_or_create and find this one)
    valuation_run, created = ValuationRun.objects.get_or_create(
        portfolio=portfolio,
        as_of_date=as_of_date,
        valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
        defaults={
            "status": RunStatus.PENDING,
            "created_by": request.user,
        },
    )

    # Update created_by if run already existed
    if not created and not valuation_run.created_by:
        valuation_run.created_by = request.user
        valuation_run.save(update_fields=["created_by"])

    # Trigger async daily close task (it will find and update this ValuationRun)
    run_portfolio_daily_close_task.delay(
        portfolio_id=portfolio.id,
        as_of_date=as_of_date.isoformat(),
        org_id=request.org_id,
    )

    # Redirect to status page
    return HttpResponseRedirect(
        reverse("analytics:daily_close_status", args=[valuation_run.id])
    )


@login_required
@require_http_methods(["GET"])
def daily_close_status(request, run_id: int):
    """
    Display daily close execution status.

    Shows the current status of a valuation run, including execution summary
    and option to mark as official if successful.
    """
    valuation_run = get_object_or_404(
        ValuationRun.objects.filter(organization_id=request.org_id), id=run_id
    )

    # Try to get execution summary from task result if available
    # For now, we'll rely on the ValuationRun status and related Report
    execution_summary = None

    # Get report if exists
    report = None
    if valuation_run.status == RunStatus.SUCCESS:
        reports = valuation_run.reports.all()
        if reports.exists():
            report = reports.first()

    # Determine if should auto-refresh (if status is pending or running)
    auto_refresh = valuation_run.status in [RunStatus.PENDING, RunStatus.RUNNING]

    return render(
        request,
        "analytics/daily_close_status.html",
        {
            "run": valuation_run,
            "execution_summary": execution_summary,
            "report": report,
            "auto_refresh": auto_refresh,
        },
    )


@login_required
@require_http_methods(["POST"])
def mark_official(request, run_id: int):
    """
    Mark a valuation run as official.

    POST only endpoint to mark a successful valuation run as official.
    """
    valuation_run = get_object_or_404(
        ValuationRun.objects.filter(organization_id=request.org_id), id=run_id
    )

    reason = request.POST.get("reason", "Marked as official via UI")

    try:
        valuation_run.mark_as_official(reason=reason, actor=request.user)
        messages.success(request, "Valuation run marked as official.")
    except Exception as e:
        messages.error(request, f"Error marking as official: {str(e)}")

    return HttpResponseRedirect(
        reverse("analytics:daily_close_status", args=[valuation_run.id])
    )
