"""
Tests for index levels import service.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from django.utils import timezone

from apps.reference_data.models import MarketIndexImport, MarketIndexValueObservation
from apps.reference_data.services.indices.import_excel import (
    _import_index_levels_excel,
    import_index_levels_from_import_record,
)
from libs.choices import ImportStatus


class TestImportIndexLevelsExcel:
    """Test cases for index levels import service."""

    def test_import_index_levels_excel_basic(self, market_index, market_data_source):
        """Test basic import of index levels."""
        # Create Excel file
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1), date(2024, 1, 2)],
                "index_code": [market_index.code, market_index.code],
                "level": [100.0, 101.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            result = _import_index_levels_excel(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="INDEX_LEVELS",
            )

            assert result["created"] == 2
            assert result["updated"] == 0
            assert len(result["errors"]) == 0
            assert result["total_rows"] == 2

            # Verify observations were created
            observations = MarketIndexValueObservation.objects.filter(
                index=market_index
            )
            assert observations.count() == 2

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_index_levels_excel_missing_columns(self, market_data_source):
        """Test import fails with missing required columns."""
        df = pd.DataFrame({"date": [date(2024, 1, 1)], "level": [100.0]})

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            with pytest.raises(ValueError, match="Missing required columns"):
                _import_index_levels_excel(
                    file_path=tmp_path,
                    source=market_data_source,
                    sheet_name="INDEX_LEVELS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_index_levels_excel_invalid_index_code(self, market_data_source):
        """Test import fails with invalid index code."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "index_code": ["INVALID"],
                "level": [100.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            with pytest.raises(ValueError, match="Index codes not found"):
                _import_index_levels_excel(
                    file_path=tmp_path,
                    source=market_data_source,
                    sheet_name="INDEX_LEVELS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_index_levels_excel_invalid_level(
        self, market_index, market_data_source
    ):
        """Test import fails with non-positive level."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "index_code": [market_index.code],
                "level": [-10.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            with pytest.raises(ValueError, match="non-positive levels"):
                _import_index_levels_excel(
                    file_path=tmp_path,
                    source=market_data_source,
                    sheet_name="INDEX_LEVELS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_index_levels_excel_with_base_point(
        self, market_index, market_data_source
    ):
        """Test import with base point updates MarketIndex."""
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "index_code": [market_index.code],
                "level": [100.0],
                "is_base": [True],
                "base_value": [100.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INDEX_LEVELS")

        try:
            # Clear base_date and base_value
            market_index.base_date = None
            market_index.base_value = None
            market_index.save()

            result = _import_index_levels_excel(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="INDEX_LEVELS",
            )

            assert result["created"] == 1

            # Verify MarketIndex was updated
            market_index.refresh_from_db()
            assert market_index.base_date == date(2024, 1, 1)
            assert market_index.base_value == 100.0

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_index_levels_from_import_record(
        self, market_index, market_data_source
    ):
        """Test import from import record."""
        # Create Excel file
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
            # Create import record with actual file
            from django.core.files import File

            with open(tmp_path, "rb") as f:
                import_record = MarketIndexImport.objects.create(
                    index=market_index,
                    source=market_data_source,
                    sheet_name="INDEX_LEVELS",
                    file=File(f, name="test.xlsx"),
                )

            result = import_index_levels_from_import_record(import_record)

            assert result["created"] == 1
            import_record.refresh_from_db()
            assert import_record.status == ImportStatus.SUCCESS
            assert import_record.observations_created == 1

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_index_levels_excel_updates_existing(
        self, market_index, market_data_source
    ):
        """Test import updates existing observations."""
        # Create existing observation
        MarketIndexValueObservation.objects.create(
            index=market_index,
            date=date(2024, 1, 1),
            value=99.0,
            source=market_data_source,
            revision=0,
            observed_at=timezone.now(),
        )

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
            result = _import_index_levels_excel(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="INDEX_LEVELS",
            )

            assert result["created"] == 0
            assert result["updated"] == 1

            # Verify value was updated
            obs = MarketIndexValueObservation.objects.get(
                index=market_index, date=date(2024, 1, 1)
            )
            assert obs.value == 100.0

        finally:
            Path(tmp_path).unlink(missing_ok=True)
