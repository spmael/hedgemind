"""
Tests for import_index_constituents_excel management command.
"""

import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.audit.models import AuditEvent
from tests.factories import (
    EquityInstrumentFactory,
    MarketDataSourceFactory,
    MarketIndexFactory,
)


class TestImportIndexConstituentsExcelCommand:
    """Test cases for import_index_constituents_excel command."""

    def test_command_requires_file(self):
        """Test command requires --file argument."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError):
            call_command("import_index_constituents_excel", stdout=out, stderr=err)

    def test_command_file_not_found(self):
        """Test command fails if file doesn't exist."""
        out = StringIO()
        err = StringIO()

        with pytest.raises(CommandError, match="File not found"):
            call_command(
                "import_index_constituents_excel",
                "--file=/nonexistent/file.xlsx",
                stdout=out,
                stderr=err,
            )

    def test_command_source_not_found(self, org_context_with_org):
        """Test command fails if source doesn't exist."""
        market_index = MarketIndexFactory(code="BVMAC")
        instrument = EquityInstrumentFactory(isin="CM1234567890")

        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": [market_index.code],
                "instrument_id": ["CM1234567890"],
                "weight": [12.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            out = StringIO()
            err = StringIO()

            with pytest.raises(CommandError, match="not found"):
                call_command(
                    "import_index_constituents_excel",
                    f"--file={tmp_path}",
                    "--source-code=NONEXISTENT",
                    stdout=out,
                    stderr=err,
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_command_success(self, market_index, market_data_source, org_context_with_org):
        """Test command succeeds with valid file."""
        instrument = EquityInstrumentFactory(isin="CM1234567890")

        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": [market_index.code],
                "instrument_id": ["CM1234567890"],
                "weight": [12.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            out = StringIO()

            call_command(
                "import_index_constituents_excel",
                f"--file={tmp_path}",
                f"--source-code={market_data_source.code}",
                stdout=out,
            )

            output = out.getvalue()
            assert "Created" in output or "created" in output.lower()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_command_creates_audit_events(
        self, market_index, market_data_source, org_context_with_org
    ):
        """Test command creates audit events."""
        instrument = EquityInstrumentFactory(isin="CM1234567890")

        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": [market_index.code],
                "instrument_id": ["CM1234567890"],
                "weight": [12.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            out = StringIO()

            initial_count = AuditEvent.objects.count()

            call_command(
                "import_index_constituents_excel",
                f"--file={tmp_path}",
                f"--source-code={market_data_source.code}",
                stdout=out,
            )

            # Verify audit event was created
            assert AuditEvent.objects.count() > initial_count
            assert AuditEvent.objects.filter(
                action="MARKETDATA_IMPORT_APPLIED"
            ).exists()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_command_reports_weight_warnings(
        self, market_index, market_data_source, org_context_with_org
    ):
        """Test command reports weight validation warnings."""
        instrument1 = EquityInstrumentFactory(isin="CM1234567890")
        instrument2 = EquityInstrumentFactory(isin="CM0987654321")

        # Weights sum to 50% (should trigger warning)
        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31), date(2024, 3, 31)],
                "index_code": [market_index.code, market_index.code],
                "instrument_id": ["CM1234567890", "CM0987654321"],
                "weight": [25.0, 25.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            out = StringIO()

            call_command(
                "import_index_constituents_excel",
                f"--file={tmp_path}",
                f"--source-code={market_data_source.code}",
                stdout=out,
            )

            output = out.getvalue()
            # Should report weight validation warnings
            assert "weight" in output.lower() or "warning" in output.lower()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

