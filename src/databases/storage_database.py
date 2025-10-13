from db.supabase import get_client, SUPABASE_BUCKET
from resources.logger import logger
from fastapi import UploadFile
import uuid

async def upload_cover_image(entity_type: str, user_id: str, file: UploadFile, private: bool = False):
    client = get_client()

    file_bytes = await file.read()
    ext = file.filename.split(".")[-1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    file_path = f"{entity_type}/{user_id}/{unique_name}"

    client.storage.from_(SUPABASE_BUCKET).upload(
        file_path,
        file_bytes,
        file_options={"content-type": file.content_type}
    )

    url = client.storage.from_(SUPABASE_BUCKET).get_public_url(file_path)

    logger.info(f"File uploaded: {file_path}")
    return {"coverUrl": url}