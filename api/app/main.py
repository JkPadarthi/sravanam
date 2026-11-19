from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, engine
from app import models  # noqa: F401
from app.routers import admin, auth, catalog, media, progress, request as requests_router

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(media.router)
app.include_router(progress.router)
app.include_router(requests_router.router)
app.include_router(admin.router)

# Browser web player (single-page app) served from the same port.
# Mounted LAST so /auth, /catalog, /media, /docs etc. keep winning.
app.mount("/", StaticFiles(directory="web", html=True), name="web")