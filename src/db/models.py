from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base

# Association table for many-to-many relationship between playlists and songs
# This table tracks when each song was added to each playlist
# playlist_songs = Table(
#     "playlist_songs",
#     Base.metadata,
#     Column("playlist_id", Integer, ForeignKey("playlists.id"), primary_key=True),
#     Column("song_id", Integer, ForeignKey("songs.id"), primary_key=True),
#     Column("added_at", DateTime(timezone=True), server_default=func.now()),  # Timestamp when song was added to playlist
# )

class PlaylistSong(Base):
    __tablename__ = "playlist_songs"

    playlist_id = Column(Integer, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    playlist = relationship("Playlist", back_populates="playlist_songs")
    song = relationship("Song", back_populates="playlist_songs")


class Song(Base):
    """
    SQLAlchemy model representing a song in the music database.
    
    A song represents a musical track with a title and artist. Songs can be
    added to multiple playlists through the many-to-many relationship.
    """
    __tablename__ = "songs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=False)

    # playlists = relationship(
    #     "Playlist", secondary=playlist_songs, back_populates="songs"
    # )
    playlist_songs = relationship("PlaylistSong", back_populates="song", passive_deletes=True)



class Playlist(Base):
    """
    SQLAlchemy model representing a music playlist.
    
    A playlist is a collection of songs that can be published or kept private.
    It contains metadata about when it was created/published and maintains
    a many-to-many relationship with songs.
    """
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    is_published = Column(Boolean, default=True, nullable=False)
    published_at = Column(DateTime(timezone=True), server_default=func.now())

    # songs = relationship("Song", secondary=playlist_songs, back_populates="playlists")
    playlist_songs = relationship("PlaylistSong", back_populates="playlist", cascade="all, delete-orphan", passive_deletes=True)
