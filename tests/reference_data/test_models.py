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
    FXRateFactory,
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
    MarketIndexValueFactory,
    MarketIndexValueObservationFactory,
    OrganizationFactory,
    YieldCurveFactory,
    YieldCurvePointFactory,
    YieldCurvePointObservationFactory,
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


class TestMarketDataSource:
    """Test cases for MarketDataSource model."""

    def test_create_market_data_source(self, market_data_source):
        """Test creating a market data source."""
        assert market_data_source.code is not None
        assert market_data_source.name is not None
        assert market_data_source.priority is not None
        assert market_data_source.is_active is True

    def test_market_data_source_str(self, market_data_source):
        """Test market data source string representation."""
        expected = f"{market_data_source.name} ({market_data_source.code})"
        assert str(market_data_source) == expected

    def test_market_data_source_unique_code(self):
        """Test that market data source codes must be unique."""
        MarketDataSourceFactory(code="TEST")
        with pytest.raises(IntegrityError):
            MarketDataSourceFactory(code="TEST")

    def test_market_data_source_has_created_at(self, market_data_source):
        """Test that created_at is automatically set."""
        assert market_data_source.created_at is not None

    def test_market_data_source_has_updated_at(self, market_data_source):
        """Test that updated_at is automatically set."""
        assert market_data_source.updated_at is not None


class TestInstrumentPriceObservation:
    """Test cases for InstrumentPriceObservation model."""

    def test_create_instrument_price_observation(
        self, instrument_price_observation, instrument, market_data_source
    ):
        """Test creating an instrument price observation."""
        assert instrument_price_observation.instrument == instrument
        assert instrument_price_observation.source == market_data_source
        assert instrument_price_observation.price is not None
        assert instrument_price_observation.date is not None

    def test_instrument_price_observation_str(self, instrument_price_observation):
        """Test instrument price observation string representation."""
        expected = (
            f"{instrument_price_observation.instrument.name} - "
            f"{instrument_price_observation.price} from "
            f"{instrument_price_observation.source.code} "
            f"({instrument_price_observation.date})"
        )
        assert str(instrument_price_observation) == expected

    def test_instrument_price_observation_unique_constraint(self, instrument):
        """Test unique constraint on instrument/date/price_type/source/revision."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        InstrumentPriceObservationFactory(
            instrument=instrument,
            date=date_val,
            price_type="close",
            source=source,
            revision=0,
        )
        with pytest.raises(IntegrityError):
            InstrumentPriceObservationFactory(
                instrument=instrument,
                date=date_val,
                price_type="close",
                source=source,
                revision=0,
            )

    def test_instrument_price_observation_has_created_at(
        self, instrument_price_observation
    ):
        """Test that created_at is automatically set."""
        assert instrument_price_observation.created_at is not None


class TestInstrumentPrice:
    """Test cases for InstrumentPrice model."""

    def test_create_instrument_price(
        self, instrument_price, instrument, market_data_source
    ):
        """Test creating an instrument price."""
        assert instrument_price.instrument == instrument
        assert instrument_price.chosen_source == market_data_source
        assert instrument_price.price is not None
        assert instrument_price.date is not None

    def test_instrument_price_str(self, instrument_price):
        """Test instrument price string representation."""
        expected = (
            f"{instrument_price.instrument.name} - "
            f"{instrument_price.price} from "
            f"{instrument_price.chosen_source.code} "
            f"({instrument_price.date})"
        )
        assert str(instrument_price) == expected

    def test_instrument_price_unique_constraint(self, instrument):
        """Test unique constraint on instrument/date/price_type."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        InstrumentPriceFactory(
            instrument=instrument,
            date=date_val,
            price_type="close",
            chosen_source=source,
        )
        with pytest.raises(IntegrityError):
            InstrumentPriceFactory(
                instrument=instrument,
                date=date_val,
                price_type="close",
                chosen_source=source,
            )

    def test_instrument_price_has_created_at(self, instrument_price):
        """Test that created_at is automatically set."""
        assert instrument_price.created_at is not None


class TestYieldCurve:
    """Test cases for YieldCurve model."""

    def test_create_yield_curve(self, yield_curve):
        """Test creating a yield curve."""
        assert yield_curve.name is not None
        assert yield_curve.curve_type is not None
        assert yield_curve.currency is not None
        assert yield_curve.is_active is True

    def test_yield_curve_str(self, yield_curve):
        """Test yield curve string representation."""
        expected = f"{yield_curve.name} ({yield_curve.currency})"
        assert str(yield_curve) == expected

    def test_yield_curve_unique_constraint(self):
        """Test unique constraint on currency/name."""
        currency = "XAF"
        YieldCurveFactory(currency=currency, name="Test Curve")
        with pytest.raises(IntegrityError):
            YieldCurveFactory(currency=currency, name="Test Curve")

    def test_yield_curve_has_created_at(self, yield_curve):
        """Test that created_at is automatically set."""
        assert yield_curve.created_at is not None


