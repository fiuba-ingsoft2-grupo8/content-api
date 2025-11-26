import databases.about_database as about_db
import databases.storage_database as storage_db
from fastapi import Depends, APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
from auth import verify_token, is_authorized
from resources.logger import logger
from common.utils import create_error_response
import schemas
from schemas import ArtistAbout, UpdateArtistAboutRequest
import uuid

router = APIRouter()


def serialize_artist_about(about_doc):
    """Convert MongoDB artist about document to API response format."""
    if not about_doc:
        return None
    
    return {
        "artistId": about_doc.get("artist_id"),
        "artist": about_doc.get("artist"),
        "bio": about_doc.get("bio"),
        "socialMedia": about_doc.get("social_media"),
        "carouselImages": about_doc.get("carousel_images", []),
        "artistPick": about_doc.get("artist_pick")
    }


@router.post("/", status_code=201)
async def create_artist_about(user: dict = Depends(verify_token)):
    """
    Crear una nueva página "About" para el artista autenticado.
    
    Este endpoint inicializa una página de información del artista utilizando el user_id y stage_name
    del token de autenticación. Todos los demás campos (biografía, redes sociales, carousel, artist pick)
    se inicializan como vacíos o nulos y pueden ser completados posteriormente mediante el endpoint de actualización.
    
    **Validaciones:**
    - El usuario debe estar autenticado
    - No puede existir ya una página "About" para este artista (retorna 409 si ya existe)
    
    **Retorna:**
    - 201: Página "About" creada exitosamente
    - 409: Ya existe una página "About" para este artista
    - 500: Error interno del servidor
    """
    try:
        artist_id = user["user_id"]
        artist_name = user["stage_name"]
        
        # Create the artist about page
        about_doc = await about_db.create_artist_about(artist_id, artist_name)
        
        if about_doc is None:
            # Already exists
            return JSONResponse(
                status_code=409,
                content=create_error_response(
                    409,
                    "Conflict",
                    "Artist about page already exists for this artist",
                    "/about"
                )
            )
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "data": serialize_artist_about(about_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating artist about: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while creating the artist about page",
                "/about"
            )
        )


@router.put("/", status_code=200)
async def update_artist_about(
    update_request: UpdateArtistAboutRequest,
    user: dict = Depends(verify_token),
    artist_id: str = Query(None, description="Artist ID to update (backoffice only)")
):
    """
    Actualizar la información de la página "About" de un artista.
    
    Este endpoint permite modificar la biografía, redes sociales, imágenes del carousel y artist pick
    de una página "About" existente. Los usuarios regulares solo pueden actualizar su propia página,
    mientras que los usuarios de backoffice pueden actualizar cualquier página especificando el artist_id.
    
    **Restricciones:**
    - No se pueden modificar los campos artistId ni artist (nombre del artista)
    - Máximo 5 imágenes en el carousel
    - Solo una imagen puede ser marcada como primaria en el carousel
    - La página "About" debe existir previamente (usar POST /about para crearla)
    
    **Autorización:**
    - Usuarios regulares: solo pueden actualizar su propia página
    - Usuarios backoffice: pueden actualizar cualquier página usando el parámetro artist_id
    
    **Retorna:**
    - 200: Página actualizada exitosamente
    - 403: No autorizado para actualizar esta página
    - 404: Página "About" no encontrada
    - 500: Error interno del servidor
    """
    try:
        # Determine target artist_id
        target_artist_id = artist_id if artist_id and user.get("user_type") == "backoffice" else user["user_id"]
        
        # Verify authorization
        if not is_authorized(user, target_artist_id):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to update this artist about page",
                    "/about"
                )
            )
        
        # Convert Pydantic model to dict, excluding None values
        update_data = update_request.model_dump(exclude_none=True)
        
        # Update the artist about page
        about_doc = await about_db.update_artist_about(target_artist_id, update_data)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found. Please create it first using POST /about",
                    "/about"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": serialize_artist_about(about_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error updating artist about: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while updating the artist about page",
                "/about"
            )
        )


