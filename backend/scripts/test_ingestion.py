"""
Test Script for Auto-Ingestion Workflow
========================================

This script tests the scalability feature:
1. Upload an unknown anime poster
2. Verify RAG fails (below threshold)
3. Gemini identifies it
4. User confirms
5. Auto-ingest to database
6. Re-upload same poster
7. Verify RAG now matches it

Usage:
    python backend/scripts/test_ingestion.py --test-poster path/to/test_poster.jpg --title "Anime Title"
"""

import asyncio
import sys
from pathlib import Path
import argparse
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.ingestion import ingest_poster
from rag.clip_embedder import generate_embedding
from rag.vector_store import VectorStore


async def test_ingestion_workflow(poster_path_str: str, anime_title: str):
    """
    Test the complete ingestion workflow.
    
    Args:
        poster_path_str: Path to test poster image
        anime_title: Title of the anime
    """
    print("\n" + "="*70)
    print("AUTO-INGESTION WORKFLOW TEST")
    print("="*70)
    
    poster_path = Path(poster_path_str)
    
    if not poster_path.exists():
        print(f"❌ Error: Test poster not found: {poster_path}")
        return
    
    # Read image
    print(f"\n📂 Loading test poster: {poster_path.name}")
    image_bytes = poster_path.read_bytes()
    print(f"   Size: {len(image_bytes)} bytes")
    
    # Step 1: Check if it's already in RAG
    print("\n🔍 Step 1: Checking if poster is in current RAG database...")
    
    DATA_DIR = Path("data")
    store = VectorStore(
        index_path=str(DATA_DIR / "index.faiss"),
        metadata_path=str(DATA_DIR / "posters.json"),
        dimension=512
    )
    
    print(f"   Current index size: {store.index.ntotal} vectors")
    
    # Generate embedding for search
    embedding = await generate_embedding(image_bytes)
    results = store.search(embedding, k=3)
    
    if results:
        print(f"\n   Top matches:")
        for i, r in enumerate(results, 1):
            print(f"   {i}. {r.anime_title} (similarity: {r.similarity:.4f})")
        
        top_match = results[0]
        if top_match.similarity >= 0.70:
            print(f"\n   ✓ Already in database with good similarity ({top_match.similarity:.4f})")
            print(f"   If you want to test ingestion, use a different poster or remove this one first.")
            return
        else:
            print(f"\n   ⚠️ Top match similarity ({top_match.similarity:.4f}) below threshold (0.70)")
            print(f"   This would trigger Gemini fallback in production.")
    else:
        print(f"   No matches found (empty index or search failed)")
    
    # Step 2: Simulate ingestion (what happens after user confirms)
    print(f"\n✨ Step 2: Simulating user confirmation for '{anime_title}'...")
    print(f"   (In production, this happens via POST /api/confirm-and-ingest)")
    
    result = await ingest_poster(
        image_bytes=image_bytes,
        anime_title=anime_title,
        source="test_script",
        save_image=True,
        file_extension=poster_path.suffix
    )
    
    if not result['success']:
        print(f"\n❌ Ingestion failed: {result.get('error')}")
        return
    
    print(f"\n✅ Ingestion successful!")
    print(f"   Slug: {result['slug']}")
    print(f"   Poster path: {result['poster_path']}")
    print(f"   Index size: {result['index_size']}")
    print(f"   Was duplicate: {result.get('was_duplicate', False)}")
    
    # Step 3: Verify it's now in the database
    print(f"\n🔍 Step 3: Verifying poster is now in database...")
    
    # Reload store to get updated index
    store = VectorStore(
        index_path=str(DATA_DIR / "index.faiss"),
        metadata_path=str(DATA_DIR / "posters.json"),
        dimension=512
    )
    
    print(f"   Reloaded index size: {store.index.ntotal} vectors")
    
    # Search again
    results = store.search(embedding, k=1)
    
    if results:
        match = results[0]
        print(f"\n   ✅ Found match: {match.anime_title}")
        print(f"   Similarity: {match.similarity:.4f}")
        print(f"   Slug: {match.slug}")
        
        if match.similarity >= 0.99:
            print(f"\n   🎉 SUCCESS! Poster is now in database and matches perfectly!")
        else:
            print(f"\n   ⚠️ Warning: Similarity is not near 1.0 ({match.similarity:.4f})")
            print(f"   This might indicate an issue with embedding generation.")
    else:
        print(f"\n   ❌ Error: No matches found after ingestion!")
        print(f"   Something went wrong - check logs.")
    
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


async def cleanup_test_entry(slug: str):
    """
    Clean up test entry from database (for repeated testing).
    
    Args:
        slug: Slug to remove
    """
    print(f"\n🧹 Cleaning up test entry: {slug}")
    
    DATA_DIR = Path("data")
    metadata_path = DATA_DIR / "posters.json"
    
    # Load metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    if slug in metadata:
        # Remove from metadata
        poster_path = metadata[slug].get('path')
        del metadata[slug]
        
        # Save updated metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # Remove poster file if it exists
        if poster_path:
            full_path = Path(poster_path)
            if full_path.exists():
                full_path.unlink()
                print(f"   ✓ Deleted poster file: {poster_path}")
        
        print(f"   ✓ Removed from metadata")
        print(f"   ⚠️ Note: FAISS index not rebuilt. Run build_faiss_index.py to clean index.")
    else:
        print(f"   Slug not found in metadata: {slug}")


def main():
    parser = argparse.ArgumentParser(description="Test auto-ingestion workflow")
    parser.add_argument("--test-poster", required=True, help="Path to test poster image")
    parser.add_argument("--title", required=True, help="Anime title for the poster")
    parser.add_argument("--cleanup", help="Clean up test entry with this slug")
    
    args = parser.parse_args()
    
    if args.cleanup:
        asyncio.run(cleanup_test_entry(args.cleanup))
    else:
        asyncio.run(test_ingestion_workflow(args.test_poster, args.title))


if __name__ == "__main__":
    main()
