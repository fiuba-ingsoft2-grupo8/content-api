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

def serialize_playlist(playlist: dict, songs: list) -> schemas.Playlist:
    if "coverUrl" in playlist :
        coverUrl = playlist["coverUrl"] 
    else:
        coverUrl = None

    if "isLikedSongs" in playlist :
        isLikedSongs = playlist["isLikedSongs"] 
    else:
        isLikedSongs = False 
    return schemas.Playlist(
        id=str(playlist["_id"]),
        name=playlist["name"],
        description=playlist["description"],
        isPublished=playlist["is_published"],
        publishedAt=playlist["published_at"],
        userId=playlist["userId"],
        songs=[
            schemas.PlaylistSong(
                id=str(song["_id"]),
                title=song["title"],
                artist=song["artist"],
                addedAt=song["added_at"],
            )
            for song in songs
        ],
        coverUrl=coverUrl,
        isLikedSongs=isLikedSongs
    )

def serialize_song(song):
    song["_id"] = str(song["_id"])
    return song