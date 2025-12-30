"""
Middleware for maintaining multi-tenant organization context per request.

This middleware determines and sets the active organization in thread-local storage
(using libs.tenant_context), enabling per-request scoping for data access and services.

Resolution methods used (in order of priority):
  1. Request header: X-ORG-ID (supports API clients, SPAs)
  2. Session key: active_org_id (set by UI interaction)
  3. If not set, auto-select if user belongs to exactly one organization

Security:
  - If an org ID is found but user is not a member, returns HTTP 403.
  - Context is always cleared after each request/response.
"""

from __future__ import annotations

from django.http import HttpResponseForbidden

from apps.organizations.models import OrganizationMember
from libs.tenant_context import set_current_org_id


class OrganizationContextMiddleware:
    """
    Middleware for maintaining multi-tenant organization context per request.

    This middleware determines and sets the active organization in thread-local storage
    (using libs.tenant_context), enabling per-request scoping for data access and services.

    Resolution priority:
        1. Header: X-ORG-ID (for API clients or SPAs)
        2. Session: active_org_id (set by UI)
        3. If still unset, auto-select if user has exactly one org membership

    Security:
        - If an org ID is provided but the user is not a member, respond with HTTP 403.
        - Context is always cleared after handling a request.

    Attributes:
        HEADER_NAME (str): HTTP header name for organization ID.
        SESSION_KEY (str): Session key name for active organization ID.
    """

    HEADER_NAME = "X-ORG-ID"
    SESSION_KEY = "active_org_id"

    def __init__(self, get_response):
        """
        Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Process the request and set organization context.

        Determines the active organization using header, session, or auto-selection,
        validates user membership, and sets the organization context for the request.

        Args:
            request: Django HttpRequest object.

        Returns:
            HttpResponse: The response from the next middleware or view.
        """
        org_id = None

        try:
            header_org = request.headers.get(self.HEADER_NAME)
            if header_org:
                org_id = int(header_org)
        except (ValueError, TypeError):
            org_id = None

        if org_id is None:
            try:
                session_org = request.session.get(self.SESSION_KEY)
                if session_org:
                    org_id = int(session_org)
            except (ValueError, TypeError):
                org_id = None

        if request.user.is_authenticated:
            # Auto-pick org if user belongs to exactly 1 org
            if org_id is None:
                memberships = OrganizationMember.objects.filter(
                    user=request.user
                ).values_list("organization_id", flat=True)
                memberships = list(memberships[:2])
                if len(memberships) == 1:
                    org_id = memberships[0]

            # Validate membership if org_id present
            if org_id is not None:
                is_member = OrganizationMember.objects.filter(
                    user=request.user, organization_id=org_id
                ).exists()
                if not is_member:
                    set_current_org_id(None)
                    request.org_id = None
                    return HttpResponseForbidden(
                        "You are not a member of this organization."
                    )

                set_current_org_id(org_id)
                request.org_id = org_id
            else:
                set_current_org_id(None)
                request.org_id = None
        else:
            set_current_org_id(None)
            request.org_id = None

        response = self.get_response(request)

        # Clean up after request
        set_current_org_id(None)
        return response
