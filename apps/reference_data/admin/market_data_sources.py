"""
Admin interfaces for market data source models.
"""

from __future__ import annotations

from django.contrib import admin

from apps.reference_data.models.market_data import (
    MarketDataSource,
    MarketDataSourcePriority,
)


@admin.register(MarketDataSource)
class MarketDataSourceAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketDataSource model.

    Provides management interface for market data sources and their priority hierarchy.
    """

    list_display = ["code", "name", "priority", "source_type", "is_active"]
    list_filter = ["source_type", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["priority", "code"]
    list_editable = ["priority", "is_active"]


@admin.register(MarketDataSourcePriority)
class MarketDataSourcePriorityAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketDataSourcePriority model.

    Provides management interface for organization-specific market data source
    priority overrides.
    """

    list_display = ["organization", "data_type", "source", "priority", "created_at"]
    list_filter = ["organization", "data_type", "source"]
    search_fields = ["organization__name", "source__code", "source__name"]
    ordering = ["organization", "data_type", "priority"]
    list_editable = ["priority"]
    raw_id_fields = ["organization", "source"]
