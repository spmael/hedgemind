"""
Management command to import issuer master data from Excel.

Usage:
    # Import from file (must be within organization context)
    python manage.py import_issuers_excel \
        --file ./scripts/data/issuers_master.xlsx \
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
from apps.reference_data.services.issuers.import_excel import import_issuers_from_file
from libs.command_utils import resolve_organization, resolve_user
from libs.tenant_context import organization_context


class Command(BaseCommand):
    """
    Management command for importing issuer master data from Excel files.

    This command imports issuer data (name, short_name, country, issuer_group)
    from Excel files. Issuers are organization-scoped, so the command requires
    an organization context.

    Key Features:
    - Imports from Excel file directly
    - Creates/updates Issuer records within organization context
    - Validates required fields and country codes
    - Supports organization context via --org-id

    Usage Example:
        python manage.py import_issuers_excel \
            --file ./scripts/data/issuers_master.xlsx \
            --sheet ISSUERS \
            --org-id 1

    Note:
        This command is primarily intended for reference data team operations.
        Excel format expected:
            name | short_name | country | issuer_group
    """

    help = "Import issuer master data from Excel file"

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
            default="ISSUERS",
            help="Sheet name to read (default: ISSUERS)",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            help="Organization ID (numeric)",
        )
        parser.add_argument(
            "--org-slug",
            type=str,
            help="Organization slug (e.g., 'cemac-bank')",
        )
        parser.add_argument(
            "--org-code",
            type=str,
            help="Organization code_name (e.g., 'CEMACBANK')",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )
        parser.add_argument(
            "--actor-username",
            type=str,
            help="Username of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        file_path = options.get("file")

        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        # Resolve organization from various identifier types
        organization = resolve_organization(
            org_id=options.get("org_id"),
            org_slug=options.get("org_slug"),
            org_code=options.get("org_code"),
        )

        # Resolve actor if provided
        actor = resolve_user(
            user_id=options.get("actor_id"),
            username=options.get("actor_username"),
        )
        if options.get("actor_id") or options.get("actor_username"):
            if actor is None:
                self.stdout.write(
                    self.style.WARNING(
                        "Actor not found. Proceeding without actor for audit log."
                    )
                )

        self.stdout.write(f"Importing issuers from file: {file_path}")
        self.stdout.write(f"Organization: {organization.name} (ID: {organization.id})")
        self.stdout.write(f"Sheet: {options.get('sheet', 'ISSUERS')}")
        self.stdout.write("")

        # Calculate file hash for audit
        file_hash = self._calculate_file_hash(file_path)

        # Import within organization context
        with organization_context(organization.id):
            try:
                # Import
                result = import_issuers_from_file(
                    file_path=file_path,
                    sheet_name=options.get("sheet", "ISSUERS"),
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created {result['created']} issuers, "
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
            "issuers_created": result.get("created", 0),
            "issuers_updated": result.get("updated", 0),
            "total_rows": result.get("total_rows", 0),
            "error_count": len(result.get("errors", [])),
            "command": "import_issuers_excel",
        }

        # Add error summary (first 10 errors to avoid huge JSON)
        if result.get("errors"):
            metadata["errors_summary"] = result["errors"][:10]

        AuditEvent.objects.create(
            organization_id=organization.id,
            actor=actor,
            action="MARKETDATA_IMPORT_APPLIED",
            object_type="Issuer",
            object_id=None,  # Not a single object, but a collection
            object_repr=f"Imported issuers from {file_name}: {result.get('created', 0)} created, {result.get('updated', 0)} updated",
            metadata=metadata,
        )
