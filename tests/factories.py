"""
Base factories for creating test data using Factory Boy.
"""

from datetime import date
from decimal import Decimal

import factory
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from djmoney.money import Money

from apps.organizations.models import Organization, OrganizationMember, OrganizationRole
from apps.portfolios.models import (
    ImportSourceType,
    ImportStatus,
    Portfolio,
    PortfolioGroup,
    PortfolioImport,
    PositionSnapshot,
    ValuationSource,
)
from apps.reference_data.models import (
    Instrument,
    InstrumentGroup,
    InstrumentType,
    Issuer,
    IssuerRating,
    ValuationMethod,
)

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
    accrued_interest = factory.LazyAttribute(
        lambda obj: _make_money(
            amount_range=(0, 100000),
            currency=(
                obj.portfolio.base_currency
                if obj.portfolio
                else settings.DEFAULT_CURRENCY
            ),
        )
    )
    valuation_method = ValuationMethod.MARK_TO_MARKET
    valuation_source = ValuationSource.MARKET
    as_of_date = factory.LazyFunction(date.today)
    last_valuation_date = factory.LazyFunction(date.today)

    # Optional fields
    portfolio_import = None
    stale_after_days = None

    # Note: organization is set automatically via OrganizationOwnedModel
    # when created within organization_context
