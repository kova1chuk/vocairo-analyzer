from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.monitoring import init_monitoring
from app.routers import health, text, enrichment, translation, image
from app.services.nltk_resources import ensure_nltk_data


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
init_monitoring()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_nltk_data()
    yield


app = FastAPI(
    title="Vocairo Text Analyzer",
    description="Text analysis API: EPUB, subtitles, plain text, word enrichment, and translation.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(text.router)
app.include_router(enrichment.router)
app.include_router(translation.router)
app.include_router(image.router)


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} docs",
        swagger_favicon_url="/static/favicon.svg",
    )


@app.get("/")
async def root():
    return {
        "service": "Vocairo Text Analyzer",
        "version": "2.0.0",
        "docs": "/docs",
    }
