from datetime import datetime
from typing import Optional, Annotated
from pydantic import BaseModel, PlainSerializer, Field
from pydantic.functional_validators import BeforeValidator
from bson import ObjectId


# Association table for many-to-many relationship between playlists and songs
# This table tracks when each song was added to each playlist
# playlist_songs = Table(
#     "playlist_songs",
#     Base.metadata,
#     Column("playlist_id", Integer, ForeignKey("playlists.id"), primary_key=True),
#     Column("song_id", Integer, ForeignKey("songs.id"), primary_key=True),
#     Column("added_at", DateTime(timezone=True), server_default=func.now()),  # Timestamp when song was added to playlist
# )

def _parse_objectid(v):
    if isinstance(v, ObjectId):
        return v
    if v is None:
        return None
    return ObjectId(str(v))

# Tipo “ObjectId serializable” para Pydantic v2
ObjectIdStr = Annotated[
    ObjectId,
    BeforeValidator(_parse_objectid),
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]


# Helper para manejar ObjectId en Pydantic
class PyObjectId(ObjectId):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class Song(BaseModel):
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    title: str
    artist: str
    duration: str

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class Playlist(BaseModel):
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    name: str
    description: str | None = None
    is_published: bool = True
    published_at: datetime = Field(default_factory=datetime.utcnow)
    cover_image: str
    userId: str

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class PlaylistSong(BaseModel):
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    playlist_id: ObjectIdStr
    song_id: ObjectIdStr
    added_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class CollectionSong(BaseModel):
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    collection_id: ObjectIdStr
    song_id: ObjectIdStr
    order: int
    early_release_date: datetime | None = None  # Fecha de lanzamiento anticipado (None = no anticipado)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class Like(BaseModel):
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    user_id: str
    target_id: ObjectIdStr  # Can be song_id or collection_id
    target_type: str  # 'song' or 'collection'
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class Share(BaseModel):
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    user_id: str
    target_id: ObjectIdStr  # Can be song_id or collection_id
    target_type: str  # 'song' or 'collection'
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class Play(BaseModel):
    """
    Permanent play metrics that are NOT deleted when users clear their history.
    This is separate from the history table which is user-specific and can be cleared.
    """
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    user_id: str
    song_id: ObjectIdStr
    played_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class ArtistAbout(BaseModel):
    """Artist about page with bio, social media, images, and featured pick."""
    id: ObjectIdStr = Field(default_factory=ObjectId, alias="_id")
    artist_id: str  # User ID of the artist
    artist: str  # Stage name
    bio: str | None = None
    social_media: dict | None = None  # {"x": "username", "instagram": "username"}
    carousel_images: list[dict] = []  # [{"url": "...", "isPrimary": bool}], max 5
    artist_pick: dict | None = None  # {"type": "collection/playlist", "id": "..."}

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}