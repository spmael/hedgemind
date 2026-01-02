"""
Admin interfaces for instrument price models.
"""

from __future__ import annotations

import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html

from apps.reference_data.models.prices import (
    InstrumentPrice,
    InstrumentPriceImport,
    InstrumentPriceObservation,
)


@admin.register(InstrumentPriceObservation)
class InstrumentPriceObservationAdmin(admin.ModelAdmin):
    """
    Admin interface for InstrumentPriceObservation model.

    Provides read-only interface for raw price observations.
    """

    list_display = [
        "instrument",
        "date",
        "price",
        "source",
        "created_at",
    ]
    list_filter = ["source", "date", "created_at"]
    search_fields = ["instrument__name", "instrument__isin", "instrument__ticker"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["instrument", "source"]
    ordering = ["-date", "instrument"]


@admin.register(InstrumentPrice)
class InstrumentPriceAdmin(admin.ModelAdmin):
    """
    Admin interface for InstrumentPrice model.

    Provides management interface for canonical instrument prices.
    """

    list_display = [
        "instrument",
        "date",
        "price",
        "chosen_source",
        "selection_reason",
        "created_at",
    ]
    list_filter = ["chosen_source", "selection_reason", "date", "created_at"]
    search_fields = ["instrument__name", "instrument__isin", "instrument__ticker"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["instrument", "chosen_source"]
    ordering = ["-date", "instrument"]


@admin.register(InstrumentPriceImport)
class InstrumentPriceImportAdmin(admin.ModelAdmin):
    """
    Admin interface for InstrumentPriceImport model.

    Provides management interface for price import tracking with enhanced
    status display, error viewing, and metrics.
    """

    list_display = [
        "file_name_display",
        "source",
        "status_display",
        "observations_summary",
        "created_by",
        "created_at",
        "completed_at",
    ]
    list_filter = ["status", "source", "created_at", "completed_at"]
    search_fields = ["file__name", "source__code", "source__name"]
    readonly_fields = [
        "file",
        "file_name_display",
        "source",
        "sheet_name",
        "status",
        "status_display",
        "error_message",
        "error_message_display",
        "observations_created",
        "observations_updated",
        "canonical_prices_created",
        "created_by",
        "created_at",
        "completed_at",
    ]
    fieldsets = (
        (
            "Import Information",
            {
                "fields": (
                    "file",
                    "file_name_display",
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
                    "canonical_prices_created",
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
        response["Content-Disposition"] = 'attachment; filename="import_errors.csv"'

        writer = csv.writer(response)
        writer.writerow(["Import ID", "File Name", "Source", "Status", "Error Message"])

        for import_obj in imports_with_errors:
            file_name = import_obj.file.name.split("/")[-1] if import_obj.file else "-"
            writer.writerow(
                [
                    import_obj.id,
                    file_name,
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
