import databases.storage_database as storage_db
import databases.collections_database as collections_db
import databases.preferences_database as preferences_db
import databases.audit_database as audit_db
import schemas
from schemas import AdminBlockRequest
from fastapi import Depends, APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from resources.logger import logger
from common.utils import create_error_response, serialize_collection
from common.countries import validate_country_codes, calculate_available_countries
from datetime import datetime, timezone
from auth import verify_token, is_authorized
from databases.collection_states import calculate_effective_state

router = APIRouter()


def _can_access_collection(user: dict, collection: dict) -> bool:
    """
    Check if a user can access a collection based on geographical restrictions.

    Returns True if:
    - User is backoffice
    - User is the owner of the collection
    - User's country is in the collection's availableCountries list
    - If availableCountries is empty => available everywhere
    """
    if user.get("user_type") == "backoffice":
        return True

    if user.get("user_id") == collection.get("artistId"):
        return True

    user_country = user.get("country", "")
    available_countries = collection.get("availableCountries", [])

    if not available_countries:
        return True

    return user_country in available_countries


def _parse_iso(dt: str | None):
    if not dt:
        return None
    try:
        if len(dt) == 10:
            return datetime.fromisoformat(dt).replace(tzinfo=timezone.utc)
        d = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


@router.post("/{collection_id}/upload-cover", status_code=201)
async def upload_collection_cover(
    collection_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(verify_token),
):
    """
    Subir una imagen de portada para una colección.
    """
    try:
        collection = await collections_db.get_collection(collection_id)
        if collection is None:
            logger.warning(f"Collection with id={collection_id} not found for deletion")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found",
                    f"/collections/{collection_id}",
                ),
            )

        if not is_authorized(user, collection["artistId"]):
            return JSONResponse(
                status_code=401,
                content=create_error_response(
                    401,
                    "Unauthorized",
                    "You are not authorized to upload a cover for this collection",
                ),
            )

        result = await storage_db.upload_cover_image("albums", collection["artistId"], file)
        cover_url = result["coverUrl"]

        updated = await collections_db.update_collection_cover(collection_id, cover_url)
        if not updated:
            logger.error(f"Failed to update playlist cover for id {collection_id}")
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "Failed to update collection cover",
                    f"/collection/{collection_id}/upload-cover",
                ),
            )

        logger.info(f"Successfully updated collection cover for {collection_id}")
        return {"coverUrl": cover_url}

    except Exception as e:
        logger.error(f"Failed to upload playlist cover: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collection/{collection_id}/upload-cover",
            ),
        )


@router.post("/", status_code=201)
async def create_collection(collection: schemas.CreateCollectionRequest, user: dict = Depends(verify_token)):
    logger.info(f"Creating collection {collection.name}")

    if user.get("stage_name", "") == "":
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", "User is not an artist", "/collections"),
        )

    try:
        if collection.availableInCountries:
            is_valid, error_msg = validate_country_codes(collection.availableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400, "Bad Request", f"availableInCountries: {error_msg}", "/collections"
                    ),
                )

        if collection.notAvailableInCountries:
            is_valid, error_msg = validate_country_codes(collection.notAvailableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400, "Bad Request", f"notAvailableInCountries: {error_msg}", "/collections"
                    ),
                )

        available_countries = calculate_available_countries(
            collection.availableInCountries,
            collection.notAvailableInCountries,
        )
        logger.info(f"Collection will be available in {len(available_countries)} countries")

        if collection.noDisponibleDesde and collection.noDisponibleHasta:
            if collection.noDisponibleDesde >= collection.noDisponibleHasta:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400,
                        "Bad Request",
                        "noDisponibleDesde must be before noDisponibleHasta",
                        "/collections",
                    ),
                )

        collection_type = collection.type.value if hasattr(collection.type, "value") else collection.type

        songs_with_early = [
            {"songId": song.songId, "earlyReleaseDate": song.earlyReleaseDate}
            for song in (collection.songs or [])
        ]

        db_collection, e = await collections_db.create_collection(
            collection.name,
            user["user_id"],
            user["stage_name"],
            collection_type,
            collection.genre,
            "None",
            collection.releaseDate,
            collection.credits,
            songs_with_early,
            available_countries,
            collection.noDisponibleDesde,
            collection.noDisponibleHasta,
            user["user_id"],
        )
        if not db_collection:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/collections"),
            )

        songs = await collections_db.get_songs_from_collection(db_collection["_id"])
        return {"data": serialize_collection(db_collection, songs, user.get("country"))}

    except Exception as e:
        logger.error(f"Failed to create collection {collection.name}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/collections"),
        )


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Deleting collection with id={collection_id}")

    collection = await collections_db.get_collection(collection_id)
    if collection is None:
        logger.warning(f"Collection with id={collection_id} not found for deletion")
        return JSONResponse(
            status_code=404,
            content=create_error_response(
                404,
                "Not Found",
                f"Collection with id {collection_id} not found",
                f"/collections/{collection_id}",
            ),
        )

    if not is_authorized(user, collection["artistId"]):
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403,
                "Forbidden",
                "You are not authorized to delete this collection",
                f"/collections/{collection_id}",
            ),
        )

    await collections_db.delete_collection(collection)
    return JSONResponse(status_code=204, content=None)


