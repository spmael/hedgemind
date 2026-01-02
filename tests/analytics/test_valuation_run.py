# tests/analytics/test_valuation_run.py (create this file)

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.money import Money

from apps.analytics.models import RunStatus, ValuationPolicy, ValuationRun
from apps.portfolios.models import PositionSnapshot
from libs.tenant_context import organization_context
from tests.factories import InstrumentFactory, PortfolioFactory, PortfolioGroupFactory


@pytest.mark.django_db
class TestValuationRun:
    """Test cases for ValuationRun model."""

    def test_create_valuation_run(self, organization):
        """Test basic creation of ValuationRun."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.PENDING,
            )

        assert run.portfolio == portfolio
        assert run.as_of_date == date(2025, 1, 15)
        assert run.valuation_policy == ValuationPolicy.USE_SNAPSHOT_MV
        assert run.status == RunStatus.PENDING
        assert run.is_official is False
        assert run.organization == organization
        assert run.inputs_hash is not None  # Should be auto-computed

    def test_valuation_run_str(self, organization):
        """Test string representation."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
            )

        str_repr = str(run)
        assert portfolio.name in str_repr
        assert "2025-01-15" in str_repr or "Jan 15" in str_repr

    def test_execute_valuation_run_policy_a(self, organization):
        """Test executing a valuation run with Policy A."""
        from apps.analytics.models import ValuationPositionResult

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create instrument and position snapshot
            instrument = InstrumentFactory(currency="XAF")
            snapshot = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            # Create valuation run
            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )

            # Execute valuation
            run.execute()

            # Verify results
            run.refresh_from_db()
            assert run.status == RunStatus.SUCCESS

            results = ValuationPositionResult.objects.filter(valuation_run=run)
            assert results.count() == 1

            result = results.first()
            assert result.position_snapshot == snapshot
            assert result.market_value_original_currency == Money(1050000, "XAF")
            assert result.market_value_base_currency == Money(1050000, "XAF")
            assert result.fx_rate_used is None  # No conversion needed

    def test_mark_as_official_unmarks_previous(self, organization, user):
        """Test that marking a run as official unmarks previous official run."""
        from apps.audit.models import AuditEvent

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            # Create position snapshots to ensure runs have different inputs_hash
            instrument1 = InstrumentFactory(currency="XAF")
            _snapshot1 = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            # Create first run and mark as official
            run1 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.SUCCESS,
                organization=organization,
            )
            run1.is_official = True
            run1.save()

            # Create additional snapshot so run2 has different inputs_hash
            instrument2 = InstrumentFactory(currency="XAF")
            _snapshot2 = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                book_value=Money(500000, "XAF"),
                market_value=Money(525000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            # Create second run (will have different inputs_hash due to additional snapshot)
            run2 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.SUCCESS,
                organization=organization,
            )

            # Mark run2 as official
            run2.mark_as_official(reason="New approved run", actor=user)

            # Verify run1 is no longer official
            run1.refresh_from_db()
            assert run1.is_official is False

            # Verify run2 is official
            run2.refresh_from_db()
            assert run2.is_official is True

            # Verify audit event was created
            audit_events = AuditEvent.objects.filter(
                object_type="ValuationRun",
                object_id=run2.id,
                action="MARK_VALUATION_OFFICIAL",
            )
            assert audit_events.exists()
            event = audit_events.first()
            assert event.metadata["reason"] == "New approved run"
            assert event.metadata["previous_official_run_id"] == run1.id

    def test_mark_as_official_requires_success_status(self, organization):
        """Test that only SUCCESS runs can be marked as official."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.PENDING,  # Not SUCCESS
                organization=organization,
            )

            with pytest.raises(ValidationError, match="must be in SUCCESS status"):
                run.mark_as_official(reason="Test", actor=None)

    def test_unmark_as_official(self, organization, user):
        """Test unmarking an official run."""
        from apps.audit.models import AuditEvent

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.SUCCESS,
                is_official=True,
                organization=organization,
            )

            run.unmark_as_official(reason="Replaced by new run", actor=user)

            run.refresh_from_db()
            assert run.is_official is False

            # Verify audit event
            audit_events = AuditEvent.objects.filter(
                object_type="ValuationRun",
                object_id=run.id,
                action="UNMARK_VALUATION_OFFICIAL",
            )
            assert audit_events.exists()
            event = audit_events.first()
            assert event.metadata["reason"] == "Replaced by new run"

    def test_get_results(self, organization):
        """Test get_results() method."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            instrument = InstrumentFactory(currency="XAF")
            snapshot = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )
            run.execute()

            results = run.get_results()
            assert results.count() == 1
            assert results.first().position_snapshot == snapshot

    def test_get_total_market_value(self, organization):
        """Test get_total_market_value() method."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create two positions
            instrument1 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            instrument2 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                book_value=Money(500000, "XAF"),
                market_value=Money(525000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )
            run.execute()

            total = run.get_total_market_value()
            assert total == Money(1575000, "XAF")  # 1050000 + 525000

    def test_get_data_quality_summary(self, organization):
        """Test get_data_quality_summary() method."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            instrument = InstrumentFactory(currency="USD")  # Different currency
            _snapshot = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument,
                quantity=Decimal("1000"),
                book_value=Money(1000, "USD"),
                market_value=Money(1000, "USD"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )
            run.execute()

            summary = run.get_data_quality_summary()
            assert summary["total_positions"] == 1
            # Should have missing FX rate issue (unless FX rate exists)
            assert "missing_fx_rates" in summary

    def test_manager_official(self, organization):
        """Test official() manager method."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            # Create official and non-official runs
            run1 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                is_official=True,
                organization=organization,
            )

            run2 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 16),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                is_official=False,
                organization=organization,
            )

            official_runs = ValuationRun.objects.official()
            assert run1 in official_runs
            assert run2 not in official_runs

    def test_manager_for_portfolio_date(self, organization):
        """Test for_portfolio_date() manager method."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            run1 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )

            run2 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 16),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )

            runs = ValuationRun.objects.for_portfolio_date(portfolio, date(2025, 1, 15))
            assert run1 in runs
            assert run2 not in runs

    def test_manager_latest_official(self, organization):
        """Test latest_official() manager method."""
        from datetime import timedelta

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            # Create position snapshot for first run (to give it a unique inputs_hash)
            instrument1 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            # Create multiple official runs (shouldn't normally happen, but test it)
            ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                is_official=True,
                created_at=timezone.now() - timedelta(days=1),
                organization=organization,
            )

            # Create additional position snapshot for second run (different inputs_hash)
            instrument2 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                book_value=Money(500000, "XAF"),
                market_value=Money(525000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            run2 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                is_official=True,
                created_at=timezone.now(),
                organization=organization,
            )

            latest = ValuationRun.objects.latest_official(portfolio, date(2025, 1, 15))
            assert latest == run2  # Should be the most recent

    def test_data_quality_flags_display(self, organization):
        """Test get_data_quality_flags_display() method."""
        from apps.analytics.models import ValuationPositionResult

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )

            # Create result with data quality flags
            instrument = InstrumentFactory(currency="USD")
            snapshot = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument,
                quantity=Decimal("1000"),
                book_value=Money(1000, "USD"),
                market_value=Money(1000, "USD"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            result = ValuationPositionResult.objects.create(
                valuation_run=run,
                position_snapshot=snapshot,
                market_value_original_currency=Money(1000, "USD"),
                market_value_base_currency=Money(0, "XAF"),
                data_quality_flags={
                    "missing_fx_rate": True,
                    "fx_currency_pair": "USD/XAF",
                },
                organization=organization,
            )

            flags_str = result.get_data_quality_flags_display()
            assert "Missing FX rate" in flags_str
            assert "USD/XAF" in flags_str

    def test_aggregates_stored_after_execution(self, organization):
        """Test that aggregates are stored after run execution."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create positions
            instrument1 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            instrument2 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                book_value=Money(500000, "XAF"),
                market_value=Money(525000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )
            run.execute()

            # Verify aggregates are stored
            run.refresh_from_db()
            assert run.total_market_value == Money(1575000, "XAF")
            assert run.position_count == 2
            assert run.positions_with_issues == 0
            assert run.missing_fx_count == 0

    def test_recalculate_total_market_value_engine_function(self, organization):
        """Test recalculate_total_market_value engine function."""
        from apps.analytics.engine.aggregation import recalculate_total_market_value

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create positions
            instrument1 = InstrumentFactory(currency="XAF")
            PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                organization=organization,
            )
            run.execute()

            # Test engine function
            recalculated = recalculate_total_market_value(run)
            assert recalculated == Money(1050000, "XAF")
            assert recalculated == run.total_market_value  # Should match stored value

    def test_create_valuation_run_with_run_context_id(self, organization):
        """Test creating ValuationRun with run_context_id."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.PENDING,
                run_context_id="batch-2025-01-15-001",
            )

        assert run.run_context_id == "batch-2025-01-15-001"
        assert run.organization == organization

    def test_create_valuation_run_without_run_context_id(self, organization):
        """Test backward compatibility: creating run without run_context_id."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                status=RunStatus.PENDING,
            )

        assert run.run_context_id is None
        assert run.organization == organization

    def test_with_run_context_queryset_method(self, organization):
        """Test with_run_context() QuerySet method."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio1 = PortfolioFactory(
                organization=organization, group=portfolio_group
            )
            portfolio2 = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            # Create runs with different run_context_id values
            run1 = ValuationRun.objects.create(
                portfolio=portfolio1,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id="batch-001",
            )

            run2 = ValuationRun.objects.create(
                portfolio=portfolio2,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id="batch-001",
            )

            run3 = ValuationRun.objects.create(
                portfolio=portfolio1,
                as_of_date=date(2025, 1, 16),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id="batch-002",
            )

            # Filter by run_context_id
            batch_001_runs = ValuationRun.objects.with_run_context("batch-001")
            assert run1 in batch_001_runs
            assert run2 in batch_001_runs
            assert run3 not in batch_001_runs
            assert batch_001_runs.count() == 2

    def test_grouping_runs_with_same_run_context_id(self, organization):
        """Test that multiple runs can share the same run_context_id."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio1 = PortfolioFactory(
                organization=organization, group=portfolio_group
            )
            portfolio2 = PortfolioFactory(
                organization=organization, group=portfolio_group
            )
            portfolio3 = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            # Create multiple runs with same run_context_id (batch run)
            run_context = "daily-close-2025-01-15"

            run1 = ValuationRun.objects.create(
                portfolio=portfolio1,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id=run_context,
            )

            run2 = ValuationRun.objects.create(
                portfolio=portfolio2,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id=run_context,
            )

            run3 = ValuationRun.objects.create(
                portfolio=portfolio3,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id=run_context,
            )

            # All runs should have the same run_context_id
            assert run1.run_context_id == run_context
            assert run2.run_context_id == run_context
            assert run3.run_context_id == run_context

            # Query all runs in this batch
            batch_runs = ValuationRun.objects.with_run_context(run_context)
            assert batch_runs.count() == 3
            assert run1 in batch_runs
            assert run2 in batch_runs
            assert run3 in batch_runs

    def test_run_context_id_independent_of_inputs_hash(self, organization):
        """Test that run_context_id is independent of inputs_hash."""
        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

            # Create first position snapshot
            instrument1 = InstrumentFactory(currency="XAF")
            snapshot1 = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                book_value=Money(1000000, "XAF"),
                market_value=Money(1050000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            # Create first run with run_context_id
            run1 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id="batch-001",
            )

            # Verify snapshot1 is included in run1's inputs
            assert snapshot1 in PositionSnapshot.objects.filter(
                portfolio=portfolio, as_of_date=date(2025, 1, 15)
            )

            # Create second position snapshot (different inputs_hash)
            instrument2 = InstrumentFactory(currency="XAF")
            snapshot2 = PositionSnapshot.objects.create(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                book_value=Money(500000, "XAF"),
                market_value=Money(525000, "XAF"),
                valuation_source="custodian",
                as_of_date=date(2025, 1, 15),
                organization=organization,
            )

            # Verify snapshot2 is now included in portfolio snapshots
            assert snapshot2 in PositionSnapshot.objects.filter(
                portfolio=portfolio, as_of_date=date(2025, 1, 15)
            )

            # Create second run with same run_context_id but different inputs
            run2 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 15),
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id="batch-001",  # Same run_context_id
            )

            # Verify they have same run_context_id but different inputs_hash
            assert run1.run_context_id == run2.run_context_id
            assert run1.inputs_hash != run2.inputs_hash

            # Create third run with different run_context_id but same inputs as run2
            # Note: We can't create a run with same inputs_hash for same portfolio/date
            # due to unique constraint (which is correct - prevents duplicate computation).
            # Instead, we'll create a run for a different date with same snapshots to show
            # that run_context_id is independent of inputs_hash conceptually.
            # For the same portfolio/date, the unique constraint correctly prevents
            # duplicate runs with identical inputs, regardless of run_context_id.

            # Create run for different date with same snapshots (will have different inputs_hash
            # because as_of_date is part of the hash computation)
            run3 = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=date(2025, 1, 16),  # Different date
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
                run_context_id="batch-002",  # Different run_context_id
            )

            # Verify that run_context_id can be different even when conceptually
            # processing similar data (different dates, but same portfolio)
            assert run2.run_context_id != run3.run_context_id
            # They will have different inputs_hash because as_of_date differs
            assert run2.inputs_hash != run3.inputs_hash

            # The key point: run_context_id is independent - same data (different dates)
            # can have different run_context_ids, and different data can share same
            # run_context_id (as shown in run1 and run2 above)
