"""
Tests for issuers import service.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from apps.reference_data.models import Issuer
from apps.reference_data.services.issuers.import_excel import import_issuers_from_file
from libs.tenant_context import organization_context
from tests.factories import OrganizationFactory


class TestImportIssuersExcel:
    """Test cases for issuers import service."""

    def test_import_issuers_basic(self, org_context_with_org):
        """Test basic import of issuers."""
        df = pd.DataFrame(
            {
                "name": ["Test Issuer 1", "Test Issuer 2"],
                "short_name": ["TI1", "TI2"],
                "country": ["GA", "CM"],
                "issuer_group": ["Bank", "Asset Manager"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            result = import_issuers_from_file(
                file_path=tmp_path,
                sheet_name="ISSUERS",
            )

            assert result["created"] == 2
            assert result["updated"] == 0
            assert len(result["errors"]) == 0
            assert result["total_rows"] == 2

            # Verify issuers were created
            issuers = Issuer.objects.all()
            assert issuers.count() == 2
            assert issuers.filter(name="Test Issuer 1").exists()
            assert issuers.filter(name="Test Issuer 2").exists()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_missing_columns(self, org_context_with_org):
        """Test import fails with missing required columns."""
        df = pd.DataFrame(
            {
                "name": ["Test Issuer"],
                "short_name": ["TI"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            with pytest.raises(ValueError, match="Missing required columns"):
                import_issuers_from_file(
                    file_path=tmp_path,
                    sheet_name="ISSUERS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_invalid_country_code(self, org_context_with_org):
        """Test import fails with invalid country code."""
        df = pd.DataFrame(
            {
                "name": ["Test Issuer"],
                "short_name": ["TI"],
                "country": ["INVALID"],  # Not 2 characters
                "issuer_group": ["Bank"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            with pytest.raises(ValueError, match="Invalid country codes"):
                import_issuers_from_file(
                    file_path=tmp_path,
                    sheet_name="ISSUERS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_updates_existing(self, org_context_with_org):
        """Test import updates existing issuers."""
        # Create existing issuer
        Issuer.objects.create(
            organization=org_context_with_org,
            name="Test Issuer",
            short_name="TI",
            country="GA",
            issuer_group="Bank",
        )

        df = pd.DataFrame(
            {
                "name": ["Test Issuer"],
                "short_name": ["TI_UPDATED"],
                "country": ["CM"],  # Different country
                "issuer_group": ["Asset Manager"],  # Different group
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            result = import_issuers_from_file(
                file_path=tmp_path,
                sheet_name="ISSUERS",
            )

            assert result["created"] == 0
            assert result["updated"] == 1

            # Verify issuer was updated
            issuer = Issuer.objects.get(name="Test Issuer")
            assert issuer.short_name == "TI_UPDATED"
            assert issuer.country == "CM"
            assert issuer.issuer_group == "Asset Manager"

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_requires_org_context(self):
        """Test import fails without organization context."""
        df = pd.DataFrame(
            {
                "name": ["Test Issuer"],
                "short_name": ["TI"],
                "country": ["GA"],
                "issuer_group": ["Bank"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            with pytest.raises(RuntimeError, match="organization context"):
                import_issuers_from_file(
                    file_path=tmp_path,
                    sheet_name="ISSUERS",
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_missing_name(self, org_context_with_org):
        """Test import reports error for missing name."""
        df = pd.DataFrame(
            {
                "name": [None],  # None will be converted to NaN in Excel
                "short_name": ["TI"],
                "country": ["GA"],
                "issuer_group": ["Bank"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            result = import_issuers_from_file(
                file_path=tmp_path,
                sheet_name="ISSUERS",
            )

            assert result["created"] == 0
            assert len(result["errors"]) > 0
            assert any("name is required" in error for error in result["errors"])

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_default_sheet_name(self, org_context_with_org):
        """Test import uses default sheet name ISSUERS."""
        df = pd.DataFrame(
            {
                "name": ["Test Issuer"],
                "short_name": ["TI"],
                "country": ["GA"],
                "issuer_group": ["Bank"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            # Don't specify sheet_name, should use default "ISSUERS"
            result = import_issuers_from_file(file_path=tmp_path)

            assert result["created"] == 1
            assert len(result["errors"]) == 0

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_import_issuers_organization_isolation(self):
        """Test issuers are isolated by organization."""
        from libs.tenant_context import set_current_org_id

        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        df = pd.DataFrame(
            {
                "name": ["Test Issuer"],
                "short_name": ["TI"],
                "country": ["GA"],
                "issuer_group": ["Bank"],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            df.to_excel(tmp_path, index=False, sheet_name="ISSUERS")

        try:
            # Import for org1
            with organization_context(org1.id):
                result1 = import_issuers_from_file(file_path=tmp_path)
                assert result1["created"] == 1

            # Import for org2
            with organization_context(org2.id):
                result2 = import_issuers_from_file(file_path=tmp_path)
                assert result2["created"] == 1

            # Verify isolation - explicitly set context and clear any previous state
            set_current_org_id(None)
            with organization_context(org1.id):
                org1_issuers = list(Issuer.objects.all())
                assert len(org1_issuers) == 1
                assert org1_issuers[0].organization_id == org1.id

            set_current_org_id(None)
            with organization_context(org2.id):
                org2_issuers = list(Issuer.objects.all())
                assert len(org2_issuers) == 1
                assert org2_issuers[0].organization_id == org2.id

        finally:
            Path(tmp_path).unlink(missing_ok=True)
            set_current_org_id(None)  # Clean up

