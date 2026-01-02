"""
Django admin configuration for report models.

This module provides admin interfaces for managing report templates and generated reports.
"""

from __future__ import annotations

from django.contrib import admin

from apps.reports.models import Report, ReportTemplate


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    """
    Admin interface for ReportTemplate model.

    Provides management interface for report template definitions.
    """

    list_display = [
        "name",
        "version",
        "template_type",
        "is_active",
        "organization",
        "created_at",
    ]
    list_filter = ["organization", "template_type", "is_active", "created_at"]
    search_fields = ["name", "version", "template_type"]
    readonly_fields = ["created_at"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """
    Admin interface for Report model.

    Provides management interface for generated reports.
    """

    list_display = [
        "template",
        "valuation_run",
        "status",
        "generated_at",
        "organization",
        "created_at",
    ]
    list_filter = ["organization", "status", "template", "created_at", "generated_at"]
    search_fields = ["template__name", "valuation_run__portfolio__name"]
    readonly_fields = [
        "pdf_file",
        "csv_file",
        "excel_file",
        "generated_at",
        "created_at",
    ]
