"""
Admin interfaces for market index models.
"""

from __future__ import annotations

import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html

from apps.reference_data.models.indices import (
    MarketIndex,
    MarketIndexConstituent,
    MarketIndexImport,
    MarketIndexValue,
    MarketIndexValueObservation,
)


@admin.register(MarketIndex)
class MarketIndexAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketIndex model.

    Provides management interface for market index definitions.
    """

    list_display = ["name", "code", "currency", "is_active", "created_at"]
    list_filter = ["currency", "is_active", "created_at"]
    search_fields = ["name", "code"]
    readonly_fields = ["created_at"]


@admin.register(MarketIndexConstituent)
class MarketIndexConstituentAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketIndexConstituent model.

    Provides management interface for index constituents.
    """

    list_display = [
        "index",
        "instrument",
        "weight",
        "as_of_date",
        "created_at",
    ]
    list_filter = ["index", "as_of_date", "created_at"]
    search_fields = ["index__name", "instrument__name", "instrument__isin"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["index", "instrument"]
    ordering = ["-as_of_date", "index", "-weight"]


@admin.register(MarketIndexValueObservation)
class MarketIndexValueObservationAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketIndexValueObservation model.

    Provides read-only interface for raw index value observations.
    """

    list_display = [
        "index",
        "date",
        "value",
        "source",
        "created_at",
    ]
    list_filter = ["index", "source", "date", "created_at"]
    search_fields = ["index__name", "index__code"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["index", "source"]
    ordering = ["-date", "index"]


@admin.register(MarketIndexValue)
class MarketIndexValueAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketIndexValue model.

    Provides management interface for canonical index values.
    """

    list_display = [
        "index",
        "date",
        "value",
        "chosen_source",
        "selection_reason",
        "created_at",
    ]
    list_filter = ["index", "chosen_source", "date", "created_at"]
    search_fields = ["index__name", "index__code"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["index", "chosen_source"]
    ordering = ["-date", "index"]


@admin.register(MarketIndexImport)
class MarketIndexImportAdmin(admin.ModelAdmin):
    """
    Admin interface for MarketIndexImport model.

    Provides management interface for index import tracking with enhanced
    status display, error viewing, and metrics.
    """

    list_display = [
        "file_name_display",
        "index",
        "source",
        "status_display",
        "observations_summary",
        "created_by",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "index", "source", "created_at", "completed_at"]
    search_fields = [
        "file__name",
        "index__name",
        "index__code",
        "source__code",
        "source__name",
    ]
    readonly_fields = [
        "file",
        "file_name_display",
        "index",
        "source",
        "sheet_name",
        "status",
        "status_display",
        "error_message",
        "error_message_display",
        "observations_created",
        "observations_updated",
        "canonical_values_created",
        "created_by",
        "created_at",
        "completed_at",
    ]
    raw_id_fields = ["index", "source"]
    fieldsets = (
        (
            "Import Information",
            {
                "fields": (
                    "file",
                    "file_name_display",
                    "index",
                    "source",
                    "sheet_name",
                )
            },
        ),
        (
            "Status & Results",
            {
                "fields": (
                    "status",
                    "status_display",
                    "observations_created",
                    "observations_updated",
                    "canonical_values_created",
                )
            },
        ),
        (
            "Error Information",
            {
                "fields": ("error_message", "error_message_display"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )
    actions = ["export_errors_action", "mark_as_processed_action"]

    @admin.display(description="File Name")
    def file_name_display(self, obj):
        """Display file name from file field."""
        if obj.file:
            return obj.file.name.split("/")[-1]
        return "-"

    @admin.display(description="Status")
    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            "pending": "#FFA500",  # Orange
            "importing": "#1E90FF",  # Blue
            "success": "#32CD32",  # Green
            "failed": "#DC143C",  # Red
            "partial": "#FFD700",  # Gold
        }
        color = status_colors.get(obj.status, "#808080")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Observations")
    def observations_summary(self, obj):
        """Display summary of observations created/updated."""
        if obj.observations_created == 0 and obj.observations_updated == 0:
            return "-"
        return (
            f"Created: {obj.observations_created}, Updated: {obj.observations_updated}"
        )

    @admin.display(description="Error Message")
    def error_message_display(self, obj):
        """Display error message with formatting."""
        if not obj.error_message:
            return "-"
        return format_html(
            '<pre style="white-space: pre-wrap;">{}</pre>', obj.error_message
        )

    @admin.action(description="Export errors to CSV")
    def export_errors_action(self, request, queryset):
        """Export error messages from selected imports to CSV."""
        imports_with_errors = queryset.exclude(error_message__isnull=True).exclude(
            error_message=""
        )
        if not imports_with_errors.exists():
            self.message_user(request, "No errors to export.", messages.WARNING)
            return

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="index_import_errors.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Import ID",
                "File Name",
                "Market Index",
                "Source",
                "Status",
                "Error Message",
            ]
        )

        for import_obj in imports_with_errors:
            file_name = import_obj.file.name.split("/")[-1] if import_obj.file else "-"
            writer.writerow(
                [
                    import_obj.id,
                    file_name,
                    import_obj.index.name if import_obj.index else "-",
                    import_obj.source.code if import_obj.source else "-",
                    import_obj.get_status_display(),
                    import_obj.error_message,
                ]
            )

        return response

    @admin.action(description="Mark selected imports as processed")
    def mark_as_processed_action(self, request, queryset):
        """Manually mark selected imports as processed."""
        from libs.choices import ImportStatus

        updated = queryset.update(status=ImportStatus.SUCCESS)
        self.message_user(
            request, f"Marked {updated} import(s) as processed.", messages.SUCCESS
        )