@router.put("/{collection_id}", status_code=200)
async def update_collection(
    collection_id: str,
    update_request: schemas.UpdateCollectionRequest,
    user: dict = Depends(verify_token),
):
    logger.info(f"Updating collection {collection_id}")
    try:
        collection = await collections_db.get_collection(collection_id)
        if collection is None:
            logger.warning(f"Collection with id={collection_id} not found")
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found",
                    f"/collections/{collection_id}",
                ),
            )

        if not is_authorized(user, collection["artistId"]):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to update this collection",
                    f"/collections/{collection_id}",
                ),
            )

        if update_request.availableInCountries is not None:
            is_valid, error_msg = validate_country_codes(update_request.availableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400,
                        "Bad Request",
                        f"availableInCountries: {error_msg}",
                        f"/collections/{collection_id}",
                    ),
                )

        if update_request.notAvailableInCountries is not None:
            is_valid, error_msg = validate_country_codes(update_request.notAvailableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400,
                        "Bad Request",
                        f"notAvailableInCountries: {error_msg}",
                        f"/collections/{collection_id}",
                    ),
                )

        available_countries = None
        if update_request.availableInCountries is not None or update_request.notAvailableInCountries is not None:
            available_countries = calculate_available_countries(
                update_request.availableInCountries,
                update_request.notAvailableInCountries,
            )
            logger.info(
                f"Updating collection {collection_id} to be available in {len(available_countries)} countries"
            )

        update_data = {}
        if update_request.name is not None:
            update_data["name"] = update_request.name
        if update_request.type is not None:
            update_data["type"] = update_request.type.value if hasattr(update_request.type, "value") else update_request.type
        if update_request.genre is not None:
            update_data["genre"] = update_request.genre
        if update_request.coverUrl is not None:
            update_data["coverUrl"] = update_request.coverUrl
        if update_request.credits is not None:
            update_data["credits"] = update_request.credits
        if available_countries is not None:
            update_data["availableCountries"] = available_countries

        if update_data:
            success = await collections_db.update_collection(collection_id, update_data, user["user_id"])
            if not success:
                return JSONResponse(
                    status_code=500,
                    content=create_error_response(
                        500,
                        "Internal Server Error",
                        "Failed to update collection",
                        f"/collections/{collection_id}",
                    ),
                )

        if update_request.songs is not None:
            await collections_db.delete_songs_from_collection(collection_id)
            order = 0
            for song_info in update_request.songs:
                ok = await collections_db.add_song_to_collection(
                    song_info.songId, collection_id, order, song_info.earlyReleaseDate
                )
                if not ok:
                    logger.error(f"Failed to add song {song_info.songId} to collection")
                order += 1

        collection = await collections_db.get_collection(collection_id)
        songs = await collections_db.get_songs_from_collection(collection_id)
        return {"data": serialize_collection(collection, songs, user.get("country"))}

    except Exception as e:
        logger.error(f"Failed to update collection: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(500, "Internal Server Error", str(e), f"/collections/{collection_id}"),
        )