class TestYieldCurvePointObservation:
    """Test cases for YieldCurvePointObservation model."""

    def test_create_yield_curve_point_observation(
        self, yield_curve_point_observation, yield_curve, market_data_source
    ):
        """Test creating a yield curve point observation."""
        assert yield_curve_point_observation.curve == yield_curve
        assert yield_curve_point_observation.source == market_data_source
        assert yield_curve_point_observation.rate is not None
        assert yield_curve_point_observation.tenor_days is not None

    def test_yield_curve_point_observation_str(self, yield_curve_point_observation):
        """Test yield curve point observation string representation."""
        expected = (
            f"{yield_curve_point_observation.curve.name} "
            f"{yield_curve_point_observation.tenor} = "
            f"{yield_curve_point_observation.rate}% from "
            f"{yield_curve_point_observation.source.code} "
            f"({yield_curve_point_observation.date})"
        )
        assert str(yield_curve_point_observation) == expected

    def test_yield_curve_point_observation_unique_constraint(self, yield_curve):
        """Test unique constraint on curve/tenor_days/date/source/revision."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        YieldCurvePointObservationFactory(
            curve=yield_curve,
            tenor_days=365,
            date=date_val,
            source=source,
            revision=0,
        )
        with pytest.raises(IntegrityError):
            YieldCurvePointObservationFactory(
                curve=yield_curve,
                tenor_days=365,
                date=date_val,
                source=source,
                revision=0,
            )

    def test_yield_curve_point_observation_has_created_at(
        self, yield_curve_point_observation
    ):
        """Test that created_at is automatically set."""
        assert yield_curve_point_observation.created_at is not None


class TestYieldCurvePoint:
    """Test cases for YieldCurvePoint model."""

    def test_create_yield_curve_point(
        self, yield_curve_point, yield_curve, market_data_source
    ):
        """Test creating a yield curve point."""
        assert yield_curve_point.curve == yield_curve
        assert yield_curve_point.chosen_source == market_data_source
        assert yield_curve_point.rate is not None
        assert yield_curve_point.tenor_days is not None

    def test_yield_curve_point_str(self, yield_curve_point):
        """Test yield curve point string representation."""
        expected = (
            f"{yield_curve_point.curve.name} "
            f"{yield_curve_point.tenor} = "
            f"{yield_curve_point.rate}% from "
            f"{yield_curve_point.chosen_source.code} "
            f"({yield_curve_point.date})"
        )
        assert str(yield_curve_point) == expected

    def test_yield_curve_point_unique_constraint(self, yield_curve):
        """Test unique constraint on curve/tenor_days/date."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        YieldCurvePointFactory(
            curve=yield_curve,
            tenor_days=365,
            date=date_val,
            chosen_source=source,
        )
        with pytest.raises(IntegrityError):
            YieldCurvePointFactory(
                curve=yield_curve,
                tenor_days=365,
                date=date_val,
                chosen_source=source,
            )

    def test_yield_curve_point_has_created_at(self, yield_curve_point):
        """Test that created_at is automatically set."""
        assert yield_curve_point.created_at is not None


