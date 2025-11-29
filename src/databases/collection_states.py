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
    Priority:
    1) Bloqueado-admin (adminBlock con scope + legacy bloqueadoAdmin)
    2) No-disponible-región (por availableCountries o ventana noDisponible)
    3) Programado (releaseDate > now)
    4) Publicado
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # 1) Bloqueo admin (nuevo con alcance + legacy)
    legacy_blocked = bool(collection.get("bloqueadoAdmin", False))
    if legacy_blocked:
        return "bloqueado-admin"

    admin_block = collection.get("adminBlock")
    if isinstance(admin_block, dict) and admin_block.get("enabled") is True:
        scope = str(admin_block.get("scope") or "global").lower()

        if scope == "global":
            return "bloqueado-admin"

        if scope == "regions":
            regions = admin_block.get("regions") or []
            # si user_country no viene, por seguridad lo tratamos como bloqueado
            if not user_country or user_country in regions:
                return "bloqueado-admin"

    # 2) No-disponible-región por país
    available_countries = collection.get("availableCountries", [])
    if available_countries and user_country:
        if user_country not in available_countries:
            return "no-disponible-region"

    # 2b) ventana no-disponible (global)
    no_disponible_desde = collection.get("noDisponibleDesde")
    no_disponible_hasta = collection.get("noDisponibleHasta")

    if no_disponible_desde and no_disponible_hasta:
        if no_disponible_desde.tzinfo is None:
            no_disponible_desde = no_disponible_desde.replace(tzinfo=timezone.utc)
        if no_disponible_hasta.tzinfo is None:
            no_disponible_hasta = no_disponible_hasta.replace(tzinfo=timezone.utc)

        if no_disponible_desde <= now <= no_disponible_hasta:
            return "no-disponible-region"

    # 3) Programado
    release_date = collection.get("releaseDate")
    if release_date:
        if release_date.tzinfo is None:
            release_date = release_date.replace(tzinfo=timezone.utc)
        if release_date > now:
            return "programado"

    # 4) Publicado
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