@router.get(
    "/{artist_id}",
    status_code=200,
    responses={
        200: {
            "description": "Artist about page information",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "artistId": "artist_123",
                            "artist": "Charly García",
                            "bio": "Músico argentino, pionero del rock nacional.",
                            "socialMedia": {
                                "x": "@charlygarcia",
                                "instagram": "@charlygarcia_oficial"
                            },
                            "carouselImages": [
                                {
                                    "url": "https://example.com/image1.jpg",
                                    "isPrimary": True
                                }
                            ],
                            "artistPick": {
                                "type": "collection",
                                "id": "507f1f77bcf86cd799439011"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_artist_about(artist_id: str):
    """
    Obtener la página "About" de un artista por su ID.
    
    Este endpoint es público y no requiere autenticación. Retorna toda la información
    del perfil del artista incluyendo biografía, redes sociales, galería de imágenes del carousel
    y el contenido destacado por el artista (artist pick).
    
    **Parámetros:**
    - artist_id: ID único del artista
    
    **Retorna:**
    - 200: Información de la página "About" del artista
    - 404: Página "About" no encontrada para este artista
    - 500: Error interno del servidor
    """
    try:
        about_doc = await about_db.get_artist_about_by_id(artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Artist about page not found for artist_id: {artist_id}",
                    f"/about/{artist_id}"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": serialize_artist_about(about_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving artist about: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while retrieving the artist about page",
                f"/about/{artist_id}"
            )
        )


@router.post("/carousel", status_code=201)
async def upload_carousel_image(
    file: UploadFile = File(...),
    user: dict = Depends(verify_token),
    artist_id: str = Query(None, description="Artist ID to upload for (backoffice only)")
):
    """
    Subir una imagen al carousel de la página "About" de un artista.
    
    Este endpoint permite agregar imágenes al carousel (galería de imágenes) de un artista.
    Las imágenes se suben al almacenamiento de Supabase y se agregan a la colección de imágenes del carousel.
    
    **Restricciones:**
    - Máximo 5 imágenes permitidas en el carousel
    - La primera imagen subida se marca automáticamente como primaria
    - La página "About" debe existir previamente
    - Las imágenes se almacenan con el formato: {artist_id}-carousel-{número}
    
    **Autorización:**
    - Usuarios regulares: solo pueden subir a su propio carousel
    - Usuarios backoffice: pueden subir a cualquier carousel especificando el artist_id
    
    **Retorna:**
    - 201: Imagen subida y agregada exitosamente
    - 400: Se alcanzó el límite de 5 imágenes
    - 403: No autorizado para subir imágenes a este carousel
    - 404: Página "About" no encontrada
    - 500: Error interno del servidor
    """
    try:
        # Determine target artist_id
        target_artist_id = artist_id if artist_id and user.get("user_type") == "backoffice" else user["user_id"]
        
        # Verify authorization
        if not is_authorized(user, target_artist_id):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to upload images for this artist",
                    "/about/carousel"
                )
            )
        
        # Get artist's current about page
        about_doc = await about_db.get_artist_about_by_id(target_artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found. Please create it first using POST /about",
                    "/about/carousel"
                )
            )
        
        # Get current carousel images
        current_images = about_doc.get("carousel_images", [])
        
        # Check if we already have 5 images
        if len(current_images) >= 5:
            return JSONResponse(
                status_code=400,
                content=create_error_response(
                    400,
                    "Bad Request",
                    "Maximum of 5 carousel images allowed. Please delete an existing image first.",
                    "/about/carousel"
                )
            )
        
        # Determine image number (1-5) based on current count
        image_number = len(current_images) + 1
        
        # Upload the image to Supabase
        upload_result = await storage_db.upload_carousel_image(target_artist_id, image_number, file)
        image_url = upload_result["imageUrl"]
        
        # Generate unique ID for the image
        image_id = str(uuid.uuid4())
        
        # Determine if this is the primary image (first one)
        is_primary = len(current_images) == 0
        
        # Add the new image to the carousel
        new_image = {
            "id": image_id,
            "url": image_url,
            "isPrimary": is_primary
        }
        current_images.append(new_image)
        
        # Update the about page with the new carousel
        update_data = {
            "carouselImages": current_images
        }
        
        updated_doc = await about_db.update_artist_about(target_artist_id, update_data)
        
        if updated_doc is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to update artist about with new carousel image",
                    "/about/carousel"
                )
            )
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": f"Carousel image uploaded successfully as image #{image_number}",
                "data": {
                    "imageId": image_id,
                    "imageUrl": image_url,
                    "imageNumber": image_number,
                    "isPrimary": is_primary,
                    "totalImages": len(current_images)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error uploading carousel image: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while uploading the carousel image",
                "/about/carousel"
            )
        )


