"""
Base factories for creating test data using Factory Boy.
"""

from datetime import date
from decimal import Decimal

import factory
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.utils.text import slugify
from djmoney.money import Money

from apps.organizations.models import Organization, OrganizationMember, OrganizationRole
from apps.portfolios.models import (
    ImportSourceType,
    Portfolio,
    PortfolioGroup,
    PortfolioImport,
    PortfolioImportError,
    PositionSnapshot,
    ValuationSource,
)
from apps.reference_data.models import (
    FXRate,
    FXRateImport,
    FXRateObservation,
    Instrument,
    InstrumentGroup,
    InstrumentPrice,
    InstrumentPriceObservation,
    InstrumentType,
    Issuer,
    IssuerRating,
    MarketDataSource,
    MarketIndex,
    MarketIndexConstituent,
    MarketIndexImport,
    MarketIndexValue,
    MarketIndexValueObservation,
    SelectionReason,
    ValuationMethod,
    YieldCurve,
    YieldCurveImport,
    YieldCurvePoint,
    YieldCurvePointObservation,
    YieldCurveType,
)
from libs.choices import ImportStatus

User = get_user_model()


class OrganizationFactory(factory.django.DjangoModelFactory):
    """Factory for creating Organization test instances."""

    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
    abbreviation = factory.LazyAttribute(
        lambda obj: obj.name[:3].upper() if len(obj.name) >= 3 else "ORG"
    )
    is_active = True
    base_currency = settings.DEFAULT_CURRENCY


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User test instances."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True