@router.get("/recommended")
async def get_album_recommendations(n: int = 10, user: dict = Depends(verify_token)):
    user_id = user["user_id"]

    genres = await preferences_db.get_user_genres(user_id) or []
    artists = await preferences_db.get_user_artists(user_id) or []

    if len(genres) == 0 and len(artists) == 0:
        popular = await collections_db.get_most_popular_albums_overall(n)
        return {"albums": [serialize_collection(a, a.get("songs", []), user.get("country")) for a in popular]}

    half = n // 2
    albums = []

    if genres:
        g = await collections_db.get_albums_by_field("genre", genres, half)
        albums.extend(g or [])

    if artists:
        limit = n if not genres else half
        a = await collections_db.get_albums_by_field("artistId", artists, limit)
        albums.extend(a or [])

    if len(albums) < n and genres:
        needed = n - len(albums)
        extra_g = await collections_db.get_albums_by_field_greedy("genre", genres, needed)
        albums.extend(extra_g or [])

    seen = set()
    unique = []
    for a in albums:
        key = str(a["_id"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    if len(unique) < n:
        needed = n - len(unique)
        popular = await collections_db.get_most_popular_albums_overall(needed)
        unique.extend(popular)

    final_seen = set()
    final_list = []
    for a in unique:
        key = str(a["_id"])
        if key not in final_seen:
            final_seen.add(key)
            final_list.append(a)
        if len(final_list) == n:
            break

    serialized = [serialize_collection(a, a.get("songs", []), user.get("country")) for a in final_list]
    logger.info(f"Generated {len(serialized)} recommendations for user {user_id}")
    return {"albums": serialized}


@router.get("/popular/{artistId}", status_code=200)
async def get_popular_collections(
    artistId: str,
    limit: int = 50,
    type: str = None,
    includeUnpublished: bool = False,
    user: dict = Depends(verify_token),
):
    logger.info(
        f"Fetching popular collections for artist {artistId} (limit={limit}, type={type}, includeUnpublished={includeUnpublished})"
    )

    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 10

    try:
        collections = await collections_db.get_popular_collections(
            artistId=artistId, limit=limit, type=type, includeUnpublished=includeUnpublished
        )

        user_country = user.get("country")
        is_backoffice = user.get("user_type") == "backoffice"

        accessible_collections = []
        for c in collections:
            if not _can_access_collection(user, c):
                continue

            if not is_backoffice and not includeUnpublished:
                # CA2: no debe aparecer si no es efectivamente "publicado" para ese país
                st = calculate_effective_state(c, user_country)
                if st != "publicado":
                    continue

            accessible_collections.append(c)

        logger.info(
            f"Filtered {len(collections)} popular collections to {len(accessible_collections)} based on restrictions/state"
        )

        serialized_collections = []
        for c in accessible_collections:
            songs = await collections_db.get_songs_from_collection(c["_id"])
            serialized_collections.append(serialize_collection(c, songs, user_country))

        return {"data": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch popular collections: {str(e)}")
        raise


@router.get("/", status_code=200)
async def get_collections(
    type: str = None,
    artistId: str = None,
    includeUnpublished: bool = False,
    state: str | None = None,  # "Publicado" | "Programado"
    publishedFrom: str | None = None,
    publishedTo: str | None = None,
    genre: str | None = None,
    user: dict = Depends(verify_token),
):
    st = (state or "").strip().lower()
    if st not in ("", "publicado", "programado"):
        st = ""

    dt_from = _parse_iso(publishedFrom)
    dt_to = _parse_iso(publishedTo)

    logger.info(
        f"Fetching collections (type={type}, artistId={artistId}, includeUnpublished={includeUnpublished}, state={st}, from={dt_from}, to={dt_to})"
    )
    try:
        collections = await collections_db.get_collections(
            type=type,
            artistId=artistId,
            includeUnpublished=includeUnpublished,
            state=st,
            published_from=dt_from,
            published_to=dt_to,
            genre=genre,
        )

        user_country = user.get("country")
        is_backoffice = user.get("user_type") == "backoffice"

        accessible_collections = []
        for c in collections:
            if not _can_access_collection(user, c):
                continue

            if not includeUnpublished:
                eff = calculate_effective_state(c, user_country)
                if not is_backoffice and eff != "publicado":
                    if user.get("user_id") != c.get("artistId"):
                        continue

            accessible_collections.append(c)

        logger.info(
            f"Filtered {len(collections)} collections to {len(accessible_collections)} based on restrictions/state"
        )

        serialized_collections = []
        for c in accessible_collections:
            songs = await collections_db.get_songs_from_collection(c["_id"])
            serialized_collections.append(serialize_collection(c, songs, user_country))

        return {"data": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise


@router.post("/{collection_id}/publish", status_code=200)
async def publish_collection(collection_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Publishing collection {collection_id} by user {user['user_id']}")

    try:
        success, error = await collections_db.publish_collection_now(collection_id, user["user_id"])

        if not success:
            if error == "Collection not found":
                return JSONResponse(
                    status_code=404,
                    content=create_error_response(404, "Not Found", error, f"/collections/{collection_id}/publish"),
                )
            elif error == "You are not authorized to publish this collection":
                return JSONResponse(
                    status_code=403,
                    content=create_error_response(403, "Forbidden", error, f"/collections/{collection_id}/publish"),
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(400, "Bad Request", error, f"/collections/{collection_id}/publish"),
                )

        collection = await collections_db.get_collection(collection_id, includeUnpublished=False)
        songs = await collections_db.get_songs_from_collection(collection["_id"])

        logger.info(f"Successfully published collection {collection_id}")
        return {"data": serialize_collection(collection, songs, user.get("country"))}

    except Exception as e:
        logger.error(f"Failed to publish collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(500, "Internal Server Error", str(e), f"/collections/{collection_id}/publish"),
        )


@router.get("/{collection_id}/early-releases", status_code=200)
async def get_collection_early_releases(collection_id: str, user: dict = Depends(verify_token)):
    logger.info(f"Fetching early releases for collection {collection_id}")
    try:
        collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        if not collection:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found",
                    f"/collections/{collection_id}/early-releases",
                ),
            )

        songs = await collections_db.get_songs_from_collection(collection["_id"], include_unreleased=False)

        return {
            "data": {
                "collectionId": str(collection["_id"]),
                "collectionName": collection["name"],
                "releaseDate": collection.get("releaseDate"),
                "earlyReleasedSongs": [
                    {
                        "id": str(song["_id"]),
                        "title": song["title"],
                        "artist": song["artist"],
                        "duration": song.get("duration", "0"),
                        "order": song["order"],
                        "earlyReleaseDate": song.get("early_release_date"),
                    }
                    for song in songs
                ],
            }
        }

    except Exception as e:
        logger.error(f"Failed to fetch early releases: {str(e)}")
        raise


@router.get("/{collection_id}", status_code=200)
async def get_collection(collection_id: str, includeUnpublished: bool = False, user: dict = Depends(verify_token)):
    logger.info(f"Fetching collection collection_id={collection_id}, includeUnpublished={includeUnpublished}")
    try:
        collection = await collections_db.get_collection(collection_id, includeUnpublished=includeUnpublished)
        if not collection:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found or not yet released",
                    f"/collections/{collection_id}",
                ),
            )

        user_country = user.get("country")
        effective_state = calculate_effective_state(collection, user_country)

        if not includeUnpublished:
            if effective_state not in ("publicado",):
                if user.get("user_type") != "backoffice" and user.get("user_id") != collection.get("artistId"):
                    return JSONResponse(
                        status_code=404,
                        content=create_error_response(
                            404,
                            "Not Found",
                            f"Collection with id {collection_id} not found or not yet released",
                            f"/collections/{collection_id}",
                        ),
                    )

        if not _can_access_collection(user, collection):
            logger.warning(
                f"User from {user.get('country', 'unknown')} attempted to access collection {collection_id} not available in their region"
            )
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "This collection is not available in your region",
                    f"/collections/{collection_id}",
                ),
            )

        songs = await collections_db.get_songs_from_collection(collection["_id"])
        return {"data": serialize_collection(collection, songs, user_country)}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise


