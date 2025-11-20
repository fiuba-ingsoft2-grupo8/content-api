"""
Collection state management and effective state calculation.
Implements the priority system: Bloqueado-admin > No-disponible-región > Programado > Publicado
"""
from datetime import datetime, timezone
from typing import Optional
from resources.logger import logger


# Estado efectivo basado en prioridad
# Prioridad: Bloqueado-admin > No-disponible-región > Programado > Publicado
def calculate_effective_state(
    collection: dict,
    user_country: str | None = None,
    now: datetime | None = None
) -> str:
    """
    Calculate the effective state of a collection based on priority rules.
    
    Priority order:
    1. Bloqueado-admin (highest priority)
    2. No-disponible-región (if user's country is not in availableCountries)
    3. Programado (if releaseDate > now)
    4. Publicado (default, lowest priority)
    
    Args:
        collection: Collection document from database
        user_country: User's country code (for region-based availability)
        now: Current datetime (defaults to now if not provided)
        
    Returns:
        Effective state: 'bloqueado-admin', 'no-disponible-region', 'programado', or 'publicado'
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    # 1. Check Bloqueado-admin (highest priority)
    if collection.get("bloqueadoAdmin", False):
        return "bloqueado-admin"
    
    # 2. Check No-disponible-región
    available_countries = collection.get("availableCountries", [])
    if available_countries and user_country:
        if user_country not in available_countries:
            return "no-disponible-region"
    
    # Check No-disponible window (if configured)
    no_disponible_desde = collection.get("noDisponibleDesde")
    no_disponible_hasta = collection.get("noDisponibleHasta")
    
    if no_disponible_desde and no_disponible_hasta:
        # Make timezone-aware if needed
        if no_disponible_desde.tzinfo is None:
            no_disponible_desde = no_disponible_desde.replace(tzinfo=timezone.utc)
        if no_disponible_hasta.tzinfo is None:
            no_disponible_hasta = no_disponible_hasta.replace(tzinfo=timezone.utc)
        
        if no_disponible_desde <= now <= no_disponible_hasta:
            return "no-disponible-region"
    
    # 3. Check Programado (releaseDate > now)
    release_date = collection.get("releaseDate")
    if release_date:
        # Make timezone-aware if needed
        if release_date.tzinfo is None:
            release_date = release_date.replace(tzinfo=timezone.utc)
        
        if release_date > now:
            return "programado"
    
    # 4. Default: Publicado
    return "publicado"


def is_collection_playable(
    collection: dict,
    user_country: str | None = None,
    now: datetime | None = None
) -> bool:
    """
    Check if a collection is playable (not blocked).
    
    A collection is playable if:
    - It's not bloqueado-admin
    - It's not in a no-disponible window
    - User's country is in availableCountries (if restrictions exist)
    
    Note: Even if playable, it might still be "programado" (not yet released).
    
    Args:
        collection: Collection document from database
        user_country: User's country code
        now: Current datetime
        
    Returns:
        True if collection is playable, False otherwise
    """
    effective_state = calculate_effective_state(collection, user_country, now)
    
    # Only bloqueado-admin and no-disponible-region prevent playback
    return effective_state not in ("bloqueado-admin", "no-disponible-region")


def should_auto_activate(collection: dict, now: datetime | None = None) -> bool:
    """
    Check if a collection should be auto-activated (transition from Programado to Publicado).
    
    A collection should be activated if:
    - It's currently in "programado" state
    - releaseDate <= now
    - It's not bloqueado-admin
    
    Args:
        collection: Collection document from database
        now: Current datetime
        
    Returns:
        True if collection should be activated, False otherwise
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    # Don't activate if bloqueado-admin
    if collection.get("bloqueadoAdmin", False):
        return False
    
    # Check if releaseDate has passed
    release_date = collection.get("releaseDate")
    if not release_date:
        return False
    
    # Make timezone-aware if needed
    if release_date.tzinfo is None:
        release_date = release_date.replace(tzinfo=timezone.utc)
    
    # Should activate if releaseDate <= now
    return release_date <= now

