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
                addedAt=song.get("added_at"),
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


def serialize_collection(collection, songs, user_country=None):
    # calculamos el estado efectivo según las reglas de prioridad
    effective_status = calculate_effective_state(collection, user_country)

    return schemas.Collection(
        id=str(collection.get("_id", "")),
        name=_str_or_fallback(collection.get("name"), "(sin nombre)"),
        artistId=_str_or_fallback(collection.get("artistId"), ""),
        artistName=_str_or_fallback(collection.get("artistName"), ""),
        type=_str_or_fallback(collection.get("type"), ""),
        genre=_str_or_fallback(collection.get("genre"), "Unknown"),
        coverUrl=collection.get("coverUrl"),
        createdAt=collection.get("createdAt"),

        credits=collection.get("credits", []),
        releaseDate=collection.get("releaseDate"),

        noDisponibleDesde=collection.get("noDisponibleDesde"),
        noDisponibleHasta=collection.get("noDisponibleHasta"),

        effectiveStatus=effective_status,

        availableCountries=collection.get("availableCountries", []),

        # Admin block information
        bloqueadoAdmin=collection.get("bloqueadoAdmin", False),
        bloqueadoAdminData=collection.get("bloqueadoAdminData"),

        totalPlays=collection.get("totalPlays"),
        totalLikes=collection.get("totalLikes"),
        totalPlaylistSaves=collection.get("totalPlaylistSaves"),
        totalShares=collection.get("totalShares"),
        popularityScore=collection.get("popularityScore"),

        songs=[
            schemas.CollectionSong(
                id=str(song.get("_id", "")),
                title=_str_or_fallback(song.get("title"), "(sin título)"),
                artist=_str_or_fallback(song.get("artist"), ""),
                duration=_str_num(song.get("duration"), "0"),  # string
                order=_int_or_fallback(song.get("order"), 0),
                earlyReleaseDate=song.get("early_release_date"),
            )
            for song in (songs or [])
        ],
    )