class TestFXRateObservation:
    """Test cases for FXRateObservation model."""

    def test_create_fx_rate_observation(self, fx_rate_observation, market_data_source):
        """Test creating an FX rate observation."""
        assert fx_rate_observation.source == market_data_source
        assert fx_rate_observation.rate is not None
        assert fx_rate_observation.base_currency is not None
        assert fx_rate_observation.quote_currency is not None

    def test_fx_rate_observation_str(self, fx_rate_observation):
        """Test FX rate observation string representation."""
        expected = (
            f"{fx_rate_observation.base_currency}/{fx_rate_observation.quote_currency} = "
            f"{fx_rate_observation.rate} ({fx_rate_observation.rate_type}) from "
            f"{fx_rate_observation.source.code} ({fx_rate_observation.date})"
        )
        assert str(fx_rate_observation) == expected

    def test_fx_rate_observation_unique_constraint(self):
        """Test unique constraint on base/quote/date/rate_type/source/revision."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        FXRateObservationFactory(
            base_currency="XAF",
            quote_currency="USD",
            date=date_val,
            rate_type="mid",
            source=source,
            revision=0,
        )
        with pytest.raises(IntegrityError):
            FXRateObservationFactory(
                base_currency="XAF",
                quote_currency="USD",
                date=date_val,
                rate_type="mid",
                source=source,
                revision=0,
            )

    def test_fx_rate_observation_has_created_at(self, fx_rate_observation):
        """Test that created_at is automatically set."""
        assert fx_rate_observation.created_at is not None


class TestFXRate:
    """Test cases for FXRate model."""

    def test_create_fx_rate(self, fx_rate, market_data_source):
        """Test creating an FX rate."""
        assert fx_rate.chosen_source == market_data_source
        assert fx_rate.rate is not None
        assert fx_rate.base_currency is not None
        assert fx_rate.quote_currency is not None

    def test_fx_rate_str(self, fx_rate):
        """Test FX rate string representation."""
        expected = (
            f"{fx_rate.base_currency}/{fx_rate.quote_currency} = "
            f"{fx_rate.rate} ({fx_rate.rate_type}) from "
            f"{fx_rate.chosen_source.code} ({fx_rate.date})"
        )
        assert str(fx_rate) == expected

    def test_fx_rate_unique_constraint(self):
        """Test unique constraint on base/quote/date/rate_type."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        FXRateFactory(
            base_currency="XAF",
            quote_currency="USD",
            date=date_val,
            rate_type="mid",
            chosen_source=source,
        )
        with pytest.raises(IntegrityError):
            FXRateFactory(
                base_currency="XAF",
                quote_currency="USD",
                date=date_val,
                rate_type="mid",
                chosen_source=source,
            )

    def test_fx_rate_has_created_at(self, fx_rate):
        """Test that created_at is automatically set."""
        assert fx_rate.created_at is not None


class TestMarketIndex:
    """Test cases for MarketIndex model."""

    def test_create_market_index(self, market_index):
        """Test creating a market index."""
        assert market_index.code is not None
        assert market_index.name is not None
        assert market_index.currency is not None
        assert market_index.is_active is True

    def test_market_index_str(self, market_index):
        """Test market index string representation."""
        expected = f"{market_index.name} ({market_index.code})"
        assert str(market_index) == expected

    def test_market_index_unique_code(self):
        """Test that market index codes must be unique."""
        MarketIndexFactory(code="BVMAC")
        with pytest.raises(IntegrityError):
            MarketIndexFactory(code="BVMAC")

    def test_market_index_has_base_date(self, market_index):
        """Test that base_date can be set."""
        assert market_index.base_date is not None

    def test_market_index_has_base_value(self, market_index):
        """Test that base_value can be set."""
        assert market_index.base_value is not None

    def test_market_index_is_active_default(self, market_index):
        """Test that market index is active by default."""
        assert market_index.is_active is True

    def test_market_index_can_be_inactive(self):
        """Test that market index can be set to inactive."""
        index = MarketIndexFactory(is_active=False)
        assert index.is_active is False

    def test_market_index_has_created_at(self, market_index):
        """Test that created_at is automatically set."""
        assert market_index.created_at is not None

    def test_market_index_has_updated_at(self, market_index):
        """Test that updated_at is automatically set."""
        assert market_index.updated_at is not None


