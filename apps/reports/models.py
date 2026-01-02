"""
Report generation models.

This module provides models for report templates and generated reports. Reports
are generated from valuation runs and stored as PDF, CSV, and Excel files.

Key components:
- ReportTemplate: Report template definitions
- ReportStatus: Status choices for report generation
- Report: Generated report instance with file storage
"""

from __future__ import annotations

from django.db import models
from django.db.models import UniqueConstraint
from django.utils.translation import gettext_lazy as _

from apps.analytics.models import ValuationRun
from libs.models import OrganizationOwnedModel


class ReportStatus(models.TextChoices):
    """
    Report status choices for report generation.

    Status flow: PENDING → GENERATING → SUCCESS / FAILED
    """

    PENDING = "pending", _("Pending")
    GENERATING = "generating", _("Generating")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")


class ReportTemplate(OrganizationOwnedModel):
    """
    ReportTemplate model representing a report template definition.

    Templates define the structure, layout, and configuration for generating reports.
    Each template can have multiple versions, allowing for template evolution while
    maintaining backward compatibility.

    Attributes:
        name (str): Template name (e.g., "Portfolio Overview v1").
        version (str): Version identifier (e.g., "1.0", "v1").
        template_type (str): Type of template ('portfolio_overview', etc.).
        config_json (dict): Template configuration (sections, layouts, etc.).
        is_active (bool): Whether this template is currently active.
        created_at (datetime): When the template was created.

    Example:
        >>> template = ReportTemplate.objects.create(
        ...     name="Portfolio Overview v1",
        ...     version="1.0",
        ...     template_type="portfolio_overview",
        ...     config_json={"sections": ["overview", "exposures", "concentration"]}
        ... )
    """

    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text="Template name (e.g., 'Portfolio Overview v1').",
    )
    version = models.CharField(
        _("Version"), max_length=50, help_text="Version identifier (e.g., '1.0', 'v1')."
    )
    template_type = models.CharField(
        _("Template Type"),
        max_length=50,
        help_text="Type of template (e.g., 'portfolio_overview').",
    )
    config_json = models.JSONField(
        _("Configuration JSON"),
        default=dict,
        blank=True,
        help_text="Template configuration (sections, layouts, etc.).",
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text="Whether this template is currently active.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Report Template")
        verbose_name_plural = _("Report Templates")
        ordering = ["name", "-version"]
        indexes = [
            models.Index(fields=["organization", "template_type", "is_active"]),
            models.Index(fields=["organization", "name", "version"]),
        ]
        # One template per name/version per organization
        constraints = [
            UniqueConstraint(
                fields=["organization", "name", "version"],
                name="uniq_report_template_org_name_version",
            ),
        ]

    def __str__(self) -> str:
        """String representation of the report template."""
        return f"{self.name} (v{self.version})"


class Report(OrganizationOwnedModel):
    """
    Report model representing a generated report instance.

    Stores metadata and file references for generated reports. Reports are linked
    to valuation runs and use report templates. Files (PDF, CSV, Excel) are stored
    in S3-compatible storage for scalability and auditability.

    Attributes:
        valuation_run (ValuationRun): The valuation run this report is based on.
        template (ReportTemplate): The template used to generate this report.
        status (str): Current generation status (pending, generating, success, failed).
        pdf_file (FileField): Generated PDF file.
        csv_file (FileField, optional): Generated CSV file.
        excel_file (FileField, optional): Generated Excel file.
        generated_at (datetime, optional): When the report was generated.
        error_message (str, optional): Error message if generation failed.

    Example:
        >>> run = ValuationRun.objects.get(id=1)
        >>> template = ReportTemplate.objects.get(name="Portfolio Overview v1")
        >>> report = Report.objects.create(
        ...     valuation_run=run,
        ...     template=template,
        ...     status=ReportStatus.PENDING
        ... )
    """

    valuation_run = models.ForeignKey(
        ValuationRun,
        on_delete=models.CASCADE,
        related_name="reports",
        help_text="Valuation run this report is based on.",
    )
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.PROTECT,
        related_name="reports",
        help_text="Template used to generate this report.",
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        help_text="Current generation status.",
    )
    pdf_file = models.FileField(
        _("PDF File"),
        upload_to="reports/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Generated PDF file.",
    )
    csv_file = models.FileField(
        _("CSV File"),
        upload_to="reports/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Generated CSV file.",
    )
    excel_file = models.FileField(
        _("Excel File"),
        upload_to="reports/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Generated Excel file.",
    )
    generated_at = models.DateTimeField(
        _("Generated At"),
        blank=True,
        null=True,
        help_text="When the report was generated.",
    )
    error_message = models.TextField(
        _("Error Message"),
        blank=True,
        null=True,
        help_text="Error message if generation failed.",
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "valuation_run"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "template"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self) -> str:
        """String representation of the report."""
        return (
            f"{self.template.name} - {self.valuation_run} ({self.get_status_display()})"
        )
