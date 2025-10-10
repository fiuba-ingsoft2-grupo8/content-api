from pydantic import BaseModel
from typing import List
from datetime import datetime


class SongBase(BaseModel):
    """
    Base Pydantic model for song data with common fields.
    
    This base class contains the core attributes that all song-related
    schemas share, promoting code reuse and consistency.
    """
    title: str
    artist: str


class CreateSongRequest(SongBase):
    """
    Request schema for creating a new song.
    
    Inherits title and artist from SongBase. Used for POST /songs endpoint
    to validate incoming song creation requests.
    """
    pass


class UpdateSongRequest(SongBase):
    """
    Request schema for updating an existing song.
    
    Inherits title and artist from SongBase. Used for PUT /songs/{id} endpoint
    to validate incoming song update requests.
    """
    pass


class Song(SongBase):
    """
    Complete song representation with database ID.
    
    Extends SongBase with the database ID field. Used for API responses
    when returning song data from the database.
    """
    _id: str

    class Config:
        from_attributes = True


class PlaylistSong(SongBase):
    """
    Song representation within a playlist context.
    
    Extends SongBase with additional metadata specific to songs within playlists,
    including when the song was added to the playlist.
    """
    id: str
    addedAt: datetime

    class Config:
        from_attributes = True


class PlaylistBase(BaseModel):
    """
    Base Pydantic model for playlist data with common fields.
    
    This base class contains the core attributes that all playlist-related
    schemas share, promoting code reuse and consistency.
    """
    name: str
    description: str
    userId: str


class CreatePlaylistRequest(PlaylistBase):
    """
    Request schema for creating a new playlist.
    
    Inherits name and description from PlaylistBase. Used for POST /playlists
    endpoint to validate incoming playlist creation requests.
    """
    pass


class Playlist(PlaylistBase):
    """
    Complete playlist representation with all metadata and songs.
    
    Extends PlaylistBase with database ID, publication status, timestamps,
    and the list of songs in the playlist. Used for API responses when
    returning complete playlist data.
    """
    id: str
    isPublished: bool
    publishedAt: datetime
    songs: List[PlaylistSong] = []

    class Config:
        from_attributes = True


class ModifySongInPlaylistRequest(BaseModel):
    """
    Request schema for adding a song to an existing playlist.
    
    Used for POST /playlists/{id}/songs endpoint to validate the request
    to add a specific song to a playlist.
    """
    songId: str
    userId: str

class ModifyPlaylistRequest(BaseModel):
    """
    Request schema for modifying or deleting a playlist.
    
    Used for POST /playlists/{id}/publish, /playlists/{id}/private, or
    DELETE /playlists/{id} endpoint.
    """
    userId: str


class SongResponse(BaseModel):
    """
    Standard API response wrapper for single song data.
    
    Provides consistent response format for endpoints returning a single song.
    """
    data: Song


class SongsResponse(BaseModel):
    """
    Standard API response wrapper for multiple songs data.
    
    Provides consistent response format for endpoints returning a list of songs.
    """
    data: List[Song]


class PlaylistResponse(BaseModel):
    """
    Standard API response wrapper for single playlist data.
    
    Provides consistent response format for endpoints returning a single playlist
    with all its songs and metadata.
    """
    data: Playlist


class PlaylistsResponse(BaseModel):
    """
    Standard API response wrapper for multiple playlists data.
    
    Provides consistent response format for endpoints returning a list of playlists.
    """
    data: List[Playlist]


class ErrorResponse(BaseModel):
    """
    Standard API error response format following RFC 7807 Problem Details.
    
    Provides consistent error response structure across all API endpoints,
    making it easier for clients to handle and display error information.
    """
    type: str
    title: str
    status: int
    detail: str
    instance: str

class ListeningHistory(BaseModel):
    # to do - documentar
    songId: str
    userId: str
    playedAt: datetime

class ListeningHistoryRequest(BaseModel):
    # to do - documentar
    songId: str
    userId: str