class OrganizationMemberFactory(factory.django.DjangoModelFactory):
    """Factory for creating OrganizationMember test instances."""

    class Meta:
        model = OrganizationMember

    organization = factory.SubFactory(OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = OrganizationRole.VIEWER
    is_active = True


class OrganizationMemberAdminFactory(OrganizationMemberFactory):
    """Factory for creating OrganizationMember test instances with admin role."""

    role = OrganizationRole.ADMIN


class OrganizationMemberAnalystFactory(OrganizationMemberFactory):
    """Factory for creating OrganizationMember test instances with analyst role."""

    role = OrganizationRole.ANALYST


class OrganizationMemberViewerFactory(OrganizationMemberFactory):
    """Factory for creating OrganizationMember test instances with viewer role."""

    role = OrganizationRole.VIEWER


# Reference Data Factories


class InstrumentGroupFactory(factory.django.DjangoModelFactory):
    """Factory for creating InstrumentGroup test instances."""

    class Meta:
        model = InstrumentGroup

    name = factory.Sequence(lambda n: f"INSTRUMENT_GROUP_{n}")
    description = factory.Faker("text", max_nb_chars=200)


class InstrumentTypeFactory(factory.django.DjangoModelFactory):
    """Factory for creating InstrumentType test instances."""

    class Meta:
        model = InstrumentType

    group = factory.SubFactory(InstrumentGroupFactory)
    name = factory.Sequence(lambda n: f"INSTRUMENT_TYPE_{n}")
    description = factory.Faker("text", max_nb_chars=200)


class IssuerFactory(factory.django.DjangoModelFactory):
    """Factory for creating Issuer test instances."""

    class Meta:
        model = Issuer

    name = factory.Sequence(lambda n: f"Issuer {n}")
    short_name = factory.LazyAttribute(lambda obj: obj.name[:20])
    country = factory.Faker("country_code")
    issuer_group = factory.Iterator(["Sovereign", "Corporate", "Financial Institution"])
    is_active = True

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context


class IssuerRatingFactory(factory.django.DjangoModelFactory):
    """Factory for creating IssuerRating test instances."""

    class Meta:
        model = IssuerRating

    issuer = factory.SubFactory(IssuerFactory)
    agency = factory.Iterator(
        [
            IssuerRating.RatingAgency.S_P,
            IssuerRating.RatingAgency.MOODY_S,
            IssuerRating.RatingAgency.FITCH,
        ]
    )
    rating = factory.Iterator(["AAA", "AA+", "AA", "A+", "A", "BBB+", "BB", "B+"])
    date_assigned = factory.LazyFunction(date.today)
    is_active = True


class InstrumentFactory(factory.django.DjangoModelFactory):
    """Factory for creating Instrument test instances."""

    class Meta:
        model = Instrument

    name = factory.Sequence(lambda n: f"Instrument {n}")
    instrument_group = factory.SubFactory(InstrumentGroupFactory)
    instrument_type = factory.SubFactory(InstrumentTypeFactory)
    currency = settings.DEFAULT_CURRENCY
    issuer = factory.SubFactory(IssuerFactory)
    country = factory.Faker("country_code")
    valuation_method = ValuationMethod.MARK_TO_MARKET
    is_active = True

    # Optional fields
    isin = None
    ticker = None
    sector = None
    maturity_date = None
    coupon_rate = None

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context


class BondInstrumentFactory(InstrumentFactory):
    """Factory for creating bond instruments with typical bond fields."""

    maturity_date = factory.LazyFunction(
        lambda: date.today().replace(year=date.today().year + 5)
    )
    coupon_rate = factory.Faker(
        "pyfloat", left_digits=1, right_digits=2, positive=True, max_value=10
    )


class EquityInstrumentFactory(InstrumentFactory):
    """Factory for creating equity instruments."""

    isin = factory.Faker("bothify", text="??##########")
    ticker = factory.Sequence(lambda n: f"EQ{n:04d}")
    sector = factory.Iterator(["Technology", "Finance", "Healthcare", "Energy"])


class PrivateAssetInstrumentFactory(InstrumentFactory):
    """Factory for creating private asset instruments."""

    valuation_method = ValuationMethod.MANUAL_DECLARED
    sector = factory.Iterator(["Real Estate", "Private Equity", "Infrastructure"])


# Portfolio Factories


class PortfolioGroupFactory(factory.django.DjangoModelFactory):
    """Factory for creating PortfolioGroup test instances."""

    class Meta:
        model = PortfolioGroup

    name = factory.Sequence(lambda n: f"GRP{n:03d}")
    description = factory.Faker("text", max_nb_chars=200)

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context


class PortfolioFactory(factory.django.DjangoModelFactory):
    """Factory for creating Portfolio test instances."""

    class Meta:
        model = Portfolio

    name = factory.Sequence(lambda n: f"PORT{n:03d}")
    full_name = factory.Faker("text", max_nb_chars=200)
    base_currency = settings.DEFAULT_CURRENCY
    group = factory.SubFactory(PortfolioGroupFactory)
    mandate_type = factory.Iterator(
        [
            "Liquidity Management",
            "Treasury",
            "Investment",
            "Reserve",
            None,
        ]
    )

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context


class PortfolioImportFactory(factory.django.DjangoModelFactory):
    """Factory for creating PortfolioImport test instances."""

    class Meta:
        model = PortfolioImport

    portfolio = factory.SubFactory(PortfolioFactory)
    as_of_date = factory.LazyFunction(date.today)
    source_type = ImportSourceType.MANUAL
    status = ImportStatus.PENDING
    rows_processed = 0
    rows_total = 0

    # Optional fields
    mapping_json = None
    error_message = None
    inputs_hash = None
    completed_at = None

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context
    # Note: file field requires actual file upload in tests


class PortfolioImportErrorFactory(factory.django.DjangoModelFactory):
    """Factory for creating PortfolioImportError test instances."""

    class Meta:
        model = PortfolioImportError

    portfolio_import = factory.SubFactory(PortfolioImportFactory)
    row_number = factory.Sequence(lambda n: n + 2)  # 1-indexed, +1 for header
    raw_row_data = factory.LazyFunction(
        lambda: {"column1": "value1", "column2": "value2"}
    )
    error_type = "validation"
    error_message = factory.Faker("sentence")
    error_code = "TEST_ERROR"

    # Optional fields
    column_name = None

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context


def _make_money(amount_range=(1000, 10000000), currency=None):
    """Helper function to create Money objects for factories."""
    import random

    if currency is None:
        currency = settings.DEFAULT_CURRENCY
    amount = Decimal(str(random.uniform(amount_range[0], amount_range[1])))
    return Money(amount, currency)


class PositionSnapshotFactory(factory.django.DjangoModelFactory):
    """Factory for creating PositionSnapshot test instances."""

    class Meta:
        model = PositionSnapshot

    portfolio = factory.SubFactory(PortfolioFactory)
    instrument = factory.SubFactory(InstrumentFactory)
    quantity = factory.Faker(
        "pydecimal", left_digits=10, right_digits=6, positive=True, max_value=1000000
    )
    book_value = factory.LazyAttribute(
        lambda obj: _make_money(
            amount_range=(1000, 10000000),
            currency=(
                obj.portfolio.base_currency
                if obj.portfolio
                else settings.DEFAULT_CURRENCY
            ),
        )
    )
    market_value = factory.LazyAttribute(
        lambda obj: _make_money(
            amount_range=(1000, 10000000),
            currency=(
                obj.portfolio.base_currency
                if obj.portfolio
                else settings.DEFAULT_CURRENCY
            ),
        )
    )
    price = factory.Faker(
        "pydecimal", left_digits=10, right_digits=6, positive=True, max_value=10000
    )
    accrued_interest = None  # Optional field
    valuation_method = ValuationMethod.MARK_TO_MARKET
    valuation_source = ValuationSource.MARKET
    as_of_date = factory.LazyFunction(date.today)
    last_valuation_date = factory.LazyFunction(date.today)

    # Optional fields
    portfolio_import = None
    stale_after_days = None

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context


# Market Data Factories


class MarketDataSourceFactory(factory.django.DjangoModelFactory):
    """Factory for creating MarketDataSource test instances."""

    class Meta:
        model = MarketDataSource

    code = factory.Sequence(lambda n: f"SOURCE{n:03d}")
    name = factory.Sequence(lambda n: f"Market Data Source {n}")
    priority = factory.Sequence(lambda n: n + 1)
    source_type = factory.Iterator(
        [
            MarketDataSource.SourceType.EXCHANGE,
            MarketDataSource.SourceType.CENTRAL_BANK,
            MarketDataSource.SourceType.VENDOR,
            MarketDataSource.SourceType.MANUAL,
        ]
    )
    is_active = True
    description = factory.Faker("text", max_nb_chars=200)


class InstrumentPriceObservationFactory(factory.django.DjangoModelFactory):
    """Factory for creating InstrumentPriceObservation test instances."""

    class Meta:
        model = InstrumentPriceObservation

    instrument = factory.SubFactory(InstrumentFactory)
    date = factory.LazyFunction(date.today)
    price_type = InstrumentPriceObservation.PriceType.CLOSE
    source = factory.SubFactory(MarketDataSourceFactory)
    price = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True, max_value=10000
    )
    quote_convention = InstrumentPriceObservation.QuoteConvention.PRICE
    clean_or_dirty = InstrumentPriceObservation.CleanOrDirty.NA
    revision = 0
    observed_at = factory.LazyFunction(lambda: timezone.now())

    # Optional fields
    volume = None
    currency = None


