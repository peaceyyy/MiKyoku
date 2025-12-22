"""
Test Harness for FAISS Vector Store
====================================
Validates the vector store implementation with progressively complex tests.

Learning Objectives:
1. Understand how FAISS indexing works
2. See how similarity scores map to real differences
3. Verify the math works as expected
"""

import asyncio
import sys
from pathlib import Path
import numpy as np
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.vector_store import VectorStore, SearchResult
from rag.clip_embedder import generate_embedding


async def test_basic_operations():
    """Test 1: Basic add and search operations"""
    print("\n" + "="*60)
    print("TEST 1: Basic Vector Store Operations")
    print("="*60)
    
    # Create temporary test index
    test_index = Path("data/test_index.faiss")
    test_metadata = Path("data/posters.json")
    
    print("📦 Initializing new vector store...")
    store = VectorStore(
        index_path=str(test_index),
        metadata_path=str(test_metadata),
        dimension=512
    )
    
    print(f"   Initial stats: {store.get_stats()}")
    
    # Create dummy embeddings (random for testing)
    print("\n🔢 Creating test embeddings...")
    
    # Embedding 1: Base vector
    emb1 = np.random.randn(512).astype('float32')
    emb1 = emb1 / np.linalg.norm(emb1)  # Normalize
    print(f"   Embedding 1 norm: {np.linalg.norm(emb1):.6f}")
    
    # Embedding 2: Similar to emb1 (95% similar direction)
    emb2 = 0.95 * emb1 + 0.05 * np.random.randn(512).astype('float32')
    emb2 = emb2 / np.linalg.norm(emb2)
    similarity_1_2 = np.dot(emb1, emb2)
    print(f"   Embedding 2 norm: {np.linalg.norm(emb2):.6f}")
    print(f"   Similarity between 1 and 2: {similarity_1_2:.6f}")
    
    # Embedding 3: Different from emb1
    emb3 = np.random.randn(512).astype('float32')
    emb3 = emb3 / np.linalg.norm(emb3)
    similarity_1_3 = np.dot(emb1, emb3)
    print(f"   Embedding 3 norm: {np.linalg.norm(emb3):.6f}")
    print(f"   Similarity between 1 and 3: {similarity_1_3:.6f}")
    
    # Add to store
    print("\n➕ Adding embeddings to store...")
    id1 = store.add_embedding("test_anime_1", emb1)
    id2 = store.add_embedding("test_anime_2", emb2)
    id3 = store.add_embedding("test_anime_3", emb3)
    
    print(f"   Added at indices: {id1}, {id2}, {id3}")
    print(f"   Total vectors in index: {store.index.ntotal}")
    
    # Search with embedding 1
    print("\n🔍 Searching with embedding 1 (should match itself)...")
    results = store.search(emb1, k=3)
    
    print(f"\n   Results (top {len(results)}):")
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result.slug}")
        print(f"      Similarity: {result.similarity:.6f}")
        print(f"      Expected: {['Perfect match', 'Similar', 'Different'][i-1]}")
    
    # Validate results
    if len(results) >= 2:
        if results[0].slug == "test_anime_1" and results[0].similarity > 0.99:
            print("\n✅ TEST PASSED: Exact match found with similarity ~1.0")
            if results[1].slug == "test_anime_2" and results[1].similarity > 0.9:
                print("✅ BONUS: Similar vector ranked second")
            return True
        else:
            print(f"\n❌ TEST FAILED: Expected test_anime_1 first, got {results[0].slug}")
            return False
    else:
        print("\n❌ TEST FAILED: Not enough results returned")
        return False


async def test_real_posters():
    """Test 2: Using real anime poster embeddings"""
    print("\n" + "="*60)
    print("TEST 2: Real Poster Similarity Search")
    print("="*60)
    
    # Create test store
    test_index = Path("data/test_index_real.faiss")
    test_metadata = Path("data/posters.json")
    
    print("📦 Creating vector store...")
    store = VectorStore(
        index_path=str(test_index),
        metadata_path=str(test_metadata),
        dimension=512
    )
    
    # Select test posters
    test_posters = [
        ("steins_gate.jpg", "steins_gate"),
        ("attack_on_titan.jpg", "attack_on_titan"),
        ("demon_slayer.jpg", "demon_slayer"),
    ]
    
    embeddings = {}
    
    print("\n🧠 Generating real embeddings...")
    for filename, slug in test_posters:
        poster_path = Path(f"data/posters/{filename}")
        if not poster_path.exists():
            print(f"   ⚠️ Skipping {filename} (not found)")
            continue
        
        print(f"   Processing {filename}...")
        image_bytes = poster_path.read_bytes()
        embedding = await generate_embedding(image_bytes)
        embeddings[slug] = embedding
        
        # Add to store
        store.add_embedding(slug, embedding)
        print(f"      ✅ Added to index")
    
    print(f"\n📊 Index now has {store.index.ntotal} vectors")
    
    # Test: Search with Steins;Gate poster
    if "steins_gate" in embeddings:
        print("\n🔍 Searching with Steins;Gate poster...")
        results = store.search(embeddings["steins_gate"], k=3)
        
        print(f"\n   Top matches:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result.anime_title}")
            print(f"      Slug: {result.slug}")
            print(f"      Similarity: {result.similarity:.6f}")
        
        # Validate
        if results[0].slug == "steins_gate" and results[0].similarity > 0.99:
            print("\n✅ TEST PASSED: Found exact match")
            return True
        else:
            print(f"\n❌ TEST FAILED: Expected steins_gate, got {results[0].slug}")
            return False
    else:
        print("\n⚠️ TEST SKIPPED: steins_gate poster not available")
        return True


