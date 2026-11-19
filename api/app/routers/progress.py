from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=list[schemas.ProgressOut])
def get_all(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Progress)
        .filter(models.Progress.user_id == user.id)
        .all()
    )
    return [
        schemas.ProgressOut(item_id=r.item_id, position_s=r.position_s)
        for r in rows
    ]


@router.put("/{item_id}")
def set_progress(
    item_id: int,
    body: schemas.ProgressIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(models.Item).get(item_id) is None:
        raise HTTPException(404, "Item not found")
    row = (
        db.query(models.Progress)
        .filter(models.Progress.user_id == user.id, models.Progress.item_id == item_id)
        .first()
    )
    if row:
        row.position_s = body.position_s
    else:
        row = models.Progress(user_id=user.id, item_id=item_id, position_s=body.position_s)
        db.add(row)
    db.commit()
    return {"ok": True}