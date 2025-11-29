from datetime import datetime, timezone, timedelta
import os
import httpx
from typing import List, Dict, Any, Optional
from resources.logger import logger
from pymongo import DESCENDING
from db.database import get_db
from db.models import CollectionSong
from bson import ObjectId
from databases.collection_states import calculate_effective_state, should_auto_activate
from databases.audit_database import log_collection_change
from enum import Enum as PyEnum

USER_API_BASE = os.getenv("USER_API_BASE", "http://host.docker.internal:8081")

def normalize_base(base: Optional[str], default: str) -> str:
    base = (base or "").strip()
    if not base:
        base = default
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base.rstrip("/")

async def create_collection(name, artistId, artistName, type, genre, coverUrl, releaseDate=None, credits=None, songs_with_early_release=None, available_countries=None, no_disponible_desde=None, no_disponible_hasta=None, user_id=None):
    """
    Create a collection with songs.
    
    Args:
        songs_with_early_release: List of dicts with 'songId' and optional 'earlyReleaseDate'
        available_countries: List of country codes where collection is available
        no_disponible_desde: Start of no-disponible window (optional)
        no_disponible_hasta: End of no-disponible window (optional)
        user_id: ID of the user creating the collection (for audit logging)
    """
    db = get_db()
    try:
        # Ensure timezone-aware datetimes
        if releaseDate and releaseDate.tzinfo is None:
            releaseDate = releaseDate.replace(tzinfo=timezone.utc)
        if no_disponible_desde and no_disponible_desde.tzinfo is None:
            no_disponible_desde = no_disponible_desde.replace(tzinfo=timezone.utc)
        if no_disponible_hasta and no_disponible_hasta.tzinfo is None:
            no_disponible_hasta = no_disponible_hasta.replace(tzinfo=timezone.utc)
        
        # Validate window if both dates provided
        if no_disponible_desde and no_disponible_hasta:
            if no_disponible_desde >= no_disponible_hasta:
                return (None, ValueError("noDisponibleDesde must be before noDisponibleHasta"))
        
        collection_doc = {
            "name": name,
            "artistId": artistId,
            "artistName": artistName,
            "type": type,
            "genre": genre,
            "coverUrl": coverUrl,
            "createdAt": datetime.now(timezone.utc),
            "releaseDate": releaseDate if releaseDate else datetime.now(timezone.utc),
            "credits": credits if credits else [],
            "availableCountries": available_countries if available_countries else [],
            "bloqueadoAdmin": False,  # Default: not blocked
        }
        
        # Add no-disponible window if provided
        if no_disponible_desde:
            collection_doc["noDisponibleDesde"] = no_disponible_desde
        if no_disponible_hasta:
            collection_doc["noDisponibleHasta"] = no_disponible_hasta
        
        result = db.collections.insert_one(collection_doc)
        logger.info(f"Successfully created collection: title={name}, artist={artistName}, type={type}, genre={genre}, id={result.inserted_id}, releaseDate={releaseDate}")

        # Add songs to collection with early release support
        order = 0
        if songs_with_early_release:
            for song_info in songs_with_early_release:
                song_id = song_info.get('songId')
                early_date = song_info.get('earlyReleaseDate')
                if not await add_song_to_collection(song_id, result.inserted_id, order, early_date):
                    logger.error(f"Failed to add song {song_id} to collection")
                order += 1
                
        collection = db.collections.find_one({"_id": result.inserted_id})
        
        # Log creation to audit if user_id provided
        if user_id and collection:
            from databases.collection_states import calculate_effective_state
            effective_state = calculate_effective_state(collection)
            await log_collection_change(
                collection_id=str(result.inserted_id),
                user_id=user_id,
                action="publication_window_update",
                previous_state=None,  # No previous state on creation
                new_state=effective_state,
                previous_release_date=None,
                new_release_date=collection.get("releaseDate"),
                previous_no_disponible_desde=None,
                new_no_disponible_desde=no_disponible_desde,
                previous_no_disponible_hasta=None,
                new_no_disponible_hasta=no_disponible_hasta,
                metadata={"action": "collection_created"}
            )
        
        return (collection, None)

    except Exception as e:
        logger.error(f"Failed to create collection: {str(e)}")
        return (None, e)