@router.put("/{collection_id}/publication-window", status_code=200)
async def configure_publication_window(
    collection_id: str,
    window_request: schemas.PublicationWindowRequest,
    user: dict = Depends(verify_token),
):
    logger.info(f"Configuring publication window for collection {collection_id} by user {user['user_id']}")

    try:
        collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        if not collection:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found",
                    f"/collections/{collection_id}/publication-window",
                ),
            )

        if not is_authorized(user, collection["artistId"]):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to configure publication window for this collection",
                    f"/collections/{collection_id}/publication-window",
                ),
            )

        success, error = await collections_db.configure_publication_window(
            collection_id=collection_id,
            release_date=window_request.releaseDate,
            no_disponible_desde=window_request.noDisponibleDesde,
            no_disponible_hasta=window_request.noDisponibleHasta,
            user_id=user["user_id"],
        )

        if not success:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    error or "Failed to configure publication window",
                    f"/collections/{collection_id}/publication-window",
                ),
            )

        updated_collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        songs = await collections_db.get_songs_from_collection(collection_id)

        logger.info(f"Successfully configured publication window for collection {collection_id}")
        return {"data": serialize_collection(updated_collection, songs, user.get("country"))}

    except Exception as e:
        logger.error(f"Failed to configure publication window for collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collections/{collection_id}/publication-window",
            ),
        )


