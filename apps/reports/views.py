"""
Views for report operations.

This module provides views for listing and downloading reports.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.reports.models import Report


@login_required
@require_http_methods(["GET"])
def reports_list(request):
    """
    List all reports for the current organization.

    Displays a table of all reports with download links for PDF/CSV/Excel.
    """
    org_id = getattr(request, "org_id", None)
    if not org_id:
        # Return empty queryset if no org context
        reports = Report.objects.none()
    else:
        reports = (
            Report.objects.filter(organization_id=org_id)
            .select_related("valuation_run__portfolio", "template")
            .order_by("-created_at")
        )

    # Optional: Filter by portfolio if provided
    portfolio_id = request.GET.get("portfolio")
    if portfolio_id:
        try:
            reports = reports.filter(valuation_run__portfolio_id=int(portfolio_id))
        except ValueError:
            pass  # Invalid portfolio ID, ignore filter

    # Optional: Get portfolios for filter dropdown
    from apps.portfolios.models import Portfolio

    portfolios = Portfolio.objects.filter(is_active=True).order_by("name")

    return render(
        request,
        "reports/list.html",
        {
            "reports": reports,
            "portfolios": portfolios,
            "selected_portfolio_id": portfolio_id,
        },
    )


@login_required
@require_http_methods(["GET"])
def download_report(request, report_id: int, file_type: str):
    """
    Download a report file (PDF, CSV, or Excel).

    Serves the requested file type if available for the report.
    """
    org_id = getattr(request, "org_id", None)
    if not org_id:
        raise Http404("No organization context available.")

    report = get_object_or_404(
        Report.objects.filter(organization_id=org_id), id=report_id
    )

    # Determine which file to serve based on file_type
    file_field = None
    content_type = None
    filename = None

    if file_type == "pdf":
        if not report.pdf_file:
            raise Http404("PDF file not available for this report.")
        file_field = report.pdf_file
        content_type = "application/pdf"
        filename = f"report_{report.id}.pdf"
    elif file_type == "csv":
        if not report.csv_file:
            raise Http404("CSV file not available for this report.")
        file_field = report.csv_file
        content_type = "text/csv"
        filename = f"report_{report.id}.csv"
    elif file_type == "excel":
        if not report.excel_file:
            raise Http404("Excel file not available for this report.")
        file_field = report.excel_file
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"report_{report.id}.xlsx"
    else:
        raise Http404("Invalid file type. Use 'pdf', 'csv', or 'excel'.")

    # Open and serve the file
    try:
        response = HttpResponse(file_field.read(), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        raise Http404(f"Error reading file: {str(e)}")