@router.put("/carousel/primary/{image_id}", status_code=200)
async def set_primary_carousel_image(
    image_id: str,
    user: dict = Depends(verify_token),
    artist_id: str = Query(None, description="Artist ID to update (backoffice only)")
):
    """
    Establecer una imagen del carousel como imagen primaria.
    
    Este endpoint permite cambiar cuál imagen del carousel se muestra como principal o destacada.
    Solo puede haber una imagen primaria a la vez, por lo que al establecer una nueva imagen primaria,
    todas las demás imágenes se marcarán automáticamente como no primarias (isPrimary: false).
    
    **Parámetros:**
    - image_id: ID único de la imagen que se quiere establecer como primaria
    
    **Restricciones:**
    - Solo una imagen puede ser primaria a la vez
    - La imagen debe existir en el carousel del artista
    
    **Autorización:**
    - Usuarios regulares: solo pueden modificar su propio carousel
    - Usuarios backoffice: pueden modificar cualquier carousel especificando el artist_id
    
    **Retorna:**
    - 200: Imagen primaria actualizada exitosamente
    - 403: No autorizado para modificar este carousel
    - 404: Página "About" o imagen no encontrada
    - 500: Error interno del servidor
    """
    try:
        # Determine target artist_id
        target_artist_id = artist_id if artist_id and user.get("user_type") == "backoffice" else user["user_id"]
        
        # Verify authorization
        if not is_authorized(user, target_artist_id):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to modify this artist's carousel",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Get artist's current about page
        about_doc = await about_db.get_artist_about_by_id(target_artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Get current carousel images
        current_images = about_doc.get("carousel_images", [])
        
        if not current_images:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "No carousel images found",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Find the image with the given ID
        image_found = False
        updated_images = []
        
        for img in current_images:
            if img.get("id") == image_id:
                image_found = True
                updated_images.append({
                    "id": img["id"],
                    "url": img["url"],
                    "isPrimary": True
                })
            else:
                updated_images.append({
                    "id": img["id"],
                    "url": img["url"],
                    "isPrimary": False
                })
        
        if not image_found:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Carousel image with ID {image_id} not found",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        # Update the about page with the modified carousel
        update_data = {
            "carouselImages": updated_images
        }
        
        updated_doc = await about_db.update_artist_about(target_artist_id, update_data)
        
        if updated_doc is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to update primary image",
                    f"/about/carousel/primary/{image_id}"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Image {image_id} set as primary",
                "data": serialize_artist_about(updated_doc)
            }
        )
        
    except Exception as e:
        logger.error(f"Error setting primary carousel image: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while setting the primary image",
                f"/about/carousel/primary/{image_id}"
            )
        )


