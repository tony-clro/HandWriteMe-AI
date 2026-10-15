from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from msflib.eventbus import bind_app_emitter
from starlette.middleware.cors import CORSMiddleware

from .api.api_v1.api import api_router
from .bootstrap import bootstrap_module_hooks
from .core.config import settings
from .db.session import engine
from sqlmodel import SQLModel
from . import models  # noqa: F401

# Ensure tables exist non-destructively on startup
SQLModel.metadata.create_all(engine)

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")
app_emitter = bind_app_emitter(app)
bootstrap_module_hooks(app_emitter)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# Static location for upload files.
if settings.STORAGE_METHOD == "file":
    app.mount(
        settings.STORAGE_BASE_URL,
        StaticFiles(directory=settings.STORAGE_PATH),
        name="storage",
    )

# Static assets for HandWriteMe UI
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(STATIC_DIR / "index.html"))

