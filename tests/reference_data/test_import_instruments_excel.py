"""
Tests for instruments import service.
"""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from apps.reference_data.models import Instrument
from apps.reference_data.services.instruments.import_excel import (
    import_instruments_from_file,
)
from libs.tenant_context import organization_context
from tests.factories import (
    InstrumentGroupFactory,
    InstrumentTypeFactory,
    IssuerFactory,
    OrganizationFactory,
)


class TestImportInstrumentsExcel:
    """Test cases for instruments import service."""

    def test_import_instruments_basic(self, org_context_with_org):
        """Test basic import of instruments."""
        # Setup required dependencies
        group = InstrumentGroupFactory(name="BOND")
        inst_type = InstrumentTypeFactory(group=group, name="GOVERNMENT")
        issuer = IssuerFactory(short_name="GOV", name="Government")

        df = pd.DataFrame(
            {
                "name": ["Test Bond 1", "Test Bond 2"],
                "isin": ["ISIN001", "ISIN002"],
                "ticker": ["BOND1", "BOND2"],
                "instrument_group_code": ["BOND", "BOND"],
                "instrument_type_code": ["GOVERNMENT", "GOVERNMENT"],
                "currency": ["XAF", "XAF"],
                "issuer_code": ["GOV", "GOV"],
                "valuation_method": ["mark_to_market", "mark_to_market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            result = import_instruments_from_file(
                file_path=tmp_path,
                sheet_name="INSTRUMENTS",
            )

            assert result["created"] == 2
            assert result["updated"] == 0
            assert len(result["errors"]) == 0
            assert result["total_rows"] == 2

            # Verify instruments were created
            instruments = Instrument.objects.all()
            assert instruments.count() == 2
            assert instruments.filter(name="Test Bond 1").exists()
            assert instruments.filter(name="Test Bond 2").exists()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_missing_columns(self, org_context_with_org):
        """Test import fails with missing required columns."""
        df = pd.DataFrame(
            {
                "name": ["Test Instrument"],
                "isin": ["ISIN001"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            with pytest.raises(ValueError, match="Missing required columns"):
                import_instruments_from_file(
                    file_path=tmp_path,
                    sheet_name="INSTRUMENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_invalid_group_code(self, org_context_with_org):
        """Test import fails with invalid instrument group code."""
        df = pd.DataFrame(
            {
                "name": ["Test Instrument"],
                "instrument_group_code": ["INVALID"],
                "instrument_type_code": ["TYPE"],
                "currency": ["XAF"],
                "issuer_code": ["ISSUER"],
                "valuation_method": ["mark_to_market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            with pytest.raises(ValueError, match="InstrumentGroup codes not found"):
                import_instruments_from_file(
                    file_path=tmp_path,
                    sheet_name="INSTRUMENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_invalid_issuer_code(self, org_context_with_org):
        """Test import fails with invalid issuer code."""
        group = InstrumentGroupFactory(name="BOND")
        InstrumentTypeFactory(group=group, name="GOVERNMENT")

        df = pd.DataFrame(
            {
                "name": ["Test Instrument"],
                "instrument_group_code": ["BOND"],
                "instrument_type_code": ["GOVERNMENT"],
                "currency": ["XAF"],
                "issuer_code": ["INVALID"],
                "valuation_method": ["mark_to_market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            with pytest.raises(ValueError, match="Issuer codes not found"):
                import_instruments_from_file(
                    file_path=tmp_path,
                    sheet_name="INSTRUMENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_updates_existing(self, org_context_with_org):
        """Test import updates existing instruments."""
        # Setup
        group = InstrumentGroupFactory(name="BOND")
        inst_type = InstrumentTypeFactory(group=group, name="GOVERNMENT")
        issuer = IssuerFactory(short_name="GOV", name="Government")

        # Create existing instrument
        Instrument.objects.create(
            organization=org_context_with_org,
            name="Test Bond",
            isin="ISIN001",
            instrument_group=group,
            instrument_type=inst_type,
            currency="XAF",
            issuer=issuer,
            valuation_method="mark_to_market",
        )

        df = pd.DataFrame(
            {
                "name": ["Test Bond Updated"],
                "isin": ["ISIN001"],  # Same ISIN
                "instrument_group_code": ["BOND"],
                "instrument_type_code": ["GOVERNMENT"],
                "currency": ["USD"],  # Different currency
                "issuer_code": ["GOV"],
                "valuation_method": ["mark_to_market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            result = import_instruments_from_file(
                file_path=tmp_path,
                sheet_name="INSTRUMENTS",
            )

            assert result["created"] == 0
            assert result["updated"] == 1

            # Verify instrument was updated
            instrument = Instrument.objects.get(isin="ISIN001")
            assert instrument.name == "Test Bond Updated"
            assert instrument.currency == "USD"

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_with_optional_fields(self, org_context_with_org):
        """Test import handles optional fields correctly."""
        group = InstrumentGroupFactory(name="BOND")
        inst_type = InstrumentTypeFactory(group=group, name="GOVERNMENT")
        issuer = IssuerFactory(short_name="GOV", name="Government")

        df = pd.DataFrame(
            {
                "name": ["Test Bond"],
                "isin": ["ISIN001"],
                "ticker": ["BOND1"],
                "instrument_group_code": ["BOND"],
                "instrument_type_code": ["GOVERNMENT"],
                "currency": ["XAF"],
                "issuer_code": ["GOV"],
                "valuation_method": ["mark_to_market"],
                "country": ["GA"],
                "maturity_date": [date(2025, 12, 31)],
                "coupon_rate": [5.5],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            result = import_instruments_from_file(
                file_path=tmp_path,
                sheet_name="INSTRUMENTS",
            )

            assert result["created"] == 1
            assert len(result["errors"]) == 0

            # Verify optional fields were set
            instrument = Instrument.objects.get(isin="ISIN001")
            assert instrument.ticker == "BOND1"
            assert instrument.country == "GA"
            assert instrument.maturity_date == date(2025, 12, 31)
            assert instrument.coupon_rate == Decimal("5.5")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_requires_org_context(self):
        """Test import fails without organization context."""
        df = pd.DataFrame(
            {
                "name": ["Test Instrument"],
                "instrument_group_code": ["BOND"],
                "instrument_type_code": ["GOVERNMENT"],
                "currency": ["XAF"],
                "issuer_code": ["GOV"],
                "valuation_method": ["mark_to_market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            with pytest.raises(RuntimeError, match="organization context"):
                import_instruments_from_file(
                    file_path=tmp_path,
                    sheet_name="INSTRUMENTS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_instruments_default_sheet_name(self, org_context_with_org):
        """Test import uses default sheet name INSTRUMENTS."""
        group = InstrumentGroupFactory(name="BOND")
        InstrumentTypeFactory(group=group, name="GOVERNMENT")
        IssuerFactory(short_name="GOV", name="Government")

        df = pd.DataFrame(
            {
                "name": ["Test Bond"],
                "instrument_group_code": ["BOND"],
                "instrument_type_code": ["GOVERNMENT"],
                "currency": ["XAF"],
                "issuer_code": ["GOV"],
                "valuation_method": ["mark_to_market"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="INSTRUMENTS")

        try:
            # Don't specify sheet_name, should use default "INSTRUMENTS"
            result = import_instruments_from_file(file_path=tmp_path)

            assert result["created"] == 1
            assert len(result["errors"]) == 0

        finally:
            Path(tmp_path).unlink(missing_ok=True)

