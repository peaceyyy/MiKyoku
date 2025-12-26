"""
AniMiKyoku FastAPI Backend
Main entry point for the anime poster identification API
"""
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Load environment variables FIRST before any other imports
load_dotenv()

# Configure logging BEFORE importing other modules
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

from logging.handlers import RotatingFileHandler


file_handler = RotatingFileHandler(
    log_dir / "backend.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)


logger = logging.getLogger(__name__)

# Reduce verbosity for noisy libraries
logging.getLogger('uvicorn').setLevel(logging.WARNING)
logging.getLogger('uvicorn.error').setLevel(logging.WARNING)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('open_clip').setLevel(logging.WARNING)
logging.getLogger('faiss').setLevel(logging.WARNING)
logging.getLogger('rag.vector_store').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from api.routes import router, rag_store

# Initialize rate limiter
# Uses client IP address for rate limit tracking
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Replace deprecated @app.on_event('startup') / shutdown handlers."""
    logger.info("="*60)
    logger.info("[STARTUP] AniMiKyoku Backend Starting...")
    logger.info("="*60)

    if rag_store is not None:
        logger.info(f"[OK] RAG System: OPERATIONAL")
        logger.info(f"     - Index vectors: {rag_store.index.ntotal}")
        logger.info(f"     - ID mappings: {len(rag_store.id_to_slug)}")
        logger.info(f"     - Metadata entries: {len(rag_store.metadata)}")
    else:
        logger.warning("[WARNING] RAG System: NOT INITIALIZED (will fallback to Gemini only)")

    logger.info("="*60)

    try:
        yield
    finally:
        logger.info("="*60)
        logger.info("[SHUTDOWN] AniMiKyoku Backend Stopping...")
        logger.info("="*60)

app = FastAPI(
    title="AniMiKyoku API",
    description="Anime poster identification with RAG + Gemini fallback",
    version="0.1.0",
    lifespan=lifespan
)

# File upload size limit middleware (10MB)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """
    Enforce file upload size limit to prevent DoS attacks and memory exhaustion.

    """
    if request.method == "POST":
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            content_length = request.headers.get("content-length")
            if content_length:
                size = int(content_length)
                if size > MAX_UPLOAD_SIZE:
                    logger.warning(
                        f"[UPLOAD REJECTED] Size {size:,} bytes exceeds limit "
                        f"{MAX_UPLOAD_SIZE:,} bytes from {request.client.host if request.client else 'unknown'}"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"File too large. Maximum upload size is {MAX_UPLOAD_SIZE / (1024*1024):.0f}MB."
                        }
                    )
    
    return await call_next(request)

# CORS configuration for React frontend (configurable via env)
origins_env = os.getenv("ALLOW_ORIGINS")
default_origins = ["http://localhost:5173", "http://localhost:3000"]
allow_origins = (
    [o.strip() for o in origins_env.split(",") if o.strip()] if origins_env else default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    rag_status = "operational" if rag_store else "unavailable"
    rag_count = rag_store.index.ntotal if rag_store else 0
    
    return {
        "message": "AniMiKyoku API is running",
        "version": "0.1.0",
        "status": "operational",
        "rag_system": {
            "status": rag_status,
            "indexed_posters": rag_count
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