@router.delete("/carousel/{image_id}", status_code=200)
async def delete_carousel_image(
    image_id: str,
    user: dict = Depends(verify_token),
    artist_id: str = Query(None, description="Artist ID to delete from (backoffice only)")
):
    """
    Eliminar una imagen del carousel por su ID.
    
    Este endpoint permite remover una imagen específica del carousel de un artista.
    Si la imagen eliminada era la imagen primaria y quedan otras imágenes en el carousel,
    la primera imagen restante se establecerá automáticamente como primaria.
    
    **Parámetros:**
    - image_id: ID único de la imagen a eliminar
    
    **Comportamiento:**
    - Si la imagen eliminada era primaria y hay otras imágenes, la primera se marca como primaria
    - Si era la única imagen, el carousel queda vacío
    
    **Autorización:**
    - Usuarios regulares: solo pueden eliminar de su propio carousel
    - Usuarios backoffice: pueden eliminar de cualquier carousel especificando el artist_id
    
    **Retorna:**
    - 200: Imagen eliminada exitosamente
    - 403: No autorizado para modificar este carousel
    - 404: Página "About" o imagen no encontrada
    - 500: Error interno del servidor
    """
    try:
        # Determine target artist_id
        target_artist_id = artist_id if artist_id and user.get("user_type") == "backoffice" else user["user_id"]
        
        # Verify authorization
        if not is_authorized(user, target_artist_id):
            return JSONResponse(
                status_code=403,
                content=create_error_response(
                    403,
                    "Forbidden",
                    "You are not authorized to modify this artist's carousel",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # Get artist's current about page
        about_doc = await about_db.get_artist_about_by_id(target_artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "Artist about page not found",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # Get current carousel images
        current_images = about_doc.get("carousel_images", [])
        
        if not current_images:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    "No carousel images found",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # Find and remove the image with the given ID
        image_found = False
        was_primary = False
        updated_images = []
        
        for img in current_images:
            if img.get("id") == image_id:
                image_found = True
                was_primary = img.get("isPrimary", False)
                # Don't add this image to updated_images (effectively deleting it)
            else:
                updated_images.append(img)
        
        if not image_found:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Carousel image with ID {image_id} not found",
                    f"/about/carousel/{image_id}"
                )
            )
        
        # If the deleted image was primary and there are remaining images,
        # set the first one as primary
        if was_primary and len(updated_images) > 0:
            updated_images[0]["isPrimary"] = True
        
        # Update the about page with the modified carousel
        update_data = {
            "carouselImages": updated_images
        }
        
        updated_doc = await about_db.update_artist_about(target_artist_id, update_data)
        
        if updated_doc is None:
            return JSONResponse(
                status_code=500,
                content=create_error_response(
                    500,
                    "Internal Server Error",
                    "Failed to delete carousel image",
                    f"/about/carousel/{image_id}"
                )
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Image {image_id} deleted successfully",
                "data": {
                    "deletedImageId": image_id,
                    "remainingImages": len(updated_images),
                    "newPrimarySet": was_primary and len(updated_images) > 0
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error deleting carousel image: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while deleting the carousel image",
                f"/about/carousel/{image_id}"
            )
        )


@router.get(
    "/appears-in/{artist_id}",
    status_code=200,
    responses={
        200: {
            "description": "Collections and playlists where the artist appears",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "collections": [
                                {
                                    "id": "507f1f77bcf86cd799439011",
                                    "name": "Abbey Road",
                                    "artistName": "The Beatles",
                                    "coverUrl": "https://example.com/cover.jpg",
                                    "type": "album",
                                    "year": 1969
                                }
                            ],
                            "playlists": [
                                {
                                    "id": "507f1f77bcf86cd799439012",
                                    "name": "Rock Classics",
                                    "coverUrl": "https://example.com/playlist.jpg",
                                    "type": "playlist",
                                    "year": 2024
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
)
async def get_artist_appears_in(artist_id: str, limit: int = Query(6, ge=4, le=6)):
    """
    Obtener colecciones y playlists donde aparece un artista.
    
    Este endpoint retorna las colecciones (álbumes, EPs, singles) y playlists públicas
    donde el artista aparece, ya sea como artista principal o en los créditos.
    
    **Criterios de Aceptación:**
    
    **CA 1: Fuentes y alcance**
    - Incluye Álbum/EP/Single donde el artista es el principal o está en créditos
    - Incluye Playlists públicas que contengan ≥1 canción del artista
    
    **CA 2: Presentación**
    - Cada ítem muestra: portada, título, chip de tipo (Álbum/EP/Playlist/Single) y año
    
    **CA 3: Cantidad y orden**
    - Retorna 4-6 tarjetas (configurable via query param limit)
    - Releases (Álbum/EP/Single): ordenados por fecha de publicación descendente (más reciente primero),
      desempate alfabético
    - Playlists públicas: ordenadas por popularidad reciente (número de canciones como proxy),
      desempate alfabético
    
    **Parámetros:**
    - artist_id: ID único del artista (user_id)
    - limit: Número de resultados a retornar (entre 4 y 6, por defecto 6)
    
    **Retorna:**
    - 200: Listas de colecciones y playlists donde aparece el artista
    - 404: Artista no encontrado o sin página "About"
    - 500: Error interno del servidor
    """
    try:
        # Get artist about page to get stage name
        about_doc = await about_db.get_artist_about_by_id(artist_id)
        
        if about_doc is None:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Artist about page not found for artist_id: {artist_id}",
                    f"/about/appears-in/{artist_id}"
                )
            )
        
        stage_name = about_doc.get("artist")
        if not stage_name:
            return JSONResponse(
                status_code=404,
                content=create_error_response(
                    404,
                    "Not Found",
                    f"Artist stage name not found for artist_id: {artist_id}",
                    f"/about/appears-in/{artist_id}"
                )
            )
        
        # Get appearances
        appearances = await about_db.get_artist_appearances(artist_id, stage_name, limit)
        
        # Serialize collections
        collections_data = []
        for collection in appearances.get("collections", []):
            release_date = collection.get("releaseDate")
            year = release_date.year if release_date else None
            
            collections_data.append({
                "id": str(collection["_id"]),
                "name": collection.get("name", ""),
                "artistName": collection.get("artistName", ""),
                "coverUrl": collection.get("coverUrl", ""),
                "type": collection.get("type", ""),
                "year": year
            })
        
        # Serialize playlists
        playlists_data = []
        for playlist in appearances.get("playlists", []):
            published_at = playlist.get("published_at")
            year = published_at.year if published_at else None
            
            playlists_data.append({
                "id": str(playlist["_id"]),
                "name": playlist.get("name", ""),
                "coverUrl": playlist.get("coverUrl"),
                "type": "playlist",
                "year": year
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "collections": collections_data,
                    "playlists": playlists_data
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving artist appearances: {e}")
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                500,
                "Internal Server Error",
                "An error occurred while retrieving artist appearances",
                f"/about/appears-in/{artist_id}"
            )
        )

