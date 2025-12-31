"""
Tests for import_index_levels_excel management command.
"""

import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.audit.models import AuditEvent
from apps.reference_data.models import MarketIndexImport
from tests.factories import (
    MarketDataSourceFactory,
    MarketIndexFactory,
    MarketIndexImportFactory,
)


class TestImportIndexLevelsExcelCommand:
    """Test cases for import_index_levels_excel command."""

    def test_command_requires_mode(self):
        """Test command requires either --import-id or --file."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError, match="Must specify either"):
            call_command("import_index_levels_excel", stdout=out, stderr=err)

    def test_command_rejects_both_modes(self):
        """Test command rejects both --import-id and --file."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError, match="Cannot specify both"):
            call_command(
                "import_index_levels_excel",
                "--import-id=1",
                "--file=test.xlsx",
                stdout=out,
                stderr=err,
            )

    def test_import_record_mode_not_found(self):
        """Test import record mode fails if record doesn't exist."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError, match="not found"):
            call_command(
                "import_index_levels_excel",
                "--import-id=99999",
                stdout=out,
                stderr=err,
            )

    def test_backfill_mode_file_not_found(self, market_data_source):
        """Test backfill mode fails if file doesn't exist."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError, match="File not found"):
            call_command(
                "import_index_levels_excel",
                "--file=/nonexistent/file.xlsx",
                stdout=out,
                stderr=err,
            )

    def test_backfill_mode_source_not_found(self):
        """Test backfill mode fails if source doesn't exist."""
        # Create temp file
        market_index = MarketIndexFactory(code="BVMAC")
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "index_code": [market_index.code],
                "level": [100.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            out = StringIO()
            err = StringIO()

            with pytest.raises(CommandError, match="not found"):
                call_command(
                    "import_index_levels_excel",
                    f"--file={tmp_path}",
                    "--source-code=NONEXISTENT",
                    stdout=out,
                    stderr=err,
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @patch(
        "apps.reference_data.management.commands.import_index_levels_excel.import_index_levels_from_import_record"
    )
    def test_import_record_mode_success(self, mock_import, market_index, market_data_source):
        """Test import record mode succeeds."""
        mock_import.return_value = {
            "created": 10,
            "updated": 5,
            "errors": [],
            "total_rows": 15,
            "min_date": date(2024, 1, 1),
            "max_date": date(2024, 1, 15),
        }

        import_record = MarketIndexImportFactory(
            index=market_index,
            source=market_data_source,
        )

        out = StringIO()
        call_command(
            "import_index_levels_excel",
            f"--import-id={import_record.id}",
            stdout=out,
        )

        mock_import.assert_called_once()
        assert "Created 10 observations" in out.getvalue()

    def test_backfill_mode_creates_import_records(self, market_data_source):
        """Test backfill mode creates import records."""
        market_index = MarketIndexFactory(code="BVMAC")
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "index_code": [market_index.code],
                "level": [100.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            out = StringIO()

            with patch(
                "apps.reference_data.management.commands.import_index_levels_excel.import_index_levels_from_import_record"
            ) as mock_import:
                mock_import.return_value = {
                    "created": 1,
                    "updated": 0,
                    "errors": [],
                    "total_rows": 1,
                }

                call_command(
                    "import_index_levels_excel",
                    f"--file={tmp_path}",
                    f"--source-code={market_data_source.code}",
                    stdout=out,
                )

                # Verify import record was created
                import_records = MarketIndexImport.objects.filter(
                    index=market_index, source=market_data_source
                )
                assert import_records.exists()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_command_creates_audit_events(self, market_index, market_data_source):
        """Test command creates audit events."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "index_code": [market_index.code],
                "level": [100.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            out = StringIO()

            with patch(
                "apps.reference_data.management.commands.import_index_levels_excel.import_index_levels_from_import_record"
            ) as mock_import:
                mock_import.return_value = {
                    "created": 1,
                    "updated": 0,
                    "errors": [],
                    "total_rows": 1,
                }

                initial_count = AuditEvent.objects.count()

                call_command(
                    "import_index_levels_excel",
                    f"--file={tmp_path}",
                    f"--source-code={market_data_source.code}",
                    stdout=out,
                )

                # Verify audit events were created
                assert AuditEvent.objects.count() > initial_count
                assert AuditEvent.objects.filter(
                    action="MARKETDATA_IMPORT_CREATED"
                ).exists()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

