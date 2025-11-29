from datetime import timezone
from resources.logger import logger
import schemas
from databases.collection_states import calculate_effective_state
# Portadas por defecto (se usan si no se pasa cover explícito)
DEFAULT_COVERS = [
    "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/default/default-green.png",
    "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/default/default-orange.png",
    "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/default/default-purple.png",
]


def create_error_response(status_code: int, title: str, detail: str, instance: str = ""):
    logger.debug(f"Creating error response: {status_code} - {title} - {detail} - {instance}")
    return {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }


def _str_or_fallback(v, fb: str = "") -> str:
    return v if isinstance(v, str) else fb


def _int_or_fallback(v, fb: int = 0) -> int:
    try:
        return int(v)  # acepta int/str numérica
    except Exception:
        return fb


def _str_num(v, fb: str = "0") -> str:
    """Devuelve un string numérico: '123'. Si no se puede parsear, usa fb."""
    try:
        return str(int(v))
    except Exception:
        return fb


def serialize_playlist(playlist: dict, songs: list) -> schemas.Playlist:
    """
    Serializa una playlist de Mongo a schemas.Playlist.
    - Forzamos tipos para que Pydantic no falle (description siempre str).
    - Campos opcionales con fallback.
    """
    from datetime import datetime, timezone
    
    cover_url = playlist.get("coverUrl")
    is_liked_songs = bool(playlist.get("isLikedSongs", False))
    is_mix = bool(playlist.get("isMix", False))

    # Fallbacks seguros para Pydantic
    _id = str(playlist.get("_id", ""))
    name = _str_or_fallback(playlist.get("name"), "(sin nombre)")
    description = _str_or_fallback(playlist.get("description"), "")
    is_published = bool(playlist.get("is_published", False))
    published_at = playlist.get("published_at")  # str ISO o datetime
    user_id = _str_or_fallback(playlist.get("userId"), "unknown")

    return schemas.Playlist(
        id=_id,
        name=name,
        description=description,
        isPublished=is_published,
        publishedAt=published_at,
        userId=user_id,
        songs=[
            schemas.PlaylistSong(
                id=str(song.get("_id", "")),
                title=_str_or_fallback(song.get("title"), "(sin título)"),
                artist=_str_or_fallback(song.get("artist"), ""),
                duration=_str_num(song.get("duration"), "0"),  # string (no int)
                addedAt=song.get("added_at") or datetime.now(timezone.utc),
                order=_int_or_fallback(song.get("order"), 0),
            )
            for song in (songs or [])
        ],
        coverUrl=cover_url,
        isLikedSongs=is_liked_songs,
        isMix=is_mix,
    )


def serialize_song(song: dict, is_liked: bool | None = None):
    song["_id"] = str(song["_id"])
    if is_liked is not None:
        song["isLiked"] = is_liked
    return song


def _iso(dt):
    if not dt:
        return None
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_collection(collection_or_col, *args, user_country=None) -> schemas.Collection:
    """
    Soporta:
      - serialize_collection(col, songs)
      - serialize_collection(col, songs, user_country)
      - serialize_collection(collection, col, songs)              (legacy)
      - serialize_collection(collection, col, songs, user_country) (legacy)
    """

    # --- Resolver parámetros ---
    if len(args) == 1:
        # (col, songs)
        col = collection_or_col
        songs = args[0]
    elif len(args) == 2:
        # (collection, col, songs)  OR  (col, songs, user_country)?? -> acá asumimos legacy
        col = args[0]
        songs = args[1]
    elif len(args) >= 3:
        col = args[0]
        songs = args[1]
        user_country = args[2]
    else:
        raise TypeError(
            "serialize_collection expected (col, songs[, user_country]) or (collection, col, songs[, user_country])"
        )

    # --- Admin block ---
    admin_block = col.get("adminBlock") or {}
    admin_block_enabled = isinstance(admin_block, dict) and admin_block.get("enabled") is True
    legacy_blocked = bool(col.get("bloqueadoAdmin", False))

    by_val = admin_block.get("by")

    admin_block_out = None
    if admin_block_enabled:
        admin_block_out = {
            "enabled": True,
            "scope": admin_block.get("scope") or "global",
            "regions": admin_block.get("regions") or [],
            "reasonCode": admin_block.get("reasonCode"),
            "by": None if by_val is None else str(by_val),
            "at": _iso(admin_block.get("at")),
        }

    admin_blocked = legacy_blocked or admin_block_enabled

    # --- Effective status (backend) ---
    effective_status = calculate_effective_state(col, user_country)

    # --- Serialize songs ---
    songs_out = [
        schemas.CollectionSong(
            id=str(song.get("_id", "")),
            title=str(song.get("title") or "(sin título)"),
            artist=str(song.get("artist") or ""),
            duration=str(int(song.get("duration"))) if str(song.get("duration", "")).isdigit() else str(song.get("duration") or "0"),
            order=int(song.get("order") or 0),
            earlyReleaseDate=song.get("early_release_date"),
        )
        for song in (songs or [])
    ]

    return schemas.Collection(
        id=str(col.get("_id", "")),
        name=str(col.get("name") or "(sin nombre)"),
        artistId=str(col.get("artistId") or ""),
        artistName=str(col.get("artistName") or ""),
        type=str(col.get("type") or ""),
        genre=str(col.get("genre") or "Unknown"),
        coverUrl=col.get("coverUrl"),
        createdAt=col.get("createdAt"),
        credits=col.get("credits", []),
        releaseDate=col.get("releaseDate"),
        noDisponibleDesde=col.get("noDisponibleDesde"),
        noDisponibleHasta=col.get("noDisponibleHasta"),
        effectiveStatus=effective_status,
        adminBlock=admin_block_out,
        adminBlocked=admin_blocked,
        bloqueadoAdmin=legacy_blocked,
        availableCountries=col.get("availableCountries", []),
        totalPlays=col.get("totalPlays"),
        totalLikes=col.get("totalLikes"),
        totalPlaylistSaves=col.get("totalPlaylistSaves"),
        totalShares=col.get("totalShares"),
        popularityScore=col.get("popularityScore"),
        songs=songs_out,
    )