class InstrumentPriceFactory(factory.django.DjangoModelFactory):
    """Factory for creating InstrumentPrice test instances."""

    class Meta:
        model = InstrumentPrice

    instrument = factory.SubFactory(InstrumentFactory)
    date = factory.LazyFunction(date.today)
    price_type = InstrumentPrice.PriceType.CLOSE
    chosen_source = factory.SubFactory(MarketDataSourceFactory)
    price = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True, max_value=10000
    )
    quote_convention = InstrumentPrice.QuoteConvention.PRICE
    clean_or_dirty = InstrumentPrice.CleanOrDirty.NA
    selection_reason = SelectionReason.AUTO_POLICY
    selected_at = factory.LazyFunction(lambda: timezone.now())

    # Optional fields
    observation = None
    volume = None
    currency = None
    selected_by = None


class YieldCurveFactory(factory.django.DjangoModelFactory):
    """Factory for creating YieldCurve test instances."""

    class Meta:
        model = YieldCurve

    name = factory.Sequence(lambda n: f"Yield Curve {n}")
    curve_type = factory.Iterator(
        [
            YieldCurveType.GOVT,
            YieldCurveType.SWAP,
            YieldCurveType.OIS,
            YieldCurveType.CORPORATE,
        ]
    )
    currency = settings.DEFAULT_CURRENCY
    country = factory.Faker("country_code")
    is_active = True
    description = factory.Faker("text", max_nb_chars=200)