@router.post("/{collection_id}/admin-block", status_code=200)
async def set_admin_block(
    collection_id: str,
    req: AdminBlockRequest,
    user: dict = Depends(verify_token),
):
    """
    Bloquear o desbloquear una colección como administrador, con alcance + motivo.

    CA1: en bloqueo requiere scope (global/regions) y reasonCode (y regions si scope=regions)
    CA4: auditoría usuario/timestamp/alcance/motivo
    """
    logger.info(
        f"Setting admin block for collection {collection_id} to {req.blocked} by user {user.get('user_id')}"
    )

    if user.get("user_type") != "backoffice":
        return JSONResponse(
            status_code=403,
            content=create_error_response(
                403,
                "Forbidden",
                "Only backoffice users can set admin blocks",
                f"/collections/{collection_id}/admin-block",
            ),
        )

    if req.blocked:
        if not req.scope or not req.reasonCode:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "scope and reasonCode are required when blocking",
                    f"/collections/{collection_id}/admin-block",
                ),
            )
        if req.scope == "regions":
            if not req.regions or len(req.regions) == 0:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400,
                        "Bad Request",
                        "regions is required when scope=regions",
                        f"/collections/{collection_id}/admin-block",
                    ),
                )
            ok, msg = validate_country_codes(req.regions)
            if not ok:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400,
                        "Bad Request",
                        f"regions: {msg}",
                        f"/collections/{collection_id}/admin-block",
                    ),
                )

    try:
        success, error = await collections_db.set_admin_block(
            collection_id=collection_id,
            blocked=req.blocked,
            scope=req.scope,
            regions=req.regions,
            reason_code=req.reasonCode,
            user_id=user["user_id"],
        )

        if not success:
            if error == "Collection not found":
                return JSONResponse(
                    status_code=404,
                    content=create_error_response(
                        404,
                        "Not Found",
                        error,
                        f"/collections/{collection_id}/admin-block",
                    ),
                )
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    error or "Failed to update collection",
                    f"/collections/{collection_id}/admin-block",
                ),
            )

        collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        songs = await collections_db.get_songs_from_collection(collection_id)

        logger.info(
            f"Successfully {'blocked' if req.blocked else 'unblocked'} collection {collection_id}"
        )
        return {"data": serialize_collection(collection, songs, user.get("country"))}

    except Exception as e:
        logger.error(f"Failed to set admin block for collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collections/{collection_id}/admin-block",
            ),
        )


