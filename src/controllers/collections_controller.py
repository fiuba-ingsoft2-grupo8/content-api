import databases.storage_database as storage_db
import databases.collections_database as collections_db
import databases.preferences_database as preferences_db
import databases.audit_database as audit_db
import schemas
from schemas import AdminBlockRequest
from fastapi import Depends
from auth import verify_token, is_authorized
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from resources.logger import logger
from common.utils import create_error_response, serialize_collection
from common.countries import validate_country_codes, calculate_available_countries
from fastapi import UploadFile, File, Form
from datetime import datetime, timezone
from databases.collection_states import calculate_effective_state, is_collection_playable

router = APIRouter()


def _can_access_collection(user: dict, collection: dict) -> bool:
    """
    Check if a user can access a collection based on geographical restrictions.
    
    Returns True if:
    - User is backoffice
    - User is the owner of the collection
    - User's country is in the collection's availableCountries list
    
    Args:
        user: User dictionary from verify_token
        collection: Collection document from database
        
    Returns:
        bool: True if user can access, False otherwise
    """
    # Backoffice users can access all collections
    if user.get("user_type") == "backoffice":
        return True
    
    # Owner can access their own collections
    if user.get("user_id") == collection.get("artistId"):
        return True
    
    # Check geographical restrictions
    user_country = user.get("country", "")
    available_countries = collection.get("availableCountries", [])
    
    # If no restrictions, available everywhere
    if not available_countries:
        return True
    
    # Check if user's country is in the available list
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
async def upload_collection_cover(collection_id: str, file: UploadFile = File(...), user: dict = Depends(verify_token)):
    """
    Subir una imagen de portada para una colección.
    
    Este endpoint permite subir y actualizar la imagen de portada (cover) de una colección
    (álbum, EP o single). La imagen se sube al almacenamiento de Supabase y se actualiza
    la URL de la portada en la base de datos.
    
    **Parámetros:**
    - collection_id: ID de la colección a la que se le subirá la portada
    - file: Archivo de imagen a subir
    
    **Autorización:**
    - Solo el artista dueño de la colección o usuarios backoffice pueden subir portadas
    
    **Retorna:**
    - 201: Portada subida y actualizada exitosamente
    - 401: No autorizado para modificar esta colección
    - 404: Colección no encontrada
    - 500: Error interno del servidor
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
                    f"/collection/{collection_id}/upload-cover"
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
                f"/collection/{collection_id}/upload-cover"
            ),
        )

@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Collection created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "id": "507f1f77bcf86cd799439011",
                            "name": "Clics Modernos",
                            "artistId": "artist_123",
                            "artistName": "Charly García",
                            "type": "album",
                            "genre": "Rock",
                            "coverUrl": "https://example.com/cover.jpg",
                            "releaseDate": "2025-12-01T00:00:00Z",
                            "songs": []
                        }
                    }
                }
            }
        }
    }
)
async def create_collection(collection: schemas.CreateCollectionRequest, user: dict = Depends(verify_token)):
    """
    Crear una nueva colección (álbum, EP o single).
    
    Este endpoint permite a un artista crear una nueva colección musical. Una colección agrupa
    canciones bajo un lanzamiento común y puede ser de tipo álbum, EP o single. Se puede especificar
    una fecha de lanzamiento futura para programar publicaciones, así como releases anticipados de canciones individuales.
    También se puede configurar una ventana de disponibilidad (no-disponible) al momento de la creación.
    
    **Información requerida:**
    - name: Nombre de la colección
    - type: Tipo de colección (album, single, ep)
    - genre: Género musical
    - releaseDate: Fecha de lanzamiento (puede ser futura para programar)
    - songs: Lista de canciones con sus respectivas fechas de early release (opcional)
    - credits: Créditos de producción, colaboradores, etc. (opcional)
    - noDisponibleDesde: Inicio de ventana no-disponible (opcional)
    - noDisponibleHasta: Fin de ventana no-disponible (opcional)
    
    **Validaciones:**
    - El usuario debe ser un artista (tener stage_name)
    - Las canciones especificadas deben existir
    - Si se proporcionan noDisponibleDesde y noDisponibleHasta, noDisponibleDesde debe ser anterior a noDisponibleHasta
    
    **Comportamiento:**
    - Si releaseDate > ahora: estado efectivo = "programado"
    - Si releaseDate <= ahora: estado efectivo = "publicado" (si no hay otros bloqueos)
    - Si noDisponibleDesde <= ahora <= noDisponibleHasta: estado efectivo = "no-disponible-region"
    - El estado efectivo se calcula y se registra en auditoría al crear la colección
    
    **Retorna:**
    - 201: Colección creada exitosamente con la lista de canciones
    - 400: Datos inválidos o usuario no es artista
    """
    logger.info(
        f"Creating collection {collection.name}"
    )

    if user["stage_name"] == "":
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", "User is not an artist", "/collections"),
        )

    try:
        # Validate country codes if provided
        if collection.availableInCountries:
            is_valid, error_msg = validate_country_codes(collection.availableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(400, "Bad Request", f"availableInCountries: {error_msg}", "/collections"),
                )
        
        if collection.notAvailableInCountries:
            is_valid, error_msg = validate_country_codes(collection.notAvailableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(400, "Bad Request", f"notAvailableInCountries: {error_msg}", "/collections"),
                )
        
        # Calculate final list of available countries
        available_countries = calculate_available_countries(
            collection.availableInCountries,
            collection.notAvailableInCountries
        )
        logger.info(f"Collection will be available in {len(available_countries)} countries")
        
        # Validate no-disponible window if provided
        if collection.noDisponibleDesde and collection.noDisponibleHasta:
            if collection.noDisponibleDesde >= collection.noDisponibleHasta:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(400, "Bad Request", "noDisponibleDesde must be before noDisponibleHasta", "/collections"),
                )
        
        # uploaded_file = await storage_db.upload_cover_image(collection.artistId, collection.type, file)
        collection_type = collection.type.value if hasattr(collection.type, 'value') else collection.type
        
        # Prepare songs with early release info
        songs_with_early = [
            {
                "songId": song.songId,
                "earlyReleaseDate": song.earlyReleaseDate
            }
            for song in collection.songs
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
            user["user_id"]
        )
        if not db_collection:
            return JSONResponse(
                status_code=400,
                content=create_error_response(400, "Bad Request", str(e), "/collections"),
            )

        songs = await collections_db.get_songs_from_collection(db_collection['_id'])
        return {"data": serialize_collection(db_collection, songs)}
    except Exception as e:
        logger.error(f"Failed to create collection {collection.name}: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=create_error_response(400, "Bad Request", str(e), "/collections"),
        )


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, user: dict = Depends(verify_token)):
    """
    Eliminar una colección permanentemente.
    
    Este endpoint permite eliminar una colección completa de la base de datos.
    La eliminación es permanente y también elimina las relaciones de la colección
    con sus canciones, aunque las canciones en sí mismas no se eliminan.
    
    **Parámetros:**
    - collection_id: ID de la colección a eliminar
    
    **Autorización:**
    - Solo el artista dueño de la colección o usuarios backoffice pueden eliminarla
    
    **Retorna:**
    - 204: Colección eliminada exitosamente (sin contenido)
    - 403: No autorizado para eliminar esta colección
    - 404: Colección no encontrada
    """
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
    
    # Verify user is the owner of the collection or is backoffice
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
async def update_collection(collection_id: str, update_request: schemas.UpdateCollectionRequest, user: dict = Depends(verify_token)):
    """
    Actualizar la información de una colección existente.
    
    Este endpoint permite modificar los metadatos de una colección (nombre, tipo, género, portada, créditos)
    así como actualizar la lista de canciones y su orden. Solo se actualizan los campos proporcionados,
    los campos omitidos permanecen sin cambios.
    
    **Campos actualizables:**
    - name: Nombre de la colección
    - type: Tipo (album, single, ep)
    - genre: Género musical
    - coverUrl: URL de la portada
    - credits: Información de créditos
    - songs: Lista completa de canciones con orden y fechas de early release
    
    **Autorización:**
    - Solo el artista dueño o usuarios backoffice pueden actualizar colecciones
    
    **Nota:** Si se proporciona una nueva lista de canciones, reemplaza completamente la lista anterior.
    
    **Retorna:**
    - 200: Colección actualizada exitosamente
    - 403: No autorizado para actualizar esta colección
    - 404: Colección no encontrada
    - 500: Error interno del servidor
    """
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
        
        # Verify user is the owner of the collection or is backoffice
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
        
        # Validate country codes if provided
        if update_request.availableInCountries is not None:
            is_valid, error_msg = validate_country_codes(update_request.availableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(400, "Bad Request", f"availableInCountries: {error_msg}", f"/collections/{collection_id}"),
                )
        
        if update_request.notAvailableInCountries is not None:
            is_valid, error_msg = validate_country_codes(update_request.notAvailableInCountries)
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(400, "Bad Request", f"notAvailableInCountries: {error_msg}", f"/collections/{collection_id}"),
                )
        
        # Calculate available countries if any country field is provided
        available_countries = None
        if update_request.availableInCountries is not None or update_request.notAvailableInCountries is not None:
            available_countries = calculate_available_countries(
                update_request.availableInCountries,
                update_request.notAvailableInCountries
            )
            logger.info(f"Updating collection {collection_id} to be available in {len(available_countries)} countries")
        
        # Build update dictionary with only provided fields
        update_data = {}
        if update_request.name is not None:
            update_data["name"] = update_request.name
        if update_request.type is not None:
            update_data["type"] = update_request.type.value if hasattr(update_request.type, 'value') else update_request.type
        if update_request.genre is not None:
            update_data["genre"] = update_request.genre
        if update_request.coverUrl is not None:
            update_data["coverUrl"] = update_request.coverUrl
        if update_request.credits is not None:
            update_data["credits"] = update_request.credits
        if available_countries is not None:
            update_data["availableCountries"] = available_countries
        
        # Update collection metadata if there are fields to update
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
        
        # Update songs if provided
        if update_request.songs is not None:
            await collections_db.delete_songs_from_collection(collection_id)
            order = 0
            for song_info in update_request.songs:
                if not await collections_db.add_song_to_collection(song_info.songId, collection_id, order, song_info.earlyReleaseDate):
                    logger.error(f"Failed to add song {song_info.songId} to collection")
                order += 1
        
        # Get updated collection with songs
        collection = await collections_db.get_collection(collection_id)
        songs = await collections_db.get_songs_from_collection(collection_id)

        return {"data": serialize_collection(collection, songs)}

    except Exception as e:
        logger.error(f"Failed to update collection: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collections/{collection_id}",
            ),
        )


@router.get(
    "/recommended",
    responses={
        200: {
            "description": "Album recommendations based on user preferences",
            "content": {
                "application/json": {
                    "example": {
                        "albums": ["id1", "id2", "id3"]
                    }
                }
            }
        }
    }
)

async def get_album_recommendations(n: int = 10, user: dict = Depends(verify_token)):
    user_id = user["user_id"]

    genres = await preferences_db.get_user_genres(user_id) or []
    artists = await preferences_db.get_user_artists(user_id) or []

    if len(genres) == 0 and len(artists) == 0:
        popular = await collections_db.get_most_popular_albums_overall(n)
        return {
            "albums": [
                serialize_collection(a, a.get("songs", []))
                for a in popular
            ]
        }

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

    serialized = [
        serialize_collection(a, a.get("songs", []))
        for a in final_list
    ]

    logger.info(f"Generated {len(serialized)} recommendations for user {user_id}")
    return {"albums": serialized}


@router.get("/popular/{artistId}", status_code=200)
async def get_popular_collections(artistId: str, limit: int = 50, type: str = None, includeUnpublished: bool = False, user: dict = Depends(verify_token)):
    """
    Obtener las colecciones de un artista ordenadas por popularidad.
    
    Este endpoint retorna las colecciones de un artista específico ordenadas por popularidad,
    determinada por la cantidad de reproducciones totales de las canciones en cada colección.
    Es útil para mostrar el contenido más popular de un artista.
    
    **Parámetros de ruta:**
    - artistId: ID del artista (requerido)
    
    **Parámetros de consulta:**
    - limit: Número máximo de colecciones a retornar (por defecto: 50, máximo: 100)
    - type: Filtro opcional por tipo de colección (album, single, ep)
    - includeUnpublished: Incluir colecciones no publicadas aún (por defecto: False)
    
    **Nota:** Las colecciones incluyen todas sus canciones con detalles completos.
    
    **Retorna:**
    - 200: Lista de colecciones ordenadas por popularidad
    """
    logger.info(f"Fetching popular collections for artist {artistId} (limit={limit}, type={type}, includeUnpublished={includeUnpublished})")
    
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 10
    
    try:
        collections = await collections_db.get_popular_collections(artistId=artistId, limit=limit, type=type, includeUnpublished=includeUnpublished)
        
        # Filter collections by geographical access and admin block
        # CA 2: bloqueado-admin collections should NOT appear in Popular
        is_backoffice = user.get("user_type") == "backoffice"
        accessible_collections = [
            collection for collection in collections 
            if _can_access_collection(user, collection) and (is_backoffice or not collection.get("bloqueadoAdmin", False))
        ]
        logger.info(f"Filtered {len(collections)} popular collections to {len(accessible_collections)} based on geographical restrictions and admin blocks")
        
        serialized_collections = []
        for collection in accessible_collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, collection, songs))
        return {"data": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch popular collections: {str(e)}")
        raise


@router.get(
    "/",
    status_code=200,
    responses={
        200: {
            "description": "List of collections",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "507f1f77bcf86cd799439011",
                                "name": "Clics Modernos",
                                "artistId": "artist_123",
                                "artistName": "Charly García",
                                "type": "album",
                                "genre": "Rock",
                                "coverUrl": "https://example.com/cover.jpg",
                                "releaseDate": "1983-11-11T00:00:00Z",
                                "songs": []
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_collections(
    type: str = None,
    artistId: str = None,
    includeUnpublished: bool = False,
    # nuevos filtros catálogo:
    state: str | None = None,          # "Publicado" | "Programado"
    publishedFrom: str | None = None,  # ISO date/datetime -> sobre releaseDate
    publishedTo: str | None = None,    # ISO date/datetime
    genre: str | None = None, 
    user: dict = Depends(verify_token),
):
    """
    Obtener colecciones con filtros avanzados de catálogo.
    
    Este endpoint permite buscar y filtrar colecciones musicales (álbumes, EPs, singles)
    con diversos criterios. Es especialmente útil para pantallas de catálogo y administración
    de contenido, permitiendo filtrar por estado de publicación, fechas y tipo.
    
    **Parámetros de consulta:**
    - type: Filtrar por tipo de colección (album, single, ep)
    - artistId: Filtrar por artista específico
    - includeUnpublished: Incluir colecciones no publicadas (por defecto: False)
    - state: Estado de la colección - "Publicado" (ya lanzado) o "Programado" (lanzamiento futuro)
    - publishedFrom: Fecha inicial del rango de publicación (formato ISO date/datetime)
    - publishedTo: Fecha final del rango de publicación (formato ISO date/datetime)
    
    **Comportamiento:**
    - Sin filtros: retorna todas las colecciones publicadas
    - Con state="Publicado": colecciones con releaseDate <= ahora
    - Con state="Programado": colecciones con releaseDate > ahora
    - Los filtros de fecha aplican sobre releaseDate
    
    **Retorna:**
    - 200: Lista de colecciones que cumplen los criterios, cada una con sus canciones
    """
    st = (state or "").strip().lower()
    if st not in ("", "publicado", "programado"):
        st = ""

    dt_from = _parse_iso(publishedFrom)
    dt_to = _parse_iso(publishedTo)

    logger.info(f"Fetching collections (type={type}, artistId={artistId}, includeUnpublished={includeUnpublished}, state={st}, from={dt_from}, to={dt_to})")
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
        
        # Filter collections by geographical access and effective state
        user_country = user.get("country")
        is_backoffice = user.get("user_type") == "backoffice"
        
        accessible_collections = []
        for collection in collections:
            # Check geographical access
            if not _can_access_collection(user, collection):
                continue
            
            # Check effective state if not including unpublished
            if not includeUnpublished:
                effective_state = calculate_effective_state(collection, user_country)
                # Only show published collections to regular users
                if not is_backoffice and effective_state != "publicado":
                    # Allow owner to see their own collections
                    if user.get("user_id") != collection.get("artistId"):
                        continue
            
            accessible_collections.append(collection)
        
        logger.info(f"Filtered {len(collections)} collections to {len(accessible_collections)} based on geographical restrictions and effective state")
        
        serialized_collections = []
        for collection in accessible_collections:
            songs = await collections_db.get_songs_from_collection(collection["_id"])
            serialized_collections.append(serialize_collection(collection, collection, songs))
        return {"data": serialized_collections}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise


@router.post("/{collection_id}/publish", status_code=200)
async def publish_collection(collection_id: str, user: dict = Depends(verify_token)):
    """
    Publicar inmediatamente una colección no publicada.
    
    Este endpoint permite publicar una colección que estaba programada para lanzamiento futuro
    o que aún no tenía fecha de publicación. Al publicarla, se establece la fecha de lanzamiento
    (releaseDate) al momento actual, haciendo la colección visible públicamente.
    
    **Parámetros de ruta:**
    - collection_id: ID de la colección a publicar
    
    **Validaciones:**
    - La colección debe pertenecer al artista que hace la solicitud
    - La colección no debe estar ya publicada (releaseDate debe ser futura o null)
    
    **Retorna:**
    - 200: Colección publicada exitosamente con la información actualizada
    - 400: La colección ya está publicada
    - 403: No autorizado para publicar esta colección
    - 404: Colección no encontrada
    - 500: Error interno del servidor
    """
    logger.info(f"Publishing collection {collection_id} by user {user['user_id']}")
    
    try:
        success, error = await collections_db.publish_collection_now(collection_id, user["user_id"])
        
        if not success:
            if error == "Collection not found":
                return JSONResponse(
                    status_code=404,
                    content=create_error_response(
                        404,
                        "Not Found",
                        error,
                        f"/collections/{collection_id}/publish",
                    ),
                )
            elif error == "You are not authorized to publish this collection":
                return JSONResponse(
                    status_code=403,
                    content=create_error_response(
                        403,
                        "Forbidden",
                        error,
                        f"/collections/{collection_id}/publish",
                    ),
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(
                        400,
                        "Bad Request",
                        error,
                        f"/collections/{collection_id}/publish",
                    ),
                )
        
        # Get the published collection with its songs
        collection = await collections_db.get_collection(collection_id, includeUnpublished=False)
        songs = await collections_db.get_songs_from_collection(collection["_id"])
        
        logger.info(f"Successfully published collection {collection_id}")
        return {"data": serialize_collection(collection, songs)}
        
    except Exception as e:
        logger.error(f"Failed to publish collection {collection_id}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                f"/collections/{collection_id}/publish",
            ),
        )


@router.get("/{collection_id}/early-releases", status_code=200)
async def get_collection_early_releases(collection_id: str, user: dict = Depends(verify_token)):
    """
    Obtener las canciones lanzadas anticipadamente de una colección.
    
    Este endpoint retorna las canciones de una colección que han sido lanzadas como singles
    o previews antes del lanzamiento completo del álbum o EP. Es útil para mostrar qué canciones
    de un próximo lanzamiento ya están disponibles para escuchar.
    
    **Parámetros de ruta:**
    - collection_id: ID de la colección
    
    **Comportamiento:**
    - Solo retorna canciones con earlyReleaseDate <= ahora
    - La colección principal puede estar aún no publicada
    - Útil para mostrar "singles del álbum" o "adelantos"
    
    **Retorna:**
    - 200: Lista de canciones lanzadas anticipadamente con sus detalles
    - 404: Colección no encontrada
    """
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
        
        # Get only early released songs
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
                        "earlyReleaseDate": song.get("early_release_date")
                    }
                    for song in songs
                ]
            }
        }

    except Exception as e:
        logger.error(f"Failed to fetch early releases: {str(e)}")
        raise


@router.get("/{collection_id}", status_code=200)
async def get_collection(collection_id: str, includeUnpublished: bool = False, user: dict = Depends(verify_token)):
    """
    Obtener una colección específica por su ID.
    
    Este endpoint retorna toda la información de una colección incluyendo sus metadatos
    (nombre, artista, tipo, género, portada, fecha de lanzamiento) y la lista completa
    de canciones en su orden original.
    
    **Parámetros de ruta:**
    - collection_id: ID de la colección
    
    **Parámetros de consulta:**
    - includeUnpublished: Si es true, permite ver colecciones no publicadas aún (por defecto: False)
    
    **Comportamiento:**
    - Por defecto solo retorna colecciones ya publicadas (releaseDate <= ahora)
    - Con includeUnpublished=true muestra también colecciones programadas para futuro
    
    **Retorna:**
    - 200: Información completa de la colección con todas sus canciones
    - 404: Colección no encontrada o no publicada aún
    """
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
        
        # Check geographical access and effective state
        user_country = user.get("country")
        effective_state = calculate_effective_state(collection, user_country)
        
        # If not including unpublished, check if collection is effectively published
        if not includeUnpublished:
            if effective_state not in ("publicado",):
                # Allow backoffice and owner to see even if not published
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
        
        # Check geographical access
        if not _can_access_collection(user, collection):
            logger.warning(f"User from {user.get('country', 'unknown')} attempted to access collection {collection_id} not available in their region")
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

        return {"data": serialize_collection(collection, songs)}

    except Exception as e:
        logger.error(f"Failed to fetch collections: {str(e)}")
        raise

@router.put("/{collection_id}/publication-window", status_code=200)
async def configure_publication_window(
    collection_id: str,
    window_request: schemas.PublicationWindowRequest,
    user: dict = Depends(verify_token)
):
    """
    Configurar ventana de publicación para una colección.
    
    Este endpoint permite configurar la política de publicación que determina
    el estado No-disponible y/o Programado de una colección.
    
    **Parámetros:**
    - releaseDate: Fecha/hora de lanzamiento con zona horaria (opcional)
    - noDisponibleDesde: Inicio de ventana no-disponible (opcional)
    - noDisponibleHasta: Fin de ventana no-disponible (opcional)
    
    **Comportamiento:**
    - Si releaseDate > ahora: estado efectivo = "programado"
    - Si releaseDate <= ahora: estado efectivo = "publicado" (si no hay otros bloqueos)
    - Si noDisponibleDesde <= ahora <= noDisponibleHasta: estado efectivo = "no-disponible-region"
    - El estado efectivo se recalcula inmediatamente y se registra en auditoría
    
    **Autorización:**
    - Solo el artista dueño o usuarios backoffice pueden configurar la ventana
    
    **Retorna:**
    - 200: Ventana de publicación configurada exitosamente
    - 403: No autorizado
    - 404: Colección no encontrada
    - 400: Datos inválidos (ej: noDisponibleDesde >= noDisponibleHasta)
    """
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
        
        # Verify authorization
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
        
        # Configure publication window
        success, error = await collections_db.configure_publication_window(
            collection_id=collection_id,
            release_date=window_request.releaseDate,
            no_disponible_desde=window_request.noDisponibleDesde,
            no_disponible_hasta=window_request.noDisponibleHasta,
            user_id=user["user_id"]
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
        
        # Get updated collection
        updated_collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        songs = await collections_db.get_songs_from_collection(collection_id)
        
        logger.info(f"Successfully configured publication window for collection {collection_id}")
        return {"data": serialize_collection(updated_collection, songs)}
        
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
    block_request: schemas.AdminBlockRequest,
    user: dict = Depends(verify_token)
):
    """
    Bloquear o desbloquear una colección como administrador.
    
    Este endpoint permite a usuarios backoffice bloquear o desbloquear
    una colección con alcance específico (global o por regiones) y motivo.
    
    **Parámetros en el body:**
    - blocked: true para bloquear, false para desbloquear
    - scope: 'global' o 'regions' (requerido al bloquear)
    - regions: lista de códigos de región (requerido si scope es 'regions')
    - reasonCode: código del motivo del bloqueo (requerido al bloquear)
    
    **Comportamiento:**
    - Bloqueado: el ítem no aparece en Popular/Búsqueda/Explorar
    - En Colecciones: visible pero con acciones deshabilitadas e indicador
    - Desbloqueo: revierte el override y aplica disponibilidad vigente
    
    **Prioridad de estados:**
    - Bloqueado-admin tiene la máxima prioridad
    - Incluso si está Publicado, si está bloqueado-admin, no se puede reproducir
    
    **Auditoría:**
    - Se registra usuario, timestamp, alcance y motivo en el historial
    
    **Autorización:**
    - Solo usuarios backoffice pueden bloquear/desbloquear
    
    **Retorna:**
    - 200: Estado de bloqueo actualizado exitosamente
    - 400: Parámetros inválidos
    - 403: No autorizado (no es backoffice)
    - 404: Colección no encontrada
    """
    logger.info(f"Setting admin block for collection {collection_id} to {block_request.blocked} by user {user['user_id']}")
    
    # Verify backoffice access
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

    # Validación CA1
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
        if req.scope == "regions" and (not req.regions or len(req.regions) == 0):
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "regions is required when scope=regions",
                    f"/collections/{collection_id}/admin-block",
                ),
            )

    try:
        success, error = await collections_db.set_admin_block(
            collection_id=collection_id,
            blocked=block_request.blocked,
            user_id=user["user_id"],
            scope=block_request.scope,
            regions=block_request.regions,
            reason_code=block_request.reasonCode
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

        # devolver colección actualizada
        collection = await collections_db.get_collection(collection_id, includeUnpublished=True)
        songs = await collections_db.get_songs_from_collection(collection_id)
        
        logger.info(f"Successfully {'blocked' if block_request.blocked else 'unblocked'} collection {collection_id}")
        return {"data": serialize_collection(collection, songs)}

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
    user: dict = Depends(verify_token)
):
    """
    Obtener el historial de cambios de auditoría de una colección.
    
    Este endpoint retorna los últimos cambios registrados en la auditoría de una colección,
    incluyendo cambios de estado, ediciones de campos, actualizaciones de ventana de publicación,
    cambios en países disponibles, etc.
    
    **Parámetros de ruta:**
    - collection_id: ID de la colección
    
    **Parámetros de consulta:**
    - limit: Número máximo de cambios a retornar (por defecto: 10, máximo: 50)
    
    **Autorización:**
    - Solo el artista dueño o usuarios backoffice pueden ver el historial de auditoría
    
    **Retorna:**
    - 200: Lista de cambios ordenados por fecha (más recientes primero)
    - 403: No autorizado para ver el historial
    - 404: Colección no encontrada
    """
    logger.info(f"Fetching audit history for collection {collection_id} (limit={limit})")
    
    try:
        # Validate limit
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 10
        
        # Get collection to verify access
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
        
        # Verify authorization (owner or backoffice)
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
        
        # Get audit log entries
        audit_entries = await audit_db.get_collection_audit_log(collection_id, limit=limit)
        
        # Serialize audit entries
        serialized_entries = []
        for entry in audit_entries:
            serialized_entry = {
                "id": str(entry["_id"]),
                "collectionId": str(entry["collection_id"]),
                "userId": entry["user_id"],
                "action": entry["action"],
                "timestamp": entry["timestamp"].isoformat() if entry.get("timestamp") else None,
            }
            
            # Add state changes if present
            if entry.get("previous_state") or entry.get("new_state"):
                serialized_entry["stateChange"] = {
                    "previous": entry.get("previous_state"),
                    "new": entry.get("new_state")
                }
            
            # Add publication window changes if present
            publication_changes = {}
            if entry.get("previous_release_date") or entry.get("new_release_date"):
                publication_changes["releaseDate"] = {
                    "previous": entry.get("previous_release_date").isoformat() if entry.get("previous_release_date") else None,
                    "new": entry.get("new_release_date").isoformat() if entry.get("new_release_date") else None
                }
            if entry.get("previous_no_disponible_desde") or entry.get("new_no_disponible_desde"):
                publication_changes["noDisponibleDesde"] = {
                    "previous": entry.get("previous_no_disponible_desde").isoformat() if entry.get("previous_no_disponible_desde") else None,
                    "new": entry.get("new_no_disponible_desde").isoformat() if entry.get("new_no_disponible_desde") else None
                }
            if entry.get("previous_no_disponible_hasta") or entry.get("new_no_disponible_hasta"):
                publication_changes["noDisponibleHasta"] = {
                    "previous": entry.get("previous_no_disponible_hasta").isoformat() if entry.get("previous_no_disponible_hasta") else None,
                    "new": entry.get("new_no_disponible_hasta").isoformat() if entry.get("new_no_disponible_hasta") else None
                }
            if entry.get("previous_bloqueado_admin") is not None or entry.get("new_bloqueado_admin") is not None:
                publication_changes["bloqueadoAdmin"] = {
                    "previous": entry.get("previous_bloqueado_admin"),
                    "new": entry.get("new_bloqueado_admin")
                }
            if publication_changes:
                serialized_entry["publicationChanges"] = publication_changes
            
            # Add metadata if present
            if entry.get("metadata"):
                serialized_entry["metadata"] = entry["metadata"]
            
            serialized_entries.append(serialized_entry)
        
        logger.info(f"Retrieved {len(serialized_entries)} audit entries for collection {collection_id}")
        return {
            "data": {
                "collectionId": collection_id,
                "collectionName": collection.get("name"),
                "auditHistory": serialized_entries
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
    
    Este endpoint debe ser llamado periódicamente (ej: desde un cron job) para activar
    automáticamente las colecciones que han alcanzado su releaseDate.
    
    **Comportamiento:**
    - Busca todas las colecciones con releaseDate <= ahora
    - Que no estén bloqueado-admin
    - Registra el cambio de estado en auditoría
    - El estado efectivo pasa de "programado" a "publicado"
    
    **Autorización:**
    - Solo usuarios backoffice o sistema pueden llamar este endpoint
    - En producción, debería ser llamado por un cron job con token de sistema
    
    **Retorna:**
    - 200: Proceso completado con estadísticas
    """
    
    try:
        activated_count, errors = await collections_db.auto_activate_scheduled_collections()
        
        return {
            "data": {
                "activatedCount": activated_count,
                "errors": errors,
                "success": len(errors) == 0
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to auto-activate collections: {str(e)}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                str(e),
                "/collections/auto-activate",
            ),
        )
