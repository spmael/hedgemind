"""
Base factories for creating test data using Factory Boy.
"""

from datetime import date

import factory
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.organizations.models import Organization, OrganizationMember, OrganizationRole
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
