"""
Tests for organization query utilities.
"""

from apps.organizations.models import OrganizationMember
from libs.organization_query import for_current_organization
from libs.tenant_context import set_current_org_id


class TestOrganizationQuery:
    """Test cases for organization query functions."""

    def test_for_current_organization_with_org_set(self, organization, user):
        """Test filtering by current organization when org is set."""
        from tests.factories import OrganizationMemberFactory

        set_current_org_id(organization.id)

        # Use OrganizationMember which has organization_id field
        member = OrganizationMemberFactory(organization=organization, user=user)
        queryset = for_current_organization(OrganizationMember)

        assert queryset.model == OrganizationMember
        # Should filter by organization_id
        assert member in queryset

    def test_for_current_organization_with_no_org(self):
        """Test that returns empty queryset when no org is set."""
        set_current_org_id(None)

        queryset = for_current_organization(OrganizationMember)

        assert queryset.model == OrganizationMember
        assert queryset.count() == 0

    def test_for_current_organization_filters_correctly(self, organization, user):
        """Test that only returns members matching current org."""
        from tests.factories import OrganizationFactory, OrganizationMemberFactory

        org1 = organization
        org2 = OrganizationFactory()

        member1 = OrganizationMemberFactory(organization=org1, user=user)
        member2 = OrganizationMemberFactory(organization=org2, user=user)

        set_current_org_id(org1.id)

        queryset = for_current_organization(OrganizationMember)

        assert member1 in queryset
        assert member2 not in queryset

    def test_for_current_organization_updates_with_context_change(
        self, organization, user
    ):
        """Test that queryset reflects context changes."""
        from tests.factories import OrganizationFactory, OrganizationMemberFactory

        org1 = organization
        org2 = OrganizationFactory()

        member1 = OrganizationMemberFactory(organization=org1, user=user)
        member2 = OrganizationMemberFactory(organization=org2, user=user)

        set_current_org_id(org1.id)
        queryset1 = for_current_organization(OrganizationMember)
        assert member1 in queryset1
        assert member2 not in queryset1

        set_current_org_id(org2.id)
        queryset2 = for_current_organization(OrganizationMember)
        assert member1 not in queryset2
        assert member2 in queryset2
