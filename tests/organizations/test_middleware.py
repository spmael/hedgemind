"""
Tests for organizations middleware.
"""

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from apps.organizations.middleware import OrganizationContextMiddleware
from libs.tenant_context import get_current_org_id


def _add_session_to_request(request):
    """Helper to add session support to a RequestFactory request."""
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


def _add_user_to_request(request, user=None):
    """Helper to add user attribute to a RequestFactory request."""
    from django.contrib.auth.models import AnonymousUser

    if user is None:
        # Add anonymous user
        user = AnonymousUser()

    request.user = user
    return request


class TestOrganizationContextMiddleware:
    """Test cases for OrganizationContextMiddleware."""

    def test_middleware_clears_context(self, organization):
        """Test that middleware clears organization context after request."""
        middleware = OrganizationContextMiddleware(lambda request: None)
        request = RequestFactory().get("/")
        _add_session_to_request(request)
        _add_user_to_request(request)

        # Set context before request
        from libs.tenant_context import set_current_org_id

        set_current_org_id(organization.id)
        assert get_current_org_id() == organization.id

        # Process request
        middleware(request)

        # Context should be cleared
        assert get_current_org_id() is None

    def test_middleware_handles_no_context(self):
        """Test that middleware handles requests with no existing context."""
        middleware = OrganizationContextMiddleware(lambda request: None)
        request = RequestFactory().get("/")
        _add_session_to_request(request)
        _add_user_to_request(request)

        # No context set
        assert get_current_org_id() is None

        # Process request
        middleware(request)

        # Context should still be None
        assert get_current_org_id() is None

    def test_middleware_preserves_response(self):
        """Test that middleware preserves the response from view."""

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/")
        _add_session_to_request(request)
        _add_user_to_request(request)
        response = middleware(request)

        assert response.status_code == 200
        assert response.content == b"OK"

    def test_middleware_resolves_org_from_header(self, organization, user):
        """Test that middleware resolves organization from X-ORG-ID header."""
        from libs.tenant_context import get_current_org_id

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/", HTTP_X_ORG_ID=str(organization.id))
        _add_session_to_request(request)
        _add_user_to_request(request, user)

        # Create membership so user can access org
        from tests.factories import OrganizationMemberFactory

        OrganizationMemberFactory(organization=organization, user=user)

        response = middleware(request)

        assert response.status_code == 200
        assert get_current_org_id() is None  # Cleared after request
        assert hasattr(request, "org_id")
        assert request.org_id == organization.id

    def test_middleware_resolves_org_from_session(self, organization, user):
        """Test that middleware resolves organization from session."""
        from libs.tenant_context import get_current_org_id

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/")
        _add_session_to_request(request)
        request.session["active_org_id"] = organization.id
        _add_user_to_request(request, user)

        # Create membership so user can access org
        from tests.factories import OrganizationMemberFactory

        OrganizationMemberFactory(organization=organization, user=user)

        response = middleware(request)

        assert response.status_code == 200
        assert get_current_org_id() is None  # Cleared after request
        assert request.org_id == organization.id

    def test_middleware_auto_selects_single_org(self, organization, user):
        """Test that middleware auto-selects organization if user has only one membership."""
        from libs.tenant_context import get_current_org_id

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/")
        _add_session_to_request(request)
        _add_user_to_request(request, user)

        # Create single membership
        from tests.factories import OrganizationMemberFactory

        OrganizationMemberFactory(organization=organization, user=user)

        response = middleware(request)

        assert response.status_code == 200
        assert get_current_org_id() is None  # Cleared after request
        assert request.org_id == organization.id

    def test_middleware_returns_403_for_non_member(self, organization, user):
        """Test that middleware returns 403 if user is not a member of the organization."""

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/", HTTP_X_ORG_ID=str(organization.id))
        _add_session_to_request(request)
        _add_user_to_request(request, user)

        # Don't create membership - user is not a member

        response = middleware(request)

        assert response.status_code == 403
        assert "not a member" in response.content.decode().lower()

    def test_middleware_header_takes_priority_over_session(self, organization, user):
        """Test that header takes priority over session for org resolution."""
        _other_org = organization
        from tests.factories import OrganizationFactory, OrganizationMemberFactory

        header_org = OrganizationFactory()
        session_org = OrganizationFactory()

        # User is member of both
        OrganizationMemberFactory(organization=header_org, user=user)
        OrganizationMemberFactory(organization=session_org, user=user)

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/", HTTP_X_ORG_ID=str(header_org.id))
        _add_session_to_request(request)
        request.session["active_org_id"] = session_org.id
        _add_user_to_request(request, user)

        response = middleware(request)

        assert response.status_code == 200
        assert request.org_id == header_org.id  # Header takes priority

    def test_middleware_handles_invalid_header_value(self, user):
        """Test that middleware handles invalid header values gracefully."""

        def mock_view(request):
            from django.http import HttpResponse

            return HttpResponse("OK")

        middleware = OrganizationContextMiddleware(mock_view)
        request = RequestFactory().get("/", HTTP_X_ORG_ID="invalid")
        _add_session_to_request(request)
        _add_user_to_request(request, user)

        response = middleware(request)

        # Should not crash, just treat as no org
        assert response.status_code == 200
        assert request.org_id is None
