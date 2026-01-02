"""
Shared pytest fixtures for all tests.
"""

# Ensure Django is configured before importing anything that uses Django settings
pytest_plugins = ["pytest_django"]

import pytest  # noqa: E402
from django.test import RequestFactory  # noqa: E402

from libs.tenant_context import set_current_org_id  # noqa: E402
from tests.factories import (  # noqa: E402
    BondInstrumentFactory,
    EquityInstrumentFactory,
    ExposureResultFactory,
    FXRateFactory,
    FXRateImportFactory,
    FXRateObservationFactory,
    InstrumentFactory,
    InstrumentGroupFactory,
    InstrumentPriceFactory,
    InstrumentPriceObservationFactory,
    InstrumentTypeFactory,
    IssuerFactory,
    IssuerRatingFactory,
    MarketDataSourceFactory,
    MarketIndexConstituentFactory,
    MarketIndexFactory,
    MarketIndexImportFactory,
    MarketIndexValueFactory,
    MarketIndexValueObservationFactory,
    OrganizationFactory,
    OrganizationMemberAdminFactory,
    OrganizationMemberAnalystFactory,
    OrganizationMemberFactory,
    OrganizationMemberViewerFactory,
    PortfolioFactory,
    PortfolioGroupFactory,
    PortfolioImportErrorFactory,
    PortfolioImportFactory,
    PositionSnapshotFactory,
    PrivateAssetInstrumentFactory,
    ReportFactory,
    ReportTemplateFactory,
    UserFactory,
    ValuationPositionResultFactory,
    ValuationRunFactory,
    YieldCurveFactory,
    YieldCurveImportFactory,
    YieldCurvePointFactory,
    YieldCurvePointObservationFactory,
)


@pytest.fixture
def rf():
    """Request factory for testing views."""
    return RequestFactory()


@pytest.fixture
def organization():
    """Fixture to create an Organization instance."""
    return OrganizationFactory()


@pytest.fixture
def user():
    """Fixture to create a User instance."""
    return UserFactory()


@pytest.fixture
def admin_user():
    """Fixture to create a User instance with admin privileges."""
    user = UserFactory()
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user


@pytest.fixture
def organization_member(organization, user):
    """Fixture to create an OrganizationMember with viewer role."""
    return OrganizationMemberFactory(organization=organization, user=user)


@pytest.fixture
def admin_member(organization, user):
    """Fixture to create an OrganizationMember with admin role."""
    return OrganizationMemberAdminFactory(organization=organization, user=user)


@pytest.fixture
def analyst_member(organization, user):
    """Fixture to create an OrganizationMember with analyst role."""
    return OrganizationMemberAnalystFactory(organization=organization, user=user)


@pytest.fixture
def viewer_member(organization, user):
    """Fixture to create an OrganizationMember with viewer role."""
    return OrganizationMemberViewerFactory(organization=organization, user=user)


@pytest.fixture
def org_context():
    """Fixture to set organization context for tests."""

    def _set_org(org_id):
        set_current_org_id(org_id)
        yield
        set_current_org_id(None)

    return _set_org


