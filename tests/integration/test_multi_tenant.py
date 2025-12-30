"""
Integration tests for multi-tenant functionality.
"""

from libs.tenant_context import get_current_org_id, set_current_org_id
from tests.factories import OrganizationFactory, OrganizationMemberFactory


class TestMultiTenantContext:
    """Test cases for multi-tenant context management."""

    def test_org_context_isolation(self, organization):
        """Test that organization context is properly isolated."""
        # Set context
        set_current_org_id(organization.id)
        assert get_current_org_id() == organization.id

        # Create another org
        org2 = OrganizationFactory()
        set_current_org_id(org2.id)
        assert get_current_org_id() == org2.id
        assert get_current_org_id() != organization.id

    def test_user_membership_across_orgs(self, user):
        """Test that a user can be a member of multiple organizations."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        member1 = OrganizationMemberFactory(organization=org1, user=user)
        member2 = OrganizationMemberFactory(organization=org2, user=user)

        assert member1.organization != member2.organization
        assert member1.user == member2.user

        # User should have memberships in both orgs
        assert user.organization_memberships.count() == 2

    def test_org_context_with_fixture(self, org_context_with_org):
        """Test organization context using the fixture."""
        assert get_current_org_id() == org_context_with_org.id
        assert org_context_with_org is not None
