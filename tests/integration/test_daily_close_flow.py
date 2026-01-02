"""
Integration tests for daily close flow: portfolio → valuation → exposure → report.

Tests the complete flow from portfolio data through valuation, exposure computation,
and report generation to ensure all components work together correctly.
"""

from datetime import date
from decimal import Decimal

import pytest
from djmoney.money import Money

from apps.analytics.models import (
    ExposureDimensionType,
    ExposureResult,
    RunStatus,
    ValuationPolicy,
    ValuationRun,
)
from apps.etl.orchestration.daily_close import run_portfolio_daily_close
from apps.reports.models import Report, ReportStatus
from libs.tenant_context import organization_context
from tests.factories import (
    FXRateFactory,
    InstrumentFactory,
    IssuerFactory,
    MarketDataSourceFactory,
    PortfolioFactory,
    PortfolioGroupFactory,
    PositionSnapshotFactory,
)


@pytest.mark.django_db
class TestDailyCloseFlow:
    """Test cases for the complete daily close flow."""

    def test_run_portfolio_daily_close_full_flow(self, organization):
        """Test the complete daily close flow for a portfolio."""
        as_of_date = date(2025, 1, 15)

        with organization_context(organization.id):
            # Setup: Create portfolio, instruments, and position snapshots
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create issuers and instruments with different currencies
            issuer1 = IssuerFactory(name="Issuer 1", country="CM")
            issuer2 = IssuerFactory(name="Issuer 2", country="US")
            instrument1 = InstrumentFactory(
                currency="XAF", issuer=issuer1, country="CM"
            )
            instrument2 = InstrumentFactory(
                currency="USD", issuer=issuer2, country="US"
            )

            # Create FX rate for USD/XAF
            market_data_source = MarketDataSourceFactory()
            FXRateFactory(
                base_currency="XAF",
                quote_currency="USD",
                rate=Decimal("0.0016"),
                date=as_of_date,
                chosen_source=market_data_source,
            )

            # Create position snapshots
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                market_value=Money(1000000, "XAF"),
                as_of_date=as_of_date,
            )
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                market_value=Money(10000, "USD"),
                as_of_date=as_of_date,
            )

        # Run daily close
        result = run_portfolio_daily_close(
            portfolio_id=portfolio.id, as_of_date=as_of_date, org_id=organization.id
        )

        # Verify execution summary
        assert result["portfolio_id"] == portfolio.id
        assert result["portfolio_name"] == portfolio.name
        assert result["valuation_status"] == RunStatus.SUCCESS
        assert result["exposures_computed"] is True
        assert len(result["errors"]) == 0

        # Verify valuation run was created and executed
        with organization_context(organization.id):
            valuation_run = ValuationRun.objects.get(id=result["valuation_run_id"])
            assert valuation_run.status == RunStatus.SUCCESS
            assert valuation_run.portfolio == portfolio
            assert valuation_run.as_of_date == as_of_date

            # Verify position results were created
            position_results = valuation_run.get_results()
            assert position_results.count() == 2

            # Verify exposures were computed and stored
            exposures = valuation_run.get_exposures()
            assert exposures.count() > 0

            # Verify currency exposures exist
            currency_exposures = valuation_run.get_exposures(
                ExposureDimensionType.CURRENCY
            )
            assert currency_exposures.count() >= 2  # XAF and USD at minimum

            # Verify issuer exposures exist
            issuer_exposures = valuation_run.get_exposures(ExposureDimensionType.ISSUER)
            assert issuer_exposures.count() >= 2  # At least 2 issuers

            # Verify country exposures exist
            country_exposures = valuation_run.get_exposures(
                ExposureDimensionType.COUNTRY
            )
            assert country_exposures.count() >= 2  # CM and US at minimum

            # Verify report was generated (if renderer is available)
            if result["report_id"]:
                report = Report.objects.get(id=result["report_id"])
                assert report.status == ReportStatus.SUCCESS
                assert report.valuation_run == valuation_run
                assert report.pdf_file is not None

    def test_run_portfolio_daily_close_no_snapshots(self, organization):
        """Test daily close fails gracefully when no snapshots exist."""
        as_of_date = date(2025, 1, 15)

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization, group=portfolio_group
            )

        # Attempt to run daily close without snapshots
        with pytest.raises(ValueError, match="No PositionSnapshots found"):
            run_portfolio_daily_close(
                portfolio_id=portfolio.id,
                as_of_date=as_of_date,
                org_id=organization.id,
            )

    def test_run_portfolio_daily_close_idempotent(self, organization):
        """Test that running daily close twice is idempotent."""
        as_of_date = date(2025, 1, 15)

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            instrument = InstrumentFactory(currency="XAF")
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument,
                quantity=Decimal("1000"),
                market_value=Money(1000000, "XAF"),
                as_of_date=as_of_date,
            )

        # Run daily close first time
        result1 = run_portfolio_daily_close(
            portfolio_id=portfolio.id, as_of_date=as_of_date, org_id=organization.id
        )
        valuation_run_id_1 = result1["valuation_run_id"]

        # Run daily close second time (should reuse existing run)
        result2 = run_portfolio_daily_close(
            portfolio_id=portfolio.id, as_of_date=as_of_date, org_id=organization.id
        )
        valuation_run_id_2 = result2["valuation_run_id"]

        # Should reuse the same run (get_or_create)
        assert valuation_run_id_1 == valuation_run_id_2

    def test_exposure_computation_accuracy(self, organization):
        """Test that exposure computations are accurate."""
        as_of_date = date(2025, 1, 15)

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create instruments with known values
            issuer = IssuerFactory(name="Test Issuer")
            instrument1 = InstrumentFactory(currency="XAF", issuer=issuer, country="CM")
            instrument2 = InstrumentFactory(currency="XAF", issuer=issuer, country="CM")

            # Create position snapshots with specific values
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                market_value=Money(1000000, "XAF"),  # 1M XAF
                as_of_date=as_of_date,
            )
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                market_value=Money(500000, "XAF"),  # 500K XAF
                as_of_date=as_of_date,
            )

            # Create valuation run and execute
            valuation_run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=as_of_date,
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
            )
            valuation_run.execute()

            # Compute exposures
            valuation_run.compute_and_store_exposures()

            # Verify total market value
            total_mv = valuation_run.get_total_market_value()
            assert total_mv.amount == Decimal("1500000")  # 1M + 500K

            # Verify issuer exposure matches total
            issuer_exposures = valuation_run.get_exposures(ExposureDimensionType.ISSUER)
            assert issuer_exposures.count() == 1
            issuer_exposure = issuer_exposures.first()
            assert issuer_exposure.value_base.amount == Decimal("1500000")
            assert issuer_exposure.pct_total == Decimal("100.0000")

            # Verify currency exposure
            currency_exposures = valuation_run.get_exposures(
                ExposureDimensionType.CURRENCY
            )
            assert currency_exposures.count() == 1
            currency_exposure = currency_exposures.first()
            assert currency_exposure.value_base.amount == Decimal("1500000")
            assert currency_exposure.dimension_key == "XAF"

    def test_report_generation(self, organization):
        """Test that reports are generated correctly."""
        as_of_date = date(2025, 1, 15)

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            instrument = InstrumentFactory(currency="XAF")
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument,
                quantity=Decimal("1000"),
                market_value=Money(1000000, "XAF"),
                as_of_date=as_of_date,
            )

            # Create and execute valuation run
            valuation_run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=as_of_date,
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
            )
            valuation_run.execute()
            valuation_run.compute_and_store_exposures()

            # Generate report
            from apps.reports.renderers.portfolio_report import (
                generate_portfolio_report,
            )

            report = generate_portfolio_report(valuation_run.id)

            # Verify report was created
            assert report.status == ReportStatus.SUCCESS
            assert report.valuation_run == valuation_run
            assert report.template is not None
            assert report.pdf_file is not None
            assert report.csv_file is not None
            assert report.excel_file is not None
            assert report.generated_at is not None

            # Verify report template was created
            template = report.template
            assert template.name == "Portfolio Overview v1"
            assert template.version == "1.0"
            assert template.template_type == "portfolio_overview"

    def test_exposure_results_persisted(self, organization):
        """Test that exposure results are properly persisted."""
        as_of_date = date(2025, 1, 15)

        with organization_context(organization.id):
            portfolio_group = PortfolioGroupFactory(organization=organization)
            portfolio = PortfolioFactory(
                organization=organization,
                group=portfolio_group,
                base_currency="XAF",
            )

            # Create multiple instruments with different attributes
            issuer1 = IssuerFactory(name="Issuer 1")
            issuer2 = IssuerFactory(name="Issuer 2")
            instrument1 = InstrumentFactory(
                currency="XAF", issuer=issuer1, country="CM"
            )
            instrument2 = InstrumentFactory(
                currency="USD", issuer=issuer2, country="US"
            )

            # Create FX rate
            market_data_source = MarketDataSourceFactory()
            FXRateFactory(
                base_currency="XAF",
                quote_currency="USD",
                rate=Decimal("0.0016"),
                date=as_of_date,
                chosen_source=market_data_source,
            )

            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument1,
                quantity=Decimal("1000"),
                market_value=Money(1000000, "XAF"),
                as_of_date=as_of_date,
            )
            PositionSnapshotFactory(
                portfolio=portfolio,
                instrument=instrument2,
                quantity=Decimal("500"),
                market_value=Money(10000, "USD"),
                as_of_date=as_of_date,
            )

            # Create and execute valuation run
            valuation_run = ValuationRun.objects.create(
                portfolio=portfolio,
                as_of_date=as_of_date,
                valuation_policy=ValuationPolicy.USE_SNAPSHOT_MV,
            )
            valuation_run.execute()
            valuation_run.compute_and_store_exposures()

            # Verify exposure results are persisted
            all_exposures = ExposureResult.objects.filter(valuation_run=valuation_run)
            assert all_exposures.count() > 0

            # Verify we have exposures for all dimension types
            dimension_types = set(
                all_exposures.values_list("dimension_type", flat=True)
            )
            assert ExposureDimensionType.CURRENCY in dimension_types
            assert ExposureDimensionType.ISSUER in dimension_types
            assert ExposureDimensionType.COUNTRY in dimension_types
            assert ExposureDimensionType.INSTRUMENT_GROUP in dimension_types
            assert ExposureDimensionType.INSTRUMENT_TYPE in dimension_types

            # Verify percentages sum to 100% per dimension type (approximately)
            for dim_type in dimension_types:
                exposures = all_exposures.filter(dimension_type=dim_type)
                total_pct = sum(exp.pct_total for exp in exposures)
                # Allow small rounding differences
                assert abs(total_pct - Decimal("100")) < Decimal("0.01")
