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
    isLiked: Optional[bool] = None

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
    order: int

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

class SongOrder(BaseModel):
    songId: str
    order: int

class ReorderRequest(BaseModel):
    songs: list[SongOrder]

# Activity schemas
class ActivitySongData(BaseModel):
    """Song data within activity entry."""
    _id: str
    title: str
    artist: str
    coverUrl: Optional[str] = None

class ActivityCollectionData(BaseModel):
    """Collection data within activity entry."""
    _id: str
    name: str
    artistName: str
    coverUrl: Optional[str] = None
    type: str

class LikeActivity(BaseModel):
    """Activity entry for a like action."""
    type: str = "like"
    userId: str
    targetId: str
    targetType: str
    timestamp: datetime
    createdAt: datetime
    song: Optional[ActivitySongData] = None
    collection: Optional[ActivityCollectionData] = None

class PlayActivity(BaseModel):
    """Activity entry for a play action."""
    type: str = "play"
    userId: str
    songId: str
    targetType: str = "song"
    timestamp: datetime
    playedAt: datetime
    song: Optional[ActivitySongData] = None

class PlaylistPublishedActivity(BaseModel):
    """Activity entry for a published playlist."""
    type: str = "playlist_published"
    userId: str
    playlistId: str
    playlistName: str
    timestamp: datetime
    publishedAt: datetime

class ShareActivity(BaseModel):
    """Activity entry for a share action."""
    type: str = "share"
    userId: str
    targetId: str
    targetType: str
    timestamp: datetime
    createdAt: datetime
    song: Optional[ActivitySongData] = None
    collection: Optional[ActivityCollectionData] = None

class ActivityResponse(BaseModel):
    """Response containing a list of activities."""
    data: List[dict]  # Union of different activity types
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "type": "like",
                        "userId": "user_123",
                        "targetType": "song",
                        "song": {
                            "_id": "507f1f77bcf86cd799439011",
                            "title": "Bohemian Rhapsody",
                            "artist": "Queen",
                            "coverUrl": "https://example.com/cover.jpg"
                        },
                        "timestamp": "2025-11-10T14:30:00Z"
                    },
                    {
                        "type": "play",
                        "userId": "user_123",
                        "songId": "507f1f77bcf86cd799439012",
                        "song": {
                            "_id": "507f1f77bcf86cd799439012",
                            "title": "Imagine",
                            "artist": "John Lennon",
                            "coverUrl": "https://example.com/imagine.jpg"
                        },
                        "timestamp": "2025-11-10T13:15:00Z"
                    },
                    {
                        "type": "playlist_published",
                        "userId": "user_123",
                        "playlistId": "507f1f77bcf86cd799439013",
                        "playlistName": "My Favorites",
                        "timestamp": "2025-11-09T10:00:00Z"
                    }
                ]
            }
        }

class CollectionSong(SongBase):
    id: str
    order: int
    earlyReleaseDate: Optional[datetime] = None  # Fecha de lanzamiento anticipado
    
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

class SongWithEarlyRelease(BaseModel):
    """Song ID with optional early release date for collections."""
    songId: str
    earlyReleaseDate: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "songId": "507f1f77bcf86cd799439011",
                "earlyReleaseDate": "2025-11-15T00:00:00Z"
            }
        }

class CreateCollectionRequest(BaseModel):
    name: str
    type: CollectionType
    genre: str
    songs: List[SongWithEarlyRelease] = []  # List of songs with optional early release dates
    releaseDate: Optional[datetime] = None
    credits: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Clics Modernos",
                "type": "album",
                "genre": "Rock",
                "songs": [
                    {
                        "songId": "507f1f77bcf86cd799439011",
                        "earlyReleaseDate": "2025-11-15T00:00:00Z"
                    },
                    {
                        "songId": "507f1f77bcf86cd799439012"
                    },
                    {
                        "songId": "507f1f77bcf86cd799439013"
                    }
                ],
                "releaseDate": "2025-12-01T00:00:00Z",
                "credits": ["Charly García", "Pedro Aznar"]
            }
        }

class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[CollectionType] = None
    genre: Optional[str] = None
    coverUrl: Optional[str] = None
    songs: Optional[List[SongWithEarlyRelease]] = None
    credits: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Clics Modernos (Edición Especial)",
                "genre": "Rock Argentino",
                "songs": [
                    {
                        "songId": "507f1f77bcf86cd799439011"
                    },
                    {
                        "songId": "507f1f77bcf86cd799439012",
                        "earlyReleaseDate": "2025-11-20T00:00:00Z"
                    }
                ],
                "credits": ["Charly García", "Pedro Aznar", "Willy Iturri"]
            }
        }

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

