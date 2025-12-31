"""
Tests for index constituents import service.
"""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from apps.reference_data.models import MarketIndexConstituent
from apps.reference_data.services.indices.import_constituents_excel import (
    import_index_constituents_from_file,
)
from tests.factories import EquityInstrumentFactory


class TestImportIndexConstituentsExcel:
    """Test cases for index constituents import service."""

    def test_import_constituents_basic(
        self, market_index, market_data_source, org_context_with_org
    ):
        """Test basic import of index constituents."""
        # Create instruments
        instrument1 = EquityInstrumentFactory(isin="CM1234567890")
        _instrument2 = EquityInstrumentFactory(isin="CM0987654321")

        # Create Excel file
        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31), date(2024, 3, 31)],
                "index_code": [market_index.code, market_index.code],
                "instrument_id": ["CM1234567890", "CM0987654321"],
                "weight": [12.5, 8.25],
                "shares": [1000000, 750000],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            result = import_index_constituents_from_file(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="CONSTITUENTS",
            )

            assert result["created"] == 2
            assert result["updated"] == 0
            assert len(result["errors"]) == 0
            assert result["total_rows"] == 2

            # Verify constituents were created
            constituents = MarketIndexConstituent.objects.filter(index=market_index)
            assert constituents.count() == 2

            # Verify weights
            const1 = constituents.get(instrument=instrument1)
            assert const1.weight == Decimal("12.5")
            assert const1.shares == Decimal("1000000")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_constituents_missing_columns(self, market_data_source):
        """Test import fails with missing required columns."""
        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": ["BVMAC"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            with pytest.raises(ValueError, match="Missing required columns"):
                import_index_constituents_from_file(
                    file_path=tmp_path,
                    source=market_data_source,
                    sheet_name="CONSTITUENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_constituents_invalid_index_code(self, market_data_source):
        """Test import fails with invalid index code."""
        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": ["INVALID"],
                "instrument_id": ["CM1234567890"],
                "weight": [12.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            with pytest.raises(ValueError, match="Index codes not found"):
                import_index_constituents_from_file(
                    file_path=tmp_path,
                    source=market_data_source,
                    sheet_name="CONSTITUENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_constituents_invalid_weight(
        self, market_index, market_data_source, org_context_with_org
    ):
        """Test import fails with non-positive weight."""
        _instrument = EquityInstrumentFactory(isin="CM1234567890")

        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": [market_index.code],
                "instrument_id": ["CM1234567890"],
                "weight": [-10.0],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            with pytest.raises(ValueError, match="non-positive weights"):
                import_index_constituents_from_file(
                    file_path=tmp_path,
                    source=market_data_source,
                    sheet_name="CONSTITUENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_constituents_instrument_not_found(
        self, market_index, market_data_source
    ):
        """Test import reports error for instrument not found."""
        df = pd.DataFrame(
            {
                "as_of_date": [date(2024, 3, 31)],
                "index_code": [market_index.code],
                "instrument_id": ["INVALID_ISIN"],
                "weight": [12.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="CONSTITUENTS")

        try:
            result = import_index_constituents_from_file(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="CONSTITUENTS",
            )

            assert result["created"] == 0
            assert len(result["errors"]) > 0
            assert any("not found" in error.lower() for error in result["errors"])

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_constituents_weight_validation_warning(
        self, market_index, market_data_source, org_context_with_org
    ):
        """Test import reports warning for weight sum not ~100%."""
        _instrument1 = EquityInstrumentFactory(isin="CM1234567890")
        _instrument2 = EquityInstrumentFactory(isin="CM0987654321")

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
            result = import_index_constituents_from_file(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="CONSTITUENTS",
            )

            assert result["created"] == 2
            assert len(result["weight_validation_errors"]) > 0
            assert any(
                "weights sum to" in error
                for error in result["weight_validation_errors"]
            )

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_constituents_updates_existing(
        self, market_index, market_data_source, org_context_with_org
    ):
        """Test import updates existing constituents."""
        instrument = EquityInstrumentFactory(isin="CM1234567890")

        # Create existing constituent
        MarketIndexConstituent.objects.create(
            index=market_index,
            instrument=instrument,
            as_of_date=date(2024, 3, 31),
            weight=Decimal("10.0"),
            source=market_data_source,
        )

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
            result = import_index_constituents_from_file(
                file_path=tmp_path,
                source=market_data_source,
                sheet_name="CONSTITUENTS",
            )

            assert result["created"] == 0
            assert result["updated"] == 1

            # Verify weight was updated
            const = MarketIndexConstituent.objects.get(
                index=market_index,
                instrument=instrument,
                as_of_date=date(2024, 3, 31),
            )
            assert const.weight == Decimal("12.5")

        finally:
            Path(tmp_path).unlink(missing_ok=True)
