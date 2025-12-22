"""
AniMiKyoku FastAPI Backend
Main entry point for the anime poster identification API
"""
from dotenv import load_dotenv
import os
import logging
from pathlib import Path

# Load environment variables FIRST before any other imports
load_dotenv()

# Configure logging BEFORE importing other modules
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

from logging.handlers import RotatingFileHandler

# Configure handlers: rotating file handler to avoid excessive IO and growth,
# and a console stream handler for interactive sessions.
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

# Set console encoding to UTF-8 if possible (Windows compatibility)
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # Python < 3.7

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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router, rag_store

app = FastAPI(
    title="AniMiKyoku API",
    description="Anime poster identification with RAG + Gemini fallback",
    version="0.1.0"
)

# CORS configuration for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    """Log startup information and RAG initialization status"""
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
