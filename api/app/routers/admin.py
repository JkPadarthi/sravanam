from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.deps import get_current_admin
from app.ingest import ingest as run_ingest

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_STATUSES = {"open", "accepted", "added", "declined"}


@router.get("/summary")
def summary(user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return {
        "users": db.query(models.User).count(),
        "speakers": db.query(models.Speaker).count(),
        "series": db.query(models.Series).count(),
        "items": db.query(models.Item).count(),
        "downloads": db.query(models.Download).count(),
        "open_requests": db.query(models.Request).filter(models.Request.status == "open").count(),
    }


@router.get("/requests")
def all_requests(user: models.User = Depends(get_current_admin), db: Session = Depends(get_db)):
    emails = {u.id: u.email for u in db.query(models.User).all()}
    rows = db.query(models.Request).order_by(models.Request.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "notes": r.notes,
            "status": r.status,
            "requester": emails.get(r.user_id, "?"),
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.patch("/requests/{rid}")
def patch_request(
    rid: int,
    body: schemas.RequestStatusIn,
    user: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if body.status not in ALLOWED_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(ALLOWED_STATUSES)}")
    r = db.get(models.Request, rid)
    if r is None:
        raise HTTPException(404, "Request not found")
    r.status = body.status
    db.commit()
    return {"ok": True, "id": rid, "status": r.status}


@router.post("/ingest")
def ingest_now(user: models.User = Depends(get_current_admin)):
    """Re-scan the /media tree into the catalogue (idempotent)."""
    rc = run_ingest(dry_run=False)
    if rc != 0:
        raise HTTPException(500, "ingest failed")
    return {"ok": True, "action": "ingest"}