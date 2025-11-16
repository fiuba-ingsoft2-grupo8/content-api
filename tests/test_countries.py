import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from common.countries import (
    COUNTRIES,
    ALL_COUNTRY_CODES,
    validate_country_codes,
    calculate_available_countries
)


class TestCountriesModule:
    """Test suite for countries module."""

    def test_countries_dict_exists(self):
        """Test that COUNTRIES dictionary is defined and not empty."""
        assert COUNTRIES is not None
        assert isinstance(COUNTRIES, dict)
        assert len(COUNTRIES) > 0

    def test_all_country_codes_list(self):
        """Test that ALL_COUNTRY_CODES list matches COUNTRIES keys."""
        assert len(ALL_COUNTRY_CODES) == len(COUNTRIES)
        assert set(ALL_COUNTRY_CODES) == set(COUNTRIES.keys())

    def test_specific_country_codes(self):
        """Test that specific expected countries are in the list."""
        expected_countries = ["AR", "US", "BR", "MX", "ES", "GB", "FR", "DE"]
        for code in expected_countries:
            assert code in COUNTRIES
            assert code in ALL_COUNTRY_CODES


class TestValidateCountryCodes:
    """Test suite for validate_country_codes function."""

    def test_validate_valid_codes(self):
        """Test validation with valid country codes."""
        is_valid, error_msg = validate_country_codes(["AR", "US", "BR"])
        assert is_valid is True
        assert error_msg == ""

    def test_validate_single_valid_code(self):
        """Test validation with single valid country code."""
        is_valid, error_msg = validate_country_codes(["MX"])
        assert is_valid is True
        assert error_msg == ""

    def test_validate_all_codes(self):
        """Test validation with all country codes."""
        is_valid, error_msg = validate_country_codes(ALL_COUNTRY_CODES)
        assert is_valid is True
        assert error_msg == ""

    def test_validate_empty_list(self):
        """Test validation with empty list."""
        is_valid, error_msg = validate_country_codes([])
        assert is_valid is True
        assert error_msg == ""

    def test_validate_none_value(self):
        """Test validation with None value."""
        is_valid, error_msg = validate_country_codes(None)
        assert is_valid is True
        assert error_msg == ""

    def test_validate_invalid_code(self):
        """Test validation with invalid country code."""
        is_valid, error_msg = validate_country_codes(["XX"])
        assert is_valid is False
        assert "XX" in error_msg
        assert "Invalid country codes" in error_msg

    def test_validate_mixed_valid_and_invalid(self):
        """Test validation with mix of valid and invalid codes."""
        is_valid, error_msg = validate_country_codes(["AR", "XX", "YY"])
        assert is_valid is False
        assert "XX" in error_msg
        assert "YY" in error_msg

    def test_validate_not_a_list(self):
        """Test validation with non-list input."""
        is_valid, error_msg = validate_country_codes("AR")
        assert is_valid is False
        assert "must be a list" in error_msg

    def test_validate_case_sensitive(self):
        """Test that validation is case-sensitive."""
        is_valid, error_msg = validate_country_codes(["ar", "us"])  # lowercase
        assert is_valid is False
        assert "ar" in error_msg


class TestCalculateAvailableCountries:
    """Test suite for calculate_available_countries function."""

    def test_calculate_with_available_in_only(self):
        """Test calculation with only availableInCountries specified."""
        result = calculate_available_countries(
            available_in=["AR", "UY", "CL"],
            not_available_in=None
        )
        assert result == ["AR", "UY", "CL"]

    def test_calculate_with_not_available_in_only(self):
        """Test calculation with only notAvailableInCountries specified."""
        result = calculate_available_countries(
            available_in=None,
            not_available_in=["US", "CA"]
        )
        # Should return all countries except US and CA
        assert "US" not in result
        assert "CA" not in result
        assert "AR" in result
        assert "BR" in result
        assert len(result) == len(ALL_COUNTRY_CODES) - 2

    def test_calculate_with_both_specified_prioritizes_available_in(self):
        """Test that available_in takes precedence when both are specified."""
        result = calculate_available_countries(
            available_in=["AR", "UY"],
            not_available_in=["US", "CA"]
        )
        # Should use available_in and ignore not_available_in
        assert result == ["AR", "UY"]

    def test_calculate_with_neither_specified(self):
        """Test calculation with neither parameter specified."""
        result = calculate_available_countries(
            available_in=None,
            not_available_in=None
        )
        # Should return all countries
        assert len(result) == len(ALL_COUNTRY_CODES)
        assert set(result) == set(ALL_COUNTRY_CODES)

    def test_calculate_with_empty_lists(self):
        """Test calculation with empty lists."""
        result = calculate_available_countries(
            available_in=[],
            not_available_in=[]
        )
        # Empty available_in is falsy, empty not_available_in should return all
        assert len(result) == len(ALL_COUNTRY_CODES)

    def test_calculate_excludes_all_from_not_available(self):
        """Test that all countries in not_available_in are excluded."""
        excluded = ["US", "CA", "MX", "BR"]
        result = calculate_available_countries(
            available_in=None,
            not_available_in=excluded
        )
        
        for code in excluded:
            assert code not in result
        
        assert len(result) == len(ALL_COUNTRY_CODES) - len(excluded)

    def test_calculate_returns_copy_not_reference(self):
        """Test that function returns a copy, not reference to ALL_COUNTRY_CODES."""
        result = calculate_available_countries()
        result.append("XX")  # Modify returned list
        
        # ALL_COUNTRY_CODES should remain unchanged
        assert "XX" not in ALL_COUNTRY_CODES

    def test_calculate_with_single_country(self):
        """Test calculation with single country specified."""
        result = calculate_available_countries(available_in=["AR"])
        assert result == ["AR"]
        assert len(result) == 1

    def test_calculate_exclude_all_except_one(self):
        """Test excluding all countries except one."""
        # Exclude all except AR
        excluded = [code for code in ALL_COUNTRY_CODES if code != "AR"]
        result = calculate_available_countries(
            available_in=None,
            not_available_in=excluded
        )
        
        assert result == ["AR"]
        assert len(result) == 1

