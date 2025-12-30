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
    InstrumentFactory,
    InstrumentGroupFactory,
    InstrumentTypeFactory,
    IssuerFactory,
    IssuerRatingFactory,
    OrganizationFactory,
    OrganizationMemberAdminFactory,
    OrganizationMemberAnalystFactory,
    OrganizationMemberFactory,
    OrganizationMemberViewerFactory,
    PrivateAssetInstrumentFactory,
    UserFactory,
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