# Artist About schemas
class SocialMedia(BaseModel):
    """Social media links for an artist."""
    x: Optional[str] = None  # Twitter/X username or URL
    instagram: Optional[str] = None  # Instagram username or URL

class CarouselImage(BaseModel):
    """Image in artist carousel."""
    id: str  # Unique identifier for the image
    url: str
    isPrimary: bool = False  # Only one can be primary

class ArtistPick(BaseModel):
    """Artist's featured collection or playlist."""
    type: str  # 'collection' or 'playlist'
    id: str

class ArtistAbout(BaseModel):
    """Artist about page information."""
    artistId: str
    artist: str
    bio: Optional[str] = None
    socialMedia: Optional[SocialMedia] = None
    carouselImages: List[CarouselImage] = []  # Max 5 images
    artistPick: Optional[ArtistPick] = None
    
    class Config:
        from_attributes = True

class UpdateArtistAboutRequest(BaseModel):
    """Request to update artist about page (cannot edit artistId or artist)."""
    bio: Optional[str] = None
    socialMedia: Optional[SocialMedia] = None
    carouselImages: Optional[List[CarouselImage]] = None
    artistPick: Optional[ArtistPick] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "bio": "Músico argentino, pionero del rock nacional.",
                "socialMedia": {
                    "x": "@charlygarcia",
                    "instagram": "@charlygarcia_oficial"
                },
                "carouselImages": [
                    {
                        "url": "https://example.com/image1.jpg",
                        "isPrimary": True
                    },
                    {
                        "url": "https://example.com/image2.jpg",
                        "isPrimary": False
                    }
                ],
                "artistPick": {
                    "type": "collection",
                    "id": "507f1f77bcf86cd799439011"
                }
            }
        }


# Response schemas for consistent API documentation

class CollectionResponse(BaseModel):
    """Standard API response wrapper for single collection data."""
    data: Collection


class CollectionsResponse(BaseModel):
    """Standard API response wrapper for multiple collections data."""
    data: List[Collection]


class MessageResponse(BaseModel):
    """Standard API response for simple message responses."""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully"
            }
        }


class SearchResult(BaseModel):
    """Search results containing playlists, songs, and users."""
    playlists: List[Playlist] = []
    songs: List[Song] = []
    users: List[dict] = []  # User schema from external API


class SearchResponse(BaseModel):
    """Standard API response for search endpoint."""
    collections: SearchResult


class LikeStatus(BaseModel):
    """Like status information."""
    isLiked: bool


class LikeStatusResponse(BaseModel):
    """Standard API response for like status check."""
    data: LikeStatus


class Metrics(BaseModel):
    """Metrics data for songs, collections, or artists."""
    totalPlays: Optional[int] = 0
    totalLikes: Optional[int] = 0
    totalShares: Optional[int] = 0
    totalPlaylistSaves: Optional[int] = 0
    popularityScore: Optional[float] = 0.0


class MetricsResponse(BaseModel):
    """Standard API response for metrics data."""
    data: Metrics


class ArtistAboutResponse(BaseModel):
    """Standard API response for artist about page."""
    data: ArtistAbout


class EarlyReleaseSong(BaseModel):
    """Song information with early release date."""
    songId: str
    title: str
    artist: str
    earlyReleaseDate: Optional[datetime] = None
    coverUrl: Optional[str] = None


class EarlyReleaseSongsResponse(BaseModel):
    """Standard API response for early release songs."""
    data: List[EarlyReleaseSong]


class CoverUrlResponse(BaseModel):
    """Standard API response for cover URL upload."""
    coverUrl: str


class EarlyReleaseSongItem(BaseModel):
    """Early release song item for collection early releases endpoint."""
    id: str
    title: str
    artist: str
    duration: str
    order: int
    earlyReleaseDate: Optional[datetime] = None


class EarlyReleaseData(BaseModel):
    """Data for early release songs of a collection."""
    collectionId: str
    collectionName: str
    releaseDate: Optional[datetime] = None
    earlyReleasedSongs: List[EarlyReleaseSongItem]


class EarlyReleaseResponse(BaseModel):
    """Standard API response for collection early releases."""
    data: EarlyReleaseData


class LikedResponse(BaseModel):
    """Response for check like status endpoint."""
    liked: bool


class CarouselImageResponse(BaseModel):
    """Response for carousel image upload."""
    id: str
    url: str
    isPrimary: bool