class YieldCurvePointObservationFactory(factory.django.DjangoModelFactory):
    """Factory for creating YieldCurvePointObservation test instances."""

    class Meta:
        model = YieldCurvePointObservation

    curve = factory.SubFactory(YieldCurveFactory)
    tenor = factory.Iterator(["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y"])
    tenor_days = factory.LazyAttribute(
        lambda obj: {
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "2Y": 730,
            "5Y": 1825,
            "10Y": 3650,
        }.get(obj.tenor, 365)
    )
    rate = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, positive=True, max_value=20
    )
    date = factory.LazyFunction(date.today)
    source = factory.SubFactory(MarketDataSourceFactory)
    revision = 0
    observed_at = factory.LazyFunction(lambda: timezone.now())


class YieldCurvePointFactory(factory.django.DjangoModelFactory):
    """Factory for creating YieldCurvePoint test instances."""

    class Meta:
        model = YieldCurvePoint

    curve = factory.SubFactory(YieldCurveFactory)
    tenor = factory.Iterator(["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y"])
    tenor_days = factory.LazyAttribute(
        lambda obj: {
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "2Y": 730,
            "5Y": 1825,
            "10Y": 3650,
        }.get(obj.tenor, 365)
    )
    rate = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, positive=True, max_value=20
    )
    date = factory.LazyFunction(date.today)
    chosen_source = factory.SubFactory(MarketDataSourceFactory)
    selection_reason = SelectionReason.AUTO_POLICY
    selected_at = factory.LazyFunction(lambda: timezone.now())

    # Optional fields
    observation = None
    selected_by = None


class FXRateObservationFactory(factory.django.DjangoModelFactory):
    """Factory for creating FXRateObservation test instances."""

    class Meta:
        model = FXRateObservation

    base_currency = settings.DEFAULT_CURRENCY
    quote_currency = factory.Iterator(["USD", "EUR", "GBP"])
    rate = factory.Faker(
        "pydecimal", left_digits=1, right_digits=6, positive=True, max_value=10
    )
    rate_type = FXRateObservation.RateType.MID
    date = factory.LazyFunction(date.today)
    source = factory.SubFactory(MarketDataSourceFactory)
    revision = 0
    observed_at = factory.LazyFunction(lambda: timezone.now())