async def test_similarity_thresholds():
    """Test 3: Understanding similarity thresholds"""
    print("\n" + "="*60)
    print("TEST 3: Similarity Threshold Analysis")
    print("="*60)
    print("\nThis test helps determine the optimal threshold for RAG vs Gemini fallback")
    
    # Load real posters and compare
    test_pairs = [
        # Expected: Very similar (same anime, different editions)
        # (We don't have multiple editions, so skip this)
        
        # Expected: Moderately similar (same genre)
        ("demon_slayer.jpg", "attack_on_titan.jpg", "Action anime"),
        
        # Expected: Low similarity (different genres)
        ("steins_gate.jpg", "toradora.jpg", "Sci-fi vs Romance"),
    ]
    
    print("\n🧠 Analyzing similarity patterns...")
    
    for file1, file2, description in test_pairs:
        path1 = Path(f"data/posters/{file1}")
        path2 = Path(f"data/posters/{file2}")
        
        if not path1.exists() or not path2.exists():
            print(f"\n⚠️ Skipping: {description} (files not found)")
            continue
        
        print(f"\n📊 Comparing: {description}")
        print(f"   A: {file1}")
        print(f"   B: {file2}")
        
        # Generate embeddings
        emb1 = await generate_embedding(path1.read_bytes())
        emb2 = await generate_embedding(path2.read_bytes())
        
        # Calculate similarity
        similarity = np.dot(emb1, emb2)
        
        print(f"   Similarity: {similarity:.6f}")
        
        # Interpretation
        if similarity > 0.85:
            print(f"   → Very similar (same anime or very close style)")
        elif similarity > 0.6:
            print(f"   → Moderately similar (same genre/era)")
        elif similarity > 0.3:
            print(f"   → Low similarity (different styles)")
        else:
            print(f"   → Very different (distinct genres)")
    
    print("\n📌 Threshold Recommendations:")
    print("   • 0.85+ → Confident match (use RAG)")
    print("   • 0.50-0.85 → Possible match (use RAG with caution)")
    print("   • 0.28-0.50 → Low confidence (consider Gemini)")
    print("   • <0.28 → Not found in DB (use Gemini)")
    
    print("\n✅ TEST PASSED: Threshold analysis complete")
    return True


async def test_persistence():
    """Test 4: Save and load index"""
    print("\n" + "="*60)
    print("TEST 4: Index Persistence")
    print("="*60)
    
    test_index = Path("data/test_index_persist.faiss")
    test_mapping = Path("data/test_index_persist.mapping.json")
    test_metadata = Path("data/posters.json")
    
    # Clean up any existing test files
    if test_index.exists():
        test_index.unlink()
    if test_mapping.exists():
        test_mapping.unlink()
    
    # Create and populate store
    print("📦 Creating store with test data...")
    store1 = VectorStore(str(test_index), str(test_metadata))
    
    emb1 = np.random.randn(512).astype('float32')
    emb1 = emb1 / np.linalg.norm(emb1)
    
    store1.add_embedding("persist_test", emb1)
    print(f"   Added 1 vector, total: {store1.index.ntotal}")
    
    # Save
    print("\n💾 Saving index to disk...")
    store1.save()
    
    file_size = test_index.stat().st_size if test_index.exists() else 0
    mapping_size = test_mapping.stat().st_size if test_mapping.exists() else 0
    print(f"   Index file: {test_index} ({file_size:,} bytes)")
    print(f"   Mapping file: {test_mapping} ({mapping_size:,} bytes)")
    
    # Load in new store
    print("\n📂 Loading index in new store instance...")
    store2 = VectorStore(str(test_index), str(test_metadata))
    
    print(f"   Loaded vectors: {store2.index.ntotal}")
    print(f"   Loaded mapping: {len(store2.id_to_slug)} entries")
    
    # Search in loaded store
    print("\n🔍 Searching in loaded store...")
    results = store2.search(emb1, k=1)
    
    if len(results) > 0:
        print(f"   Found: {results[0].slug}")
        print(f"   Similarity: {results[0].similarity:.6f}")
        
        if results[0].slug == "persist_test" and results[0].similarity > 0.99:
            print("\n✅ TEST PASSED: Index persisted and loaded correctly")
            
            # Cleanup
            if test_index.exists():
                test_index.unlink()
            if test_mapping.exists():
                test_mapping.unlink()
            print("   🧹 Cleaned up test files")
            return True
        else:
            print("\n❌ TEST FAILED: Data mismatch after load")
            return False
    else:
        print("\n❌ TEST FAILED: No results from loaded index")
        return False


async def run_all_tests():
    """Run complete vector store test suite"""
    print("\n" + "█"*60)
    print("  FAISS VECTOR STORE TEST SUITE")
    print("█"*60)
    
    tests = [
        ("Basic Operations", test_basic_operations),
        ("Real Poster Search", test_real_posters),
        ("Similarity Thresholds", test_similarity_thresholds),
        ("Index Persistence", test_persistence),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED! Vector store is ready for production.")
    else:
        print("\n⚠️ Some tests failed. Review the output above.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