async def add_song_to_collection(song_id: str, collection_id: str, order, early_release_date=None):
    db = get_db()
    song_oid = ObjectId(song_id)
    collection_oid = ObjectId(collection_id)

    collection_song = CollectionSong(
        song_id=song_oid, 
        collection_id=collection_oid, 
        order=order,
        early_release_date=early_release_date
    )
    db.collection_songs.insert_one(collection_song.model_dump(by_alias=True))
    if early_release_date:
        logger.info(f"Added song {song_id} to collection with early release date {early_release_date}")
    else:
        logger.info(f"Added song {song_id} to collection")
    return True


async def delete_collection(existing_collection):
    db = get_db()
    try:
        result = db.collections.delete_one({"_id": existing_collection["_id"]})
        if result.deleted_count > 0:
            logger.info(f"Successfully deleted collection with id={existing_collection['_id']}")
        else:
            logger.warning(f"Collection with id={existing_collection['_id']} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to delete collection with id={existing_collection['_id']}: {str(e)}")


async def get_collection(id, includeUnpublished: bool = False):
    db = get_db()
    try:
        query = {"_id": ObjectId(id)}
        
        # Filter by release date unless includeUnpublished is True
        if not includeUnpublished:
            query["releaseDate"] = {"$lte": datetime.now(timezone.utc)}
        
        collection = db.collections.find_one(query)
        if collection is None:
            logger.warning(f"Collection with id={id} not found or not yet released")
            return None
                
        logger.info(f"Successfully retrieved collection '{collection['name']}'")
        return collection
    except Exception as e:
        logger.error(f"Failed to get collection with id={id}: {str(e)}")
        return None


async def get_songs_from_collection(collection_id: str, include_unreleased=True):
    """
    Get songs from a collection.
    
    Args:
        collection_id: ID of the collection
        include_unreleased: If False, only returns songs that have been early released or collection is released
    """
    db = get_db()

    collection_songs = list(db.collection_songs.find(
        {"collection_id": ObjectId(collection_id)},
        {"song_id": 1, "order": 1, "early_release_date": 1}
    ))

    if not collection_songs:
        return []

    # Filter by early release date if requested
    if not include_unreleased:
        now = datetime.now(timezone.utc)
        collection_songs = [
            cs for cs in collection_songs 
            if cs.get("early_release_date") and (
                # Ensure both datetimes are timezone-aware for comparison
                cs["early_release_date"].replace(tzinfo=timezone.utc) if cs["early_release_date"].tzinfo is None 
                else cs["early_release_date"]
            ) <= now
        ]

    song_ids = [ps["song_id"] for ps in collection_songs]
    if not song_ids:
        return []

    songs = list(db.songs.find({"_id": {"$in": song_ids}}))
    song_map = {song["_id"]: song for song in songs}
    return [
        {
            **song_map[ps["song_id"]], 
            "order": ps["order"],
            "early_release_date": ps.get("early_release_date")
        }
        for ps in collection_songs
        if ps["song_id"] in song_map
    ]


async def get_collections(
    type: str = None,
    artistId: str = None,
    includeUnpublished: bool = False,
    # nuevos filtros
    state: str = "",
    published_from=None,
    published_to=None,
    genre=None,
):
    """
    Filtros:
    - state: "publicado" (releaseDate <= now) / "programado" (releaseDate > now)
    - published_from / published_to: rango sobre releaseDate
    """
    db = get_db()
    try:
        query = {}
        if type:
            query["type"] = type
        if artistId:
            query["artistId"] = artistId

        st = (state or "").strip().lower()
        now = datetime.now(timezone.utc)

        if not includeUnpublished:
            # comportamiento público: sólo publicadas
            query["releaseDate"] = {"$lte": now}
        else:
            # backoffice/owner: se puede filtrar por estado
            if st == "publicado":
                query["releaseDate"] = {"$lte": now}
            elif st == "programado":
                query["releaseDate"] = {"$gt": now}

        # rango de fechas (siempre sobre releaseDate)
        if published_from or published_to:
            range_q = {}
            if published_from:
                range_q["$gte"] = published_from
            if published_to:
                range_q["$lte"] = published_to
            # combinar con lo que ya haya
            if "releaseDate" in query and isinstance(query["releaseDate"], dict):
                query["releaseDate"].update(range_q)
            else:
                query["releaseDate"] = range_q

        if genre:
            query["genre"] = genre  

        collections = list(
            db.collections.find(query).sort([("createdAt", DESCENDING), ("name", 1)])
        )
        logger.info(f"Retrieved {len(collections)} collections from database (includeUnpublished={includeUnpublished})")
        return collections
    except Exception as e:
        logger.error(f"Failed to retrieve collections: {str(e)}")
        return []

    
