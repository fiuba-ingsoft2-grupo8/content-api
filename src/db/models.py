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