@router.get("/{collection_id}/audit", status_code=200)
async def get_collection_audit_history(
    collection_id: str,
    limit: int = 10,
    user: dict = Depends(verify_token),
):
    """
    Obtener el historial de cambios de auditoría de una colección.
    """
    logger.info(f"Fetching audit history for collection {collection_id} (limit={limit})")

    try:
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 10

        collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        if not collection:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Collection with id {collection_id} not found",
                    f"/collections/{collection_id}/audit",
                ),
            )

        if not is_authorized(user, collection["artistId"]):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to view audit history for this collection",
                    f"/collections/{collection_id}/audit",
                ),
            )

        audit_entries = await audit_db.get_collection_audit_log(collection_id, limit=limit)

        serialized_entries = []
        for entry in (audit_entries or []):
            serialized_entry = {
                "id": str(entry.get("_id")),
                "collectionId": str(entry.get("collection_id")),
                "userId": entry.get("user_id"),
                "action": entry.get("action"),
                "timestamp": entry.get("timestamp").isoformat() if entry.get("timestamp") else None,
            }

            if entry.get("previous_state") or entry.get("new_state"):
                serialized_entry["stateChange"] = {
                    "previous": entry.get("previous_state"),
                    "new": entry.get("new_state"),
                }

            publication_changes = {}
            if entry.get("previous_release_date") or entry.get("new_release_date"):
                publication_changes["releaseDate"] = {
                    "previous": entry.get("previous_release_date").isoformat() if entry.get("previous_release_date") else None,
                    "new": entry.get("new_release_date").isoformat() if entry.get("new_release_date") else None,
                }
            if entry.get("previous_no_disponible_desde") or entry.get("new_no_disponible_desde"):
                publication_changes["noDisponibleDesde"] = {
                    "previous": entry.get("previous_no_disponible_desde").isoformat() if entry.get("previous_no_disponible_desde") else None,
                    "new": entry.get("new_no_disponible_desde").isoformat() if entry.get("new_no_disponible_desde") else None,
                }
            if entry.get("previous_no_disponible_hasta") or entry.get("new_no_disponible_hasta"):
                publication_changes["noDisponibleHasta"] = {
                    "previous": entry.get("previous_no_disponible_hasta").isoformat() if entry.get("previous_no_disponible_hasta") else None,
                    "new": entry.get("new_no_disponible_hasta").isoformat() if entry.get("new_no_disponible_hasta") else None,
                }
            if entry.get("previous_bloqueado_admin") is not None or entry.get("new_bloqueado_admin") is not None:
                publication_changes["bloqueadoAdmin"] = {
                    "previous": entry.get("previous_bloqueado_admin"),
                    "new": entry.get("new_bloqueado_admin"),
                }

            if publication_changes:
                serialized_entry["publicationChanges"] = publication_changes

            if entry.get("metadata"):
                serialized_entry["metadata"] = entry.get("metadata")

            serialized_entries.append(serialized_entry)

        logger.info(f"Retrieved {len(serialized_entries)} audit entries for collection {collection_id}")
        return {
            "data": {
                "collectionId": collection_id,
                "collectionName": collection.get("name"),
                "auditHistory": serialized_entries,
            }
        }

    except Exception as e:
        logger.error(f"Failed to fetch audit history for collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collections/{collection_id}/audit",
            ),
        )


@router.post("/auto-activate", status_code=200)
async def auto_activate_collections():
    """
    Activar automáticamente colecciones programadas que han alcanzado su fecha de lanzamiento.
    """
    try:
        activated_count, errors = await collections_db.auto_activate_scheduled_collections()
        return {
            "data": {
                "activatedCount": activated_count,
                "errors": errors,
                "success": len(errors) == 0,
            }
        }

    except Exception as e:
        logger.error(f"Failed to auto-activate collections: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(500, "Internal Server Error", str(e), "/collections/auto-activate"),
        )
