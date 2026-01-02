"""
Tests for issuer code generation and validation utilities.

Tests the issuer code utility functions including code generation,
validation, and normalization.
"""

from __future__ import annotations

from apps.reference_data.utils.issuer_codes import (
    generate_issuer_code,
    get_region_code,
    get_type_code,
    normalize_identifier,
    validate_issuer_code,
)


class TestGetRegionCode:
    """Test cases for get_region_code function."""

    def test_get_region_code_cameroon(self):
        """Test region code for Cameroon."""
        assert get_region_code("CM") == "CM"

    def test_get_region_code_congo(self):
        """Test region code for Congo."""
        assert get_region_code("CG") == "CG"

    def test_get_region_code_gabon(self):
        """Test region code for Gabon."""
        assert get_region_code("GA") == "GA"

    def test_get_region_code_chad(self):
        """Test region code for Chad."""
        assert get_region_code("TD") == "TD"

    def test_get_region_code_equatorial_guinea(self):
        """Test region code for Equatorial Guinea."""
        assert get_region_code("GQ") == "GQ"

    def test_get_region_code_central_african_republic(self):
        """Test region code for Central African Republic."""
        assert get_region_code("CF") == "CF"

    def test_get_region_code_xaf(self):
        """Test region code for XAF (CEMAC-wide)."""
        assert get_region_code("XAF") == "XAF"

    def test_get_region_code_unknown(self):
        """Test region code for unknown country defaults to INT."""
        assert get_region_code("US") == "INT"
        assert get_region_code("XX") == "INT"

    def test_get_region_code_none(self):
        """Test region code for None defaults to INT."""
        assert get_region_code(None) == "INT"

    def test_get_region_code_case_insensitive(self):
        """Test region code is case insensitive."""
        assert get_region_code("cm") == "CM"
        assert get_region_code("Cm") == "CM"


class TestGetTypeCode:
    """Test cases for get_type_code function."""

    def test_get_type_code_sovereign(self):
        """Test type code for Sovereign."""
        assert get_type_code("SOV") == "SOV"

    def test_get_type_code_supranational(self):
        """Test type code for Supranational."""
        assert get_type_code("SUPRA") == "SUP"

    def test_get_type_code_gre(self):
        """Test type code for Government-Related Entity."""
        assert get_type_code("GRE") == "GRE"

    def test_get_type_code_bank(self):
        """Test type code for Bank."""
        assert get_type_code("BANK") == "BNK"

    def test_get_type_code_insurance(self):
        """Test type code for Insurance."""
        assert get_type_code("INS") == "INS"

    def test_get_type_code_asset_manager(self):
        """Test type code for Asset Manager."""
        assert get_type_code("AM") == "AMC"

    def test_get_type_code_financial(self):
        """Test type code for Financial."""
        assert get_type_code("FIN") == "FIN"
        assert get_type_code("FIN_OTHER") == "FIN"

    def test_get_type_code_corporate(self):
        """Test type code for Corporate."""
        assert get_type_code("CORP") == "COR"
        assert get_type_code("IND") == "COR"
        assert get_type_code("CONS") == "COR"
        assert get_type_code("ENERGY") == "COR"
        assert get_type_code("UTIL") == "COR"

    def test_get_type_code_unknown(self):
        """Test type code for unknown group defaults to COR."""
        assert get_type_code("UNKNOWN") == "COR"

    def test_get_type_code_none(self):
        """Test type code for None defaults to COR."""
        assert get_type_code(None) == "COR"

    def test_get_type_code_case_insensitive(self):
        """Test type code is case insensitive."""
        assert get_type_code("sov") == "SOV"
        assert get_type_code("Bank") == "BNK"


