from resources.logger import logger
from db import models
import schemas

def create_error_response(status_code: int, title: str, detail: str, instance: str = ""):
    """
    Create a standardized error response following RFC 7807 Problem Details format.
    """
    logger.debug(
        f"Creating error response: {status_code} - {title} - {detail} - {instance}"
    )
    return {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }


def serialize_playlist(playlist: models.Playlist) -> schemas.Playlist:
    return schemas.Playlist(
        id=playlist.id,
        name=playlist.name,
        description=playlist.description,
        isPublished=playlist.is_published,
        publishedAt=playlist.published_at,
        songs=[
            schemas.PlaylistSong(
                id=ps.song.id,
                title=ps.song.title,
                artist=ps.song.artist,
                addedAt=ps.added_at,
            )
            for ps in playlist.playlist_songs
        ],
    )