import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from bson import ObjectId
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from databases.activity_database import (
    get_user_activity,
    get_following_activity,
    enrich_activity_with_details
)


class TestGetUserActivity:
    """Test suite for get_user_activity function."""

    @pytest.mark.asyncio
    async def test_get_user_activity_no_activities(self, mock_db):
        """Test getting activity for a user with no activities."""
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity("user_123")
            
            assert isinstance(activities, list)
            assert len(activities) == 0

    @pytest.mark.asyncio
    async def test_get_user_activity_with_likes(self, mock_db):
        """Test getting activity for a user with likes."""
        # Insert test likes
        user_id = "user_123"
        song_id = ObjectId()
        collection_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.likes.insert_many([
            {
                "user_id": user_id,
                "target_id": song_id,
                "target_type": "song",
                "created_at": now - timedelta(hours=1)
            },
            {
                "user_id": user_id,
                "target_id": collection_id,
                "target_type": "collection",
                "created_at": now - timedelta(hours=2)
            }
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id)
            
            assert len(activities) == 2
            
            # Check first activity (most recent)
            assert activities[0]["type"] == "like"
            assert activities[0]["userId"] == user_id
            assert activities[0]["targetType"] == "song"
            assert activities[0]["targetId"] == str(song_id)
            
            # Check second activity
            assert activities[1]["type"] == "like"
            assert activities[1]["targetType"] == "collection"

    @pytest.mark.asyncio
    async def test_get_user_activity_with_plays(self, mock_db):
        """Test getting activity for a user with song plays."""
        user_id = "user_456"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.plays.insert_many([
            {
                "user_id": user_id,
                "song_id": song_id,
                "played_at": now - timedelta(minutes=30)
            },
            {
                "user_id": user_id,
                "song_id": song_id,
                "played_at": now - timedelta(hours=1)
            }
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id)
            
            assert len(activities) == 2
            
            for activity in activities:
                assert activity["type"] == "play"
                assert activity["userId"] == user_id
                assert activity["songId"] == str(song_id)
                assert activity["targetType"] == "song"
                assert "playedAt" in activity

    @pytest.mark.asyncio
    async def test_get_user_activity_with_published_playlists(self, mock_db):
        """Test getting activity for a user with published playlists."""
        user_id = "user_789"
        playlist_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.playlists.insert_one({
            "_id": playlist_id,
            "userId": user_id,
            "name": "My Awesome Playlist",
            "is_published": True,
            "published_at": now - timedelta(days=1)
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id)
            
            assert len(activities) == 1
            
            activity = activities[0]
            assert activity["type"] == "playlist_published"
            assert activity["userId"] == user_id
            assert activity["playlistId"] == str(playlist_id)
            assert activity["playlistName"] == "My Awesome Playlist"
            assert "publishedAt" in activity

    @pytest.mark.asyncio
    async def test_get_user_activity_with_shares(self, mock_db):
        """Test getting activity for a user with shares (viewing own activity)."""
        user_id = "user_share"
        target_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.shares.insert_many([
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "song",
                "created_at": now - timedelta(hours=2)
            },
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "playlist",
                "recipient_id": "recipient_123",
                "created_at": now - timedelta(hours=3)
            }
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            # When viewing own activity, should see all shares
            activities = await get_user_activity(user_id, requesting_user_id=user_id)
            
            assert len(activities) == 2
            
            # Check first share
            assert activities[0]["type"] == "share"
            assert activities[0]["userId"] == user_id
            assert activities[0]["targetType"] == "song"
            assert "recipientId" not in activities[0]
            
            # Check second share with recipient
            assert activities[1]["type"] == "share"
            assert activities[1]["targetType"] == "playlist"
            assert activities[1]["recipientId"] == "recipient_123"

    @pytest.mark.asyncio
    async def test_get_user_activity_shares_privacy_filter(self, mock_db):
        """Test that shares are filtered when viewing another user's activity."""
        user_id = "user_with_shares"
        requesting_user_id = "requesting_user"
        other_user_id = "other_user"
        target_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # User has shared to multiple recipients
        mock_db.shares.insert_many([
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "song",
                "recipient_id": requesting_user_id,  # Share to requesting user
                "created_at": now - timedelta(hours=1)
            },
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "playlist",
                "recipient_id": other_user_id,  # Share to someone else
                "created_at": now - timedelta(hours=2)
            },
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "collection",
                "recipient_id": requesting_user_id,  # Another share to requesting user
                "created_at": now - timedelta(hours=3)
            }
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            # When requesting user views another user's activity, 
            # should only see shares made to them
            activities = await get_user_activity(user_id, requesting_user_id=requesting_user_id)
            
            assert len(activities) == 2  # Only 2 shares to requesting_user_id
            
            # All returned shares should have requesting_user_id as recipient
            for activity in activities:
                assert activity["type"] == "share"
                assert activity["userId"] == user_id
                assert activity["recipientId"] == requesting_user_id
    
    @pytest.mark.asyncio
    async def test_get_user_activity_shares_no_matching_recipient(self, mock_db):
        """Test viewing another user's activity when no shares were made to you."""
        user_id = "user_with_shares"
        requesting_user_id = "requesting_user"
        other_user_id = "other_user"
        target_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # User has only shared to other users, not to requesting user
        mock_db.shares.insert_many([
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "song",
                "recipient_id": other_user_id,
                "created_at": now - timedelta(hours=1)
            },
            {
                "user_id": user_id,
                "target_id": target_id,
                "target_type": "playlist",
                "recipient_id": "another_user",
                "created_at": now - timedelta(hours=2)
            }
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            # When requesting user views another user's activity,
            # should not see any shares
            activities = await get_user_activity(user_id, requesting_user_id=requesting_user_id)
            
            assert len(activities) == 0

    @pytest.mark.asyncio
    async def test_get_user_activity_mixed_types(self, mock_db):
        """Test getting activity with mixed activity types."""
        user_id = "mixed_user"
        song_id = ObjectId()
        playlist_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # Insert various activities
        mock_db.likes.insert_one({
            "user_id": user_id,
            "target_id": song_id,
            "target_type": "song",
            "created_at": now - timedelta(hours=1)
        })
        
        mock_db.plays.insert_one({
            "user_id": user_id,
            "song_id": song_id,
            "played_at": now - timedelta(hours=2)
        })
        
        mock_db.playlists.insert_one({
            "_id": playlist_id,
            "userId": user_id,
            "name": "Test Playlist",
            "is_published": True,
            "published_at": now - timedelta(hours=3)
        })
        
        mock_db.shares.insert_one({
            "user_id": user_id,
            "target_id": song_id,
            "target_type": "song",
            "created_at": now - timedelta(hours=4)
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            # Viewing own activity - should see all activities including shares
            activities = await get_user_activity(user_id, requesting_user_id=user_id)
            
            assert len(activities) == 4
            
            # Should be sorted by timestamp (most recent first)
            types = [a["type"] for a in activities]
            assert "like" in types
            assert "play" in types
            assert "playlist_published" in types
            assert "share" in types
            
            # Verify chronological order
            timestamps = [a["timestamp"] for a in activities]
            for i in range(len(timestamps) - 1):
                assert timestamps[i] >= timestamps[i + 1]

    @pytest.mark.asyncio
    async def test_get_user_activity_respects_limit(self, mock_db):
        """Test that the limit parameter works correctly."""
        user_id = "limit_user"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # Insert 20 likes
        likes = []
        for i in range(20):
            likes.append({
                "user_id": user_id,
                "target_id": song_id,
                "target_type": "song",
                "created_at": now - timedelta(minutes=i)
            })
        
        mock_db.likes.insert_many(likes)
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            # Test default limit (50)
            activities = await get_user_activity(user_id)
            assert len(activities) == 20  # All 20 activities
            
            # Test custom limit
            activities = await get_user_activity(user_id, limit=10)
            assert len(activities) == 10

    @pytest.mark.asyncio
    async def test_get_user_activity_filter_by_type_like(self, mock_db):
        """Test filtering activities by type: like."""
        user_id = "filter_user"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # Insert multiple activity types
        mock_db.likes.insert_one({
            "user_id": user_id,
            "target_id": song_id,
            "target_type": "song",
            "created_at": now
        })
        
        mock_db.plays.insert_one({
            "user_id": user_id,
            "song_id": song_id,
            "played_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id, activity_type="like")
            
            assert len(activities) == 1
            assert all(a["type"] == "like" for a in activities)

    @pytest.mark.asyncio
    async def test_get_user_activity_filter_by_type_play(self, mock_db):
        """Test filtering activities by type: play."""
        user_id = "filter_user"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.likes.insert_one({
            "user_id": user_id,
            "target_id": song_id,
            "target_type": "song",
            "created_at": now
        })
        
        mock_db.plays.insert_many([
            {"user_id": user_id, "song_id": song_id, "played_at": now},
            {"user_id": user_id, "song_id": song_id, "played_at": now - timedelta(hours=1)}
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id, activity_type="play")
            
            assert len(activities) == 2
            assert all(a["type"] == "play" for a in activities)

    @pytest.mark.asyncio
    async def test_get_user_activity_filter_by_type_playlist_published(self, mock_db):
        """Test filtering activities by type: playlist_published."""
        user_id = "filter_user"
        playlist_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.playlists.insert_one({
            "_id": playlist_id,
            "userId": user_id,
            "name": "Published Playlist",
            "is_published": True,
            "published_at": now
        })
        
        mock_db.likes.insert_one({
            "user_id": user_id,
            "target_id": ObjectId(),
            "target_type": "song",
            "created_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id, activity_type="playlist_published")
            
            assert len(activities) == 1
            assert all(a["type"] == "playlist_published" for a in activities)

    @pytest.mark.asyncio
    async def test_get_user_activity_filter_by_type_share(self, mock_db):
        """Test filtering activities by type: share."""
        user_id = "filter_user"
        target_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_db.shares.insert_one({
            "user_id": user_id,
            "target_id": target_id,
            "target_type": "song",
            "created_at": now
        })
        
        mock_db.likes.insert_one({
            "user_id": user_id,
            "target_id": target_id,
            "target_type": "song",
            "created_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            # Viewing own activity with filter
            activities = await get_user_activity(user_id, activity_type="share", requesting_user_id=user_id)
            
            assert len(activities) == 1
            assert all(a["type"] == "share" for a in activities)

    @pytest.mark.asyncio
    async def test_get_user_activity_unpublished_playlists_excluded(self, mock_db):
        """Test that unpublished playlists are not included in activity."""
        user_id = "user_unpub"
        playlist_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # Insert unpublished playlist
        mock_db.playlists.insert_one({
            "_id": playlist_id,
            "userId": user_id,
            "name": "Unpublished Playlist",
            "is_published": False,
            "created_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id)
            
            # Should not include unpublished playlist
            playlist_activities = [a for a in activities if a["type"] == "playlist_published"]
            assert len(playlist_activities) == 0

    @pytest.mark.asyncio
    async def test_get_user_activity_handles_exception(self, mock_db):
        """Test that exceptions are handled gracefully."""
        user_id = "error_user"
        
        # Mock the database to raise an exception
        def raise_exception(*args, **kwargs):
            raise Exception("Database error")
        
        mock_db.likes.find = raise_exception
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_user_activity(user_id)
            
            # Should return empty list on error
            assert activities == []


class TestGetFollowingActivity:
    """Test suite for get_following_activity function."""

    @pytest.mark.asyncio
    async def test_get_following_activity_no_following(self, mock_db):
        """Test getting following activity when user follows no one."""
        user_id = "lonely_user"
        
        # Mock the httpx client to return empty following list
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"following": []}
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                assert isinstance(activities, list)
                assert len(activities) == 0

    @pytest.mark.asyncio
    async def test_get_following_activity_with_test_token(self, mock_db):
        """Test that test tokens skip the external API call."""
        user_id = "test_user"
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            activities = await get_following_activity(user_id, "test_token")
            
            # Should return empty list without making API call
            assert activities == []

    @pytest.mark.asyncio
    async def test_get_following_activity_with_likes(self, mock_db):
        """Test getting following activity with likes from followed users."""
        user_id = "follower_user"
        following_user_id = "followed_user_123"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        # Mock following list from external API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        # Insert like from followed user
        mock_db.likes.insert_one({
            "user_id": following_user_id,
            "target_id": song_id,
            "target_type": "song",
            "created_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                assert len(activities) >= 1
                assert activities[0]["type"] == "like"
                assert activities[0]["userId"] == following_user_id

    @pytest.mark.asyncio
    async def test_get_following_activity_with_plays(self, mock_db):
        """Test getting following activity with plays from followed users."""
        user_id = "follower_user"
        following_user_id = "followed_user_456"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        mock_db.plays.insert_one({
            "user_id": following_user_id,
            "song_id": song_id,
            "played_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                assert len(activities) >= 1
                play_activities = [a for a in activities if a["type"] == "play"]
                assert len(play_activities) >= 1

    @pytest.mark.asyncio
    async def test_get_following_activity_with_published_playlists(self, mock_db):
        """Test getting following activity with published playlists from followed users."""
        user_id = "follower_user"
        following_user_id = "followed_user_789"
        playlist_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        mock_db.playlists.insert_one({
            "_id": playlist_id,
            "userId": following_user_id,
            "name": "Followed Playlist",
            "is_published": True,
            "published_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                assert len(activities) >= 1
                playlist_activities = [a for a in activities if a["type"] == "playlist_published"]
                assert len(playlist_activities) >= 1

    @pytest.mark.asyncio
    async def test_get_following_activity_with_shares(self, mock_db):
        """Test getting following activity with shares from followed users."""
        user_id = "follower_user"
        following_user_id = "followed_share"
        target_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        mock_db.shares.insert_one({
            "user_id": following_user_id,
            "target_id": target_id,
            "target_type": "song",
            "created_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                assert len(activities) >= 1
                share_activities = [a for a in activities if a["type"] == "share"]
                assert len(share_activities) >= 1

    @pytest.mark.asyncio
    async def test_get_following_activity_multiple_followed_users(self, mock_db):
        """Test getting following activity from multiple followed users."""
        user_id = "follower_user"
        following_users = ["followed_1", "followed_2", "followed_3"]
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": uid} for uid in following_users]
        }
        
        # Insert activities from different followed users
        for i, followed_id in enumerate(following_users):
            mock_db.likes.insert_one({
                "user_id": followed_id,
                "target_id": ObjectId(),
                "target_type": "song",
                "created_at": now - timedelta(hours=i)
            })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                assert len(activities) >= 3
                user_ids = set([a["userId"] for a in activities])
                assert len(user_ids) == 3

    @pytest.mark.asyncio
    async def test_get_following_activity_respects_limit(self, mock_db):
        """Test that the limit parameter works correctly."""
        user_id = "follower_user"
        following_user_id = "followed_user"
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        # Insert many activities
        likes = []
        for i in range(100):
            likes.append({
                "user_id": following_user_id,
                "target_id": ObjectId(),
                "target_type": "song",
                "created_at": now - timedelta(minutes=i)
            })
        
        mock_db.likes.insert_many(likes)
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                # Test with limit
                activities = await get_following_activity(user_id, "Bearer token_123", limit=10)
                
                assert len(activities) == 10

    @pytest.mark.asyncio
    async def test_get_following_activity_filter_by_type(self, mock_db):
        """Test filtering following activity by type."""
        user_id = "follower_user"
        following_user_id = "followed_user"
        song_id = ObjectId()
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        # Insert different activity types
        mock_db.likes.insert_one({
            "user_id": following_user_id,
            "target_id": song_id,
            "target_type": "song",
            "created_at": now
        })
        
        mock_db.plays.insert_one({
            "user_id": following_user_id,
            "song_id": song_id,
            "played_at": now
        })
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                # Filter by likes only
                activities = await get_following_activity(
                    user_id, "Bearer token_123", activity_type="like"
                )
                
                assert all(a["type"] == "like" for a in activities)

    @pytest.mark.asyncio
    async def test_get_following_activity_api_error(self, mock_db):
        """Test handling of API errors when fetching following list."""
        user_id = "follower_user"
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                # Should return empty list on API error
                assert activities == []

    @pytest.mark.asyncio
    async def test_get_following_activity_api_timeout(self, mock_db):
        """Test handling of API timeout when fetching following list."""
        user_id = "follower_user"
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    side_effect=Exception("Timeout")
                )
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                # Should return empty list on timeout
                assert activities == []

    @pytest.mark.asyncio
    async def test_get_following_activity_chronological_order(self, mock_db):
        """Test that following activities are sorted chronologically."""
        user_id = "follower_user"
        following_user_id = "followed_user"
        
        now = datetime.now(timezone.utc)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "following": [{"id": following_user_id}]
        }
        
        # Insert activities at different times
        mock_db.likes.insert_many([
            {
                "user_id": following_user_id,
                "target_id": ObjectId(),
                "target_type": "song",
                "created_at": now - timedelta(hours=3)
            },
            {
                "user_id": following_user_id,
                "target_id": ObjectId(),
                "target_type": "song",
                "created_at": now - timedelta(hours=1)
            },
            {
                "user_id": following_user_id,
                "target_id": ObjectId(),
                "target_type": "song",
                "created_at": now - timedelta(hours=2)
            }
        ])
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                
                activities = await get_following_activity(user_id, "Bearer token_123")
                
                # Verify chronological order (most recent first)
                timestamps = [a["timestamp"] for a in activities]
                for i in range(len(timestamps) - 1):
                    assert timestamps[i] >= timestamps[i + 1]


class TestEnrichActivityWithDetails:
    """Test suite for enrich_activity_with_details function."""

    @pytest.mark.asyncio
    async def test_enrich_like_activity_with_song(self, mock_db):
        """Test enriching like activity with song details."""
        song_id = ObjectId()
        
        # Insert song
        mock_db.songs.insert_one({
            "_id": song_id,
            "title": "Test Song",
            "artist": "Test Artist",
            "coverUrl": "http://example.com/cover.jpg"
        })
        
        activities = [
            {
                "type": "like",
                "userId": "user_123",
                "targetId": str(song_id),
                "targetType": "song",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 1
            assert "song" in enriched[0]
            assert enriched[0]["song"]["title"] == "Test Song"
            assert enriched[0]["song"]["artist"] == "Test Artist"
            assert enriched[0]["song"]["coverUrl"] == "http://example.com/cover.jpg"

    @pytest.mark.asyncio
    async def test_enrich_like_activity_with_collection(self, mock_db):
        """Test enriching like activity with collection details."""
        collection_id = ObjectId()
        
        # Insert collection
        mock_db.collections.insert_one({
            "_id": collection_id,
            "name": "Test Album",
            "artistName": "Test Artist",
            "coverUrl": "http://example.com/album.jpg",
            "type": "album"
        })
        
        activities = [
            {
                "type": "like",
                "userId": "user_123",
                "targetId": str(collection_id),
                "targetType": "collection",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 1
            assert "collection" in enriched[0]
            assert enriched[0]["collection"]["name"] == "Test Album"
            assert enriched[0]["collection"]["artistName"] == "Test Artist"
            assert enriched[0]["collection"]["type"] == "album"

    @pytest.mark.asyncio
    async def test_enrich_play_activity_with_song(self, mock_db):
        """Test enriching play activity with song details."""
        song_id = ObjectId()
        
        mock_db.songs.insert_one({
            "_id": song_id,
            "title": "Played Song",
            "artist": "Song Artist",
            "coverUrl": "http://example.com/played.jpg"
        })
        
        activities = [
            {
                "type": "play",
                "userId": "user_456",
                "songId": str(song_id),
                "targetType": "song",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 1
            assert "song" in enriched[0]
            assert enriched[0]["song"]["title"] == "Played Song"
            assert enriched[0]["song"]["artist"] == "Song Artist"

    @pytest.mark.asyncio
    async def test_enrich_share_activity_with_song(self, mock_db):
        """Test enriching share activity with song details."""
        song_id = ObjectId()
        
        mock_db.songs.insert_one({
            "_id": song_id,
            "title": "Shared Song",
            "artist": "Share Artist",
            "coverUrl": "http://example.com/shared.jpg"
        })
        
        activities = [
            {
                "type": "share",
                "userId": "user_789",
                "targetId": str(song_id),
                "targetType": "song",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 1
            assert "song" in enriched[0]
            assert enriched[0]["song"]["title"] == "Shared Song"

    @pytest.mark.asyncio
    async def test_enrich_share_activity_with_collection(self, mock_db):
        """Test enriching share activity with collection details."""
        collection_id = ObjectId()
        
        mock_db.collections.insert_one({
            "_id": collection_id,
            "name": "Shared Collection",
            "artistName": "Collection Artist",
            "coverUrl": "http://example.com/collection.jpg",
            "type": "album"
        })
        
        activities = [
            {
                "type": "share",
                "userId": "user_789",
                "targetId": str(collection_id),
                "targetType": "collection",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 1
            assert "collection" in enriched[0]
            assert enriched[0]["collection"]["name"] == "Shared Collection"

    @pytest.mark.asyncio
    async def test_enrich_share_activity_with_playlist(self, mock_db):
        """Test enriching share activity with playlist details."""
        playlist_id = ObjectId()
        
        mock_db.playlists.insert_one({
            "_id": playlist_id,
            "name": "Shared Playlist",
            "description": "A shared playlist",
            "coverUrl": "http://example.com/playlist.jpg"
        })
        
        activities = [
            {
                "type": "share",
                "userId": "user_789",
                "targetId": str(playlist_id),
                "targetType": "playlist",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 1
            assert "playlist" in enriched[0]
            assert enriched[0]["playlist"]["name"] == "Shared Playlist"
            assert enriched[0]["playlist"]["description"] == "A shared playlist"

    @pytest.mark.asyncio
    async def test_enrich_multiple_activities(self, mock_db):
        """Test enriching multiple activities at once."""
        song_id = ObjectId()
        collection_id = ObjectId()
        
        mock_db.songs.insert_one({
            "_id": song_id,
            "title": "Song 1",
            "artist": "Artist 1",
            "coverUrl": "http://example.com/song1.jpg"
        })
        
        mock_db.collections.insert_one({
            "_id": collection_id,
            "name": "Collection 1",
            "artistName": "Artist 2",
            "coverUrl": "http://example.com/collection1.jpg",
            "type": "album"
        })
        
        activities = [
            {
                "type": "like",
                "userId": "user_1",
                "targetId": str(song_id),
                "targetType": "song",
                "timestamp": datetime.now(timezone.utc)
            },
            {
                "type": "like",
                "userId": "user_2",
                "targetId": str(collection_id),
                "targetType": "collection",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            assert len(enriched) == 2
            assert "song" in enriched[0]
            assert "collection" in enriched[1]

    @pytest.mark.asyncio
    async def test_enrich_activity_missing_target(self, mock_db):
        """Test enriching activity when target doesn't exist."""
        activities = [
            {
                "type": "like",
                "userId": "user_123",
                "targetId": str(ObjectId()),  # Non-existent ID
                "targetType": "song",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            # Should still return the activity, just without enrichment
            assert len(enriched) == 1
            assert "song" not in enriched[0]
            assert enriched[0]["type"] == "like"

    @pytest.mark.asyncio
    async def test_enrich_activity_handles_exception(self, mock_db):
        """Test that exceptions during enrichment are handled gracefully."""
        song_id = ObjectId()
        
        activities = [
            {
                "type": "like",
                "userId": "user_123",
                "targetId": str(song_id),
                "targetType": "song",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        # Mock the database to raise an exception
        def raise_exception(*args, **kwargs):
            raise Exception("Database error")
        
        mock_db.songs.find_one = raise_exception
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            # Should return original activities on error
            assert len(enriched) == len(activities)
            assert enriched == activities

    @pytest.mark.asyncio
    async def test_enrich_playlist_published_activity(self, mock_db):
        """Test that playlist_published activities are returned unchanged."""
        activities = [
            {
                "type": "playlist_published",
                "userId": "user_123",
                "playlistId": str(ObjectId()),
                "playlistName": "My Playlist",
                "timestamp": datetime.now(timezone.utc)
            }
        ]
        
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details(activities)
            
            # Should return as-is (playlist_published doesn't need enrichment)
            assert len(enriched) == 1
            assert enriched[0]["type"] == "playlist_published"
            assert enriched[0]["playlistName"] == "My Playlist"

    @pytest.mark.asyncio
    async def test_enrich_empty_activities_list(self, mock_db):
        """Test enriching an empty activities list."""
        with patch("databases.activity_database.get_db", return_value=mock_db):
            enriched = await enrich_activity_with_details([])
            
            assert enriched == []

