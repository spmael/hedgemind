"""
Base factories for creating test data using Factory Boy.
"""

import factory
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.organizations.models import Organization, OrganizationMember, OrganizationRole

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
