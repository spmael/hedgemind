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