class TestMarketIndexValueObservation:
    """Test cases for MarketIndexValueObservation model."""

    def test_create_market_index_value_observation(
        self, market_index_value_observation, market_index, market_data_source
    ):
        """Test creating a market index value observation."""
        assert market_index_value_observation.index == market_index
        assert market_index_value_observation.source == market_data_source
        assert market_index_value_observation.value is not None
        assert market_index_value_observation.date is not None

    def test_market_index_value_observation_str(self, market_index_value_observation):
        """Test market index value observation string representation."""
        expected = (
            f"{market_index_value_observation.index.code} = "
            f"{market_index_value_observation.value} from "
            f"{market_index_value_observation.source.code} "
            f"({market_index_value_observation.date})"
        )
        assert str(market_index_value_observation) == expected

    def test_market_index_value_observation_unique_constraint(self, market_index):
        """Test unique constraint on index/date/source/revision."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        MarketIndexValueObservationFactory(
            index=market_index,
            date=date_val,
            source=source,
            revision=0,
        )
        with pytest.raises(IntegrityError):
            MarketIndexValueObservationFactory(
                index=market_index,
                date=date_val,
                source=source,
                revision=0,
            )

    def test_market_index_value_observation_has_created_at(
        self, market_index_value_observation
    ):
        """Test that created_at is automatically set."""
        assert market_index_value_observation.created_at is not None

    def test_market_index_value_observation_return_pct_optional(self, market_index):
        """Test that return_pct is optional."""
        observation = MarketIndexValueObservationFactory(
            index=market_index, return_pct=None
        )
        assert observation.return_pct is None


class TestMarketIndexValue:
    """Test cases for MarketIndexValue model."""

    def test_create_market_index_value(
        self, market_index_value, market_index, market_data_source
    ):
        """Test creating a market index value."""
        assert market_index_value.index == market_index
        assert market_index_value.chosen_source == market_data_source
        assert market_index_value.value is not None
        assert market_index_value.date is not None

    def test_market_index_value_str(self, market_index_value):
        """Test market index value string representation."""
        expected = (
            f"{market_index_value.index.code} = "
            f"{market_index_value.value} from "
            f"{market_index_value.chosen_source.code} "
            f"({market_index_value.date})"
        )
        assert str(market_index_value) == expected

    def test_market_index_value_unique_constraint(self, market_index):
        """Test unique constraint on index/date."""
        source = MarketDataSourceFactory()
        date_val = date.today()
        MarketIndexValueFactory(
            index=market_index,
            date=date_val,
            chosen_source=source,
        )
        with pytest.raises(IntegrityError):
            MarketIndexValueFactory(
                index=market_index,
                date=date_val,
                chosen_source=source,
            )

    def test_market_index_value_has_created_at(self, market_index_value):
        """Test that created_at is automatically set."""
        assert market_index_value.created_at is not None

    def test_market_index_value_return_pct_optional(self, market_index):
        """Test that return_pct is optional."""
        value = MarketIndexValueFactory(index=market_index, return_pct=None)
        assert value.return_pct is None


class TestMarketIndexConstituent:
    """Test cases for MarketIndexConstituent model."""

    def test_create_market_index_constituent(
        self, market_index_constituent, market_index, instrument
    ):
        """Test creating a market index constituent."""
        assert market_index_constituent.index == market_index
        assert market_index_constituent.instrument == instrument
        assert market_index_constituent.weight is not None
        assert market_index_constituent.as_of_date is not None

    def test_market_index_constituent_str(self, market_index_constituent):
        """Test market index constituent string representation."""
        expected = (
            f"{market_index_constituent.index.code} - "
            f"{market_index_constituent.instrument.name} "
            f"({market_index_constituent.weight}%) "
            f"as of {market_index_constituent.as_of_date}"
        )
        assert str(market_index_constituent) == expected

    def test_market_index_constituent_unique_constraint(self, market_index, instrument):
        """Test unique constraint on index/instrument/as_of_date."""
        date_val = date.today()
        MarketIndexConstituentFactory(
            index=market_index,
            instrument=instrument,
            as_of_date=date_val,
        )
        with pytest.raises(IntegrityError):
            MarketIndexConstituentFactory(
                index=market_index,
                instrument=instrument,
                as_of_date=date_val,
            )

    def test_market_index_constituent_time_versioned(self, market_index, instrument):
        """Test that same instrument can have different weights on different dates."""
        constituent1 = MarketIndexConstituentFactory(
            index=market_index,
            instrument=instrument,
            as_of_date=date(2024, 1, 1),
            weight=5.0,
        )
        constituent2 = MarketIndexConstituentFactory(
            index=market_index,
            instrument=instrument,
            as_of_date=date(2024, 2, 1),
            weight=6.0,
        )

        assert constituent1.instrument == constituent2.instrument
        assert constituent1.as_of_date != constituent2.as_of_date
        assert constituent1.weight != constituent2.weight

    def test_market_index_constituent_shares_optional(self, market_index, instrument):
        """Test that shares is optional."""
        constituent = MarketIndexConstituentFactory(
            index=market_index, instrument=instrument, shares=None
        )
        assert constituent.shares is None

    def test_market_index_constituent_float_shares_optional(self, market_index, instrument):
        """Test that float_shares is optional."""
        constituent = MarketIndexConstituentFactory(
            index=market_index, instrument=instrument, float_shares=None
        )
        assert constituent.float_shares is None

    def test_market_index_constituent_source_optional(self, market_index, instrument):
        """Test that source is optional."""
        constituent = MarketIndexConstituentFactory(
            index=market_index, instrument=instrument, source=None
        )
        assert constituent.source is None

    def test_market_index_constituent_relationship_to_index(self, market_index_constituent):
        """Test that constituent has correct relationship to index."""
        assert market_index_constituent.index is not None
        assert market_index_constituent in market_index_constituent.index.constituents.all()

    def test_market_index_constituent_relationship_to_instrument(
        self, market_index_constituent
    ):
        """Test that constituent has correct relationship to instrument."""
        assert market_index_constituent.instrument is not None
        assert (
            market_index_constituent
            in market_index_constituent.instrument.index_constituents.all()
        )

    def test_market_index_constituent_has_created_at(self, market_index_constituent):
        """Test that created_at is automatically set."""
        assert market_index_constituent.created_at is not None

    def test_market_index_constituent_has_updated_at(self, market_index_constituent):
        """Test that updated_at is automatically set."""
        assert market_index_constituent.updated_at is not None
