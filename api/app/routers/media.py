from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import get_db
from app.deps import get_user_media

router = APIRouter(prefix="/media", tags=["media"])


def _resolve(item: models.Item) -> Path:
    root = Path(settings.media_root).resolve()
    full = (root / item.file_path).resolve()
    if not full.is_relative_to(root):
        raise HTTPException(400, "Bad media path")
    if not full.is_file():
        raise HTTPException(404, "Media file missing on disk")
    return full


@router.get("/{item_id}/stream")
def stream(
    item_id: int,
    user: models.User = Depends(get_user_media),
    db: Session = Depends(get_db),
):
    item = db.query(models.Item).get(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    path = _resolve(item)
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@router.get("/{item_id}/download")
def download(
    item_id: int,
    user: models.User = Depends(get_user_media),
    db: Session = Depends(get_db),
):
    item = db.query(models.Item).get(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    path = _resolve(item)
    rec = models.Download(
        user_id=user.id,
        item_id=item.id,
        granted_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    db.commit()
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)