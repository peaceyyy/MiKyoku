"""
Build FAISS Index Script
=========================
Creates a FAISS search index from pre-generated embeddings in posters.json.

Process:
1. Loads embeddings from posters.json
2. Builds FAISS IndexFlatIP (Inner Product for cosine similarity)
3. Saves index to data/index.faiss
4. Saves ID mapping to data/index.mapping.json

Performance:
- Very fast: <1 second for 235 vectors
- Index size: ~480KB for 235 × 512-dimensional vectors

Usage:
    python backend/scripts/build_faiss_index.py
    
Requirements:
- Run build_embeddings.py first to generate embeddings
"""

import json
import numpy as np
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.vector_store import VectorStore


def build_faiss_index():
    """
    Build FAISS index from embeddings in metadata.
    
    Mathematical Process:
    ---------------------
    1. Load all 512-dimensional embeddings from JSON
    2. Create FAISS IndexFlatIP (dimension=512)
    3. Add vectors sequentially (maintaining ID order)
    4. Save index to disk
    
    Index Structure:
    ----------------
    - IndexFlatIP: Flat (exhaustive) search with Inner Product metric
    - For normalized vectors: Inner Product = Cosine Similarity
    - Each vector: 512 floats × 4 bytes = 2KB
    - 235 vectors = ~480KB total
    
    ID Mapping:
    -----------
    FAISS assigns sequential IDs (0, 1, 2, ...)
    We maintain a mapping: ID → anime slug
    Saved separately in .mapping.json file
    """
    
    print("\n" + "="*60)
    print("FAISS INDEX BUILDER")
    print("="*60)
    
    # Paths
    metadata_path = Path("data/posters.json")
    index_path = Path("data/index.faiss")
    
    # Validate metadata exists
    if not metadata_path.exists():
        print(f"❌ Error: Metadata file not found: {metadata_path}")
        print("   Run build_embeddings.py first to generate embeddings")
        return
    
    # Load metadata
    print(f"\n📂 Loading metadata from {metadata_path}...")
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    print(f"   Found {len(metadata)} anime entries")
    
    # Filter entries with embeddings
    print("\n🔍 Checking for embeddings...")
    entries_with_embeddings = {
        slug: data for slug, data in metadata.items()
        if data.get('embedding') is not None
    }
    
    if not entries_with_embeddings:
        print("❌ Error: No embeddings found in metadata!")
        print("   Run build_embeddings.py first to generate embeddings")
        return
    
    print(f"   ✅ Found {len(entries_with_embeddings)} entries with embeddings")
    
    # Check embedding dimensions
    sample_embedding = list(entries_with_embeddings.values())[0]['embedding']
    embedding_dim = len(sample_embedding)
    print(f"   Embedding dimension: {embedding_dim}")
    
    if embedding_dim != 512:
        print(f"⚠️ Warning: Expected 512 dimensions, found {embedding_dim}")
    
    # Initialize vector store
    print(f"\n🏗️ Creating FAISS index...")
    store = VectorStore(
        index_path=str(index_path),
        metadata_path=str(metadata_path),
        dimension=embedding_dim
    )
    
    # Sort slugs for deterministic ordering (important for consistency)
    sorted_slugs = sorted(entries_with_embeddings.keys())
    
    print(f"   Index type: IndexFlatIP")
    print(f"   Dimension: {embedding_dim}")
    print(f"   Vectors to add: {len(sorted_slugs)}")
    
    # Add embeddings to index
    print("\n➕ Adding vectors to index...")
    
    added_count = 0
    for slug in sorted_slugs:
        data = entries_with_embeddings[slug]
        embedding_list = data['embedding']
        
        # Convert to numpy array
        embedding = np.array(embedding_list, dtype='float32')
        
        # Verify normalization (should be ~1.0)
        norm = np.linalg.norm(embedding)
        if not (0.95 < norm < 1.05):
            print(f"   ⚠️ Warning: {slug} has unusual norm: {norm:.6f}")
        
        # Add to store
        store.add_embedding(slug, embedding)
        added_count += 1
    
    print(f"   ✅ Added {added_count} vectors")
    
    # Save index
    print("\n💾 Saving FAISS index...")
    store.save()
    
    # Get file sizes
    index_size = index_path.stat().st_size if index_path.exists() else 0
    mapping_path = index_path.with_suffix('.mapping.json')
    mapping_size = mapping_path.stat().st_size if mapping_path.exists() else 0
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ FAISS index built successfully!")
    print(f"\n📊 Index statistics:")
    print(f"   Total vectors: {store.index.ntotal}")
    print(f"   Dimension: {embedding_dim}")
    print(f"   Index type: IndexFlatIP")
    print(f"\n💾 Files created:")
    print(f"   Index: {index_path} ({index_size:,} bytes)")
    print(f"   Mapping: {mapping_path} ({mapping_size:,} bytes)")
    
    # Memory usage estimate
    memory_mb = (store.index.ntotal * embedding_dim * 4) / (1024 * 1024)
    print(f"\n📈 Memory usage: ~{memory_mb:.2f} MB")
    
    print("\n🎉 INDEX READY FOR PRODUCTION!")
    print("   The RAG system can now use this index for fast poster search")
    
    # Quick test
    print("\n🧪 Running quick test...")
    stats = store.get_stats()
    print(f"   Index contains {stats['total_vectors']} searchable vectors")
    
    # Try a test search with the first embedding
    first_slug = sorted_slugs[0]
    first_embedding = np.array(entries_with_embeddings[first_slug]['embedding'], dtype='float32')
    results = store.search(first_embedding, k=3)
    
    if results:
        print(f"\n   Test search with '{first_slug}':")
        for i, result in enumerate(results[:3], 1):
            print(f"   {i}. {result.anime_title} (similarity: {result.similarity:.6f})")
        
        if results[0].slug == first_slug and results[0].similarity > 0.99:
            print("\n   ✅ Test passed: Index is working correctly!")
        else:
            print("\n   ⚠️ Test warning: Top result doesn't match perfectly")
    else:
        print("   ⚠️ Test warning: No results returned")


if __name__ == "__main__":
    build_faiss_index()
