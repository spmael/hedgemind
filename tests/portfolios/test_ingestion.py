"""
Tests for portfolio ingestion service.

Tests the complete portfolio ingestion flow including:
- File reading (CSV/Excel)
- Column mapping
- Row validation
- PositionSnapshot creation
- Error tracking
- Idempotency
"""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from djmoney.money import Money

from apps.portfolios.ingestion import import_portfolio_from_file
from apps.portfolios.models import PortfolioImportError, PositionSnapshot
from libs.choices import ImportStatus
from tests.factories import (
    EquityInstrumentFactory,
    PortfolioFactory,
    PortfolioImportFactory,
    PositionSnapshotFactory,
)


class TestPortfolioIngestion:
    """Test cases for portfolio ingestion service."""

    def test_import_portfolio_basic(self, org_context_with_org):
        """Test basic import of portfolio positions."""
        # Setup
        portfolio = PortfolioFactory()
        instrument1 = EquityInstrumentFactory(isin="ISIN001", ticker="TICK1")
        instrument2 = EquityInstrumentFactory(isin="ISIN002", ticker="TICK2")

        # Create test file
        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001", "ISIN002"],
                "quantity": [1000, 2000],
                "currency": ["XAF", "XAF"],
                "price": [100.50, 200.75],
                "market_value": [100500, 401500],
                "book_value": [100000, 400000],
                "valuation_source": ["market", "market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            # Create PortfolioImport
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                as_of_date=date.today(),
                file=SimpleUploadedFile(
                    "test_portfolio.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            # Import
            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            # Assertions
            assert result["created"] == 2
            assert result["errors"] == 0
            assert result["total_rows"] == 2
            assert result["status"] == ImportStatus.SUCCESS

            # Verify snapshots were created
            snapshots = PositionSnapshot.objects.filter(
                portfolio_import=portfolio_import
            )
            assert snapshots.count() == 2
            assert snapshots.filter(instrument=instrument1).exists()
            assert snapshots.filter(instrument=instrument2).exists()

            # Verify PortfolioImport status
            portfolio_import.refresh_from_db()
            assert portfolio_import.status == ImportStatus.SUCCESS
            assert portfolio_import.rows_processed == 2
            assert portfolio_import.rows_total == 2
            assert portfolio_import.error_message is None

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_missing_required_columns(self, org_context_with_org):
        """Test import fails with missing required columns."""
        portfolio = PortfolioFactory()

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                # Missing required columns
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            with pytest.raises(ValueError, match="Missing required column mappings"):
                import_portfolio_from_file(
                    portfolio_import_id=portfolio_import.id,
                    file_path=tmp_path,
                )

            portfolio_import.refresh_from_db()
            assert portfolio_import.status == ImportStatus.FAILED

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_invalid_instrument(self, org_context_with_org):
        """Test import handles invalid instrument identifiers."""
        portfolio = PortfolioFactory()
        # Create one valid instrument
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001", "INVALID_ISIN"],
                "quantity": [1000, 2000],
                "currency": ["XAF", "XAF"],
                "price": [100.50, 200.75],
                "market_value": [100500, 401500],
                "book_value": [100000, 400000],
                "valuation_source": ["market", "market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            # Should have 1 created, 1 error
            assert result["created"] == 1
            assert result["errors"] == 1
            assert result["status"] == ImportStatus.PARTIAL

            # Verify error was recorded
            errors = PortfolioImportError.objects.filter(
                portfolio_import=portfolio_import
            )
            assert errors.count() == 1
            assert errors.first().error_type == "reference_data"
            assert "INVALID_ISIN" in errors.first().error_message

            # Verify one snapshot was created
            assert (
                PositionSnapshot.objects.filter(
                    portfolio_import=portfolio_import
                ).count()
                == 1
            )

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_duplicate_snapshot(self, org_context_with_org):
        """Test import handles duplicate snapshots (immutable behavior)."""
        portfolio = PortfolioFactory()
        instrument = EquityInstrumentFactory(isin="ISIN001")

        # Create existing snapshot
        PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=date.today(),
        )

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                "price": [100.50],
                "market_value": [100500],
                "book_value": [100000],
                "valuation_source": ["market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                as_of_date=date.today(),
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            # Should have 0 created, 1 error
            assert result["created"] == 0
            assert result["errors"] == 1
            assert result["status"] == ImportStatus.FAILED

            # Verify error was recorded
            errors = PortfolioImportError.objects.filter(
                portfolio_import=portfolio_import
            )
            assert errors.count() == 1
            assert errors.first().error_type == "business_rule"
            assert "already exists" in errors.first().error_message.lower()

            # Verify no new snapshot was created
            assert (
                PositionSnapshot.objects.filter(
                    portfolio_import=portfolio_import
                ).count()
                == 0
            )

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_validation_errors(self, org_context_with_org):
        """Test import handles validation errors."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001", "ISIN001"],
                "quantity": [1000, -500],  # Negative quantity
                "currency": ["XAF", "XAF"],
                "price": [100.50, 200.75],
                "market_value": [100500, 401500],
                "book_value": [100000, -100000],  # Negative book value
                "valuation_source": ["market", "market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            # Should have 1 created, 1 error
            assert result["created"] == 1
            assert result["errors"] == 1
            assert result["status"] == ImportStatus.PARTIAL

            # Verify validation errors were recorded
            errors = PortfolioImportError.objects.filter(
                portfolio_import=portfolio_import
            )
            assert errors.count() == 1
            assert errors.first().error_type == "validation"

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_market_value_computation(self, org_context_with_org):
        """Test import computes market_value from quantity * price."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        # File with quantity and price, but no market_value
        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                "price": [100.50],
                # market_value missing - should be computed
                "book_value": [100000],
                "valuation_source": ["market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            assert result["created"] == 1
            assert result["errors"] == 0

            # Verify market_value was computed
            snapshot = PositionSnapshot.objects.get(portfolio_import=portfolio_import)
            expected_mv = Money(1000 * Decimal("100.50"), "XAF")
            assert snapshot.market_value == expected_mv

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_price_computation(self, org_context_with_org):
        """Test import computes price from market_value / quantity."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        # File with quantity and market_value, but no price
        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                # price missing - should be computed
                "market_value": [100500],
                "book_value": [100000],
                "valuation_source": ["market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            assert result["created"] == 1
            assert result["errors"] == 0

            # Verify price was computed
            snapshot = PositionSnapshot.objects.get(portfolio_import=portfolio_import)
            expected_price = Decimal("100.50")  # 100500 / 1000
            assert snapshot.price == expected_price

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_idempotency(self, org_context_with_org):
        """Test import prevents duplicate imports (idempotency)."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                "price": [100.50],
                "market_value": [100500],
                "book_value": [100000],
                "valuation_source": ["market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            # First import
            portfolio_import1 = PortfolioImportFactory(
                portfolio=portfolio,
                as_of_date=date.today(),
                file=SimpleUploadedFile(
                    "test1.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result1 = import_portfolio_from_file(
                portfolio_import_id=portfolio_import1.id,
                file_path=tmp_path,
            )
            assert result1["created"] == 1
            assert result1["status"] == ImportStatus.SUCCESS

            # Second import with same file (should be rejected)
            portfolio_import2 = PortfolioImportFactory(
                portfolio=portfolio,
                as_of_date=date.today(),
                file=SimpleUploadedFile(
                    "test2.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            with pytest.raises(ValueError, match="Duplicate import detected"):
                import_portfolio_from_file(
                    portfolio_import_id=portfolio_import2.id,
                    file_path=tmp_path,
                )

            portfolio_import2.refresh_from_db()
            assert portfolio_import2.status == ImportStatus.FAILED

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_csv_format(self, org_context_with_org):
        """Test import works with CSV files."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                "price": [100.50],
                "market_value": [100500],
                "book_value": [100000],
                "valuation_source": ["market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_csv(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.csv",
                    Path(tmp_path).read_bytes(),
                    content_type="text/csv",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            assert result["created"] == 1
            assert result["errors"] == 0
            assert result["status"] == ImportStatus.SUCCESS

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_with_accrued_interest(self, org_context_with_org):
        """Test import handles accrued_interest field."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                "price": [100.50],
                "market_value": [100500],
                "book_value": [100000],
                "valuation_source": ["market"],
                "accrued_interest": [5000],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            assert result["created"] == 1

            # Verify accrued_interest was stored
            snapshot = PositionSnapshot.objects.get(portfolio_import=portfolio_import)
            assert snapshot.accrued_interest == Money(5000, "XAF")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_status_progression(self, org_context_with_org):
        """Test import status progresses correctly."""
        portfolio = PortfolioFactory()
        _instrument = EquityInstrumentFactory(isin="ISIN001")

        df = pd.DataFrame(
            {
                "instrument_identifier": ["ISIN001"],
                "quantity": [1000],
                "currency": ["XAF"],
                "price": [100.50],
                "market_value": [100500],
                "book_value": [100000],
                "valuation_source": ["market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                status=ImportStatus.PENDING,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            # Status should progress: PENDING -> PARSING -> VALIDATING -> SUCCESS
            import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            portfolio_import.refresh_from_db()
            assert portfolio_import.status == ImportStatus.SUCCESS
            assert portfolio_import.completed_at is not None

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_portfolio_bulk_operations(self, org_context_with_org):
        """Test import uses bulk operations for performance."""
        portfolio = PortfolioFactory()
        # Create 100 instruments (needed for import to succeed)
        _instruments = [
            EquityInstrumentFactory(isin=f"ISIN{i:03d}") for i in range(100)
        ]

        # Create large file
        data = {
            "instrument_identifier": [f"ISIN{i:03d}" for i in range(100)],
            "quantity": [1000] * 100,
            "currency": ["XAF"] * 100,
            "price": [100.50] * 100,
            "market_value": [100500] * 100,
            "book_value": [100000] * 100,
            "valuation_source": ["market"] * 100,
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False)

        try:
            portfolio_import = PortfolioImportFactory(
                portfolio=portfolio,
                file=SimpleUploadedFile(
                    "test.xlsx",
                    Path(tmp_path).read_bytes(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )

            result = import_portfolio_from_file(
                portfolio_import_id=portfolio_import.id,
                file_path=tmp_path,
            )

            # All should be created
            assert result["created"] == 100
            assert result["errors"] == 0
            assert result["status"] == ImportStatus.SUCCESS

            # Verify all snapshots were created
            assert (
                PositionSnapshot.objects.filter(
                    portfolio_import=portfolio_import
                ).count()
                == 100
            )

        finally:
            Path(tmp_path).unlink(missing_ok=True)
