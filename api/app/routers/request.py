from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("", response_model=schemas.RequestOut)
def create(
    body: schemas.RequestIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.title.strip():
        raise HTTPException(400, "Title is required")
    req = models.Request(
        user_id=user.id,
        title=body.title.strip(),
        notes=(body.notes or "").strip(),
        status="open",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get("/mine", response_model=list[schemas.RequestOut])
def mine(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Request)
        .filter(models.Request.user_id == user.id)
        .order_by(models.Request.created_at.desc())
        .all()
    )
    return rows