from resources.logger import logger
import schemas

DEFAULT_COVERS = [
    "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/default/default-green.png",
    "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/default/default-orange.png",
    "https://qalwnsoihhprqeppeloi.supabase.co/storage/v1/object/public/images/playlists/default/default-purple.png"
]

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
    print("hasta aca todo bien")
    print("Songs passed to serializer:", songs)

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
                duration=song.get("duration", "0"),
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

def serialize_collection(collection: dict, songs: list) -> schemas.Collection:

    return schemas.Collection(
        id=str(collection["_id"]),
        name=collection["name"],
        artistId=collection["artistId"],
        artistName=collection["artistName"],
        type=collection["type"],
        coverUrl=collection["coverUrl"],
        createdAt=collection["createdAt"],
        releaseDate=collection.get("releaseDate"),
        # Popularity metrics (optional, only in popular collections)
        totalPlays=collection.get("totalPlays"),
        totalLikes=collection.get("totalLikes"),
        totalPlaylistSaves=collection.get("totalPlaylistSaves"),
        totalShares=collection.get("totalShares"),
        popularityScore=collection.get("popularityScore"),
        songs=[
            schemas.CollectionSong(
                id=str(song["_id"]),
                title=song["title"],
                artist=song["artist"],
                duration=song.get("duration", "0"),
                order=song['order'],
            )
            for song in songs
        ]
    )