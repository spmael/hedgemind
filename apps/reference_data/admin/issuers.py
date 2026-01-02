"""
Admin interfaces for issuer models.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from django.contrib import admin, messages
from django.http import HttpResponse

from apps.reference_data.models.issuers import Issuer, IssuerRating


class IssuerRatingInline(admin.TabularInline):
    """Inline admin for IssuerRating within Issuer."""

    model = IssuerRating
    extra = 0
    fields = ["agency", "rating", "date_assigned", "is_active"]
    readonly_fields = ["created_at"]


@admin.register(Issuer)
class IssuerAdmin(admin.ModelAdmin):
    """
    Admin interface for Issuer model.

    Provides management interface for issuers (organization-scoped).
    Supports bulk export to Excel template format.
    """

    list_display = [
        "name",
        "short_name",
        "country",
        "issuer_group",
        "is_active",
        "created_at",
    ]
    list_filter = ["organization", "country", "issuer_group", "is_active", "created_at"]
    search_fields = ["name", "short_name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["organization"]
    inlines = [IssuerRatingInline]
    actions = ["export_to_excel_template"]

    @admin.action(description="Export selected issuers to Excel template")
    def export_to_excel_template(self, request, queryset):
        """Export selected issuers to Excel template format."""
        if not queryset.exists():
            self.message_user(request, "No issuers selected.", messages.WARNING)
            return

        # Prepare data in template format
        data = []
        for issuer in queryset:
            data.append(
                {
                    "name": issuer.name or "",
                    "short_name": issuer.short_name or "",
                    "country": issuer.country or "",
                    "issuer_group": issuer.issuer_group or "",
                }
            )

        df = pd.DataFrame(data)

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Issuers", index=False)

        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="issuers_export.xlsx"'
        return response


@admin.register(IssuerRating)
class IssuerRatingAdmin(admin.ModelAdmin):
    """
    Admin interface for IssuerRating model.

    Provides management interface for issuer credit ratings.
    """

    list_display = [
        "issuer",
        "agency",
        "rating",
        "date_assigned",
        "is_active",
        "created_at",
    ]
    list_filter = ["agency", "is_active", "date_assigned", "created_at"]
    search_fields = ["issuer__name", "rating"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["issuer"]
    ordering = ["-date_assigned", "agency"]
