# Sravanam

శ్రవణం — a free, ad-free app for listening to Telugu pravachanam.

**Model:** Free to listen · ₹10/mo *sustainer* pass (server upkeep, not a paywall) ·
sources linked openly (YouTube) · users can request any discourse.

**Stack:** Flutter app (iOS + Android) + FastAPI/Postgres backend + Razorpay autopay.
Runs on `abhi`. See `DESIGN.md`.

## Services (docker compose)

| Service | Port | Notes |
|---------|------|-------|
| `db` | `127.0.0.1:5433` | Postgres 16, localhost only |
| `api` | `8110` | FastAPI — auth, catalogue, media, progress, requests |

Media tree is mounted read-only at `/media` (host `~/pravachanam`).

## Quickstart (on abhi)

```bash
cd ~/sravanam
cp .env.example .env        # fill secrets
docker compose up -d --build
docker compose exec api alembic revision --autogenerate -m initial
docker compose exec api alembic upgrade head
docker compose exec api python -m app.ingest      # scan /media into catalogue
curl -s localhost:8110/health
```

## Roadmap
Backend core (this milestone) → Flutter app → Razorpay sustainer → CDN.