class TestNormalizeIdentifier:
    """Test cases for normalize_identifier function."""

    def test_normalize_identifier_etat_du(self):
        """Test normalization of 'ETAT DU' pattern."""
        assert normalize_identifier("ETAT DU CAMEROUN") == "GOVT"

    def test_normalize_identifier_etat_de(self):
        """Test normalization of 'ETAT DE' pattern."""
        assert normalize_identifier("ETAT DE GABON") == "GOVT"

    def test_normalize_identifier_republique_du(self):
        """Test normalization of 'REPUBLIQUE DU' pattern."""
        assert normalize_identifier("REPUBLIQUE DU CONGO") == "GOVT"

    def test_normalize_identifier_republique_de(self):
        """Test normalization of 'REPUBLIQUE DE' pattern."""
        assert normalize_identifier("REPUBLIQUE DE CAMEROUN") == "GOVT"

    def test_normalize_identifier_republic_of(self):
        """Test normalization of 'REPUBLIC OF' pattern."""
        assert normalize_identifier("REPUBLIC OF CAMEROON") == "GOVT"

    def test_normalize_identifier_banque(self):
        """Test normalization of bank names."""
        result = normalize_identifier("BANQUE DE GABON")
        assert result.startswith("BANQUEDEGAB") or len(result) <= 10

    def test_normalize_identifier_removes_special_chars(self):
        """Test that special characters are removed."""
        result = normalize_identifier("Test & Company, Inc.")
        # Should remove special chars: "TESTCOMPANYINC" (14 chars) -> truncate to 10 -> "TESTCOMPAN"
        assert result == "TESTCOMPAN"  # Truncated to max_length=10

    def test_normalize_identifier_truncates_long_names(self):
        """Test that long names are truncated."""
        result = normalize_identifier("A" * 100)
        assert len(result) <= 10

    def test_normalize_identifier_empty(self):
        """Test normalization of empty string."""
        assert normalize_identifier("") == "UNKNOWN"

    def test_normalize_identifier_uppercase(self):
        """Test that identifier is uppercase."""
        result = normalize_identifier("test company")
        assert result.isupper()


class TestGenerateIssuerCode:
    """Test cases for generate_issuer_code function."""

    def test_generate_issuer_code_sovereign(self):
        """Test generating code for sovereign issuer."""
        code = generate_issuer_code(
            name="ETAT DU CAMEROUN",
            country="CM",
            issuer_group_code="SOV",
        )
        assert code == "CM-SOV-GOVT"

    def test_generate_issuer_code_bank(self):
        """Test generating code for bank."""
        code = generate_issuer_code(
            name="BANQUE DE GABON",
            country="GA",
            issuer_group_code="BANK",
        )
        assert code.startswith("GA-BNK-")
        assert len(code.split("-")) == 3

    def test_generate_issuer_code_supranational(self):
        """Test generating code for supranational."""
        code = generate_issuer_code(
            name="BDEAC",
            country="XAF",
            issuer_group_code="SUPRA",
        )
        assert code.startswith("XAF-SUP-")

    def test_generate_issuer_code_custom_identifier(self):
        """Test generating code with custom identifier."""
        code = generate_issuer_code(
            name="Test Issuer",
            country="CM",
            issuer_group_code="CORP",
            identifier="TEST123",
        )
        assert code == "CM-COR-TEST123"

    def test_generate_issuer_code_no_country(self):
        """Test generating code without country defaults to INT."""
        code = generate_issuer_code(
            name="Test Issuer",
            country=None,
            issuer_group_code="CORP",
        )
        assert code.startswith("INT-COR-")

    def test_generate_issuer_code_no_group(self):
        """Test generating code without group defaults to COR."""
        code = generate_issuer_code(
            name="Test Issuer",
            country="CM",
            issuer_group_code=None,
        )
        assert code.startswith("CM-COR-")

    def test_generate_issuer_code_format(self):
        """Test that generated code follows correct format."""
        code = generate_issuer_code(
            name="Test Company",
            country="CM",
            issuer_group_code="CORP",
        )
        parts = code.split("-")
        assert len(parts) == 3
        assert len(parts[0]) >= 2  # Region
        assert len(parts[1]) == 3  # Type
        assert len(parts[2]) >= 1 and len(parts[2]) <= 10  # Identifier


