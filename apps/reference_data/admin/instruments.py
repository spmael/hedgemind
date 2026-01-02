"""
Admin interfaces for instrument models.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from django.contrib import admin, messages
from django.http import HttpResponse

from apps.reference_data.models.instruments import (
    Instrument,
    InstrumentGroup,
    InstrumentType,
)


@admin.register(InstrumentGroup)
class InstrumentGroupAdmin(admin.ModelAdmin):
    """
    Admin interface for InstrumentGroup model.

    Provides management interface for instrument groups (global taxonomy).
    """

    list_display = ["name", "description", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]


class InstrumentTypeInline(admin.TabularInline):
    """Inline admin for InstrumentType within InstrumentGroup."""

    model = InstrumentType
    extra = 0
    fields = ["name", "description"]


@admin.register(InstrumentType)
class InstrumentTypeAdmin(admin.ModelAdmin):
    """
    Admin interface for InstrumentType model.

    Provides management interface for instrument types within groups.
    """

    list_display = ["name", "group", "description", "created_at"]
    list_filter = ["group", "created_at"]
    search_fields = ["name", "description", "group__name"]
    raw_id_fields = ["group"]


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    """
    Admin interface for Instrument model.

    Provides management interface for financial instruments (organization-scoped).
    Supports bulk export to Excel template format.
    """

    list_display = [
        "name",
        "isin",
        "ticker",
        "instrument_group",
        "instrument_type",
        "currency",
        "issuer",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "organization",
        "instrument_group",
        "instrument_type",
        "currency",
        "valuation_method",
        "is_active",
        "created_at",
    ]
    search_fields = ["name", "isin", "ticker", "issuer__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["organization", "issuer", "instrument_group", "instrument_type"]
    actions = ["export_to_excel_template"]

    @admin.action(description="Export selected instruments to Excel template")
    def export_to_excel_template(self, request, queryset):
        """Export selected instruments to Excel template format."""
        if not queryset.exists():
            self.message_user(request, "No instruments selected.", messages.WARNING)
            return

        # Prepare data in template format
        data = []
        for instrument in queryset.select_related(
            "instrument_group", "instrument_type", "issuer"
        ):
            data.append(
                {
                    "instrument_identifier": instrument.isin or instrument.ticker or "",
                    "name": instrument.name or "",
                    "instrument_group_code": (
                        instrument.instrument_group.name
                        if instrument.instrument_group
                        else ""
                    ),
                    "instrument_type_code": (
                        instrument.instrument_type.name
                        if instrument.instrument_type
                        else ""
                    ),
                    "currency": instrument.currency or "",
                    "issuer_code": (
                        instrument.issuer.short_name if instrument.issuer else ""
                    ),
                    "valuation_method": instrument.valuation_method or "",
                    "isin": instrument.isin or "",
                    "ticker": instrument.ticker or "",
                    "country": instrument.country or "",
                    "sector": instrument.sector or "",
                }
            )

        df = pd.DataFrame(data)

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Instruments", index=False)

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="instruments_export.xlsx"'
        )
        return response

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "organization",
                    "name",
                    "isin",
                    "ticker",
                    "instrument_group",
                    "instrument_type",
                )
            },
        ),
        (
            "Issuer & Location",
            {"fields": ("issuer", "country", "sector", "currency")},
        ),
        (
            "Bond Details",
            {
                "fields": (
                    "maturity_date",
                    "coupon_rate",
                    "coupon_frequency",
                    "face_value",
                    "amortization_method",
                    "first_listing_date",
                    "last_coupon_date",
                    "next_coupon_date",
                    "original_offering_amount",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Equity/Fund Details",
            {
                "fields": (
                    "units_outstanding",
                    "fund_category",
                    "fund_launch_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Valuation",
            {"fields": ("valuation_method", "is_active")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
