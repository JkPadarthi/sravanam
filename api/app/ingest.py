"""Sravanam ingest — scan MEDIA_ROOT tree into speakers/series/items (idempotent).

Run inside the api container:
    docker compose exec api python -m app.ingest [--dry-run]

Layout:  /media/<Category>/<Series>/<episode>.mp3
         e.g. /media/Sampoorna_Ramayanam/Sundara_Kanda/Sundara_7.mp3
"""
import argparse
import sys
from pathlib import Path

from mutagen.mp3 import MP3

from app.config import settings
from app.db import SessionLocal
from app import models

SPEAKER = "Chaganti Koteswara Rao"
SKIP_DIRS = {"kanda_clips", "_mono", "waste"}

PARVA_ORDER = [
    "Adi", "Sabha", "Aranya", "Virata", "Udyoga", "Bheeshma", "Drona", "Karna",
    "Salya", "Sauptika", "Stree", "Shanti", "Anushasana", "Aswamedha",
    "Ashramavasa", "Mausala", "Mahaprasthanika", "Svargarohana",
]
KANDA_ORDER = ["Bala", "Ayodhya", "Aranya", "Kishkindha", "Sundara", "Yuddha"]

ORDER_MAP = {}
for _map in (PARVA_ORDER, KANDA_ORDER):
    for _i, _name in enumerate(_map):
        ORDER_MAP[_name] = _i


def _human(name: str) -> str:
    return name.replace("_", " ").strip()


def _item_index(stem: str) -> int:
    """'Sundara_7' -> 7 ; 'Adi_12_old' -> 0 (fallback to filename order)."""
    tail = stem.split("_")[-1]
    return int(tail) if tail.isdigit() else 0


def ensure_speaker(db, name: str) -> models.Speaker:
    sp = db.query(models.Speaker).filter(models.Speaker.name == name).first()
    if sp is None:
        sp = models.Speaker(name=name)
        db.add(sp)
        db.commit()
        db.refresh(sp)
    return sp


def ingest(dry_run: bool) -> int:
    root = Path(settings.media_root)
    if not root.is_dir():
        print(f"ERROR: media_root {root} not found", file=sys.stderr)
        return 1

    created = updated = watched = 0
    db = SessionLocal()
    try:
        speaker = ensure_speaker(db, SPEAKER)

        for top in sorted(d for d in root.iterdir() if d.is_dir()):
            if top.name in SKIP_DIRS:
                continue
            category = top.name

            for series_dir in sorted(d for d in top.iterdir() if d.is_dir()):
                mp3s = sorted(series_dir.glob("*.mp3"))
                if not mp3s:
                    continue

                token = _human(series_dir.name).split()[0]
                sort_order = ORDER_MAP.get(token, 999)
                title = _human(series_dir.name)

                series = (
                    db.query(models.Series)
                    .filter(models.Series.title == title, models.Series.category == category)
                    .first()
                )
                if series is None:
                    series = models.Series(
                        title=title,
                        category=category,
                        speaker_id=speaker.id,
                        sort_order=sort_order,
                    )
                    db.add(series)
                    db.commit()
                    db.refresh(series)
                else:
                    if series.speaker_id != speaker.id:
                        series.speaker_id = speaker.id
                    if series.sort_order != sort_order:
                        series.sort_order = sort_order

                for f in mp3s:
                    idx = _item_index(f.stem)
                    rel = str(f.relative_to(root))
                    try:
                        duration = MP3(str(f)).info.length
                    except Exception:
                        duration = 0.0
                    size = f.stat().st_size
                    ep_title = f"{title} — {idx}" if idx else f.stem

                    existing = (
                        db.query(models.Item)
                        .filter(models.Item.file_path == rel)
                        .first()
                    )
                    if existing:
                        existing.series_id = series.id
                        existing.title = ep_title
                        existing.index_no = idx
                        existing.duration_s = duration
                        existing.size_bytes = size
                        updated += 1
                    else:
                        db.add(models.Item(
                            series_id=series.id,
                            title=ep_title,
                            index_no=idx,
                            duration_s=duration,
                            size_bytes=size,
                            file_path=rel,
                            published_at=None,
                        ))
                        created += 1
                    watched += 1

                db.commit()

    finally:
        db.close()

    print(f"ingest: {created} created, {updated} updated, {watched} files watched")
    if dry_run:
        print("(--dry-run: nothing was persisted)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.exit(ingest(args.dry_run))