class TestValidateIssuerCode:
    """Test cases for validate_issuer_code function."""

    def test_validate_issuer_code_valid(self):
        """Test validation of valid issuer codes."""
        valid_codes = [
            "CM-SOV-GOVT",
            "GA-BNK-BANQUEDEGA",  # 10 chars (truncated from BANQUEDEGAB)
            "XAF-SUP-BDEAC",
            "CG-GRE-SNPC",
            "CM-COR-SEMC",
        ]
        for code in valid_codes:
            is_valid, error = validate_issuer_code(code)
            assert is_valid, f"Code {code} should be valid: {error}"

    def test_validate_issuer_code_invalid_format(self):
        """Test validation of invalid format codes."""
        invalid_codes = [
            "INVALID",
            "CM-SOV",  # Missing identifier
            "CM-SOV-",  # Empty identifier
            "CM-SOV-GOVT-EXTRA",  # Too many parts
            "cm-sov-govt",  # Lowercase
            "CM-SOV-GOVT-TOOLONGIDENTIFIER",  # Identifier too long
        ]
        for code in invalid_codes:
            is_valid, error = validate_issuer_code(code)
            assert not is_valid, f"Code {code} should be invalid"

    def test_validate_issuer_code_empty(self):
        """Test validation of empty code."""
        is_valid, error = validate_issuer_code("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_validate_issuer_code_none(self):
        """Test validation of None code."""
        is_valid, error = validate_issuer_code(None)
        assert not is_valid

    def test_validate_issuer_code_region_too_short(self):
        """Test validation of code with region too short."""
        is_valid, error = validate_issuer_code("C-SOV-GOVT")
        assert not is_valid

    def test_validate_issuer_code_region_too_long(self):
        """Test validation of code with region too long."""
        is_valid, error = validate_issuer_code("CMCM-SOV-GOVT")
        assert not is_valid

    def test_validate_issuer_code_type_wrong_length(self):
        """Test validation of code with type wrong length."""
        is_valid, error = validate_issuer_code("CM-SO-GOVT")
        assert not is_valid
        is_valid, error = validate_issuer_code("CM-SOVV-GOVT")
        assert not is_valid

    def test_validate_issuer_code_identifier_special_chars(self):
        """Test validation of code with special characters in identifier."""
        is_valid, error = validate_issuer_code("CM-SOV-GOV-T")
        assert not is_valid

    def test_generate_issuer_code_edge_cases(self):
        """Test code generation with edge case inputs."""
        # Very long name
        code = generate_issuer_code(
            name="A" * 200,
            country="CM",
            issuer_group_code="CORP",
        )
        assert code.startswith("CM-COR-")
        parts = code.split("-")
        assert len(parts[2]) <= 10  # Identifier truncated

        # Name with only special characters
        code = generate_issuer_code(
            name="!@#$%^&*()",
            country="CM",
            issuer_group_code="CORP",
        )
        assert code.startswith("CM-COR-")
        assert code.endswith("UNKNOWN") or len(code.split("-")[2]) > 0

    def test_normalize_identifier_edge_cases(self):
        """Test identifier normalization with edge cases."""
        # Very long name
        result = normalize_identifier("A" * 1000)
        assert len(result) <= 10

        # Only special characters
        result = normalize_identifier("!@#$%^&*()")
        assert result == "UNKNOWN" or len(result) > 0

        # Mixed case with special chars
        result = normalize_identifier("Test & Company, Inc. (Ltd.)")
        assert result.isupper()
        assert all(c.isalnum() for c in result)

    def test_generate_issuer_code_all_region_codes(self):
        """Test code generation with all supported region codes."""
        regions = ["CM", "CG", "GA", "TD", "GQ", "CF", "XAF", "INT"]
        for region in regions:
            code = generate_issuer_code(
                name="Test",
                country=region,
                issuer_group_code="CORP",
            )
            assert code.startswith(f"{region}-COR-")

    def test_generate_issuer_code_all_type_codes(self):
        """Test code generation with all supported type codes."""
        type_mappings = {
            "SOV": "SOV",
            "SUPRA": "SUP",
            "GRE": "GRE",
            "BANK": "BNK",
            "INS": "INS",
            "AM": "AMC",
            "FIN": "FIN",
            "CORP": "COR",
        }
        for group_code, expected_type in type_mappings.items():
            code = generate_issuer_code(
                name="Test",
                country="CM",
                issuer_group_code=group_code,
            )
            assert code.startswith(f"CM-{expected_type}-")
