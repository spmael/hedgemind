"""
Tests for reference_data models.

This module tests the reference data models including InstrumentGroup, InstrumentType,
Issuer, IssuerRating, and Instrument. Tests verify model behavior, constraints,
organization scoping, and relationships.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.reference_data.models import IssuerRating, ValuationMethod
from libs.tenant_context import organization_context
from tests.factories import (
    InstrumentFactory,
    InstrumentGroupFactory,
    InstrumentTypeFactory,
    IssuerFactory,
    IssuerRatingFactory,
    OrganizationFactory,
)


class TestInstrumentGroup:
    """Test cases for InstrumentGroup model."""

    def test_create_instrument_group(self, instrument_group):
        """Test creating an instrument group."""
        assert instrument_group.name is not None
        assert instrument_group.name.startswith("INSTRUMENT_GROUP_")
        assert instrument_group.description is not None

    def test_instrument_group_str(self, instrument_group):
        """Test instrument group string representation."""
        assert str(instrument_group) == instrument_group.name

    def test_instrument_group_unique_name(self):
        """Test that instrument group names must be unique."""
        InstrumentGroupFactory(name="TEST_GROUP")
        with pytest.raises(IntegrityError):
            InstrumentGroupFactory(name="TEST_GROUP")

    def test_instrument_group_has_created_at(self, instrument_group):
        """Test that created_at is automatically set."""
        assert instrument_group.created_at is not None

    def test_instrument_group_has_updated_at(self, instrument_group):
        """Test that updated_at is automatically set."""
        assert instrument_group.updated_at is not None


class TestInstrumentType:
    """Test cases for InstrumentType model."""

    def test_create_instrument_type(self, instrument_type):
        """Test creating an instrument type."""
        assert instrument_type.name is not None
        assert instrument_type.group is not None
        assert instrument_type.name.startswith("INSTRUMENT_TYPE_")

    def test_instrument_type_str(self, instrument_type):
        """Test instrument type string representation."""
        expected = f"{instrument_type.group.name} - {instrument_type.name}"
        assert str(instrument_type) == expected

    def test_instrument_type_unique_per_group(self, instrument_group):
        """Test that instrument type names must be unique within a group."""
        InstrumentTypeFactory(group=instrument_group, name="TEST_TYPE")
        with pytest.raises(IntegrityError):
            InstrumentTypeFactory(group=instrument_group, name="TEST_TYPE")

    def test_instrument_type_same_name_different_groups(self):
        """Test that same type name can exist in different groups."""
        group1 = InstrumentGroupFactory(name="GROUP1")
        group2 = InstrumentGroupFactory(name="GROUP2")

        type1 = InstrumentTypeFactory(group=group1, name="COMMON_TYPE")
        type2 = InstrumentTypeFactory(group=group2, name="COMMON_TYPE")

        assert type1.name == type2.name
        assert type1.group != type2.group

    def test_instrument_type_relationship_to_group(self, instrument_type):
        """Test that instrument type has correct relationship to group."""
        assert instrument_type.group is not None
        assert instrument_type in instrument_type.group.types.all()

    def test_instrument_type_has_created_at(self, instrument_type):
        """Test that created_at is automatically set."""
        assert instrument_type.created_at is not None

    def test_instrument_type_has_updated_at(self, instrument_type):
        """Test that updated_at is automatically set."""
        assert instrument_type.updated_at is not None


class TestIssuer:
    """Test cases for Issuer model."""

    def test_create_issuer(self, issuer):
        """Test creating an issuer within organization context."""
        assert issuer.name is not None
        assert issuer.name.startswith("Issuer ")
        assert issuer.is_active is True

    def test_issuer_str(self, issuer):
        """Test issuer string representation."""
        assert str(issuer) == issuer.name

    def test_issuer_unique_per_organization(self, org_context_with_org):
        """Test that issuer names must be unique per organization."""
        IssuerFactory(name="Test Issuer")
        with pytest.raises(IntegrityError):
            IssuerFactory(name="Test Issuer")

    def test_issuer_can_have_same_name_different_organizations(self):
        """Test that same issuer name can exist in different organizations."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            issuer1 = IssuerFactory(name="Same Name Issuer")

        with organization_context(org2.id):
            issuer2 = IssuerFactory(name="Same Name Issuer")

        assert issuer1.name == issuer2.name
        assert issuer1.organization != issuer2.organization

    def test_issuer_organization_isolation(self):
        """Test that issuers are isolated by organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        with organization_context(org1.id):
            issuer1 = IssuerFactory()

        with organization_context(org2.id):
            issuer2 = IssuerFactory()

        # Verify isolation
        from apps.reference_data.models import Issuer

        with organization_context(org1.id):
            assert issuer1 in Issuer.objects.all()
            assert issuer2 not in Issuer.objects.all()

        with organization_context(org2.id):
            assert issuer2 in Issuer.objects.all()
            assert issuer1 not in Issuer.objects.all()

    def test_issuer_is_active_default(self, issuer):
        """Test that issuer is active by default."""
        assert issuer.is_active is True

    def test_issuer_can_be_inactive(self, org_context_with_org):
        """Test that issuer can be set to inactive."""
        issuer = IssuerFactory(is_active=False)
        assert issuer.is_active is False

    def test_issuer_has_created_at(self, issuer):
        """Test that created_at is automatically set."""
        assert issuer.created_at is not None

    def test_issuer_has_updated_at(self, issuer):
        """Test that updated_at is automatically set."""
        assert issuer.updated_at is not None


class TestIssuerRating:
    """Test cases for IssuerRating model."""

    def test_create_issuer_rating(self, issuer_rating):
        """Test creating an issuer rating."""
        assert issuer_rating.issuer is not None
        assert issuer_rating.agency is not None
        assert issuer_rating.rating is not None
        assert issuer_rating.date_assigned is not None
        assert issuer_rating.is_active is True

    def test_issuer_rating_str(self, issuer_rating):
        """Test issuer rating string representation."""
        expected = (
            f"{issuer_rating.issuer.name} - {issuer_rating.agency}: "
            f"{issuer_rating.rating} (as of {issuer_rating.date_assigned})"
        )
        assert str(issuer_rating) == expected

    def test_issuer_rating_unique_per_issuer_agency_date(self, issuer):
        """Test that ratings are unique per issuer, agency, and date."""
        rating_date = date(2024, 1, 1)
        IssuerRatingFactory(
            issuer=issuer,
            agency=IssuerRating.RatingAgency.S_P,
            date_assigned=rating_date,
        )
        with pytest.raises(IntegrityError):
            IssuerRatingFactory(
                issuer=issuer,
                agency=IssuerRating.RatingAgency.S_P,
                date_assigned=rating_date,
            )

    def test_issuer_rating_same_agency_different_dates(self, issuer):
        """Test that same agency can rate issuer on different dates."""
        rating1 = IssuerRatingFactory(
            issuer=issuer,
            agency=IssuerRating.RatingAgency.S_P,
            date_assigned=date(2024, 1, 1),
        )
        rating2 = IssuerRatingFactory(
            issuer=issuer,
            agency=IssuerRating.RatingAgency.S_P,
            date_assigned=date(2024, 2, 1),
        )

        assert rating1.agency == rating2.agency
        assert rating1.date_assigned != rating2.date_assigned

    def test_issuer_rating_multiple_agencies(self, issuer):
        """Test that multiple agencies can rate the same issuer."""
        rating1 = IssuerRatingFactory(
            issuer=issuer,
            agency=IssuerRating.RatingAgency.S_P,
            date_assigned=date(2024, 1, 1),
        )
        rating2 = IssuerRatingFactory(
            issuer=issuer,
            agency=IssuerRating.RatingAgency.MOODY_S,
            date_assigned=date(2024, 1, 1),
        )

        assert rating1.issuer == rating2.issuer
        assert rating1.agency != rating2.agency

    def test_issuer_rating_relationship_to_issuer(self, issuer_rating):
        """Test that rating has correct relationship to issuer."""
        assert issuer_rating.issuer is not None
        assert issuer_rating in issuer_rating.issuer.ratings.all()

    def test_issuer_rating_is_active_default(self, issuer_rating):
        """Test that rating is active by default."""
        assert issuer_rating.is_active is True

    def test_issuer_rating_has_created_at(self, issuer_rating):
        """Test that created_at is automatically set."""
        assert issuer_rating.created_at is not None


class TestInstrument:
    """Test cases for Instrument model."""

    def test_create_instrument(self, instrument):
        """Test creating an instrument within organization context."""
        assert instrument.name is not None
        assert instrument.instrument_group is not None
        assert instrument.instrument_type is not None
        assert instrument.issuer is not None
        assert instrument.valuation_method == ValuationMethod.MARK_TO_MARKET
        assert instrument.is_active is True

    def test_instrument_str_with_isin(
        self, org_context_with_org, instrument_group, instrument_type, issuer
    ):
        """Test instrument string representation with ISIN."""
        instrument = InstrumentFactory(
            instrument_group=instrument_group,
            instrument_type=instrument_type,
            issuer=issuer,
            isin="US1234567890",
            name="Test Bond",
        )
        assert str(instrument) == "Test Bond (US1234567890)"

    def test_instrument_str_with_ticker(
        self, org_context_with_org, instrument_group, instrument_type, issuer
    ):
        """Test instrument string representation with ticker."""
        instrument = InstrumentFactory(
            instrument_group=instrument_group,
            instrument_type=instrument_type,
            issuer=issuer,
            ticker="TEST",
            name="Test Equity",
        )
        assert str(instrument) == "Test Equity (TEST)"

    def test_instrument_str_without_isin_or_ticker(self, instrument):
        """Test instrument string representation without ISIN or ticker."""
        assert str(instrument) == instrument.name

    def test_instrument_organization_isolation(self):
        """Test that instruments are isolated by organization."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        group = InstrumentGroupFactory()
        instrument_type = InstrumentTypeFactory(group=group)

        with organization_context(org1.id):
            issuer1 = IssuerFactory()
            instrument1 = InstrumentFactory(
                instrument_group=group,
                instrument_type=instrument_type,
                issuer=issuer1,
            )

        with organization_context(org2.id):
            issuer2 = IssuerFactory()
            instrument2 = InstrumentFactory(
                instrument_group=group,
                instrument_type=instrument_type,
                issuer=issuer2,
            )

        # Verify isolation
        from apps.reference_data.models import Instrument

        with organization_context(org1.id):
            assert instrument1 in Instrument.objects.all()
            assert instrument2 not in Instrument.objects.all()

        with organization_context(org2.id):
            assert instrument2 in Instrument.objects.all()
            assert instrument1 not in Instrument.objects.all()

    def test_instrument_requires_group(
        self, org_context_with_org, instrument_type, issuer
    ):
        """Test that instrument requires an instrument group."""
        from apps.reference_data.models import Instrument

        with pytest.raises((IntegrityError, ValidationError)):
            Instrument.objects.create(
                name="Test Instrument",
                instrument_type=instrument_type,
                issuer=issuer,
            )

    def test_instrument_requires_type(
        self, org_context_with_org, instrument_group, issuer
    ):
        """Test that instrument requires an instrument type."""
        from apps.reference_data.models import Instrument

        with pytest.raises((IntegrityError, ValidationError)):
            Instrument.objects.create(
                name="Test Instrument",
                instrument_group=instrument_group,
                issuer=issuer,
            )

    def test_instrument_requires_issuer(
        self, org_context_with_org, instrument_group, instrument_type
    ):
        """Test that instrument requires an issuer."""
        from apps.reference_data.models import Instrument

        with pytest.raises((IntegrityError, ValidationError)):
            Instrument.objects.create(
                name="Test Instrument",
                instrument_group=instrument_group,
                instrument_type=instrument_type,
            )

    def test_bond_instrument_factory(self, bond_instrument):
        """Test bond instrument factory creates proper bond."""
        assert bond_instrument.maturity_date is not None
        assert bond_instrument.coupon_rate is not None
        assert bond_instrument.maturity_date > date.today()

    def test_equity_instrument_factory(self, equity_instrument):
        """Test equity instrument factory creates proper equity."""
        assert equity_instrument.isin is not None
        assert equity_instrument.ticker is not None
        assert equity_instrument.sector is not None

    def test_private_asset_instrument_factory(self, private_asset_instrument):
        """Test private asset instrument factory creates proper private asset."""
        assert (
            private_asset_instrument.valuation_method == ValuationMethod.MANUAL_DECLARED
        )
        assert private_asset_instrument.sector is not None

    def test_instrument_valuation_method_default(self, instrument):
        """Test that valuation method defaults to MARK_TO_MARKET."""
        assert instrument.valuation_method == ValuationMethod.MARK_TO_MARKET

    def test_instrument_is_active_default(self, instrument):
        """Test that instrument is active by default."""
        assert instrument.is_active is True

    def test_instrument_has_created_at(self, instrument):
        """Test that created_at is automatically set."""
        assert instrument.created_at is not None

    def test_instrument_has_updated_at(self, instrument):
        """Test that updated_at is automatically set."""
        assert instrument.updated_at is not None

    def test_instrument_relationship_to_group(self, instrument):
        """Test that instrument has correct relationship to group."""
        assert instrument.instrument_group is not None
        assert instrument in instrument.instrument_group.instruments.all()

    def test_instrument_relationship_to_type(self, instrument):
        """Test that instrument has correct relationship to type."""
        assert instrument.instrument_type is not None
        assert instrument in instrument.instrument_type.instruments.all()

    def test_instrument_relationship_to_issuer(self, instrument):
        """Test that instrument has correct relationship to issuer."""
        assert instrument.issuer is not None
        assert instrument in instrument.issuer.instruments.all()