class FXRateFactory(factory.django.DjangoModelFactory):
    """Factory for creating FXRate test instances."""

    class Meta:
        model = FXRate

    base_currency = settings.DEFAULT_CURRENCY
    quote_currency = factory.Iterator(["USD", "EUR", "GBP"])
    rate = factory.Faker(
        "pydecimal", left_digits=1, right_digits=6, positive=True, max_value=10
    )
    rate_type = FXRate.RateType.MID
    date = factory.LazyFunction(date.today)
    chosen_source = factory.SubFactory(MarketDataSourceFactory)
    selection_reason = SelectionReason.AUTO_POLICY
    selected_at = factory.LazyFunction(lambda: timezone.now())

    # Create observation to satisfy validation (required when not MANUAL_OVERRIDE)
    # Use LazyAttribute to create observation after all fields are set but before save
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override _create to create observation before validation."""
        # Extract observation if provided, otherwise create it
        observation = kwargs.pop("observation", None)
        if (
            observation is None
            and kwargs.get("selection_reason") != SelectionReason.MANUAL_OVERRIDE
        ):
            # Create observation with matching fields
            observation = FXRateObservationFactory(
                base_currency=kwargs.get("base_currency", settings.DEFAULT_CURRENCY),
                quote_currency=kwargs.get("quote_currency", "USD"),
                rate=kwargs.get("rate"),
                rate_type=kwargs.get("rate_type", FXRate.RateType.MID),
                date=kwargs.get("date", date.today()),
                source=kwargs.get("chosen_source"),
            )
        if observation:
            kwargs["observation"] = observation
        return super()._create(model_class, *args, **kwargs)

    # Optional fields
    selected_by = None


class YieldCurveImportFactory(factory.django.DjangoModelFactory):
    """Factory for creating YieldCurveImport test instances."""

    class Meta:
        model = YieldCurveImport

    source = factory.SubFactory(MarketDataSourceFactory)
    curve = factory.SubFactory(YieldCurveFactory)
    file = factory.LazyAttribute(
        lambda _: SimpleUploadedFile(
            "test_curve.xlsx",
            b"dummy content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    sheet_name = None
    status = ImportStatus.PENDING
    error_message = None
    observations_created = 0
    observations_updated = 0
    canonical_points_created = 0
    completed_at = None
    created_by = None


class FXRateImportFactory(factory.django.DjangoModelFactory):
    """Factory for creating FXRateImport test instances."""

    class Meta:
        model = FXRateImport

    source = factory.SubFactory(MarketDataSourceFactory)
    file = factory.LazyAttribute(
        lambda _: SimpleUploadedFile(
            "test_fx_rates.xlsx",
            b"dummy content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    sheet_name = "FX_RATES"
    status = ImportStatus.PENDING
    error_message = None
    observations_created = 0
    observations_updated = 0
    canonical_rates_created = 0
    completed_at = None
    created_by = None


# Market Index Factories


class MarketIndexFactory(factory.django.DjangoModelFactory):
    """Factory for creating MarketIndex test instances."""

    class Meta:
        model = MarketIndex

    code = factory.Sequence(lambda n: f"INDEX{n:03d}")
    name = factory.Sequence(lambda n: f"Market Index {n}")
    currency = settings.DEFAULT_CURRENCY
    description = factory.Faker("text", max_nb_chars=200)
    base_date = factory.LazyFunction(date.today)
    base_value = factory.Faker(
        "pydecimal", left_digits=3, right_digits=2, positive=True, max_value=1000
    )
    is_active = True


class MarketIndexValueObservationFactory(factory.django.DjangoModelFactory):
    """Factory for creating MarketIndexValueObservation test instances."""

    class Meta:
        model = MarketIndexValueObservation

    index = factory.SubFactory(MarketIndexFactory)
    date = factory.LazyFunction(date.today)
    value = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True, max_value=10000
    )
    return_pct = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=False,
        max_value=10,
        min_value=-10,
    )
    source = factory.SubFactory(MarketDataSourceFactory)
    revision = 0
    observed_at = factory.LazyFunction(lambda: timezone.now())


class MarketIndexValueFactory(factory.django.DjangoModelFactory):
    """Factory for creating MarketIndexValue test instances."""

    class Meta:
        model = MarketIndexValue

    index = factory.SubFactory(MarketIndexFactory)
    date = factory.LazyFunction(date.today)
    chosen_source = factory.SubFactory(MarketDataSourceFactory)
    value = factory.Faker(
        "pydecimal", left_digits=5, right_digits=2, positive=True, max_value=10000
    )
    return_pct = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=2,
        positive=False,
        max_value=10,
        min_value=-10,
    )
    selection_reason = SelectionReason.AUTO_POLICY
    selected_at = factory.LazyFunction(lambda: timezone.now())

    # Optional fields
    observation = None
    selected_by = None


class MarketIndexConstituentFactory(factory.django.DjangoModelFactory):
    """Factory for creating MarketIndexConstituent test instances."""

    class Meta:
        model = MarketIndexConstituent

    index = factory.SubFactory(MarketIndexFactory)
    instrument = factory.SubFactory(InstrumentFactory)
    as_of_date = factory.LazyFunction(date.today)
    weight = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, positive=True, max_value=50
    )
    shares = factory.Faker(
        "pydecimal", left_digits=10, right_digits=2, positive=True, max_value=10000000
    )
    float_shares = None
    source = factory.SubFactory(MarketDataSourceFactory)


class MarketIndexImportFactory(factory.django.DjangoModelFactory):
    """Factory for creating MarketIndexImport test instances."""

    class Meta:
        model = MarketIndexImport

    index = factory.SubFactory(MarketIndexFactory)
    source = factory.SubFactory(MarketDataSourceFactory)
    file = factory.LazyAttribute(
        lambda _: SimpleUploadedFile(
            "test_index_values.xlsx",
            b"dummy content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    sheet_name = "INDEX_LEVELS"
    status = ImportStatus.PENDING
    error_message = None
    observations_created = 0
    observations_updated = 0
    canonical_values_created = 0
    completed_at = None
    created_by = None