@pytest.fixture
def org_context_with_org(organization):
    """Fixture that sets organization context using a created organization."""
    set_current_org_id(organization.id)
    yield organization
    set_current_org_id(None)


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Give all tests access to the database.
    This is equivalent to @pytest.mark.django_db on every test.
    """
    pass


@pytest.fixture(autouse=True)
def clear_org_context():
    """
    Automatically clear organization context before and after each test.
    Ensures tests don't leak organization context between runs.
    """
    # Clear before test
    set_current_org_id(None)
    yield
    # Clear after test
    set_current_org_id(None)


# Reference Data Fixtures


@pytest.fixture
def instrument_group():
    """Fixture to create an InstrumentGroup instance."""
    return InstrumentGroupFactory()


@pytest.fixture
def instrument_type(instrument_group):
    """Fixture to create an InstrumentType instance."""
    return InstrumentTypeFactory(group=instrument_group)


@pytest.fixture
def issuer(org_context_with_org):
    """Fixture to create an Issuer instance within organization context."""
    return IssuerFactory()


@pytest.fixture
def issuer_rating(issuer):
    """Fixture to create an IssuerRating instance."""
    return IssuerRatingFactory(issuer=issuer)


@pytest.fixture
def instrument(org_context_with_org, instrument_group, instrument_type, issuer):
    """Fixture to create an Instrument instance within organization context."""
    return InstrumentFactory(
        instrument_group=instrument_group,
        instrument_type=instrument_type,
        issuer=issuer,
    )


@pytest.fixture
def bond_instrument(org_context_with_org, instrument_group, instrument_type, issuer):
    """Fixture to create a bond Instrument instance."""
    return BondInstrumentFactory(
        instrument_group=instrument_group,
        instrument_type=instrument_type,
        issuer=issuer,
    )


@pytest.fixture
def equity_instrument(org_context_with_org, instrument_group, instrument_type, issuer):
    """Fixture to create an equity Instrument instance."""
    return EquityInstrumentFactory(
        instrument_group=instrument_group,
        instrument_type=instrument_type,
        issuer=issuer,
    )


@pytest.fixture
def private_asset_instrument(
    org_context_with_org, instrument_group, instrument_type, issuer
):
    """Fixture to create a private asset Instrument instance."""
    return PrivateAssetInstrumentFactory(
        instrument_group=instrument_group,
        instrument_type=instrument_type,
        issuer=issuer,
    )


# Portfolio Fixtures


@pytest.fixture
def portfolio_group(org_context_with_org):
    """Fixture to create a PortfolioGroup instance within organization context."""
    return PortfolioGroupFactory()


@pytest.fixture
def portfolio(org_context_with_org, portfolio_group):
    """Fixture to create a Portfolio instance within organization context."""
    return PortfolioFactory(group=portfolio_group)


@pytest.fixture
def portfolio_import(org_context_with_org, portfolio):
    """Fixture to create a PortfolioImport instance."""
    return PortfolioImportFactory(portfolio=portfolio)


@pytest.fixture
def portfolio_import_error(org_context_with_org, portfolio_import):
    """Fixture to create a PortfolioImportError instance."""
    return PortfolioImportErrorFactory(portfolio_import=portfolio_import)


@pytest.fixture
def position_snapshot(org_context_with_org, portfolio, instrument):
    """Fixture to create a PositionSnapshot instance."""
    return PositionSnapshotFactory(portfolio=portfolio, instrument=instrument)


# Market Data Fixtures


@pytest.fixture
def market_data_source():
    """Fixture to create a MarketDataSource instance."""
    return MarketDataSourceFactory()


@pytest.fixture
def instrument_price_observation(instrument, market_data_source):
    """Fixture to create an InstrumentPriceObservation instance."""
    return InstrumentPriceObservationFactory(
        instrument=instrument, source=market_data_source
    )


@pytest.fixture
def instrument_price(instrument, market_data_source):
    """Fixture to create an InstrumentPrice instance."""
    return InstrumentPriceFactory(
        instrument=instrument, chosen_source=market_data_source
    )


@pytest.fixture
def yield_curve():
    """Fixture to create a YieldCurve instance."""
    return YieldCurveFactory()


@pytest.fixture
def yield_curve_point_observation(yield_curve, market_data_source):
    """Fixture to create a YieldCurvePointObservation instance."""
    return YieldCurvePointObservationFactory(
        curve=yield_curve, source=market_data_source
    )


@pytest.fixture
def yield_curve_point(yield_curve, market_data_source):
    """Fixture to create a YieldCurvePoint instance."""
    return YieldCurvePointFactory(curve=yield_curve, chosen_source=market_data_source)


@pytest.fixture
def fx_rate_observation(market_data_source):
    """Fixture to create an FXRateObservation instance."""
    return FXRateObservationFactory(source=market_data_source)


@pytest.fixture
def fx_rate(market_data_source):
    """Fixture to create an FXRate instance."""
    # Factory will automatically create observation to satisfy validation
    return FXRateFactory(chosen_source=market_data_source)


@pytest.fixture
def yield_curve_import(yield_curve, market_data_source):
    """Fixture to create a YieldCurveImport instance."""
    return YieldCurveImportFactory(curve=yield_curve, source=market_data_source)


@pytest.fixture
def fx_rate_import(market_data_source):
    """Fixture to create an FXRateImport instance."""
    return FXRateImportFactory(source=market_data_source)


# Market Index Fixtures


@pytest.fixture
def market_index():
    """Fixture to create a MarketIndex instance."""
    return MarketIndexFactory()


@pytest.fixture
def market_index_value_observation(market_index, market_data_source):
    """Fixture to create a MarketIndexValueObservation instance."""
    return MarketIndexValueObservationFactory(
        index=market_index, source=market_data_source
    )


@pytest.fixture
def market_index_value(market_index, market_data_source):
    """Fixture to create a MarketIndexValue instance."""
    return MarketIndexValueFactory(index=market_index, chosen_source=market_data_source)


@pytest.fixture
def market_index_constituent(market_index, instrument):
    """Fixture to create a MarketIndexConstituent instance."""
    return MarketIndexConstituentFactory(index=market_index, instrument=instrument)


@pytest.fixture
def market_index_import(market_index, market_data_source):
    """Fixture to create a MarketIndexImport instance."""
    return MarketIndexImportFactory(index=market_index, source=market_data_source)


# Analytics Fixtures


@pytest.fixture
def valuation_run(org_context_with_org, portfolio):
    """Fixture to create a ValuationRun instance."""
    return ValuationRunFactory(portfolio=portfolio)


@pytest.fixture
def valuation_position_result(org_context_with_org, valuation_run, position_snapshot):
    """Fixture to create a ValuationPositionResult instance."""
    return ValuationPositionResultFactory(
        valuation_run=valuation_run, position_snapshot=position_snapshot
    )


@pytest.fixture
def exposure_result(org_context_with_org, valuation_run):
    """Fixture to create an ExposureResult instance."""
    return ExposureResultFactory(valuation_run=valuation_run)


# Reports Fixtures


@pytest.fixture
def report_template(org_context_with_org):
    """Fixture to create a ReportTemplate instance."""
    return ReportTemplateFactory()


@pytest.fixture
def report(org_context_with_org, valuation_run, report_template):
    """Fixture to create a Report instance."""
    return ReportFactory(valuation_run=valuation_run, template=report_template)
