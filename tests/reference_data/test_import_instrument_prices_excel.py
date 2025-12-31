"""
Tests for instrument prices import service.
"""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from django.utils import timezone

from apps.reference_data.models import InstrumentPriceObservation
from apps.reference_data.services.prices.import_excel import import_prices_from_file
from libs.tenant_context import organization_context
from tests.factories import (
    EquityInstrumentFactory,
    MarketDataSourceFactory,
    OrganizationFactory,
)


class TestImportInstrumentPricesExcel:
    """Test cases for instrument prices import service."""

    def test_import_prices_basic(self, org_context_with_org):
        """Test basic import of price observations."""
        # Setup
        instrument = EquityInstrumentFactory(isin="ISIN001")
        source = MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1), date(2024, 1, 2)],
                "instrument_id": ["ISIN001", "ISIN001"],
                "price": [100.0, 101.5],
                "price_type": ["close", "close"],
                "quote_convention": ["percent_of_par", "percent_of_par"],
                "clean_or_dirty": ["clean", "clean"],
                "Volume": [1000, 1500],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
                sheet_name="PRICES",
            )

            assert result["created"] == 2
            assert result["updated"] == 0
            assert len(result["errors"]) == 0
            assert result["total_rows"] == 2

            # Verify observations were created
            observations = InstrumentPriceObservation.objects.filter(
                instrument=instrument
            )
            assert observations.count() == 2

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_missing_columns(self, org_context_with_org):
        """Test import fails with missing required columns."""
        MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            with pytest.raises(ValueError, match="Missing required columns"):
                import_prices_from_file(
                    file_path=tmp_path,
                    source_code="BVMAC",
                    sheet_name="PRICES",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_invalid_source_code(self, org_context_with_org):
        """Test import fails with invalid source code."""
        EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
                "price": [100.0],
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            with pytest.raises(ValueError, match="MarketDataSource with code"):
                import_prices_from_file(
                    file_path=tmp_path,
                    source_code="INVALID",
                    sheet_name="PRICES",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_instrument_not_found(self, org_context_with_org):
        """Test import reports error for instrument not found."""
        MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["INVALID_ISIN"],
                "price": [100.0],
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
                sheet_name="PRICES",
            )

            assert result["created"] == 0
            assert len(result["errors"]) > 0
            assert any("not found" in error.lower() for error in result["errors"])

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_updates_existing(self, org_context_with_org):
        """Test import updates existing observations."""
        # Setup
        instrument = EquityInstrumentFactory(isin="ISIN001")
        source = MarketDataSourceFactory(code="BVMAC")

        # Create existing observation
        InstrumentPriceObservation.objects.create(
            instrument=instrument,
            date=date(2024, 1, 1),
            price=Decimal("99.0"),
            price_type="close",
            quote_convention="percent_of_par",
            clean_or_dirty="clean",
            source=source,
            revision=0,
            observed_at=timezone.now(),
        )

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
                "price": [100.0],  # Updated price
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
                sheet_name="PRICES",
            )

            assert result["created"] == 0
            assert result["updated"] == 1

            # Verify price was updated
            obs = InstrumentPriceObservation.objects.get(
                instrument=instrument, date=date(2024, 1, 1)
            )
            assert obs.price == Decimal("100.0")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_with_revision(self, org_context_with_org):
        """Test import handles revision numbers correctly."""
        instrument = EquityInstrumentFactory(isin="ISIN001")
        source = MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
                "price": [100.0],
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            # Import with revision 1
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
                sheet_name="PRICES",
                revision=1,
            )

            assert result["created"] == 1

            # Should create separate observation with revision 1
            obs = InstrumentPriceObservation.objects.get(
                instrument=instrument, date=date(2024, 1, 1), revision=1
            )
            assert obs.price == Decimal("100.0")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_normalizes_choice_values(self, org_context_with_org):
        """Test import normalizes choice values (uppercase to lowercase)."""
        instrument = EquityInstrumentFactory(isin="ISIN001")
        MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
                "price": [100.0],
                "price_type": ["CLOSE"],  # Uppercase
                "quote_convention": ["PERCENT_OF_PAR"],  # Uppercase
                "clean_or_dirty": ["CLEAN"],  # Uppercase
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
                sheet_name="PRICES",
            )

            assert result["created"] == 1

            # Verify values were normalized to lowercase
            obs = InstrumentPriceObservation.objects.get(
                instrument=instrument, date=date(2024, 1, 1)
            )
            assert obs.price_type == "close"
            assert obs.quote_convention == "percent_of_par"
            assert obs.clean_or_dirty == "clean"

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_requires_org_context(self):
        """Test import fails without organization context."""
        MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
                "price": [100.0],
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            with pytest.raises(RuntimeError, match="organization context"):
                import_prices_from_file(
                    file_path=tmp_path,
                    source_code="BVMAC",
                    sheet_name="PRICES",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_default_sheet_name(self, org_context_with_org):
        """Test import uses default sheet name PRICES."""
        instrument = EquityInstrumentFactory(isin="ISIN001")
        MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["ISIN001"],
                "price": [100.0],
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            # Don't specify sheet_name, should use default "PRICES"
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
            )

            assert result["created"] == 1
            assert len(result["errors"]) == 0

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_prices_lookup_by_ticker(self, org_context_with_org):
        """Test import can lookup instruments by ticker."""
        instrument = EquityInstrumentFactory(ticker="TICKER001", isin=None)
        MarketDataSourceFactory(code="BVMAC")

        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 1)],
                "instrument_id": ["TICKER001"],  # Using ticker
                "price": [100.0],
                "price_type": ["close"],
                "quote_convention": ["percent_of_par"],
                "clean_or_dirty": ["clean"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="PRICES")

        try:
            result = import_prices_from_file(
                file_path=tmp_path,
                source_code="BVMAC",
                sheet_name="PRICES",
            )

            assert result["created"] == 1
            assert len(result["errors"]) == 0

            # Verify observation was created for correct instrument
            obs = InstrumentPriceObservation.objects.get(
                instrument=instrument, date=date(2024, 1, 1)
            )
            assert obs.price == Decimal("100.0")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

