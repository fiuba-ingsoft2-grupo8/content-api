"""
Country codes and names for geographical restrictions.
"""

COUNTRIES = {
    "DE": "Alemania",
    "SA": "Arabia Saudita",
    "AR": "Argentina",
    "AU": "Australia",
    "AT": "Austria",
    "BE": "Bélgica",
    "BO": "Bolivia",
    "BR": "Brasil",
    "CA": "Canada",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "KR": "Corea del Sur",
    "DK": "Dinamarca",
    "EC": "Ecuador",
    "EG": "Egipto",
    "AE": "Emiratos Árabes Unidos",
    "ES": "España",
    "US": "Estados Unidos",
    "PH": "Filipinas",
    "FI": "Finlandia",
    "FR": "Francia",
    "GR": "Grecia",
    "IN": "India",
    "ID": "Indonesia",
    "IL": "Israel",
    "IT": "Italia",
    "JP": "Japón",
    "KE": "Kenia",
    "MY": "Malasia",
    "MX": "Mexico",
    "NG": "Nigeria",
    "NO": "Noruega",
    "NZ": "Nueva Zelanda",
    "NL": "Países Bajos",
    "PA": "Panama",
    "PY": "Paraguay",
    "PE": "Peru",
    "PL": "Polonia",
    "PT": "Portugal",
    "GB": "Reino Unido",
    "SG": "Singapur",
    "ZA": "Sudáfrica",
    "SE": "Suecia",
    "CH": "Suiza",
    "TH": "Tailandia",
    "TR": "Turquía",
    "UY": "Uruguay",
    "VE": "Venezuela",
    "VN": "Vietnam"
}

ALL_COUNTRY_CODES = list(COUNTRIES.keys())


def validate_country_codes(codes: list) -> tuple[bool, str]:
    """
    Validate that all country codes are valid.
    
    Args:
        codes: List of country codes to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not codes:
        return True, ""
    
    if not isinstance(codes, list):
        return False, "Country codes must be a list"
    
    invalid_codes = [code for code in codes if code not in COUNTRIES]
    if invalid_codes:
        return False, f"Invalid country codes: {', '.join(invalid_codes)}"
    
    return True, ""


def calculate_available_countries(available_in: list = None, not_available_in: list = None) -> list:
    """
    Calculate the final list of countries where content is available.
    
    Logic:
    - If available_in is specified, use that list
    - If available_in is not specified but not_available_in is, use all countries except those
    - If neither is specified, available in all countries
    
    Args:
        available_in: List of country codes where content IS available
        not_available_in: List of country codes where content is NOT available
        
    Returns:
        List of country codes where content is available
    """
    # If explicitly specified where it's available, use that
    if available_in:
        return available_in
    
    # If specified where it's NOT available, return all except those
    if not_available_in:
        return [code for code in ALL_COUNTRY_CODES if code not in not_available_in]
    
    # If nothing specified, available everywhere
    return ALL_COUNTRY_CODES.copy()

