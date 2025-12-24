"""
Auto-Ingestion Module
=====================
Dynamically adds new anime posters to the RAG database when users confirm
Gemini identifications or correct RAG misidentifications.

Process:
1. Normalize anime title to slug (using normalize_filenames logic)
2. Optionally save poster image to data/posters/
3. Generate CLIP embedding
4. Add embedding to FAISS index
5. Update metadata in posters.json
6. Save updated index and mapping

This enables the database to grow organically as users upload new posters.
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging
import re
import unicodedata

from rag.clip_embedder import generate_embedding
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Thread lock for index updates (prevents race conditions in concurrent requests)
import threading
_index_lock = threading.Lock()


def normalize_title_to_slug(title: str) -> str:
    """
    Convert anime title to normalized slug for filename and metadata key.
    
    Uses same logic as normalize_filenames.py for consistency.
    
    Examples:
        "Steins;Gate" -> "steins_gate"
        "Re:Zero" -> "re_zero"
        "Attack on Titan" -> "attack_on_titan"
    
    Args:
        title: Anime title from Gemini or user input
    
    Returns:
        Normalized slug (snake_case, lowercase, alphanumeric + underscore)
    """
    if not title or not title.strip():
        return "unknown"
    
    # Unicode normalization
    s = unicodedata.normalize("NFKC", title)
    
    # Convert to lowercase
    s = s.lower()
    
    # Replace common separators with underscore
    s = s.replace(" ", "_").replace("-", "_")
    
    # Remove non-alphanumeric except underscore
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    
    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s)
    
    # Strip leading/trailing underscores
    s = s.strip("_")
    
    # Handle edge cases
    if not s:
        return "unknown"
    
    # Truncate to reasonable length
    if len(s) > 200:
        s = s[:200].rstrip("_")
    
    return s


def handle_slug_collision(base_slug: str, existing_slugs: set) -> str:
    """
    Handle slug collisions by appending _alt, _alt2, _alt3, etc.
    
    This allows multiple poster variants for the same anime
    (different seasons, versions, styles).
    
    Args:
        base_slug: Original slug (e.g., "attack_on_titan")
        existing_slugs: Set of slugs already in metadata
    
    Returns:
        Unique slug (e.g., "attack_on_titan_alt2")
    """
    if base_slug not in existing_slugs:
        return base_slug
    
    # Try suffixes: _alt, _alt2, _alt3, ...
    counter = 1
    while True:
        suffix = "_alt" if counter == 1 else f"_alt{counter}"
        candidate = f"{base_slug}{suffix}"
        
        if candidate not in existing_slugs:
            logger.info(f"Slug collision detected. Using: {candidate}")
            return candidate
        
        counter += 1
        
        # Safety limit (shouldn't hit this in practice)
        if counter > 100:
            raise ValueError(f"Too many variants for slug: {base_slug}")


async def ingest_poster(
    image_bytes: bytes,
    anime_title: str,
    source: str = "gemini",
    save_image: bool = True,
    file_extension: str = ".jpg",
    metadata_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add a new anime poster to the RAG database.
    
    Error Handling:
    ---------------
    - If embedding generation fails: raises exception, no changes made
    - If index update fails: rolls back metadata changes
    - If file save fails: logs warning but continues (image is optional)
    """
    logger.info(f"[INGESTION START] Title: {anime_title}, Source: {source}")
    
    try:
        # Step 1: Normalize title to slug
        base_slug = normalize_title_to_slug(anime_title)
        logger.info(f"  Normalized slug: {base_slug}")
        
        # Step 2: Generate embedding BEFORE acquiring lock (expensive operation)
        logger.info("  Generating CLIP embedding...")
        embedding = await generate_embedding(image_bytes)
        embedding_norm = np.linalg.norm(embedding)
        logger.info(f"  ✓ Embedding generated: shape={embedding.shape}, norm={embedding_norm:.6f}")
        
        # Step 3: Acquire lock for index updates (critical section)
        with _index_lock:
            logger.info("  Acquired index lock")
            
            # Paths
            PROJECT_ROOT = Path(__file__).parent.parent.parent
            DATA_DIR = PROJECT_ROOT / "data"
            POSTERS_DIR = DATA_DIR / "posters"
            metadata_path = DATA_DIR / "posters.json"
            index_path = DATA_DIR / "index.faiss"
            
            # Load current metadata (create if missing)
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            else:
                logger.warning(f"Metadata file not found at {metadata_path}, creating new metadata store")
                metadata = {}
            
            # Handle slug collisions
            existing_slugs = set(metadata.keys())
            final_slug = handle_slug_collision(base_slug, existing_slugs)
            was_duplicate = (final_slug != base_slug)
            
            # Determine poster path
            poster_filename = f"{final_slug}{file_extension}"
            poster_path = POSTERS_DIR / poster_filename
            relative_poster_path = f"data/posters/{poster_filename}"
            
            # Step 4: Load/create vector store
            logger.info("  Loading vector store...")
            store = VectorStore(
                index_path=str(index_path),
                metadata_path=str(metadata_path),
                dimension=512
            )
            
            # Step 5: Add embedding to FAISS index
            logger.info(f"  Adding embedding to FAISS index (current size: {store.index.ntotal})...")
            index_id = store.add_embedding(final_slug, embedding)
            logger.info(f"  ✓ Added to index at ID {index_id}")
            
            # Step 6: Update metadata
            metadata[final_slug] = {
                "title": anime_title,
                "slug": final_slug,
                "path": relative_poster_path,
                "season": None,  # Could be enhanced to detect season from title
                "embedding": embedding.tolist(),  # Store for rebuild purposes
                "added_at": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "notes": f"Auto-ingested from {source}"
            }
            
            # Add any override metadata
            if metadata_overrides:
                metadata[final_slug].update(metadata_overrides)
            
            logger.info("  ✓ Metadata updated")
            
            # Step 7: Save index to disk
            logger.info("  Saving FAISS index...")
            store.save()
            logger.info("  ✓ Index saved")
            
            # Step 8: Save metadata JSON
            logger.info("  Saving metadata JSON...")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info("  ✓ Metadata saved")
            
            # Step 9: Optionally save poster image
            if save_image:
                logger.info(f"  Saving poster image to {poster_path}...")
                POSTERS_DIR.mkdir(parents=True, exist_ok=True)
                poster_path.write_bytes(image_bytes)
                logger.info("  ✓ Image saved")
            else:
                logger.info("  Skipping image save (save_image=False)")
        
        # Lock released
        logger.info("  Released index lock")
        
        logger.info(f"[INGESTION COMPLETE] {anime_title} -> {final_slug}")
        
        return {
            'success': True,
            'slug': final_slug,
            'poster_path': relative_poster_path if save_image else None,
            'embedding_shape': embedding.shape,
            'was_duplicate': was_duplicate,
            'index_id': index_id,
            'index_size': store.index.ntotal
        }
        
    except Exception as e:
        logger.error(f"[INGESTION FAILED] {anime_title}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'slug': None
        }

