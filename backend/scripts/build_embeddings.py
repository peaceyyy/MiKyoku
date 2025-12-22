"""
Build Embeddings Script
=======================
Generates CLIP embeddings for all anime posters and saves them to posters.json.

Process:
1. Scans data/posters/ for image files
2. For each poster:
   - Loads the image
   - Generates 512-dimensional embedding using CLIP
   - Updates metadata in posters.json
3. Saves updated metadata with embeddings

Performance:
- ~1-2 seconds per poster (CLIP inference)
- 235 posters = ~4-8 minutes total
- Can resume if interrupted (skips existing embeddings)

Usage:
    python backend/scripts/build_embeddings.py
    python backend/scripts/build_embeddings.py --force  # Regenerate all
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from tqdm import tqdm
import argparse

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.clip_embedder import generate_embedding, load_clip_model


async def build_embeddings(force_regenerate: bool = False):
    """
    Generate embeddings for all posters and update metadata.
    
    Args:
        force_regenerate: If True, regenerate all embeddings even if they exist
    
    Process Explanation:
    --------------------
    1. Pre-load CLIP model (expensive one-time operation)
    2. Load existing metadata from posters.json
    3. Match poster files with metadata entries
    4. Generate embeddings for posters without them (or all if force=True)
    5. Save updated metadata back to posters.json
    
    Error Handling:
    ---------------
    - Skips files that aren't in metadata
    - Continues on individual poster failures
    - Saves progress periodically (every 10 posters)
    """
    
    print("\n" + "="*60)
    print("ANIME POSTER EMBEDDING GENERATOR")
    print("="*60)
    
    # Paths
    posters_dir = Path("data/posters")
    metadata_path = Path("data/posters.json")
    
    # Validate paths
    if not posters_dir.exists():
        print(f"❌ Error: Posters directory not found: {posters_dir}")
        return
    
    if not metadata_path.exists():
        print(f"❌ Error: Metadata file not found: {metadata_path}")
        return
    
    # Pre-load CLIP model (takes ~2 seconds, do it once)
    print("\n⏳ Loading CLIP model...")
    load_clip_model()
    print("✅ Model loaded and ready")
    
    # Load metadata
    print(f"\n📂 Loading metadata from {metadata_path}...")
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    print(f"   Found {len(metadata)} anime entries in metadata")
    
    # Get all poster files
    poster_files = list(posters_dir.glob("*"))
    poster_files = [f for f in poster_files if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.jfif', '.webp']]
    
    print(f"   Found {len(poster_files)} image files in {posters_dir}")
    
    # Match files to metadata entries
    print("\n🔍 Matching files to metadata entries...")
    work_queue = []
    
    for poster_file in poster_files:
        # Try to find matching metadata entry
        # The slug should match the filename (without extension)
        file_stem = poster_file.stem  # filename without extension
        
        if file_stem not in metadata:
            print(f"   ⚠️ No metadata for {poster_file.name}, skipping...")
            continue
        
        # Check if embedding already exists
        has_embedding = metadata[file_stem].get('embedding') is not None
        
        if has_embedding and not force_regenerate:
            continue  # Skip, already has embedding
        
        work_queue.append((file_stem, poster_file))
    
    if not work_queue:
        print("\n✅ All posters already have embeddings!")
        print("   Use --force to regenerate all embeddings")
        return
    
    print(f"\n📊 Processing queue: {len(work_queue)} posters need embeddings")
    
    if force_regenerate:
        print("   (Force mode: regenerating ALL embeddings)")
    
    # Process posters with progress bar
    print("\n🧠 Generating embeddings...\n")
    
    updated_count = 0
    failed_count = 0
    
    # Use tqdm for a nice progress bar
    for slug, poster_file in tqdm(work_queue, desc="Processing posters", unit="poster"):
        try:
            # Read image file
            image_bytes = poster_file.read_bytes()
            
            # Generate embedding (the magic happens here!)
            # This calls CLIP model: image → 512 numbers
            embedding = await generate_embedding(image_bytes)
            
            # Convert numpy array to list for JSON serialization
            embedding_list = embedding.tolist()
            
            # Update metadata
            metadata[slug]['embedding'] = embedding_list
            metadata[slug]['embedding_generated_at'] = datetime.now(timezone.utc).isoformat()
            
            updated_count += 1
            
            # Save progress every 10 posters (in case of interruption)
            if updated_count % 10 == 0:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            tqdm.write(f"   ❌ Failed to process {poster_file.name}: {e}")
            failed_count += 1
            continue
    
    # Final save
    print("\n💾 Saving final metadata...")
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Successfully processed: {updated_count} posters")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count} posters")
    print(f"💾 Metadata saved to: {metadata_path}")
    
    # Calculate total embeddings
    total_with_embeddings = sum(1 for data in metadata.values() if data.get('embedding') is not None)
    print(f"\n📊 Database status: {total_with_embeddings}/{len(metadata)} posters have embeddings")
    
    if total_with_embeddings == len(metadata):
        print("\n🎉 ALL POSTERS NOW HAVE EMBEDDINGS!")
        print("   Next step: Run build_faiss_index.py to create the search index")
    else:
        missing = len(metadata) - total_with_embeddings
        print(f"\n⚠️ {missing} posters still need embeddings")


def main():
    """Parse arguments and run embedding generation"""
    parser = argparse.ArgumentParser(
        description="Generate CLIP embeddings for anime posters"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Regenerate all embeddings, even if they already exist'
    )
    
    args = parser.parse_args()
    
    # Run async function
    asyncio.run(build_embeddings(force_regenerate=args.force))


if __name__ == "__main__":
    main()
