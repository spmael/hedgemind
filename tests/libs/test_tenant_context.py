"""
Tests for tenant context utilities.
"""

from libs.tenant_context import (
    get_current_org_id,
    organization_context,
    set_current_org_id,
)


class TestTenantContext:
    """Test cases for tenant context functions."""

    def test_set_and_get_org_id(self):
        """Test setting and getting organization ID."""
        set_current_org_id(1)
        assert get_current_org_id() == 1

        set_current_org_id(2)
        assert get_current_org_id() == 2

        set_current_org_id(None)
        assert get_current_org_id() is None

    def test_get_org_id_when_not_set(self):
        """Test getting org ID when not set returns None."""
        set_current_org_id(None)
        assert get_current_org_id() is None

    def test_organization_context_manager(self):
        """Test organization context manager sets and restores org ID."""
        # Set initial context
        set_current_org_id(1)
        assert get_current_org_id() == 1

        # Use context manager
        with organization_context(2):
            assert get_current_org_id() == 2

        # Should restore previous value
        assert get_current_org_id() == 1

    def test_organization_context_manager_with_none(self):
        """Test organization context manager with None clears context."""
        set_current_org_id(1)
        assert get_current_org_id() == 1

        with organization_context(None):
            assert get_current_org_id() is None

        # Should restore previous value
        assert get_current_org_id() == 1

    def test_organization_context_manager_nested(self):
        """Test nested organization context managers."""
        set_current_org_id(1)

        with organization_context(2):
            assert get_current_org_id() == 2

            with organization_context(3):
                assert get_current_org_id() == 3

            assert get_current_org_id() == 2

        assert get_current_org_id() == 1

    def test_organization_context_manager_exception_handling(self):
        """Test that context manager restores org ID even on exception."""
        set_current_org_id(1)

        try:
            with organization_context(2):
                assert get_current_org_id() == 2
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still restore previous value
        assert get_current_org_id() == 1
