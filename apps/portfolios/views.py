"""
Views for portfolio management operations.

This module provides views for portfolio import operations, including file upload,
preflight validation, import status tracking, and missing instrument export.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.portfolios.models import Portfolio, PortfolioImport
from apps.portfolios.services.export_missing_instruments import (
    export_missing_instruments_csv,
)
from apps.portfolios.services.preflight import preflight_portfolio_import
from apps.portfolios.tasks import import_portfolio_task
from libs.choices import ImportSourceType
from libs.tenant_context import organization_context


@login_required
@require_http_methods(["GET", "POST"])
def upload_holdings(request):
    """
    Upload holdings file and create PortfolioImport record.

    GET: Display upload form.
    POST: Handle file upload, create PortfolioImport, trigger async import task.
    """
    if request.method == "GET":
        # Get portfolios for current organization
        portfolios = Portfolio.objects.filter(is_active=True).order_by("name")
        return render(
            request,
            "portfolios/upload_holdings.html",
            {
                "portfolios": portfolios,
            },
        )

    # POST: Handle file upload
    if not hasattr(request, "org_id") or request.org_id is None:
        messages.error(request, "No organization context available.")
        return HttpResponseRedirect(reverse("portfolios:upload_holdings"))

    portfolio_id = request.POST.get("portfolio")
    as_of_date_str = request.POST.get("as_of_date")
    uploaded_file = request.FILES.get("file")

    # Validate required fields
    errors = []
    if not portfolio_id:
        errors.append("Portfolio is required.")
    if not as_of_date_str:
        errors.append("As-of date is required.")
    if not uploaded_file:
        errors.append("File is required.")

    if errors:
        for error in errors:
            messages.error(request, error)
        portfolios = Portfolio.objects.filter(is_active=True).order_by("name")
        return render(
            request,
            "portfolios/upload_holdings.html",
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
            "portfolios/upload_holdings.html",
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
            "portfolios/upload_holdings.html",
            {
                "portfolios": portfolios,
            },
        )

    # Create PortfolioImport record
    portfolio_import = PortfolioImport.objects.create(
        portfolio=portfolio,
        file=uploaded_file,
        as_of_date=as_of_date,
        source_type=ImportSourceType.MANUAL,
        status="pending",
    )

    # Run preflight validation automatically after upload
    # (Import will be triggered manually after preflight passes)
    try:
        with organization_context(request.org_id):
            _preflight_result = preflight_portfolio_import(portfolio_import.id)
    except Exception as e:
        messages.warning(
            request,
            f"Preflight validation could not be run: {str(e)}. "
            "You can run it manually from the import status page.",
        )

    # Redirect to status page (which will show preflight results)
    return HttpResponseRedirect(
        reverse("portfolios:import_status", args=[portfolio_import.id])
    )


@login_required
@require_http_methods(["GET"])
def import_status(request, import_id: int):
    """
    Display import status and progress.

    Shows the current status of a portfolio import, including preflight validation
    results, progress (rows processed/total), and any errors encountered.
    """
    portfolio_import = get_object_or_404(
        PortfolioImport.objects.filter(organization_id=request.org_id), id=import_id
    )

    # Get errors if any
    errors = portfolio_import.errors.all()[:20]  # Limit to first 20 errors

    # Run preflight validation if not already imported
    preflight_result = None
    if portfolio_import.status == "pending":
        try:
            with organization_context(request.org_id):
                preflight_result = preflight_portfolio_import(portfolio_import.id)
        except Exception as e:
            # Preflight failed to run (e.g., file not readable)
            preflight_result = {
                "ready": False,
                "missing_instruments": [],
                "missing_fx_rates": [],
                "missing_prices": [],
                "missing_curves": [],
                "warnings": [f"Preflight validation error: {str(e)}"],
            }

    # Determine if should auto-refresh (if status is pending or processing)
    auto_refresh = portfolio_import.status in [
        "pending",
        "parsing",
        "validating",
        "processing",
        "importing",
    ]

    return render(
        request,
        "portfolios/import_status.html",
        {
            "import": portfolio_import,
            "errors": errors,
            "auto_refresh": auto_refresh,
            "preflight_result": preflight_result,
        },
    )


@login_required
@require_http_methods(["POST"])
def run_preflight(request, import_id: int):
    """
    Run preflight validation for a portfolio import.

    POST: Run preflight and redirect back to status page with results.
    """
    portfolio_import = get_object_or_404(
        PortfolioImport.objects.filter(organization_id=request.org_id), id=import_id
    )

    try:
        with organization_context(request.org_id):
            preflight_result = preflight_portfolio_import(portfolio_import.id)
        if preflight_result["ready"]:
            messages.success(request, "Preflight validation passed. Ready to import.")
        else:
            messages.warning(
                request,
                f"Preflight validation found {len(preflight_result.get('missing_instruments', []))} "
                f"missing instruments and {len(preflight_result.get('missing_fx_rates', []))} "
                "missing FX rates.",
            )
    except Exception as e:
        messages.error(request, f"Preflight validation failed: {str(e)}")

    return HttpResponseRedirect(
        reverse("portfolios:import_status", args=[portfolio_import.id])
    )


@login_required
@require_http_methods(["POST"])
def start_import(request, import_id: int):
    """
    Start the portfolio import process.

    POST: Trigger async import task and redirect to status page.
    """
    portfolio_import = get_object_or_404(
        PortfolioImport.objects.filter(organization_id=request.org_id), id=import_id
    )

    # Only allow starting import if status is pending
    if portfolio_import.status != "pending":
        messages.error(
            request,
            f"Cannot start import: current status is '{portfolio_import.get_status_display()}'.",
        )
        return HttpResponseRedirect(
            reverse("portfolios:import_status", args=[portfolio_import.id])
        )

    # Trigger async import task
    import_portfolio_task.delay(portfolio_import.id, request.org_id)
    messages.success(request, "Import started. Processing in background...")

    return HttpResponseRedirect(
        reverse("portfolios:import_status", args=[portfolio_import.id])
    )


@login_required
@require_http_methods(["GET"])
def export_missing_instruments(request, import_id: int):
    """
    Export missing instruments as CSV for instrument import template.

    GET: Download CSV file with missing instruments formatted for import.
    """
    portfolio_import = get_object_or_404(
        PortfolioImport.objects.filter(organization_id=request.org_id), id=import_id
    )

    try:
        with organization_context(request.org_id):
            csv_content, filename = export_missing_instruments_csv(portfolio_import.id)

        response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except ValueError as e:
        messages.error(request, str(e))
        return HttpResponseRedirect(
            reverse("portfolios:import_status", args=[portfolio_import.id])
        )
    except Exception as e:
        messages.error(request, f"Failed to export missing instruments: {str(e)}")
        return HttpResponseRedirect(
            reverse("portfolios:import_status", args=[portfolio_import.id])
        )
