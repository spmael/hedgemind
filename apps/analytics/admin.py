"""
Django admin configuration for analytics models.

This module provides admin interfaces for managing valuation runs, position results,
and exposure results.
"""

from __future__ import annotations

from django.contrib import admin

from apps.analytics.models import ExposureResult, ValuationPositionResult, ValuationRun


class ValuationPositionResultInline(admin.TabularInline):
    """
    Inline admin for ValuationPositionResult model.

    Read-only inline for viewing position-level valuation results.
    """

    model = ValuationPositionResult
    extra = 0
    can_delete = False
    readonly_fields = [
        "position_snapshot",
        "market_value_original_currency",
        "market_value_base_currency",
        "fx_rate_used",
        "fx_rate_source",
        "data_quality_flags",
    ]
    fields = [
        "position_snapshot",
        "market_value_original_currency",
        "market_value_base_currency",
        "fx_rate_used",
        "fx_rate_source",
    ]
    show_change_link = False


class ExposureResultInline(admin.TabularInline):
    """
    Inline admin for ExposureResult model.

    Read-only inline for viewing exposure computation results grouped by dimension type.
    """

    model = ExposureResult
    extra = 0
    can_delete = False
    readonly_fields = ["dimension_type", "dimension_label", "value_base", "pct_total"]
    fields = ["dimension_type", "dimension_label", "value_base", "pct_total"]
    show_change_link = False


@admin.register(ValuationRun)
class ValuationRunAdmin(admin.ModelAdmin):
    """
    Admin interface for ValuationRun model.

    Provides management interface for valuation runs with read-only inline results
    and exposures.
    """

    list_display = [
        "portfolio",
        "as_of_date",
        "valuation_policy",
        "is_official",
        "status",
        "total_market_value",
        "position_count",
        "created_at",
    ]
    list_filter = [
        "organization",
        "portfolio",
        "status",
        "is_official",
        "as_of_date",
        "valuation_policy",
    ]
    search_fields = ["portfolio__name", "run_context_id"]
    readonly_fields = [
        "inputs_hash",
        "run_context_id",
        "total_market_value",
        "position_count",
        "positions_with_issues",
        "missing_fx_count",
        "log",
        "created_at",
    ]
    inlines = [ValuationPositionResultInline, ExposureResultInline]


@admin.register(ValuationPositionResult)
class ValuationPositionResultAdmin(admin.ModelAdmin):
    """
    Admin interface for ValuationPositionResult model.

    Provides read-only interface for position-level valuation results.
    """

    list_display = [
        "valuation_run",
        "position_snapshot",
        "market_value_base_currency",
        "market_value_original_currency",
        "fx_rate_used",
        "fx_rate_source",
    ]
    list_filter = [
        "valuation_run__organization",
        "valuation_run__portfolio",
        "valuation_run__as_of_date",
        "fx_rate_source",
        "data_quality_flags",
    ]
    search_fields = [
        "valuation_run__portfolio__name",
        "position_snapshot__instrument__name",
        "position_snapshot__instrument__isin",
    ]
    readonly_fields = [
        "valuation_run",
        "position_snapshot",
        "market_value_original_currency",
        "market_value_base_currency",
        "fx_rate_used",
        "fx_rate_source",
        "data_quality_flags",
    ]
    raw_id_fields = ["valuation_run", "position_snapshot"]
    ordering = ["-valuation_run__as_of_date", "valuation_run"]


@admin.register(ExposureResult)
class ExposureResultAdmin(admin.ModelAdmin):
    """
    Admin interface for ExposureResult model.

    Provides read-only interface for exposure computation results.
    """

    list_display = [
        "valuation_run",
        "dimension_type",
        "dimension_label",
        "value_base",
        "pct_total",
    ]
    list_filter = [
        "valuation_run__organization",
        "valuation_run__portfolio",
        "valuation_run__as_of_date",
        "dimension_type",
    ]
    search_fields = [
        "valuation_run__portfolio__name",
        "dimension_label",
    ]
    readonly_fields = [
        "valuation_run",
        "dimension_type",
        "dimension_label",
        "value_base",
        "pct_total",
    ]
    raw_id_fields = ["valuation_run"]
    ordering = ["-valuation_run__as_of_date", "dimension_type", "-value_base"]
