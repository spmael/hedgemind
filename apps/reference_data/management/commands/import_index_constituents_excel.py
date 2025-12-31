"""
Management command to import market index constituent data from Excel.

Usage:
    # Import from file
    python manage.py import_index_constituents_excel \
        --file ./scripts/data/bvmac_constituents.xlsx \
        --source-code BVMAC \
        --sheet CONSTITUENTS
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.audit.models import AuditEvent
from apps.reference_data.models import MarketDataSource
from apps.reference_data.services.indices.import_constituents_excel import (
    import_index_constituents_from_file,
)


class Command(BaseCommand):
    """
    Management command for importing market index constituent data from Excel files.

    This command imports constituent data (which instruments are in an index and their weights)
    from Excel files. Unlike index levels, constituents don't have a separate import record model
    since they're simpler reference data.

    Key Features:
    - Imports from Excel file directly
    - Validates weight sums per index/date (~100% ±0.5% tolerance)
    - Creates/updates MarketIndexConstituent records
    - Supports instrument lookup by ISIN or ticker

    Usage Example:
        python manage.py import_index_constituents_excel \
            --file ./scripts/data/bvmac_constituents.xlsx \
            --source-code BVMAC \
            --sheet CONSTITUENTS

    Note:
        This command is primarily intended for reference data team operations.
        Excel format expected:
            as_of_date | index_code | instrument_id | weight | shares | float_shares
    """

    help = "Import market index constituent data from Excel file"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to Excel file",
        )
        parser.add_argument(
            "--source-code",
            type=str,
            default="BVMAC",
            help="MarketDataSource code (default: BVMAC)",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default="CONSTITUENTS",
            help="Sheet name to read (default: CONSTITUENTS)",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        file_path = options.get("file")

        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        # Get source
        source_code = options.get("source_code", "BVMAC")
        try:
            source = MarketDataSource.objects.get(code=source_code)
        except MarketDataSource.DoesNotExist:
            raise CommandError(f"MarketDataSource with code='{source_code}' not found")

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

        self.stdout.write(f"Importing constituents from file: {file_path}")
        self.stdout.write(
            f"Source: {source.name} ({source.code}, priority={source.priority})"
        )
        self.stdout.write(f"Sheet: {options.get('sheet', 'CONSTITUENTS')}")
        self.stdout.write("")

        # Calculate file hash for audit
        file_hash = self._calculate_file_hash(file_path)

        try:
            # Import
            result = import_index_constituents_from_file(
                file_path=file_path,
                source=source,
                sheet_name=options.get("sheet", "CONSTITUENTS"),
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created {result['created']} constituents, "
                    f"updated {result['updated']}"
                )
            )

            # Report weight validation warnings
            if result.get("weight_validation_errors"):
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ Weight validation warnings ({len(result['weight_validation_errors'])}):"
                    )
                )
                for error in result["weight_validation_errors"][:10]:  # Show first 10
                    self.stdout.write(f"  - {error}")
                if len(result["weight_validation_errors"]) > 10:
                    self.stdout.write(
                        f"  ... and {len(result['weight_validation_errors']) - 10} more"
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
                    self.stdout.write(f"  ... and {len(result['errors']) - 20} more")

            # Create audit event
            self._create_import_audit(file_path, source, result, file_hash, actor)

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
        source: MarketDataSource,
        result: dict,
        file_hash: str,
        actor,
    ):
        """Create audit event for import."""
        file_name = Path(file_path).name

        metadata = {
            "source_code": source.code,
            "source_name": source.name,
            "file_name": file_name,
            "file_path": file_path,
            "file_hash": file_hash,
            "constituents_created": result.get("created", 0),
            "constituents_updated": result.get("updated", 0),
            "total_rows": result.get("total_rows", 0),
            "error_count": len(result.get("errors", [])),
            "weight_validation_warnings": len(
                result.get("weight_validation_errors", [])
            ),
            "command": "import_index_constituents_excel",
        }

        # Add error summary (first 10 errors to avoid huge JSON)
        if result.get("errors"):
            metadata["errors_summary"] = result["errors"][:10]

        # Add weight validation summary
        if result.get("weight_validation_errors"):
            metadata["weight_validation_summary"] = result["weight_validation_errors"][
                :10
            ]

        AuditEvent.objects.create(
            organization_id=None,  # Global reference data
            actor=actor,
            action="MARKETDATA_IMPORT_APPLIED",
            object_type="MarketIndexConstituent",
            object_id=None,  # Not a single object, but a collection
            object_repr=f"Imported constituents from {file_name}: {result.get('created', 0)} created, {result.get('updated', 0)} updated",
            metadata=metadata,
        )
