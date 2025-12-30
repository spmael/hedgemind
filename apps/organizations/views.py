"""
Views for organizations app.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.organizations.models import Organization, OrganizationMember


@login_required
@require_http_methods(["POST"])
def switch_organization(request, org_id: int):
    """
    Switch the active organization for the current user.

    Sets the active_org_id in the session and validates that the user
    is a member of the requested organization.

    Args:
        request: Django request object
        org_id: Organization ID to switch to

    Returns:
        JsonResponse with success status and organization info, or error
    """
    try:
        organization = Organization.objects.get(id=org_id, is_active=True)
    except Organization.DoesNotExist:
        return JsonResponse({"error": "Organization not found or inactive"}, status=404)

    # Validate user is a member
    is_member = OrganizationMember.objects.filter(
        user=request.user,
        organization=organization,
        is_active=True,
    ).exists()

    if not is_member:
        return JsonResponse(
            {"error": "You are not a member of this organization"}, status=403
        )

    # Set active organization in session
    request.session["active_org_id"] = organization.id
    request.session.save()

    return JsonResponse(
        {
            "success": True,
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug,
            },
        }
    )


@login_required
@require_http_methods(["GET"])
def list_user_organizations(request):
    """
    List all organizations the current user is a member of.

    Returns:
        JsonResponse with list of organizations
    """
    memberships = OrganizationMember.objects.filter(
        user=request.user, is_active=True
    ).select_related("organization")

    organizations = [
        {
            "id": membership.organization.id,
            "name": membership.organization.name,
            "slug": membership.organization.slug,
            "role": membership.role,
            "is_active": membership.organization.is_active,
        }
        for membership in memberships
        if membership.organization.is_active
    ]

    return JsonResponse({"organizations": organizations})
