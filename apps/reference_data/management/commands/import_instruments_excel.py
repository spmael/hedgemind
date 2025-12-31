"""
Management command to import instrument master data from Excel.

Usage:
    # Import from file (must be within organization context)
    python manage.py import_instruments_excel \
        --file ./scripts/data/instruments_master.xlsx \
        --sheet Sheet1 \
        --org-id 1
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.reference_data.services.instruments.import_excel import (
    import_instruments_from_file,
)
from libs.tenant_context import organization_context


class Command(BaseCommand):
    """
    Management command for importing instrument master data from Excel files.

    This command imports instrument data from Excel files. Instruments are
    organization-scoped, so the command requires an organization context.

    Key Features:
    - Imports from Excel file directly
    - Creates/updates Instrument records within organization context
    - Validates required fields and relationships (InstrumentGroup, InstrumentType, Issuer)
    - Supports all instrument types: bonds, equities, funds, deposits
    - Handles optional fields appropriately

    Usage Example:
        python manage.py import_instruments_excel \
            --file ./scripts/data/instruments_master.xlsx \
            --sheet INSTRUMENTS \
            --org-id 1

    Note:
        This command is primarily intended for reference data team operations.
        Excel format expected:
            isin | name | ticker | instrument_group_code | instrument_type_code |
            currency | issuer_code | country | ... (see import service for full list)
    """

    help = "Import instrument master data from Excel file"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to Excel file",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default="INSTRUMENTS",
            help="Sheet name to read (default: INSTRUMENTS)",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            required=True,
            help="Organization ID (required for organization-scoped instruments)",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        file_path = options.get("file")
        org_id = options.get("org_id")

        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

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

        self.stdout.write(f"Importing instruments from file: {file_path}")
        self.stdout.write(f"Organization: {organization.name} (ID: {org_id})")
        self.stdout.write(f"Sheet: {options.get('sheet', 'INSTRUMENTS')}")
        self.stdout.write("")

        # Calculate file hash for audit
        file_hash = self._calculate_file_hash(file_path)

        # Import within organization context
        with organization_context(org_id):
            try:
                # Import
                result = import_instruments_from_file(
                    file_path=file_path,
                    sheet_name=options.get("sheet", "INSTRUMENTS"),
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created {result['created']} instruments, "
                        f"updated {result['updated']}"
                    )
                )

                # Report errors
                if result.get("errors"):
                    self.stdout.write("")
                    self.stdout.write(
                        self.style.ERROR(f"✗ {len(result['errors'])} errors:")
                    )
                    for error in result["errors"][:20]:  # Show first 20
                        self.stdout.write(f"  - {error}")
                    if len(result["errors"]) > 20:
                        self.stdout.write(
                            f"  ... and {len(result['errors']) - 20} more"
                        )

                # Create audit event
                self._create_import_audit(
                    file_path, organization, result, file_hash, actor
                )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Import failed: {str(e)}"))
                raise

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file for audit logging."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _create_import_audit(
        self,
        file_path: str,
        organization: Organization,
        result: dict,
        file_hash: str,
        actor,
    ):
        """Create audit event for import."""
        file_name = Path(file_path).name

        metadata = {
            "organization_id": organization.id,
            "organization_name": organization.name,
            "file_name": file_name,
            "file_path": file_path,
            "file_hash": file_hash,
            "instruments_created": result.get("created", 0),
            "instruments_updated": result.get("updated", 0),
            "total_rows": result.get("total_rows", 0),
            "error_count": len(result.get("errors", [])),
            "command": "import_instruments_excel",
        }

        # Add error summary (first 10 errors to avoid huge JSON)
        if result.get("errors"):
            metadata["errors_summary"] = result["errors"][:10]

        AuditEvent.objects.create(
            organization_id=organization.id,
            actor=actor,
            action="MARKETDATA_IMPORT_APPLIED",
            object_type="Instrument",
            object_id=None,  # Not a single object, but a collection
            object_repr=f"Imported instruments from {file_name}: {result.get('created', 0)} created, {result.get('updated', 0)} updated",
            metadata=metadata,
        )
