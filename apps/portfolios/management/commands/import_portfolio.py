"""
Management command to import portfolio positions from file.

Usage:
    # Import portfolio from existing PortfolioImport record
    python manage.py import_portfolio \
        --portfolio-import-id=123 \
        --org-id=1 \
        --actor-id=5
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.portfolios.ingestion.import_excel import import_portfolio_from_file
from apps.portfolios.models import PortfolioImport
from libs.tenant_context import organization_context


class Command(BaseCommand):
    """
    Management command for importing portfolio positions from file.

    This command triggers the import of portfolio positions from a previously
    uploaded file by executing the import service on an existing PortfolioImport
    record. The command requires organization context and can optionally record
    an actor for audit purposes.

    Key Features:
    - Executes import on existing PortfolioImport record
    - Creates audit events tracking who ran the import
    - Displays detailed import results (created, errors, status)
    - Handles errors gracefully with audit logging

    Usage Example:
        python manage.py import_portfolio \
            --portfolio-import-id=123 \
            --org-id=1 \
            --actor-id=5

    Note:
        The PortfolioImport record must already exist (typically created via
        file upload in UI or another process). This command executes the import
        service function on that record.
    """

    help = "Import portfolio positions from file (execute import on PortfolioImport record)"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--portfolio-import-id",
            type=int,
            required=True,
            help="ID of PortfolioImport record to process",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            required=True,
            help="Organization ID (required for organization context)",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        portfolio_import_id = options.get("portfolio_import_id")
        org_id = options.get("org_id")

        # Validate organization exists
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization with id={org_id} not found")

        # Get actor if provided
        actor = None
        actor_id = options.get("actor_id")
        if actor_id:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                actor = User.objects.get(pk=actor_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"User with ID {actor_id} does not exist, proceeding without actor"
                    )
                )

        # Validate PortfolioImport exists and belongs to organization
        # Use _base_manager to bypass organization context filtering for validation
        try:
            portfolio_import = PortfolioImport._base_manager.filter(
                id=portfolio_import_id, organization_id=org_id
            ).first()
            if not portfolio_import:
                # Try without filter to see if it exists at all
                if not PortfolioImport._base_manager.filter(
                    id=portfolio_import_id
                ).exists():
                    raise CommandError(
                        f"PortfolioImport with id={portfolio_import_id} not found"
                    )
                else:
                    raise CommandError(
                        f"PortfolioImport {portfolio_import_id} does not belong to organization {org_id}"
                    )
        except Exception as e:
            if isinstance(e, CommandError):
                raise
            raise CommandError(f"Error validating PortfolioImport: {str(e)}")

        # Display initial information
        file_name = (
            Path(portfolio_import.file.name).name
            if portfolio_import.file
            else "Unknown"
        )
        self.stdout.write(
            f"Importing portfolio positions from PortfolioImport {portfolio_import_id}"
        )
        self.stdout.write(f"Organization: {organization.name} (ID: {org_id})")
        self.stdout.write(
            f"Portfolio: {portfolio_import.portfolio.name} (ID: {portfolio_import.portfolio.id})"
        )
        self.stdout.write(f"File: {file_name}")
        self.stdout.write(f"As-of Date: {portfolio_import.as_of_date}")
        self.stdout.write("")

        # Import within organization context
        with organization_context(org_id):
            try:
                # Execute import
                result = import_portfolio_from_file(portfolio_import_id)

                # Display results
                status_display = result.get("status", "UNKNOWN").upper()
                if status_display == "SUCCESS":
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Import completed successfully: {result.get('created', 0)} positions created"
                        )
                    )
                elif status_display == "PARTIAL":
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ Import completed with errors: {result.get('created', 0)} positions created, "
                            f"{result.get('errors', 0)} errors"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Import failed: {result.get('errors', 0)} errors, "
                            f"{result.get('created', 0)} positions created"
                        )
                    )

                self.stdout.write(f"  Total rows: {result.get('total_rows', 0)}")
                self.stdout.write(f"  Created: {result.get('created', 0)}")
                self.stdout.write(f"  Errors: {result.get('errors', 0)}")
                self.stdout.write(f"  Status: {result.get('status', 'UNKNOWN')}")

                # Show error details if any
                if result.get("errors", 0) > 0:
                    # Reload portfolio_import to get updated error info
                    portfolio_import.refresh_from_db()
                    if portfolio_import.error_message:
                        self.stdout.write("")
                        self.stdout.write(self.style.WARNING("Error summary:"))
                        self.stdout.write(f"  {portfolio_import.error_message}")

                    # Show individual errors (first 20)
                    errors = portfolio_import.errors.all()[:20]
                    if errors:
                        self.stdout.write("")
                        self.stdout.write(self.style.ERROR("First errors:"))
                        for error in errors:
                            self.stdout.write(
                                f"  Row {error.row_number}: [{error.error_type}] {error.error_message}"
                            )
                        total_errors = portfolio_import.errors.count()
                        if total_errors > 20:
                            self.stdout.write(
                                f"  ... and {total_errors - 20} more errors"
                            )

                # Create audit event
                self._create_import_audit(portfolio_import, organization, result, actor)

            except Exception as e:
                error_message = str(e)
                self.stdout.write(self.style.ERROR(f"✗ Import failed: {error_message}"))

                # Create audit event even on failure
                self._create_import_audit(
                    portfolio_import,
                    organization,
                    {"status": "FAILED", "errors": 1, "created": 0, "total_rows": 0},
                    actor,
                    error_message=error_message,
                )

                raise CommandError(f"Portfolio import failed: {error_message}")

    def _create_import_audit(
        self,
        portfolio_import: PortfolioImport,
        organization: Organization,
        result: dict,
        actor,
        error_message: str | None = None,
    ):
        """
        Create audit event for portfolio import.

        Args:
            portfolio_import: The PortfolioImport record.
            organization: The Organization record.
            result: Result dictionary from import_portfolio_from_file().
            actor: User object who ran the command (or None).
            error_message: Error message if import failed (optional).
        """
        # Get file information
        file_name = (
            Path(portfolio_import.file.name).name
            if portfolio_import.file
            else "Unknown"
        )
        file_path = portfolio_import.file.path if portfolio_import.file else None

        # Build metadata
        metadata = {
            "organization_id": organization.id,
            "organization_name": organization.name,
            "portfolio_import_id": portfolio_import.id,
            "portfolio_id": portfolio_import.portfolio.id,
            "portfolio_name": portfolio_import.portfolio.name,
            "file_name": file_name,
            "as_of_date": str(portfolio_import.as_of_date),
            "created": result.get("created", 0),
            "errors": result.get("errors", 0),
            "total_rows": result.get("total_rows", 0),
            "status": result.get("status", "UNKNOWN"),
            "command": "import_portfolio",
        }

        # Add file path if accessible
        if file_path:
            try:
                # Only include path if file exists
                if portfolio_import.file.storage.exists(portfolio_import.file.name):
                    metadata["file_path"] = file_path
            except Exception:
                # If we can't determine file path, skip it
                pass

        # Add error message if provided
        if error_message:
            metadata["error_message"] = error_message

        # Build object representation
        status_str = result.get("status", "UNKNOWN").upper()
        object_repr = (
            f"Portfolio import from {file_name} "
            f"(Portfolio: {portfolio_import.portfolio.name}, "
            f"As-of: {portfolio_import.as_of_date}): "
            f"{result.get('created', 0)} positions created, "
            f"{result.get('errors', 0)} errors, status: {status_str}"
        )

        AuditEvent.objects.create(
            organization_id=organization.id,
            actor=actor,
            action="PORTFOLIO_IMPORT_EXECUTED",
            object_type="PortfolioImport",
            object_id=portfolio_import.id,
            object_repr=object_repr,
            metadata=metadata,
        )
