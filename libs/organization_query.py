"""
Helper: Provides functions to filter querysets to the current organization.
Uses thread-local context so that services and views can enforce per-request/org data safety.
Call `for_current_organization(model)` to get objects scoped to the active org.
"""
from __future__ import annotations
from typing import Type
from django.db.models import QuerySet, Model
from libs.tenant_context import get_current_org_id


def for_current_organization(model: Type[Model]) -> QuerySet:
    """
    Returns a queryset for the given model filtered to the current organization
    based on the thread-local organization context.

    Args:
        model (Type[Model]): The Django model class to filter.

    Returns:
        QuerySet: QuerySet filtered to objects related to the current organization,
                  or an empty QuerySet if no organization is set in the context.
    """
    
    org_id = get_current_org_id()
    if org_id is None:
        return model.objects.none()
    
    return model.objects.filter(organization_id=org_id)