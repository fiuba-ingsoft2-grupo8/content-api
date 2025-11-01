from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile, File
from enum import Enum


class CollectionType(str, Enum):
    ALBUM = "album"
    SINGLE = "single"
    EP = "ep"

class SongBase(BaseModel):
    """
    Base Pydantic model for song data with common fields.
    
    This base class contains the core attributes that all song-related
    schemas share, promoting code reuse and consistency.
    """
    title: str
    artist: str
    duration: str


class CreateSongRequest(BaseModel):
    """
    Request schema for creating a new song.
    
    Artist is derived from the user's stage_name in the authentication token,
    so it's not included in the request body.
    """
    title: str
    duration: str

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
    coverUrl: Optional[str] = None
    isLikedSongs: Optional[bool] = False


class CreatePlaylistRequest(BaseModel):
    name: str
    description: str
    coverUrl: Optional[str] = None
    isLikedSongs: Optional[bool] = False
    


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

class PlaylistImageRequest(BaseModel):
    file: UploadFile = File(...) 


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
    songId: str
    userId: str
    playedAt: datetime
    progress: int

class ListeningHistoryRequest(BaseModel):
    songId: str
    progress: Optional[int] = 0

class CollectionSong(SongBase):
    id: str
    order: int
    
    class Config:
        from_attributes = True

class CollectionBase(BaseModel):
    """
    Base Pydantic model for playlist data with common fields.
    
    This base class contains the core attributes that all collecttion-related
    schemas share, promoting code reuse and consistency.
    """
    id: str
    name: str
    artistId: str
    artistName: str
    type: CollectionType
    genre: str
    coverUrl: str
    createdAt: datetime
    releaseDate: Optional[datetime] = None
    credits: Optional[List[str]] = None

class Collection(CollectionBase):
    """
    Complete playlist representation with all metadata and songs.
    
    Extends PlaylistBase with database ID, publication status, timestamps,
    and the list of songs in the playlist. Used for API responses when
    returning complete playlist data.
    """
    songs: List[CollectionSong] = []
    # Optional popularity metrics (only present in popular collections endpoint)
    totalPlays: Optional[int] = None
    totalLikes: Optional[int] = None
    totalPlaylistSaves: Optional[int] = None
    totalShares: Optional[int] = None
    popularityScore: Optional[float] = None

    class Config:
        from_attributes = True

class CreateCollectionRequest(BaseModel):
    name: str
    type: CollectionType
    genre: str
    songIds: List[str]
    releaseDate: Optional[datetime] = None
    credits: Optional[List[str]] = None

class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[CollectionType] = None
    genre: Optional[str] = None
    coverUrl: Optional[str] = None
    songIds: Optional[List[str]] = None
    credits: Optional[List[str]] = None

# Metrics schemas
class SongMetrics(BaseModel):
    """Metrics for a single song."""
    songId: str
    plays: int
    likes: int
    shares: int

class CollectionMetrics(BaseModel):
    """
    Metrics for a collection (album/EP/single).
    Note: likes = sum of likes from all songs in the collection.
    """
    collectionId: str
    totalPlays: int
    likes: int  # Sum of likes from all songs
    shares: int

class PeriodMetrics(BaseModel):
    """Metrics for a specific period with comparison to previous period."""
    value: int
    delta: int
    percentChange: float

class ArtistMetrics(BaseModel):
    """Overall metrics for an artist."""
    artistId: str
    monthlyListeners: PeriodMetrics
    plays: PeriodMetrics
    saves: PeriodMetrics
    shares: PeriodMetrics

class LikeRequest(BaseModel):
    """Request to like/unlike a song or collection."""
    targetId: str
    targetType: str  # 'song' or 'collection'

class ShareRequest(BaseModel):
    """Request to record a share."""
    targetId: str
    targetType: str  # 'song' or 'collection'