async def delete_songs_from_collection(collection_id: str):
    db = get_db()

    try:
        result = db.collection_songs.delete_many({ "collection_id": ObjectId(collection_id)})
        logger.info(f"Se eliminaron {result.deleted_count} de collection_sogns")
        return
    except Exception as e:
        logger.error(f"Failed to delete songs from collections: {str(e)}")
        return


async def update_collection_cover(collection_id: str, cover_url: str):
    db = get_db()
    result = db.collections.update_one(
        {"_id": ObjectId(collection_id)},
        {"$set": {"coverUrl": cover_url}}
    )
    return result.modified_count > 0

async def update_collection(collection_id: str, update_data: dict, user_id: str | None = None):
    """
    Updates collection fields based on update_data.
    Recalculates effective state and logs changes to audit.

    Auditoría (CA3):
      - user_id, timestamp
      - cambios (territorios y/o vigencias)
      - alcance/región (scope)
    """
    db = get_db()

    def _diff_list(prev: list[str] | None, new: list[str] | None):
        prev = prev or []
        new = new or []
        return {
            "from": prev,
            "to": new,
            "added": [x for x in new if x not in prev],
            "removed": [x for x in prev if x not in new],
        }

    try:
        if not update_data:
            logger.warning(f"No fields to update for collection {collection_id}")
            return True

        current_collection = await get_collection(collection_id, includeUnpublished=True)
        if not current_collection:
            logger.error(f"Collection {collection_id} not found for update")
            return False

        previous_state = calculate_effective_state(current_collection)

        # Snapshot previo para auditoría
        previous_release_date = current_collection.get("releaseDate")
        previous_no_disponible_desde = current_collection.get("noDisponibleDesde")
        previous_no_disponible_hasta = current_collection.get("noDisponibleHasta")
        previous_bloqueado_admin = current_collection.get("bloqueadoAdmin", False)
        previous_admin_block = current_collection.get("adminBlock")
        previous_available_countries = current_collection.get("availableCountries", [])

        # Update
        result = db.collections.update_one(
            {"_id": ObjectId(collection_id)},
            {"$set": update_data}
        )

        if result.modified_count <= 0:
            logger.info(f"No changes made to collection {collection_id}")
            return True

        logger.info(f"Successfully updated collection {collection_id} with fields: {list(update_data.keys())}")

        updated_collection = await get_collection(collection_id, includeUnpublished=True)
        if not updated_collection:
            return True

        new_state = calculate_effective_state(updated_collection)

        # Armar changes (territorios / vigencias)
        changes: dict = {}

        if "availableCountries" in update_data:
            changes["territorios"] = _diff_list(previous_available_countries, update_data.get("availableCountries"))

        if any(k in update_data for k in ["releaseDate", "noDisponibleDesde", "noDisponibleHasta"]):
            changes["vigencias"] = {
                "from": {
                    "releaseDate": previous_release_date,
                    "noDisponibleDesde": previous_no_disponible_desde,
                    "noDisponibleHasta": previous_no_disponible_hasta,
                },
                "to": {
                    "releaseDate": update_data.get("releaseDate", previous_release_date),
                    "noDisponibleDesde": update_data.get("noDisponibleDesde", previous_no_disponible_desde),
                    "noDisponibleHasta": update_data.get("noDisponibleHasta", previous_no_disponible_hasta),
                },
            }

        # Alcance/scope (simple): si hay lista de países => "regions"
        scope = {
            "type": "regions" if (update_data.get("availableCountries") or previous_available_countries) else "global",
            "regions": update_data.get("availableCountries") or previous_available_countries or [],
        }

        # Acción para auditoría como antes
        action = "publication_window_update" if any(
            k in update_data for k in ["releaseDate", "noDisponibleDesde", "noDisponibleHasta"]
        ) else "state_change"

        if user_id:
            await log_collection_change(
                collection_id=collection_id,
                user_id=user_id,
                action=action,
                previous_state=previous_state,
                new_state=new_state,
                previous_release_date=previous_release_date,
                new_release_date=update_data.get("releaseDate"),
                previous_no_disponible_desde=previous_no_disponible_desde,
                new_no_disponible_desde=update_data.get("noDisponibleDesde"),
                previous_no_disponible_hasta=previous_no_disponible_hasta,
                new_no_disponible_hasta=update_data.get("noDisponibleHasta"),
                previous_bloqueado_admin=previous_bloqueado_admin,
                new_bloqueado_admin=update_data.get("bloqueadoAdmin"),
                metadata={
                    "updated_fields": list(update_data.keys()),
                    "scope": scope,
                    "changes": changes,
                    "previous_adminBlock": previous_admin_block,
                    "new_adminBlock": update_data.get("adminBlock"),
                }
            )

        return True

    except Exception as e:
        logger.error(f"Failed to update collection {collection_id}: {str(e)}")
        return False


