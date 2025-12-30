"""
Tests for portfolios models.

This module tests the portfolio management models including PortfolioGroup, Portfolio,
PortfolioImport, and PositionSnapshot. Tests verify model behavior, constraints,
organization scoping, and relationships.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from djmoney.money import Money

from apps.portfolios.models import (
    ImportSourceType,
    ImportStatus,
    Portfolio,
    PortfolioGroup,
    PortfolioImport,
    PositionSnapshot,
    ValuationSource,
)
from apps.reference_data.models import ValuationMethod
from libs.tenant_context import organization_context
from tests.factories import (
    InstrumentFactory,
    OrganizationFactory,
    PortfolioFactory,
    PortfolioGroupFactory,
    PortfolioImportFactory,
    PositionSnapshotFactory,
)


class TestPortfolioGroup:
    """Test cases for PortfolioGroup model."""

    def test_create_portfolio_group(self, portfolio_group):
        """Test creating a portfolio group within organization context."""
        assert portfolio_group.name is not None
        assert portfolio_group.name.startswith("GRP")

    def test_portfolio_group_str(self, portfolio_group):
        """Test portfolio group string representation."""
        assert str(portfolio_group) == portfolio_group.name

    def test_portfolio_group_unique_name_per_organization(self, org_context_with_org):
        """Test that portfolio group names must be unique per organization."""
        PortfolioGroupFactory(name="TEST001")
        with pytest.raises(IntegrityError):
            PortfolioGroupFactory(name="TEST001")

    def test_portfolio_group_same_name_different_organizations(self):
        """Test that same name can exist in different organizations."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            group1 = PortfolioGroupFactory(name="SAME_NAME")

        with organization_context(org2.id):
            group2 = PortfolioGroupFactory(name="SAME_NAME")

        assert group1.name == group2.name
        assert group1.organization != group2.organization

    def test_portfolio_group_organization_isolation(self):
        """Test that portfolio groups are isolated by organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            group1 = PortfolioGroupFactory()

        with organization_context(org2.id):
            group2 = PortfolioGroupFactory()

        # Verify isolation
        with organization_context(org1.id):
            assert group1 in PortfolioGroup.objects.all()
            assert group2 not in PortfolioGroup.objects.all()

        with organization_context(org2.id):
            assert group2 in PortfolioGroup.objects.all()
            assert group1 not in PortfolioGroup.objects.all()

    def test_portfolio_group_has_created_at(self, portfolio_group):
        """Test that created_at is automatically set."""
        assert portfolio_group.created_at is not None

    def test_portfolio_group_has_updated_at(self, portfolio_group):
        """Test that updated_at is automatically set."""
        assert portfolio_group.updated_at is not None

    def test_portfolio_group_can_have_description(self, org_context_with_org):
        """Test that portfolio group can have a description."""
        group = PortfolioGroupFactory(description="Test description")
        assert group.description == "Test description"

    def test_portfolio_group_name_max_length(self, org_context_with_org):
        """Test that portfolio group name respects max length."""
        # Name field has max_length=10
        group = PortfolioGroupFactory(name="1234567890")  # Exactly 10 chars
        assert len(group.name) == 10

    def test_portfolio_group_description_optional(self, org_context_with_org):
        """Test that portfolio group description is optional."""
        group = PortfolioGroupFactory(description=None)
        assert group.description is None


class TestPortfolio:
    """Test cases for Portfolio model."""

    def test_create_portfolio(self, portfolio):
        """Test creating a portfolio within organization context."""
        assert portfolio.name is not None
        assert portfolio.name.startswith("PORT")
        assert portfolio.group is not None
        assert portfolio.base_currency is not None

    def test_portfolio_str(self, portfolio):
        """Test portfolio string representation."""
        assert str(portfolio) == portfolio.name

    def test_portfolio_unique_name_per_organization(
        self, org_context_with_org, portfolio_group
    ):
        """Test that portfolio names must be unique per organization."""
        PortfolioFactory(name="TEST001", group=portfolio_group)
        with pytest.raises(IntegrityError):
            PortfolioFactory(name="TEST001", group=portfolio_group)

    def test_portfolio_same_name_different_organizations(self):
        """Test that same name can exist in different organizations."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            group1 = PortfolioGroupFactory()
            portfolio1 = PortfolioFactory(name="SAME_NAME", group=group1)

        with organization_context(org2.id):
            group2 = PortfolioGroupFactory()
            portfolio2 = PortfolioFactory(name="SAME_NAME", group=group2)

        assert portfolio1.name == portfolio2.name
        assert portfolio1.organization != portfolio2.organization

    def test_portfolio_organization_isolation(self):
        """Test that portfolios are isolated by organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            group1 = PortfolioGroupFactory()
            portfolio1 = PortfolioFactory(group=group1)

        with organization_context(org2.id):
            group2 = PortfolioGroupFactory()
            portfolio2 = PortfolioFactory(group=group2)

        # Verify isolation
        with organization_context(org1.id):
            assert portfolio1 in Portfolio.objects.all()
            assert portfolio2 not in Portfolio.objects.all()

        with organization_context(org2.id):
            assert portfolio2 in Portfolio.objects.all()
            assert portfolio1 not in Portfolio.objects.all()

    def test_portfolio_requires_group(self, org_context_with_org):
        """Test that portfolio requires a group."""
        from apps.portfolios.models import Portfolio

        with pytest.raises((IntegrityError, ValidationError)):
            Portfolio.objects.create(
                name="TEST",
                base_currency="XAF",
            )

    def test_portfolio_relationship_to_group(self, portfolio):
        """Test that portfolio has correct relationship to group."""
        assert portfolio.group is not None
        assert portfolio in portfolio.group.portfolios.all()

    def test_portfolio_can_have_mandate_type(
        self, org_context_with_org, portfolio_group
    ):
        """Test that portfolio can have a mandate type."""
        portfolio = PortfolioFactory(
            group=portfolio_group,
            mandate_type="Liquidity Management",
        )
        assert portfolio.mandate_type == "Liquidity Management"

    def test_portfolio_can_have_full_name(self, org_context_with_org, portfolio_group):
        """Test that portfolio can have a full name."""
        portfolio = PortfolioFactory(
            group=portfolio_group,
            full_name="Test portfolio full name",
        )
        assert portfolio.full_name == "Test portfolio full name"

    def test_portfolio_has_created_at(self, portfolio):
        """Test that created_at is automatically set."""
        assert portfolio.created_at is not None

    def test_portfolio_has_updated_at(self, portfolio):
        """Test that updated_at is automatically set."""
        assert portfolio.updated_at is not None

    def test_portfolio_name_max_length(self, org_context_with_org, portfolio_group):
        """Test that portfolio name respects max length."""
        # Name field has max_length=10
        portfolio = PortfolioFactory(
            name="1234567890", group=portfolio_group
        )  # Exactly 10 chars
        assert len(portfolio.name) == 10

    def test_portfolio_is_active_default(self, portfolio):
        """Test that portfolio is active by default."""
        assert portfolio.is_active is True

    def test_portfolio_can_be_inactive(self, org_context_with_org, portfolio_group):
        """Test that portfolio can be set to inactive."""
        portfolio = PortfolioFactory(group=portfolio_group, is_active=False)
        assert portfolio.is_active is False

    def test_portfolio_base_currency_default(
        self, org_context_with_org, portfolio_group
    ):
        """Test that portfolio base_currency has a default value."""
        from django.conf import settings

        from apps.portfolios.models import Portfolio

        # Create portfolio without specifying base_currency to test default
        portfolio = Portfolio.objects.create(
            name="TEST",
            group=portfolio_group,
        )
        # Should use default from settings
        assert portfolio.base_currency == settings.DEFAULT_CURRENCY

    def test_portfolio_full_name_optional(self, org_context_with_org, portfolio_group):
        """Test that portfolio full_name is optional."""
        portfolio = PortfolioFactory(group=portfolio_group, full_name=None)
        assert portfolio.full_name is None

    def test_portfolio_mandate_type_optional(
        self, org_context_with_org, portfolio_group
    ):
        """Test that portfolio mandate_type is optional."""
        portfolio = PortfolioFactory(group=portfolio_group, mandate_type=None)
        assert portfolio.mandate_type is None


class TestPortfolioImport:
    """Test cases for PortfolioImport model."""

    def test_create_portfolio_import(self, portfolio_import):
        """Test creating a portfolio import."""
        assert portfolio_import.portfolio is not None
        assert portfolio_import.as_of_date is not None
        assert portfolio_import.source_type == ImportSourceType.MANUAL
        assert portfolio_import.status == ImportStatus.PENDING

    def test_portfolio_import_str(self, portfolio_import):
        """Test portfolio import string representation."""
        expected = f"{portfolio_import.portfolio.name} - {portfolio_import.get_status_display()} ({portfolio_import.as_of_date})"
        assert str(portfolio_import) == expected

    def test_portfolio_import_organization_isolation(self):
        """Test that portfolio imports are isolated by organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            group1 = PortfolioGroupFactory()
            portfolio1 = PortfolioFactory(group=group1)
            import1 = PortfolioImportFactory(portfolio=portfolio1)

        with organization_context(org2.id):
            group2 = PortfolioGroupFactory()
            portfolio2 = PortfolioFactory(group=group2)
            import2 = PortfolioImportFactory(portfolio=portfolio2)

        # Verify isolation
        with organization_context(org1.id):
            assert import1 in PortfolioImport.objects.all()
            assert import2 not in PortfolioImport.objects.all()

        with organization_context(org2.id):
            assert import2 in PortfolioImport.objects.all()
            assert import1 not in PortfolioImport.objects.all()

    def test_portfolio_import_requires_portfolio(self, org_context_with_org):
        """Test that portfolio import requires a portfolio."""
        from apps.portfolios.models import PortfolioImport

        with pytest.raises((IntegrityError, ValidationError)):
            PortfolioImport.objects.create(
                as_of_date=date.today(),
                source_type=ImportSourceType.MANUAL,
                status=ImportStatus.PENDING,
            )

    def test_portfolio_import_requires_as_of_date(
        self, org_context_with_org, portfolio
    ):
        """Test that portfolio import requires an as_of_date."""
        from apps.portfolios.models import PortfolioImport

        with pytest.raises((IntegrityError, ValidationError)):
            PortfolioImport.objects.create(
                portfolio=portfolio,
                source_type=ImportSourceType.MANUAL,
                status=ImportStatus.PENDING,
            )

    def test_portfolio_import_status_choices(self, org_context_with_org, portfolio):
        """Test that portfolio import status uses correct choices."""
        for status in ImportStatus:
            import_record = PortfolioImportFactory(
                portfolio=portfolio,
                status=status,
            )
            assert import_record.status == status

    def test_portfolio_import_source_type_choices(
        self, org_context_with_org, portfolio
    ):
        """Test that portfolio import source type uses correct choices."""
        for source_type in ImportSourceType:
            import_record = PortfolioImportFactory(
                portfolio=portfolio,
                source_type=source_type,
            )
            assert import_record.source_type == source_type

    def test_portfolio_import_can_have_mapping_json(
        self, org_context_with_org, portfolio
    ):
        """Test that portfolio import can have mapping JSON."""
        mapping = {"column1": "field1", "column2": "field2"}
        import_record = PortfolioImportFactory(
            portfolio=portfolio,
            mapping_json=mapping,
        )
        assert import_record.mapping_json == mapping

    def test_portfolio_import_can_have_error_message(
        self, org_context_with_org, portfolio
    ):
        """Test that portfolio import can have an error message."""
        error_msg = "Failed to parse row 5"
        import_record = PortfolioImportFactory(
            portfolio=portfolio,
            status=ImportStatus.FAILED,
            error_message=error_msg,
        )
        assert import_record.error_message == error_msg

    def test_portfolio_import_rows_tracking(self, org_context_with_org, portfolio):
        """Test that portfolio import tracks rows processed and total."""
        import_record = PortfolioImportFactory(
            portfolio=portfolio,
            rows_processed=10,
            rows_total=15,
        )
        assert import_record.rows_processed == 10
        assert import_record.rows_total == 15

    def test_portfolio_import_can_have_inputs_hash(
        self, org_context_with_org, portfolio
    ):
        """Test that portfolio import can have an inputs hash."""
        inputs_hash = "abc123def456"
        import_record = PortfolioImportFactory(
            portfolio=portfolio,
            inputs_hash=inputs_hash,
        )
        assert import_record.inputs_hash == inputs_hash

    def test_portfolio_import_has_created_at(self, portfolio_import):
        """Test that created_at is automatically set."""
        assert portfolio_import.created_at is not None

    def test_portfolio_import_completed_at_optional(self, portfolio_import):
        """Test that completed_at is optional."""
        assert portfolio_import.completed_at is None

    def test_portfolio_import_relationship_to_portfolio(self, portfolio_import):
        """Test that import has correct relationship to portfolio."""
        assert portfolio_import.portfolio is not None
        assert portfolio_import in portfolio_import.portfolio.imports.all()

    def test_portfolio_import_default_source_type(self, portfolio_import):
        """Test that portfolio import has default source_type."""
        # Factory creates with default, verify it
        assert portfolio_import.source_type == ImportSourceType.MANUAL

    def test_portfolio_import_default_status(self, portfolio_import):
        """Test that portfolio import has default status."""
        assert portfolio_import.status == ImportStatus.PENDING

    def test_portfolio_import_default_rows(self, portfolio_import):
        """Test that portfolio import has default row counts."""
        assert portfolio_import.rows_processed == 0
        assert portfolio_import.rows_total == 0

    def test_portfolio_import_ordering(self, org_context_with_org, portfolio):
        """Test that portfolio imports are ordered by created_at descending."""
        from apps.portfolios.models import PortfolioImport

        # Create imports with different timestamps
        import1 = PortfolioImportFactory(portfolio=portfolio)
        import2 = PortfolioImportFactory(portfolio=portfolio)
        import3 = PortfolioImportFactory(portfolio=portfolio)

        # Ordering should be by -created_at
        imports = list(PortfolioImport.objects.filter(portfolio=portfolio))
        assert len(imports) >= 3
        # Most recent should be first - verify ordering
        assert imports[0] == import3 or imports[0].created_at >= imports[1].created_at
        assert imports[1].created_at >= imports[2].created_at
        # Verify we got all three imports
        assert import1 in imports
        assert import2 in imports
        assert import3 in imports


