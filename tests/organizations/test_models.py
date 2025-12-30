"""
Tests for organizations models.
"""

import pytest
from django.db import IntegrityError

from apps.organizations.models import OrganizationRole
from tests.factories import OrganizationFactory, OrganizationMemberFactory


class TestOrganization:
    """Test cases for Organization model."""

    def test_create_organization(self, organization):
        """Test creating an organization using fixture."""
        assert organization.name.startswith("Organization")
        assert organization.slug is not None
        assert organization.is_active is True

    def test_organization_str(self, organization):
        """Test organization string representation."""
        assert str(organization) == organization.name

    def test_organization_slug_generation(self):
        """Test that slug is generated correctly from name."""
        org = OrganizationFactory(name="Acme Corporation")
        assert org.slug == "acme-corporation"

    def test_organization_unique_slug(self):
        """Test that slug must be unique."""
        OrganizationFactory(slug="test-org")
        with pytest.raises(IntegrityError):
            OrganizationFactory(slug="test-org")

    def test_organization_abbreviation(self, organization):
        """Test organization abbreviation generation."""
        assert organization.abbreviation is not None
        assert len(organization.abbreviation) <= 10

    def test_organization_base_currency(self, organization):
        """Test organization base currency default."""
        assert organization.base_currency is not None

    def test_organization_is_active_default(self):
        """Test that organization is active by default."""
        org = OrganizationFactory()
        assert org.is_active is True

    def test_organization_can_be_inactive(self):
        """Test that organization can be set to inactive."""
        org = OrganizationFactory(is_active=False)
        assert org.is_active is False


class TestOrganizationMember:
    """Test cases for OrganizationMember model."""

    def test_create_organization_member(self, organization_member):
        """Test creating an organization member using fixture."""
        assert organization_member.organization is not None
        assert organization_member.user is not None
        assert organization_member.role == OrganizationRole.VIEWER

    def test_organization_member_str(self, organization_member):
        """Test organization member string representation."""
        expected = f"{organization_member.user} @ {organization_member.organization} ({organization_member.role})"
        assert str(organization_member) == expected

    def test_organization_member_unique_together(self, organization, user):
        """Test that user can only have one membership per organization."""
        OrganizationMemberFactory(organization=organization, user=user)

        with pytest.raises(IntegrityError):
            OrganizationMemberFactory(organization=organization, user=user)

    def test_organization_member_default_role(self, organization_member):
        """Test that default role is VIEWER."""
        assert organization_member.role == OrganizationRole.VIEWER

    def test_organization_member_admin_role(self, admin_member):
        """Test admin member has admin role."""
        assert admin_member.role == OrganizationRole.ADMIN

    def test_organization_member_analyst_role(self, analyst_member):
        """Test analyst member has analyst role."""
        assert analyst_member.role == OrganizationRole.ANALYST

    def test_organization_member_viewer_role(self, viewer_member):
        """Test viewer member has viewer role."""
        assert viewer_member.role == OrganizationRole.VIEWER

    def test_organization_member_is_active_default(self, organization_member):
        """Test that member is active by default."""
        assert organization_member.is_active is True

    def test_user_can_have_multiple_org_memberships(self, user):
        """Test that a user can be a member of multiple organizations."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        member1 = OrganizationMemberFactory(organization=org1, user=user)
        member2 = OrganizationMemberFactory(organization=org2, user=user)

        assert member1.organization != member2.organization
        assert member1.user == member2.user
