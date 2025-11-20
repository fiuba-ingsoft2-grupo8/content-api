"""
Audit database operations for tracking collection state changes.
"""
from datetime import datetime, timezone
from resources.logger import logger
from db.database import get_db
from db.models import CollectionAudit
from bson import ObjectId


async def log_collection_change(
    collection_id: str,
    user_id: str,
    action: str,
    previous_state: str | None = None,
    new_state: str | None = None,
    previous_release_date: datetime | None = None,
    new_release_date: datetime | None = None,
    previous_no_disponible_desde: datetime | None = None,
    new_no_disponible_desde: datetime | None = None,
    previous_no_disponible_hasta: datetime | None = None,
    new_no_disponible_hasta: datetime | None = None,
    previous_bloqueado_admin: bool | None = None,
    new_bloqueado_admin: bool | None = None,
    metadata: dict | None = None
):
    """
    Log a change to a collection's publication window or state.
    
    Args:
        collection_id: ID of the collection
        user_id: ID of the user making the change (or 'system' for auto-activation)
        action: Type of action ('state_change', 'publication_window_update', 'auto_activation')
        previous_state: Previous effective state
        new_state: New effective state
        previous_release_date: Previous release date
        new_release_date: New release date
        previous_no_disponible_desde: Previous no-disponible start date
        new_no_disponible_desde: New no-disponible start date
        previous_no_disponible_hasta: Previous no-disponible end date
        new_no_disponible_hasta: New no-disponible end date
        previous_bloqueado_admin: Previous admin block status
        new_bloqueado_admin: New admin block status
        metadata: Additional context information
    """
    db = get_db()
    try:
        audit_entry = CollectionAudit(
            collection_id=ObjectId(collection_id),
            user_id=user_id,
            action=action,
            previous_state=previous_state,
            new_state=new_state,
            previous_release_date=previous_release_date,
            new_release_date=new_release_date,
            previous_no_disponible_desde=previous_no_disponible_desde,
            new_no_disponible_desde=new_no_disponible_desde,
            previous_no_disponible_hasta=previous_no_disponible_hasta,
            new_no_disponible_hasta=new_no_disponible_hasta,
            previous_bloqueado_admin=previous_bloqueado_admin,
            new_bloqueado_admin=new_bloqueado_admin,
            metadata=metadata
        )
        db.collection_audit.insert_one(audit_entry.model_dump(by_alias=True))
        logger.info(f"Logged {action} for collection {collection_id} by user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log collection change: {str(e)}")


async def get_collection_audit_log(collection_id: str, limit: int = 50):
    """
    Get audit log entries for a collection.
    
    Args:
        collection_id: ID of the collection
        limit: Maximum number of entries to return
        
    Returns:
        List of audit log entries, most recent first
    """
    db = get_db()
    try:
        entries = list(
            db.collection_audit.find(
                {"collection_id": ObjectId(collection_id)}
            ).sort("timestamp", -1).limit(limit)
        )
        return entries
    except Exception as e:
        logger.error(f"Failed to get audit log for collection {collection_id}: {str(e)}")
        return []