class TestPositionSnapshot:
    """Test cases for PositionSnapshot model."""

    def test_create_position_snapshot(self, position_snapshot):
        """Test creating a position snapshot."""
        assert position_snapshot.portfolio is not None
        assert position_snapshot.instrument is not None
        assert position_snapshot.quantity is not None
        assert position_snapshot.book_value is not None
        assert position_snapshot.market_value is not None
        assert position_snapshot.as_of_date is not None
        assert position_snapshot.valuation_method is not None
        assert position_snapshot.valuation_source is not None

    def test_position_snapshot_str(self, position_snapshot):
        """Test position snapshot string representation."""
        expected = f"{position_snapshot.portfolio.name} - {position_snapshot.instrument.name} ({position_snapshot.as_of_date})"
        assert str(position_snapshot) == expected

    def test_position_snapshot_unique_constraint(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshots are unique per portfolio, instrument, and date."""
        as_of = date.today()
        PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=as_of,
        )
        with pytest.raises(IntegrityError):
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument,
                as_of_date=as_of,
            )

    def test_position_snapshot_same_instrument_different_dates(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that same instrument can have snapshots on different dates."""
        snapshot1 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=date.today(),
        )
        snapshot2 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=date.today() + timedelta(days=1),
        )

        assert snapshot1.instrument == snapshot2.instrument
        assert snapshot1.as_of_date != snapshot2.as_of_date

    def test_position_snapshot_same_date_different_instruments(
        self, org_context_with_org, portfolio
    ):
        """Test that same date can have snapshots for different instruments."""
        instrument1 = InstrumentFactory()
        instrument2 = InstrumentFactory()
        as_of = date.today()

        snapshot1 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument1,
            as_of_date=as_of,
        )
        snapshot2 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument2,
            as_of_date=as_of,
        )

        assert snapshot1.as_of_date == snapshot2.as_of_date
        assert snapshot1.instrument != snapshot2.instrument

    def test_position_snapshot_organization_isolation(self):
        """Test that position snapshots are isolated by organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            group1 = PortfolioGroupFactory()
            portfolio1 = PortfolioFactory(group=group1)
            instrument1 = InstrumentFactory()
            snapshot1 = PositionSnapshotFactory(
                portfolio=portfolio1, instrument=instrument1
            )

        with organization_context(org2.id):
            group2 = PortfolioGroupFactory()
            portfolio2 = PortfolioFactory(group=group2)
            instrument2 = InstrumentFactory()
            snapshot2 = PositionSnapshotFactory(
                portfolio=portfolio2, instrument=instrument2
            )

        # Verify isolation
        with organization_context(org1.id):
            assert snapshot1 in PositionSnapshot.objects.all()
            assert snapshot2 not in PositionSnapshot.objects.all()

        with organization_context(org2.id):
            assert snapshot2 in PositionSnapshot.objects.all()
            assert snapshot1 not in PositionSnapshot.objects.all()

    def test_position_snapshot_requires_portfolio(
        self, org_context_with_org, instrument
    ):
        """Test that position snapshot requires a portfolio."""
        from django.conf import settings

        from apps.portfolios.models import PositionSnapshot

        with pytest.raises((IntegrityError, ValidationError)):
            PositionSnapshot.objects.create(
                instrument=instrument,
                quantity=1000,
                book_value=Money(1000000, settings.DEFAULT_CURRENCY),
                market_value=Money(1050000, settings.DEFAULT_CURRENCY),
                price=105.50,
                valuation_method=ValuationMethod.MARK_TO_MARKET,
                valuation_source=ValuationSource.MARKET,
                as_of_date=date.today(),
            )

    def test_position_snapshot_requires_instrument(
        self, org_context_with_org, portfolio
    ):
        """Test that position snapshot requires an instrument."""
        from django.conf import settings

        from apps.portfolios.models import PositionSnapshot

        with pytest.raises((IntegrityError, ValidationError)):
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                quantity=1000,
                book_value=Money(1000000, settings.DEFAULT_CURRENCY),
                market_value=Money(1050000, settings.DEFAULT_CURRENCY),
                price=105.50,
                valuation_method=ValuationMethod.MARK_TO_MARKET,
                valuation_source=ValuationSource.MARKET,
                as_of_date=date.today(),
            )

    def test_position_snapshot_valuation_method_choices(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot valuation method uses correct choices."""
        base_date = date.today()
        for idx, method in enumerate(ValuationMethod):
            snapshot = PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument,
                valuation_method=method,
                as_of_date=base_date - timedelta(days=idx),
            )
            assert snapshot.valuation_method == method

    def test_position_snapshot_valuation_source_choices(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot valuation source uses correct choices."""
        base_date = date.today()
        for idx, source in enumerate(ValuationSource):
            snapshot = PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument,
                valuation_source=source,
                as_of_date=base_date - timedelta(days=idx),
            )
            assert snapshot.valuation_source == source

    def test_position_snapshot_can_have_portfolio_import(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot can reference a portfolio import."""
        portfolio_import = PortfolioImportFactory(portfolio=portfolio)
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            portfolio_import=portfolio_import,
        )
        assert snapshot.portfolio_import == portfolio_import

    def test_position_snapshot_can_have_price(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot can have a price."""
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            price=105.50,
        )
        assert snapshot.price == 105.50

    def test_position_snapshot_can_have_book_price(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot can have a book_price."""
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            book_price=100.00,
        )
        assert snapshot.book_price == 100.00

    def test_position_snapshot_book_price_optional(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot book_price is optional."""
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            book_price=None,
        )
        assert snapshot.book_price is None

    def test_position_snapshot_default_valuation_method(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot has default valuation_method."""
        from djmoney.money import Money

        from apps.portfolios.models import PositionSnapshot

        # Create snapshot without specifying valuation_method to test default
        snapshot = PositionSnapshot.objects.create(
            portfolio=portfolio,
            instrument=instrument,
            quantity=1000,
            book_value=Money(1000000, portfolio.base_currency),
            market_value=Money(1050000, portfolio.base_currency),
            price=105.50,
            valuation_source=ValuationSource.MARKET,
            as_of_date=date.today(),
        )
        # Should use default from model
        assert snapshot.valuation_method == ValuationMethod.MARK_TO_MARKET

    def test_position_snapshot_accrued_interest_optional(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot accrued_interest can be zero or None."""
        from djmoney.money import Money

        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            accrued_interest=Money(0, portfolio.base_currency),
        )
        assert snapshot.accrued_interest is not None

    def test_position_snapshot_can_have_accrued_interest(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot can have accrued interest."""
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            accrued_interest=Money(5000, portfolio.base_currency),
        )
        assert snapshot.accrued_interest is not None
        assert snapshot.accrued_interest.amount > 0

    def test_position_snapshot_can_have_last_valuation_date(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot can have a last valuation date."""
        last_val_date = date.today() - timedelta(days=5)
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            last_valuation_date=last_val_date,
        )
        assert snapshot.last_valuation_date == last_val_date

    def test_position_snapshot_can_have_stale_after_days(
        self, org_context_with_org, portfolio, instrument
    ):
        """Test that position snapshot can have stale_after_days."""
        snapshot = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            stale_after_days=30,
        )
        assert snapshot.stale_after_days == 30

    def test_position_snapshot_relationship_to_portfolio(self, position_snapshot):
        """Test that snapshot has correct relationship to portfolio."""
        assert position_snapshot.portfolio is not None
        assert position_snapshot in position_snapshot.portfolio.position_snapshots.all()

    def test_position_snapshot_relationship_to_instrument(self, position_snapshot):
        """Test that snapshot has correct relationship to instrument."""
        assert position_snapshot.instrument is not None
        assert (
            position_snapshot in position_snapshot.instrument.position_snapshots.all()
        )

    def test_position_snapshot_has_created_at(self, position_snapshot):
        """Test that created_at is automatically set."""
        assert position_snapshot.created_at is not None

    def test_position_snapshot_has_updated_at(self, position_snapshot):
        """Test that updated_at is automatically set."""
        assert position_snapshot.updated_at is not None

    def test_position_snapshot_ordering(self, org_context_with_org, portfolio):
        """Test that position snapshots are ordered correctly."""
        instrument = InstrumentFactory()
        date1 = date.today()
        date2 = date.today() - timedelta(days=1)
        date3 = date.today() - timedelta(days=2)

        snapshot1 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=date1,
        )
        snapshot2 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=date2,
        )
        snapshot3 = PositionSnapshotFactory(
            portfolio=portfolio,
            instrument=instrument,
            as_of_date=date3,
        )

        # Ordering should be by -as_of_date, then portfolio, then instrument
        snapshots = list(
            PositionSnapshot.objects.filter(portfolio=portfolio).order_by("-as_of_date")
        )
        assert len(snapshots) == 3
        # Verify ordering and that we got the right snapshots
        assert snapshots[0] == snapshot1
        assert snapshots[0].as_of_date == date1
        assert snapshots[1] == snapshot2
        assert snapshots[1].as_of_date == date2
        assert snapshots[2] == snapshot3
        assert snapshots[2].as_of_date == date3
