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

import asyncio
import json
import os
import tempfile
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging
import re
import unicodedata
import portalocker  # Cross-platform file locking

from rag.clip_embedder import generate_embedding
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Thread lock for index updates (prevents race conditions in concurrent requests)
import threading
_index_lock = threading.Lock()


def get_data_dir() -> Path:
    """Resolve the persistent data directory, respecting DATA_DIR_PATH."""
    project_root = Path(__file__).parent.parent.parent
    return Path(os.getenv("DATA_DIR_PATH") or str(project_root / "data"))


def _is_same_anime_slug(candidate_slug: str, base_slug: str) -> bool:
    """Return True if candidate_slug is base_slug or an _alt/_altN variant of it."""
    if candidate_slug == base_slug:
        return True
    alt_prefix = f"{base_slug}_alt"
    if candidate_slug == alt_prefix:
        return True
    if candidate_slug.startswith(alt_prefix):
        suffix = candidate_slug[len(alt_prefix):]
        return suffix.isdigit()
    return False


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


def _atomic_write_text(target_path: Path, content: str) -> None:
    """Write text atomically to target_path via a same-directory temporary file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, target_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _ingest_poster_sync(
    image_bytes: bytes,
    anime_title: str,
    base_slug: str,
    embedding: np.ndarray,
    source: str,
    save_image: bool,
    file_extension: str,
    metadata_overrides: Optional[Dict[str, Any]],
    vector_store: Optional[VectorStore],
    data_dir: Optional[Path],
    duplicate_similarity_threshold: float,
) -> Dict[str, Any]:
    """Run locked disk + VectorStore persistence on a worker thread."""
    with _index_lock:
        logger.info("  Acquired index lock")

        DATA_DIR = Path(data_dir) if data_dir is not None else get_data_dir()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        POSTERS_DIR = DATA_DIR / "posters"
        metadata_path = DATA_DIR / "posters.json"
        index_path = DATA_DIR / "index.faiss"
        lock_path = DATA_DIR / ".ingestion.lock"

        # Dedicated lock file avoids pre-lock metadata creation races and Windows
        # byte-range lock conflicts when VectorStore reads or os.replace swaps metadata_path.
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            logger.info("  Acquiring file lock for ingestion...")
            portalocker.lock(lock_file, portalocker.LOCK_EX)
            logger.info("  ✓ File lock acquired")

            try:
                if metadata_path.exists():
                    content = metadata_path.read_text(encoding="utf-8")
                    metadata = json.loads(content) if content.strip() else {}
                else:
                    metadata = {}

                # Load/create vector store
                logger.info("  Loading vector store...")
                store = VectorStore(
                    index_path=str(index_path),
                    metadata_path=str(metadata_path),
                    dimension=512,
                )

                # Near-duplicate guard for the same anime
                if store.index.ntotal > 0:
                    existing_matches = store.search(
                        embedding,
                        k=min(10, store.index.ntotal),
                        min_similarity=duplicate_similarity_threshold,
                    )
                    for match in existing_matches:
                        if _is_same_anime_slug(match.slug, base_slug):
                            logger.info(
                                f"  Skipping near-duplicate ingestion for '{anime_title}': "
                                f"matched existing '{match.slug}' (similarity={match.similarity:.4f})"
                            )
                            if vector_store is not None:
                                vector_store.sync_from(store, metadata)
                            return {
                                'success': True,
                                'slug': match.slug,
                                'poster_path': match.poster_path or None,
                                'embedding_shape': embedding.shape,
                                'was_duplicate': True,
                                'skipped_duplicate': True,
                                'index_id': None,
                                'index_size': store.index.ntotal,
                            }

                # Handle slug collisions (now safe from races)
                existing_slugs = set(metadata.keys())
                final_slug = handle_slug_collision(base_slug, existing_slugs)
                was_duplicate = (final_slug != base_slug)

                # Determine poster path (empty string in metadata when save_image=False)
                poster_filename = f"{final_slug}{file_extension}"
                poster_path = POSTERS_DIR / poster_filename
                relative_poster_path = f"data/posters/{poster_filename}" if save_image else ""

                # Add embedding to FAISS index
                logger.info(f"  Adding embedding to FAISS index (current size: {store.index.ntotal})...")
                index_id = store.add_embedding(final_slug, embedding)
                logger.info(f"  ✓ Added to index at ID {index_id}")

                # Update metadata in memory and serialize BEFORE mutating disk
                metadata[final_slug] = {
                    "title": anime_title,
                    "slug": final_slug,
                    "path": relative_poster_path,
                    "season": None,
                    "embedding": embedding.tolist(),
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "source": source,
                    "notes": f"Auto-ingested from {source}",
                }
                if metadata_overrides:
                    metadata[final_slug].update(metadata_overrides)

                serialized_metadata = json.dumps(metadata, indent=2, ensure_ascii=False)
                logger.info("  ✓ Metadata serialized in memory")

                # Persist index and metadata atomically
                logger.info("  Saving FAISS index...")
                store.save()
                logger.info("  ✓ Index saved")

                logger.info("  Saving metadata JSON...")
                _atomic_write_text(metadata_path, serialized_metadata)
                logger.info("  ✓ Metadata saved")

                # Sync live in-memory VectorStore only after disk persistence succeeds
                if vector_store is not None:
                    vector_store.sync_from(store, metadata)
                    logger.info(f"  ✓ Live VectorStore synced ({vector_store.index.ntotal} vectors)")
            finally:
                logger.info("  Released file lock")

        # Optionally save poster image (best-effort; never fail committed index update)
        saved_poster_path: Optional[str] = None
        if save_image:
            try:
                logger.info(f"  Saving poster image to {poster_path}...")
                POSTERS_DIR.mkdir(parents=True, exist_ok=True)
                poster_path.write_bytes(image_bytes)
                saved_poster_path = relative_poster_path
                logger.info("  ✓ Image saved")
            except Exception as img_err:
                logger.warning(f"  ⚠️ Failed to save poster image (index remains valid): {img_err}")
        else:
            logger.info("  Skipping image save (save_image=False)")

    logger.info("  Released index lock")
    logger.info(f"[INGESTION COMPLETE] {anime_title} -> {final_slug}")

    return {
        'success': True,
        'slug': final_slug,
        'poster_path': saved_poster_path,
        'embedding_shape': embedding.shape,
        'was_duplicate': was_duplicate,
        'skipped_duplicate': False,
        'index_id': index_id,
        'index_size': store.index.ntotal,
    }


async def ingest_poster(
    image_bytes: bytes,
    anime_title: str,
    source: str = "gemini",
    save_image: bool = True,
    file_extension: str = ".jpg",
    metadata_overrides: Optional[Dict[str, Any]] = None,
    vector_store: Optional[VectorStore] = None,
    data_dir: Optional[Path] = None,
    duplicate_similarity_threshold: float = 0.98,
) -> Dict[str, Any]:
    """
    Add a new anime poster to the RAG database.
    
    Error Handling:
    ---------------
    - If embedding generation fails: raises exception, no changes made
    - If index or metadata persistence fails: leaves live VectorStore untouched
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
        
        # Step 3: Offload blocking locks and disk/FAISS I/O to worker thread
        return await asyncio.to_thread(
            _ingest_poster_sync,
            image_bytes,
            anime_title,
            base_slug,
            embedding,
            source,
            save_image,
            file_extension,
            metadata_overrides,
            vector_store,
            data_dir,
            duplicate_similarity_threshold,
        )
        
    except Exception as e:
        logger.error(f"[INGESTION FAILED] {anime_title}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'slug': None
        }

