from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.db import get_db

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _series_out(s: models.Series, item_count: int) -> schemas.SeriesOut:
    return schemas.SeriesOut(
        id=s.id,
        title=s.title,
        speaker=(s.speaker.name if s.speaker else ""),
        category=s.category,
        description=s.description,
        sort_order=s.sort_order,
        item_count=item_count,
    )


@router.get("/series", response_model=list[schemas.SeriesOut])
def list_series(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Series)
        .options(joinedload(models.Series.speaker))
        .order_by(models.Series.sort_order, models.Series.id)
        .all()
    )
    counts = dict(
        db.query(models.Item.series_id, func.count())
        .group_by(models.Item.series_id)
        .all()
    )
    return [_series_out(s, counts.get(s.id, 0)) for s in rows]


@router.get("/series/{series_id}", response_model=schemas.SeriesDetail)
def series_detail(series_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Series).options(joinedload(models.Series.speaker)).get(series_id)
    if s is None:
        raise HTTPException(404, "Series not found")
    items = (
        db.query(models.Item)
        .filter(models.Item.series_id == series_id)
        .order_by(models.Item.index_no)
        .all()
    )
    return schemas.SeriesDetail(
        series=_series_out(s, len(items)),
        items=[schemas.ItemOut.model_validate(i) for i in items],
    )


@router.get("/items/{item_id}", response_model=schemas.ItemOut)
def item_detail(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).get(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return item