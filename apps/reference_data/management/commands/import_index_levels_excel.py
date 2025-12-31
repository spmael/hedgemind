"""
Management command to import market index level data from Excel.

Supports two modes:
1. One-time backfill: --file path/to/file.xlsx (copies to media, creates import record)
2. From import record: --import-id 123 (reads from stored file)

Usage:
    # One-time backfill (for historical data)
    python manage.py import_index_levels_excel \
        --file ./scripts/data/bvmac_index_levels.xlsx \
        --source-code BVMAC \
        --sheet INDEX_LEVELS \
        --canonicalize
    
    # From import record (normal workflow)
    python manage.py import_index_levels_excel \
        --import-id 123 \
        --canonicalize
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.reference_data.models import MarketDataSource, MarketIndexImport
from apps.reference_data.services.indices.canonicalize import canonicalize_index_values
from apps.reference_data.services.indices.import_excel import (
    import_index_levels_from_import_record,
)
from libs.choices import ImportStatus


class Command(BaseCommand):
    """
    Management command for importing market index level data from Excel files.

    This command supports both historical backfill (one-time upload via local file) and 
    regular ingestion (via MarketIndexImport records referencing files in media storage).

    Key Features:
    - One-time backfill mode: Copies Excel from local path into media storage and creates an import record.
    - Import record mode: Imports using a previously uploaded file and import record.
    - Optional canonicalization of index values after import (selects best observation by source priority).

    Usage Example:
        # One-time backfill for historical data:
        python manage.py import_index_levels_excel \
            --file ./scripts/data/bvmac_index_levels.xlsx \
            --source-code BVMAC \
            --sheet INDEX_LEVELS \
            --canonicalize

        # From import record (normal workflow):
        python manage.py import_index_levels_excel \
            --import-id 123 \
            --canonicalize

    Note:
        This command is primarily intended for reference data team operations and backfills.
        Excel format expected:
            date | index_code | level | is_base | base_value | comment
    """

    help = "Import market index level data from Excel file (supports backfill and import record modes)"

    def add_arguments(self, parser):
        """Add command-line arguments."""
        # Mode selection
        parser.add_argument(
            "--import-id",
            type=int,
            help="MarketIndexImport ID (reads from stored file - normal workflow)",
        )
        parser.add_argument(
            "--file",
            type=str,
            help="Path to Excel file (one-time backfill - copies to media storage)",
        )

        # Required for --file mode
        parser.add_argument(
            "--source-code",
            type=str,
            default="BVMAC",
            help="MarketDataSource code (default: BVMAC, required for --file mode)",
        )
        parser.add_argument(
            "--sheet",
            type=str,
            default="INDEX_LEVELS",
            help="Sheet name to read (default: INDEX_LEVELS, for --file mode)",
        )

        # Options
        parser.add_argument(
            "--revision",
            type=int,
            default=0,
            help="Revision number (default: 0)",
        )
        parser.add_argument(
            "--canonicalize",
            action="store_true",
            help="Canonicalize observations after import (select best by source priority)",
        )
        parser.add_argument(
            "--index-code",
            type=str,
            help="Index code for canonicalization (e.g., BVMAC). If not provided, canonicalizes all indices.",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for canonicalization (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="End date for canonicalization (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--actor-id",
            type=int,
            help="User ID of the actor performing this action (for audit log)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        import_id = options.get("import_id")
        file_path = options.get("file")

        # Validate mode
        if import_id and file_path:
            raise CommandError(
                "Cannot specify both --import-id and --file. Choose one mode."
            )
        if not import_id and not file_path:
            raise CommandError("Must specify either --import-id or --file.")

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

        # Store actor in options for use in handlers
        options["actor"] = actor

        # Mode 1: Import from stored file (normal workflow)
        if import_id:
            self._handle_import_record_mode(import_id, options)

        # Mode 2: One-time backfill (copy to media, create import record)
        elif file_path:
            self._handle_backfill_mode(file_path, options)

    def _handle_import_record_mode(self, import_id: int, options: dict):
        """Handle import from stored import record."""
        try:
            import_record = MarketIndexImport.objects.get(id=import_id)
        except MarketIndexImport.DoesNotExist:
            raise CommandError(f"MarketIndexImport with id={import_id} not found")

        if import_record.status == ImportStatus.IMPORTING:
            raise CommandError(f"Import {import_id} is already in progress")

        self.stdout.write(f"Importing from stored file: {import_record.file.name}")
        self.stdout.write(
            f"Source: {import_record.source.name} ({import_record.source.code})"
        )
        self.stdout.write(
            f"Index: {import_record.index.name} ({import_record.index.code})"
        )
        self.stdout.write("")

        # Update status
        import_record.status = ImportStatus.IMPORTING
        import_record.save()

        try:
            # Import
            result = import_index_levels_from_import_record(
                import_record=import_record,
                revision=options.get("revision", 0),
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created {result['created']} observations, "
                    f"updated {result['updated']}"
                )
            )
            if result.get("errors"):
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ {len(result['errors'])} errors (see import record)"
                    )
                )

            # Create audit event for import application
            self._create_import_applied_audit(
                import_record, result, options.get("actor")
            )

            # Canonicalize if requested
            if options.get("canonicalize"):
                self._canonicalize(options, import_record)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Import failed: {str(e)}"))
            raise

    def _handle_backfill_mode(self, file_path: str, options: dict):
        """Handle one-time backfill (copy to media, create import record)."""
        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        # Get source
        source_code = options.get("source_code", "BVMAC")
        try:
            source = MarketDataSource.objects.get(code=source_code)
        except MarketDataSource.DoesNotExist:
            raise CommandError(f"MarketDataSource with code='{source_code}' not found")

        self.stdout.write(f"Backfilling from file: {file_path}")
        self.stdout.write(
            f"Source: {source.name} ({source.code}, priority={source.priority})"
        )
        self.stdout.write("")

        # Note: For index imports, we need to determine which index(s) are in the file
        # For now, we'll require the user to specify an index, or we'll read the file
        # to determine indices. For MVP, let's read the file to get unique index codes.
        import pandas as pd

        try:
            df = pd.read_excel(
                file_path, sheet_name=options.get("sheet", "INDEX_LEVELS")
            )
            if "index_code" not in df.columns:
                raise CommandError("Excel file must contain 'index_code' column")
            unique_index_codes = df["index_code"].str.upper().str.strip().unique()
        except Exception as e:
            raise CommandError(
                f"Failed to read Excel file to determine indices: {str(e)}"
            )

        # For each unique index code, create an import record
        from apps.reference_data.models import MarketIndex

        indices = MarketIndex.objects.filter(code__in=unique_index_codes)
        indices_by_code = {idx.code: idx for idx in indices}

        missing_indices = [
            code for code in unique_index_codes if code not in indices_by_code
        ]
        if missing_indices:
            raise CommandError(
                f"Index codes not found in MarketIndex: {missing_indices}. "
                f"Please create MarketIndex records first."
            )

        # Calculate file hash for audit
        file_hash = self._calculate_file_hash(file_path)

        # Copy file to media storage
        file_name = Path(file_path).name
        upload_path = (
            f"market_data/index_values/{timezone.now().strftime('%Y/%m')}/{file_name}"
        )

        self.stdout.write(f"Copying file to media storage: {upload_path}")

        # Create import record for each index (or one record if single index)
        # For simplicity, create one import record per index
        # Read file once and reuse for all indices
        with open(file_path, "rb") as f:
            file_content = f.read()

        import_records = []
        for index_code in unique_index_codes:
            index = indices_by_code[index_code]
            # Create a new File object for each index (Django needs separate file objects)
            from io import BytesIO

            file_obj = File(BytesIO(file_content), name=file_name)
            import_record = MarketIndexImport.objects.create(
                index=index,
                source=source,
                sheet_name=options.get("sheet", "INDEX_LEVELS"),
                file=file_obj,
                status=ImportStatus.PENDING,
            )
            import_records.append(import_record)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created import record for {index.code}: {import_record.id}"
                )
            )

        self.stdout.write("")

        # Create audit events for import creation
        for import_record in import_records:
            self._create_import_created_audit(
                import_record, file_hash, options.get("actor")
            )

        # Now import from the stored files
        for import_record in import_records:
            import_record.status = ImportStatus.IMPORTING
            import_record.save()

            try:
                result = import_index_levels_from_import_record(
                    import_record=import_record,
                    revision=options.get("revision", 0),
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ [{import_record.index.code}] Created {result['created']} observations, "
                        f"updated {result['updated']}"
                    )
                )

                # Create audit event for import application
                self._create_import_applied_audit(
                    import_record, result, options.get("actor")
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ [{import_record.index.code}] Import failed: {str(e)}"
                    )
                )
                raise

        # Canonicalize if requested
        if options.get("canonicalize"):
            self._canonicalize(options, None)

    def _canonicalize(
        self, options: dict, import_record: MarketIndexImport | None = None
    ):
        """Canonicalize index values (select best observation by source priority)."""
        self.stdout.write("")
        self.stdout.write(
            "Canonicalizing index values (selecting best by source priority)..."
        )

        # Parse dates if provided
        from datetime import date as date_type

        start_date = None
        end_date = None
        if options.get("start_date"):
            start_date = date_type.fromisoformat(options["start_date"])
        if options.get("end_date"):
            end_date = date_type.fromisoformat(options["end_date"])

        index_code = options.get("index_code")

        try:
            canon_result = canonicalize_index_values(
                index_code=index_code,
                start_date=start_date,
                end_date=end_date,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created {canon_result['created']} canonical values, "
                    f"updated {canon_result['updated']}, "
                    f"skipped {canon_result['skipped']}"
                )
            )

            # Update import record if provided
            if import_record:
                import_record.canonical_values_created = canon_result["created"]
                import_record.save()

            # Create audit event for canonicalization
            self._create_canonicalized_audit(
                index_code,
                start_date,
                end_date,
                canon_result,
                options.get("actor"),
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Canonicalization failed: {str(e)}"))
            raise

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file for audit logging."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _create_import_created_audit(
        self, import_record: MarketIndexImport, file_hash: str, actor
    ):
        """Create audit event for import record creation."""
        AuditEvent.objects.create(
            organization_id=None,  # Global reference data
            actor=actor,
            action="MARKETDATA_IMPORT_CREATED",
            object_type="MarketIndexImport",
            object_id=import_record.id,
            object_repr=f"Import {import_record.id}: {import_record.file.name}",
            metadata={
                "import_id": import_record.id,
                "index_code": import_record.index.code,
                "index_name": import_record.index.name,
                "source_code": import_record.source.code,
                "source_name": import_record.source.name,
                "file_name": import_record.file.name,
                "file_hash": file_hash,
                "sheet_name": import_record.sheet_name,
                "command": "import_index_levels_excel",
            },
        )

    def _create_import_applied_audit(
        self, import_record: MarketIndexImport, result: dict, actor
    ):
        """Create audit event for import application."""
        metadata = {
            "import_id": import_record.id,
            "index_code": import_record.index.code,
            "index_name": import_record.index.name,
            "source_code": import_record.source.code,
            "source_name": import_record.source.name,
            "file_name": import_record.file.name,
            "observations_created": result.get("created", 0),
            "observations_updated": result.get("updated", 0),
            "total_rows": result.get("total_rows", 0),
            "error_count": len(result.get("errors", [])),
            "command": "import_index_levels_excel",
        }

        # Add date range if available
        if result.get("min_date"):
            metadata["min_date"] = result["min_date"].isoformat()
        if result.get("max_date"):
            metadata["max_date"] = result["max_date"].isoformat()

        # Add error summary (first 10 errors to avoid huge JSON)
        if result.get("errors"):
            metadata["errors_summary"] = result["errors"][:10]

        AuditEvent.objects.create(
            organization_id=None,  # Global reference data
            actor=actor,
            action="MARKETDATA_IMPORT_APPLIED",
            object_type="MarketIndexImport",
            object_id=import_record.id,
            object_repr=f"Import {import_record.id} applied: {result.get('created', 0)} created, {result.get('updated', 0)} updated",
            metadata=metadata,
        )

    def _create_canonicalized_audit(
        self, index_code, start_date, end_date, result: dict, actor
    ):
        """Create audit event for canonicalization."""
        from datetime import date as date_type

        metadata = {
            "index_code": index_code,
            "canonical_values_created": result.get("created", 0),
            "canonical_values_updated": result.get("updated", 0),
            "canonical_values_skipped": result.get("skipped", 0),
            "total_groups": result.get("total_groups", 0),
            "error_count": len(result.get("errors", [])),
            "command": "import_index_levels_excel",
        }

        # Add date range if provided
        if start_date:
            if isinstance(start_date, date_type):
                metadata["start_date"] = start_date.isoformat()
            else:
                metadata["start_date"] = str(start_date)
        if end_date:
            if isinstance(end_date, date_type):
                metadata["end_date"] = end_date.isoformat()
            else:
                metadata["end_date"] = str(end_date)

        # Add error summary (first 10 errors)
        if result.get("errors"):
            metadata["errors_summary"] = result["errors"][:10]

        object_repr = "Canonicalized index values"
        if index_code:
            object_repr += f" {index_code}"
        object_repr += (
            f": {result.get('created', 0)} created, {result.get('updated', 0)} updated"
        )

        AuditEvent.objects.create(
            organization_id=None,  # Global reference data
            actor=actor,
            action="MARKETDATA_CANONICALIZED",
            object_type="MarketIndexValue",
            object_id=None,  # Not a single object, but a collection
            object_repr=object_repr,
            metadata=metadata,
        )