async def publish_collection_now(collection_id: str, artist_id: str):
    """
    Publishes a collection immediately by setting its release date to now.
    Only works if the collection is unpublished and belongs to the requesting artist.
    
    Args:
        collection_id: The ID of the collection to publish
        artist_id: The ID of the artist making the request
        
    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    db = get_db()
    try:
        # Get collection including unpublished ones
        collection = await get_collection(collection_id, includeUnpublished=True)
        
        if not collection:
            return (False, "Collection not found")
        
        # Check if artist owns the collection
        if collection["artistId"] != artist_id:
            return (False, "You are not authorized to publish this collection")
        
        # Check if collection is already published
        if collection.get("releaseDate"):
            release_date = collection["releaseDate"]
            # Ensure both datetimes are timezone-aware for comparison
            if release_date.tzinfo is None:
                release_date = release_date.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            if release_date <= now:
                return (False, "Collection is already published")
        
        # Update release date to now
        result = db.collections.update_one(
            {"_id": ObjectId(collection_id)},
            {"$set": {"releaseDate": datetime.now(timezone.utc)}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Successfully published collection {collection_id}")
            return (True, None)
        else:
            logger.warning(f"Failed to publish collection {collection_id}")
            return (False, "Failed to publish collection")
            
    except Exception as e:
        logger.error(f"Failed to publish collection {collection_id}: {str(e)}")
        return (False, str(e))


async def get_popular_collections(artistId: str, limit: int = 50, type: str = None, includeUnpublished: bool = False):
    """
    Get collections ordered by popularity score for a specific artist.
    
    Popularity score is calculated from multiple metrics:
    - Plays: reproductions of songs in the collection
    - Likes: likes on songs in the collection
    - Playlist saves: times songs are added to playlists
    - Shares: times songs/collection are shared
    
    Args:
        artistId: Artist ID (required)
        limit: Maximum number of collections to return
        type: Optional filter by collection type (album, single, ep)
        includeUnpublished: Whether to include unpublished collections (default: False)
        
    Returns:
        List of collections with popularity metrics
    """
    db = get_db()
    try:
        # Get all collections for the artist with optional type filter
        query = {"artistId": artistId}
        if type:
            query["type"] = type
        
        # Filter by release date unless includeUnpublished is True
        if not includeUnpublished:
            query["releaseDate"] = {"$lte": datetime.now(timezone.utc)}
            
        collections = list(db.collections.find(query))
        
        # Calculate popularity for each collection
        collections_with_metrics = []
        for collection in collections:
            # Get all songs in the collection
            collection_songs = list(db.collection_songs.find(
                {"collection_id": collection["_id"]},
                {"song_id": 1}
            ))
            song_ids = [cs["song_id"] for cs in collection_songs]
            
            # Initialize metrics
            total_plays = 0
            total_likes = 0
            total_playlist_saves = 0
            total_shares = 0
            
            if song_ids:
                # Count plays from permanent plays table
                total_plays = db.plays.count_documents({"song_id": {"$in": song_ids}})
                
                # Count likes on songs in the collection
                total_likes = db.likes.count_documents({
                    "target_id": {"$in": song_ids},
                    "target_type": "song"
                })
                
                # Count how many times songs are saved in playlists
                total_playlist_saves = db.playlist_songs.count_documents({
                    "song_id": {"$in": song_ids}
                })
                
                # Count shares of songs in the collection
                total_shares = db.shares.count_documents({
                    "target_id": {"$in": song_ids},
                    "target_type": "song"
                })
            
            # Calculate popularity score (weighted sum)
            # Weights can be adjusted based on importance of each metric
            popularity_score = (
                total_plays * 1.0 +       # Plays have base weight
                total_likes * 2.0 +       # Likes are more valuable
                total_playlist_saves * 3.0 +  # Saves indicate strong interest
                total_shares * 5.0        # Shares are most valuable (viral potential)
            )
            
            # Add all metrics to collection
            collection["totalPlays"] = total_plays
            collection["totalLikes"] = total_likes
            collection["totalPlaylistSaves"] = total_playlist_saves
            collection["totalShares"] = total_shares
            collection["popularityScore"] = popularity_score
            collections_with_metrics.append(collection)
        
        # Sort by popularity score descending
        collections_with_metrics.sort(key=lambda x: x["popularityScore"], reverse=True)
        
        # Return limited results
        result = collections_with_metrics[:limit]
        logger.info(f"Retrieved {len(result)} popular collections (sorted by popularity score)")
        return result
        
    except Exception as e:
        logger.error(f"Failed to retrieve popular collections: {str(e)}")
        return []


async def get_most_popular_albums_overall(limit: int = 50):
    """
    Get the most popular albums globally, excluding admin-blocked ones.
    CA2: no debe mostrarse en rankings/listados si está Bloqueado-admin.
    """
    db = get_db()

    try:
        now = datetime.now(timezone.utc)

        query = {
            "type": "album",
            "releaseDate": {"$lte": now},
            # excluir bloqueos admin (legacy y nuevo global)
            "$nor": [
                {"bloqueadoAdmin": True},
                {"adminBlock.enabled": True, "adminBlock.scope": "global"},
            ],
        }

        albums = list(db.collections.find(query))
        albums_with_metrics = []

        for album in albums:
            album_songs = list(db.collection_songs.find(
                {"collection_id": album["_id"]},
                {"song_id": 1}
            ))

            song_ids = [s["song_id"] for s in album_songs]

            total_plays = 0
            total_likes = 0
            total_playlist_saves = 0
            total_shares = 0

            if song_ids:
                total_plays = db.plays.count_documents({"song_id": {"$in": song_ids}})
                total_likes = db.likes.count_documents({
                    "target_id": {"$in": song_ids},
                    "target_type": "song"
                })
                total_playlist_saves = db.playlist_songs.count_documents({"song_id": {"$in": song_ids}})
                total_shares = db.shares.count_documents({
                    "target_id": {"$in": song_ids},
                    "target_type": "song"
                })

            popularity_score = (
                total_plays * 1.0 +
                total_likes * 2.0 +
                total_playlist_saves * 3.0 +
                total_shares * 5.0
            )

            album["totalPlays"] = total_plays
            album["totalLikes"] = total_likes
            album["totalPlaylistSaves"] = total_playlist_saves
            album["totalShares"] = total_shares
            album["popularityScore"] = popularity_score

            albums_with_metrics.append(album)

        albums_with_metrics.sort(key=lambda x: x["popularityScore"], reverse=True)

        result = albums_with_metrics[:limit]
        logger.info(f"Retrieved {len(result)} most popular albums overall (excluding admin blocked)")
        return result

    except Exception as e:
        logger.error(f"Failed to compute global popular albums: {str(e)}")
        return []


async def _fetch_users_by_name(name: str, base_url: str = USER_API_BASE, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Llama al endpoint público GET /users/search?q=<name> y devuelve [{"id": "<uuid>"}, ...]
    Ajustá el path si en tu API quedó distinto.
    """
    url = f"{USER_API_BASE}/users/search"
    headers = {}
    if token:
        headers["Authorization"] = token
    # timeouts: 5s connect, 20s total lectura
    timeout = httpx.Timeout(20.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.info(f"User API base: {USER_API_BASE}")
        logger.info(f"Calling: {USER_API_BASE.rstrip('/')}/users/search?q={name} (token: {bool(token)})")
        resp = await client.get(url, params={"q": name}, headers=headers)
        resp.raise_for_status()
        data = resp.json()  
        # La respuesta esperada es {"users": [...], "count": N}
        items = data.get("users") or data.get("result") or []
        return [{"id": u.get("id")} for u in items if u.get("id")]


async def get_ids_by_name(name: str, token: Optional[str] = None):
    db = get_db()
    try:
        logger.info(f"Fetching user IDs by name: {name}")
        users = await _fetch_users_by_name(name, token)
    except httpx.HTTPStatusError as e:
        logger.error(f"User API devolvió {e.response.status_code}: {e.response.text}")
        users = []
    except Exception as e:
        logger.exception(f"Error llamando User API: {e}")
        users = []

    try:
        playlists = list(
            db.playlists.find(
                {"name": {"$regex": name, "$options": "i"}},
                {"_id": 1}
            )
        )
        songs = list(
            db.songs.find(
                {"title": {"$regex": name, "$options": "i"}},
                {"_id": 1}
            )
        )
        
        # Search for collections (albums, EPs, singles) by name
        # Only include published collections
        now = datetime.now(timezone.utc)
        albums = list(
            db.collections.find(
                {
                    "name": {"$regex": name, "$options": "i"},
                    "releaseDate": {"$lte": now}
                },
                {"_id": 1}
            )
        )

        collections = {
            "playlists": playlists,   # ej: [{"_id": ObjectId(...)}]
            "songs": songs,           # ej: [{"_id": ObjectId(...)}]
            "albums": albums,         # ej: [{"_id": ObjectId(...)}]
            "users": users,           # ej: [{"id": "uuid"}, ...]
        }

        logger.info(f"Found {sum(len(v) for v in collections.values())} items with name '{name}': {len(playlists)} playlists, {len(songs)} songs, {len(albums)} albums, {len(users)} users")
        logger.debug(f"Collections: {collections}")
        return collections

    except Exception as e:
        logger.exception(f"Failed to search collections by name='{name}': {e}")
        return False
    

async def get_albums_by_field(field: str, values: list[str], limit: int):
    db = get_db()

    try:
        now = datetime.now(timezone.utc)
        per_value = max(limit // len(values), 1)
        results = []

        for value in values:
            query = {
                field: value,
                "type": "album",
                "releaseDate": {"$lte": now},
            }

            cursor = db.collections.find(query).limit(per_value)
            items = list(cursor)

            logger.info(f"{field}={value}: fetched {len(items)} albums")

            results.extend(items)

        logger.info(f"Total albums fetched using {field}: {len(results)}")
        return results[:limit]

    except Exception as e:
        logger.error(f"Failed to get albums for {field}={values}: {str(e)}")
        return None
    

async def get_albums_by_field_greedy(field: str, values: list[str], limit: int):
    db = get_db()
    
    try:
        now = datetime.now(timezone.utc)
        results = []

        for value in values:
            if len(results) >= limit:
                break
            query = {
                field: value,
                "type": "album",
                "releaseDate": {"$lte": now},
            }

            remaining = limit - len(results)
            cursor = db.collections.find(query).limit(remaining)
            items = list(cursor)
            results.extend(items)

        logger.info(f"Total albums fetched using {field}: {len(results)}")
        return results[:limit]

    except Exception as e:
        logger.error(f"Failed greedy fetch for {field}={values}: {str(e)}")
        return []


async def configure_publication_window(
    collection_id: str,
    release_date: datetime | None = None,
    no_disponible_desde: datetime | None = None,
    no_disponible_hasta: datetime | None = None,
    user_id: str | None = None
):
    """
    Configure publication window for a collection.
    Sets releaseDate and optional no-disponible window.
    
    Args:
        collection_id: ID of the collection
        release_date: Release date/time with timezone
        no_disponible_desde: Start of no-disponible window (optional)
        no_disponible_hasta: End of no-disponible window (optional)
        user_id: ID of the user making the change (for audit)
        
    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    db = get_db()
    try:
        collection = await get_collection(collection_id, includeUnpublished=True)
        if not collection:
            return (False, "Collection not found")
        
        # Build update data
        update_data = {}
        if release_date is not None:
            # Ensure timezone-aware
            if release_date.tzinfo is None:
                release_date = release_date.replace(tzinfo=timezone.utc)
            update_data["releaseDate"] = release_date
        
        if no_disponible_desde is not None:
            if no_disponible_desde.tzinfo is None:
                no_disponible_desde = no_disponible_desde.replace(tzinfo=timezone.utc)
            update_data["noDisponibleDesde"] = no_disponible_desde
        
        if no_disponible_hasta is not None:
            if no_disponible_hasta.tzinfo is None:
                no_disponible_hasta = no_disponible_hasta.replace(tzinfo=timezone.utc)
            update_data["noDisponibleHasta"] = no_disponible_hasta
        
        if not update_data:
            return (False, "No fields to update")
        
        # Validate window
        if update_data.get("noDisponibleDesde") and update_data.get("noDisponibleHasta"):
            if update_data["noDisponibleDesde"] >= update_data["noDisponibleHasta"]:
                return (False, "noDisponibleDesde must be before noDisponibleHasta")
        
        # Update collection
        success = await update_collection(collection_id, update_data, user_id)
        if success:
            return (True, None)
        else:
            return (False, "Failed to update collection")
            
    except Exception as e:
        logger.error(f"Failed to configure publication window for collection {collection_id}: {str(e)}")
        return (False, str(e))

def _normalize_admin_scope(scope) -> str:
    """
    Normaliza scope a los únicos valores permitidos por schema:
    "global" | "regions"
    Soporta: Enum (AdminBlockScope.GLOBAL), strings "AdminBlockScope.GLOBAL", etc.
    """
    if scope is None:
        return "global"

    # Enum -> value
    if isinstance(scope, PyEnum):
        scope = scope.value

    if not isinstance(scope, str):
        return "global"

    s = scope.strip()

    # "AdminBlockScope.GLOBAL" -> "GLOBAL"
    if s.startswith("AdminBlockScope."):
        s = s.split(".", 1)[1]

    s = s.lower()

    if s == "global":
        return "global"
    if s in ("regions", "region", "regiones"):
        return "regions"

    return "global"

async def set_admin_block(
    collection_id: str,
    blocked: bool,
    scope: str | None = None,
    regions: list[str] | None = None,
    reason_code: str | None = None,
    user_id: str | None = None
):
    db = get_db()
    try:
        collection = await get_collection(collection_id, includeUnpublished=True)
        if not collection:
            return (False, "Collection not found")

        scope_norm = _normalize_admin_scope(scope)

        # Validaciones CA1 (en backend por seguridad)
        if blocked:
            if not scope or not reason_code:
                return (False, "scope and reasonCode are required when blocking")
            if scope_norm == "regions" and (not regions or len(regions) == 0):
                return (False, "regions is required when scope=regions")

        previous_state = calculate_effective_state(collection, user_country=None)
        previous_bloqueado_admin = collection.get("bloqueadoAdmin", False)
        previous_admin_block = collection.get("adminBlock") or {}

        now = datetime.now(timezone.utc)

        if blocked:
            admin_block = {
                "enabled": True,
                "scope": scope_norm,          # ✅ SIEMPRE "global" | "regions"
                "regions": regions or [],
                "reasonCode": reason_code,
                "by": user_id,
                "at": now,
            }
            update = {"$set": {"adminBlock": admin_block, "bloqueadoAdmin": True}}
        else:
            update = {"$unset": {"adminBlock": ""}, "$set": {"bloqueadoAdmin": False}}

        result = db.collections.update_one({"_id": ObjectId(collection_id)}, update)
        if result.matched_count == 0:
            return (False, "Collection not found")

        updated_collection = await get_collection(collection_id, includeUnpublished=True)
        new_state = calculate_effective_state(updated_collection, user_country=None) if updated_collection else previous_state

        # Auditoría CA4 (incluye alcance + motivo)
        if user_id:
            unblock_reason = reason_code or previous_admin_block.get("reasonCode") or "UNBLOCK"

            meta = {
                "scope": scope_norm if blocked else _normalize_admin_scope(previous_admin_block.get("scope")),
                "regions": (regions or []) if blocked else (previous_admin_block.get("regions") or []),
                "reasonCode": reason_code if blocked else unblock_reason,
                "action": "admin_block" if blocked else "admin_unblock",
            }

            await log_collection_change(
                collection_id=collection_id,
                user_id=user_id,
                action="state_change",
                previous_state=previous_state,
                new_state=new_state,
                previous_bloqueado_admin=previous_bloqueado_admin,
                new_bloqueado_admin=blocked,
                metadata=meta
            )

        logger.info(f"Successfully {'blocked' if blocked else 'unblocked'} collection {collection_id}")
        return (True, None)

    except Exception as e:
        logger.error(f"Failed to set admin block for collection {collection_id}: {str(e)}")
        return (False, str(e))

async def auto_activate_scheduled_collections():
    """
    Automatically activate collections that have reached their release date.
    This function should be called periodically (e.g., via cron job).
    
    Returns:
        Tuple of (activated_count: int, errors: list)
    """
    db = get_db()
    activated_count = 0
    errors = []
    
    try:
        now = datetime.now(timezone.utc)
        
        # Find all collections that should be activated
        # (releaseDate <= now, not bloqueadoAdmin, currently in "programado" state)
        collections = list(db.collections.find({
            "releaseDate": {"$lte": now},
            "bloqueadoAdmin": {"$ne": True}
        }))
        
        for collection in collections:
            try:
                # Check if should activate
                if should_auto_activate(collection, now):
                    # Calculate previous state as if it were before releaseDate
                    # (simulate a time just before releaseDate to get "programado" state)
                    release_date = collection.get("releaseDate")
                    if release_date and release_date.tzinfo is None:
                        release_date = release_date.replace(tzinfo=timezone.utc)
                    
                    # Previous state would have been "programado" before releaseDate
                    # Calculate state just before releaseDate
                    just_before_release = release_date - timedelta(seconds=1) if release_date else now
                    previous_state = calculate_effective_state(collection, now=just_before_release)
                    
                    # Current state is now "publicado" (since releaseDate <= now)
                    new_state = calculate_effective_state(collection, now=now)
                    
                    # Only log if state actually changed
                    if previous_state != new_state:
                        # Log auto-activation
                        await log_collection_change(
                            collection_id=str(collection["_id"]),
                            user_id="system",
                            action="auto_activation",
                            previous_state=previous_state,
                            new_state=new_state,
                            previous_release_date=collection.get("releaseDate"),
                            new_release_date=collection.get("releaseDate"),
                            metadata={"auto_activated_at": now.isoformat()}
                        )
                        
                        activated_count += 1
                        logger.info(f"Auto-activated collection {collection['_id']} from {previous_state} to {new_state}")
                    else:
                        logger.debug(f"Collection {collection['_id']} state unchanged ({previous_state}), skipping activation log")
                    
            except Exception as e:
                error_msg = f"Failed to auto-activate collection {collection.get('_id')}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        logger.info(f"Auto-activation completed: {activated_count} collections activated, {len(errors)} errors")
        return (activated_count, errors)
        
    except Exception as e:
        logger.error(f"Failed to auto-activate scheduled collections: {str(e)}")
        errors.append(str(e))
        return (activated_count, errors)
