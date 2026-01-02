"""
Django admin configuration for portfolio models.

This module provides admin interfaces for managing portfolios, portfolio groups,
portfolio imports, and import errors.
"""

from __future__ import annotations

from django.contrib import admin

from apps.portfolios.models import (
    Portfolio,
    PortfolioGroup,
    PortfolioImport,
    PortfolioImportError,
    PositionSnapshot,
)


@admin.register(PortfolioGroup)
class PortfolioGroupAdmin(admin.ModelAdmin):
    """
    Admin interface for PortfolioGroup model.

    Provides management interface for portfolio groups with organization filtering.
    """

    list_display = ["name", "description", "organization", "created_at"]
    list_filter = ["organization", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    """
    Admin interface for Portfolio model.

    Provides management interface for portfolios with organization filtering and search.
    """

    list_display = [
        "name",
        "full_name",
        "base_currency",
        "group",
        "is_active",
        "organization",
    ]
    list_filter = ["organization", "group", "is_active", "base_currency"]
    search_fields = ["name", "full_name"]
    readonly_fields = ["created_at", "updated_at"]


class PortfolioImportErrorInline(admin.TabularInline):
    """
    Inline admin for PortfolioImportError model.

    Read-only inline for viewing import errors associated with a portfolio import.
    """

    model = PortfolioImportError
    extra = 0
    can_delete = False
    readonly_fields = [
        "row_number",
        "column_name",
        "error_type",
        "error_message",
        "error_code",
        "raw_row_data",
        "created_at",
    ]
    fields = [
        "row_number",
        "column_name",
        "error_type",
        "error_message",
        "error_code",
    ]
    show_change_link = False


@admin.register(PortfolioImport)
class PortfolioImportAdmin(admin.ModelAdmin):
    """
    Admin interface for PortfolioImport model.

    Provides management interface for portfolio imports with inline error viewing.
    """

    list_display = [
        "portfolio",
        "as_of_date",
        "status",
        "source_type",
        "rows_processed",
        "rows_total",
        "created_at",
    ]
    list_filter = ["organization", "portfolio", "status", "source_type", "as_of_date"]
    search_fields = ["portfolio__name"]
    readonly_fields = ["file", "inputs_hash", "created_at", "completed_at"]
    inlines = [PortfolioImportErrorInline]


@admin.register(PositionSnapshot)
class PositionSnapshotAdmin(admin.ModelAdmin):
    """
    Admin interface for PositionSnapshot model.

    Provides read-only interface for viewing position snapshots with organization filtering.
    Position snapshots are immutable and should not be edited through admin.
    """

    list_display = [
        "portfolio",
        "instrument",
        "as_of_date",
        "quantity",
        "market_value",
        "book_value",
        "valuation_method",
        "valuation_source",
        "created_at",
    ]
    list_filter = [
        "organization",
        "portfolio",
        "as_of_date",
        "valuation_method",
        "valuation_source",
        "created_at",
    ]
    search_fields = [
        "portfolio__name",
        "instrument__name",
        "instrument__isin",
        "instrument__ticker",
    ]
    readonly_fields = [
        "portfolio",
        "portfolio_import",
        "instrument",
        "quantity",
        "book_price",
        "book_value",
        "market_value",
        "price",
        "accrued_interest",
        "valuation_method",
        "valuation_source",
        "as_of_date",
        "last_valuation_date",
        "stale_after_days",
        "created_at",
        "updated_at",
    ]
    fields = [
        "portfolio",
        "portfolio_import",
        "instrument",
        "as_of_date",
        "quantity",
        "book_price",
        "book_value",
        "market_value",
        "price",
        "accrued_interest",
        "valuation_method",
        "valuation_source",
        "last_valuation_date",
        "stale_after_days",
        "created_at",
        "updated_at",
    ]
    ordering = ["-as_of_date", "portfolio", "instrument"]
