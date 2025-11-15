from datetime import datetime, timezone
from resources.logger import logger
from db.database import get_db
from bson import ObjectId
from db.models import Share


async def create_share(user_id: str, target_id: str, target_type: str, recipient_id: str = None):
    """
    Crear un registro de compartido para una canción, colección o playlist.
    
    Args:
        user_id: El usuario que está compartiendo
        target_id: El ID del elemento que se está compartiendo (canción, colección o playlist)
        target_type: Tipo de contenido compartido ('song', 'collection', 'playlist')
        recipient_id: Opcional - usuario específico que recibe el share (para shares directos)
        
    Returns:
        (share_dict, error) tupla
    """
    db = get_db()
    try:
        # Validar que el objetivo existe
        if target_type == "song":
            target = db.songs.find_one({"_id": ObjectId(target_id)})
        elif target_type == "collection":
            target = db.collections.find_one({"_id": ObjectId(target_id)})
        elif target_type == "playlist":
            target = db.playlists.find_one({"_id": ObjectId(target_id)})
        else:
            return None, ValueError(f"Invalid target_type: {target_type}")
        
        if not target:
            return None, ValueError(f"{target_type.capitalize()} with id {target_id} not found")
        
        # Crear el registro de compartido
        share = Share(
            user_id=user_id,
            target_id=ObjectId(target_id),
            target_type=target_type
        )
        share_dict = share.model_dump(by_alias=True)
        
        # Agregar recipient_id si se proporciona (para shares directos a amigos)
        if recipient_id:
            share_dict["recipient_id"] = recipient_id
        
        result = db.shares.insert_one(share_dict)
        share_dict["_id"] = result.inserted_id
        
        logger.info(
            f"User {user_id} shared {target_type} {target_id}"
            + (f" with {recipient_id}" if recipient_id else " publicly")
        )
        
        return share_dict, None
        
    except Exception as e:
        logger.error(f"Failed to create share: {str(e)}")
        return None, e


async def get_shares_for_user(user_id: str, limit: int = 50):
    """
    Obtener shares que fueron enviados a un usuario específico.
    Retorna shares ordenados por fecha de creación (más reciente primero).
    
    Args:
        user_id: El ID del usuario para obtener shares
        limit: Número máximo de shares a retornar
        
    Returns:
        Lista de diccionarios de shares
    """
    db = get_db()
    try:
        shares = list(db.shares.find(
            {"recipient_id": user_id}
        ).sort("created_at", -1).limit(limit))
        
        # Convertir ObjectIds a strings
        for share in shares:
            share["_id"] = str(share["_id"])
            share["target_id"] = str(share["target_id"])
        
        return shares
        
    except Exception as e:
        logger.error(f"Failed to get shares for user {user_id}: {str(e)}")
        return []


async def enrich_share_with_details(share: dict):
    """
    Enriquecer un share con detalles sobre el contenido compartido.
    
    Args:
        share: Diccionario de share con user_id, target_id, target_type
        
    Returns:
        Diccionario de share enriquecido con detalles del contenido
    """
    db = get_db()
    try:
        enriched = share.copy()
        target_type = share.get("target_type")
        target_id = share.get("target_id")
        
        # Mapear snake_case a camelCase para consistencia
        if "recipient_id" in share:
            enriched["recipientId"] = share["recipient_id"]
        if "user_id" in share:
            enriched["userId"] = share["user_id"]
        if "target_type" in share:
            enriched["targetType"] = share["target_type"]
        if "target_id" in share:
            enriched["targetId"] = str(share["target_id"])
        if "created_at" in share:
            enriched["createdAt"] = share["created_at"]
        
        if target_type == "song":
            song = db.songs.find_one({"_id": ObjectId(target_id)})
            if song:
                enriched["song"] = {
                    "_id": str(song["_id"]),
                    "title": song.get("title", ""),
                    "artist": song.get("artist", ""),
                    "coverUrl": song.get("coverUrl"),
                    "duration": song.get("duration", "0")
                }
        elif target_type == "collection":
            collection = db.collections.find_one({"_id": ObjectId(target_id)})
            if collection:
                enriched["collection"] = {
                    "_id": str(collection["_id"]),
                    "name": collection.get("name", ""),
                    "artistName": collection.get("artistName", ""),
                    "coverUrl": collection.get("coverUrl"),
                    "type": collection.get("type", "")
                }
        elif target_type == "playlist":
            playlist = db.playlists.find_one({"_id": ObjectId(target_id)})
            if playlist:
                enriched["playlist"] = {
                    "_id": str(playlist["_id"]),
                    "name": playlist.get("name", ""),
                    "description": playlist.get("description", ""),
                    "coverUrl": playlist.get("coverUrl"),
                    "userId": playlist.get("userId", "")
                }
        
        return enriched
        
    except Exception as e:
        logger.error(f"Failed to enrich share: {str(e)}")
        return share


async def get_user_shares_count(user_id: str):
    """Obtener el número total de shares que un usuario ha hecho."""
    db = get_db()
    try:
        count = db.shares.count_documents({"user_id": user_id})
        return count
    except Exception as e:
        logger.error(f"Failed to get user shares count: {str(e)}")
        return 0

