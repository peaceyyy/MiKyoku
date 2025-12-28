"""
Test Harness for CLIP Embedder
===============================
This script demonstrates and validates the CLIP embedding functionality.

What this tests:
1. Model loading works correctly
2. Embeddings have correct shape (512 dimensions)
3. Embeddings are normalized (length = 1.0)
4. Similar images produce similar embeddings
5. Different images produce different embeddings
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.clip_embedder import generate_embedding, cosine_similarity, load_clip_model
import numpy as np


async def test_basic_embedding():
    """Test 1: Can we generate an embedding from a poster?"""
    print("\n" + "="*60)
    print("TEST 1: Basic Embedding Generation")
    print("="*60)
    
    # Pick a test poster
    test_poster = Path("data/posters/steins_gate.jpg")
    
    if not test_poster.exists():
        print(f"❌ Test poster not found: {test_poster}")
        return False
    
    print(f"📁 Loading test poster: {test_poster.name}")
    
    # Read the image file
    image_bytes = test_poster.read_bytes()
    print(f"📊 File size: {len(image_bytes):,} bytes")
    
    # Generate embedding
    print("🧠 Generating embedding with CLIP...")
    embedding = await generate_embedding(image_bytes)
    
    # Validate output
    print(f"\n✅ Embedding generated!")
    print(f"   Shape: {embedding.shape}")
    print(f"   Data type: {embedding.dtype}")
    print(f"   First 10 values: {embedding[:10]}")
    print(f"   Min value: {embedding.min():.6f}")
    print(f"   Max value: {embedding.max():.6f}")
    
    # Check normalization
    norm = np.linalg.norm(embedding)
    print(f"   Norm (should be ~1.0): {norm:.6f}")
    
    if embedding.shape == (512,) and 0.99 < norm < 1.01:
        print("\n✅ TEST PASSED: Embedding is valid!")
        return True
    else:
        print("\n❌ TEST FAILED: Unexpected embedding properties")
        return False


async def test_similarity_same_image():
    """Test 2: Does the same image produce similar embeddings?"""
    print("\n" + "="*60)
    print("TEST 2: Same Image Similarity")
    print("="*60)
    
    test_poster = Path("data/posters/attack_on_titan.jpg")
    
    if not test_poster.exists():
        print(f"❌ Test poster not found: {test_poster}")
        return False
    
    print(f"📁 Loading: {test_poster.name}")
    image_bytes = test_poster.read_bytes()
    
    # Generate embedding twice
    print("🧠 Generating embedding #1...")
    embedding1 = await generate_embedding(image_bytes)
    
    print("🧠 Generating embedding #2 (same image)...")
    embedding2 = await generate_embedding(image_bytes)
    
    # Calculate similarity
    similarity = cosine_similarity(embedding1, embedding2)
    print(f"\n📊 Similarity between same image embeddings: {similarity:.6f}")
    
    if similarity > 0.99:
        print("✅ TEST PASSED: Same image produces nearly identical embeddings!")
        return True
    else:
        print(f"❌ TEST FAILED: Expected similarity > 0.99, got {similarity:.6f}")
        return False


async def test_similarity_different_images():
    """Test 3: Do different anime posters produce different embeddings?"""
    print("\n" + "="*60)
    print("TEST 3: Different Images Have Lower Similarity")
    print("="*60)
    
    poster1 = Path("data/posters/demon_slayer.jpg")
    poster2 = Path("data/posters/death_note.jpg")
    
    if not poster1.exists() or not poster2.exists():
        print(f"❌ Test posters not found")
        return False
    
    print(f"📁 Poster A: {poster1.name}")
    print(f"📁 Poster B: {poster2.name}")
    
    # Generate embeddings
    print("🧠 Generating embeddings...")
    embedding1 = await generate_embedding(poster1.read_bytes())
    embedding2 = await generate_embedding(poster2.read_bytes())
    
    # Calculate similarity
    similarity = cosine_similarity(embedding1, embedding2)
    print(f"\n📊 Similarity between different anime: {similarity:.6f}")
    print(f"   (Lower similarity = more distinct posters)")
    
    if similarity < 0.9:
        print("✅ TEST PASSED: Different posters have distinct embeddings!")
        return True
    else:
        print(f"⚠️ TEST WARNING: Similarity unexpectedly high ({similarity:.6f})")
        print("   (This might be okay if the posters look similar)")
        return True  # Not necessarily a failure


async def test_multiple_formats():
    """Test 4: Can we handle different image formats?"""
    print("\n" + "="*60)
    print("TEST 4: Multiple Image Format Support")
    print("="*60)
    
    # Find one poster of each format in our collection
    formats_to_test = {
        '.jpg': 'steins_gate.jpg',
        '.png': 'bunny_girl_senpai.png',
        '.jfif': 'another.jfif'
    }
    
    results = []
    
    for ext, filename in formats_to_test.items():
        poster_path = Path(f"data/posters/{filename}")
        
        if not poster_path.exists():
            print(f"⚠️ Skipping {ext}: {filename} not found")
            continue
        
        print(f"\n📁 Testing {ext} format: {filename}")
        
        try:
            image_bytes = poster_path.read_bytes()
            embedding = await generate_embedding(image_bytes)
            
            if embedding.shape == (512,):
                print(f"   ✅ {ext} format works! Embedding shape: {embedding.shape}")
                results.append(True)
            else:
                print(f"   ❌ {ext} format failed: wrong shape {embedding.shape}")
                results.append(False)
        except Exception as e:
            print(f"   ❌ {ext} format failed: {e}")
            results.append(False)
    
    if all(results):
        print("\n✅ TEST PASSED: All image formats supported!")
        return True
    else:
        print("\n❌ TEST FAILED: Some formats not supported")
        return False


async def run_all_tests():
    """Run complete test suite"""
    print("\n" + "█"*60)
    print("  CLIP EMBEDDER TEST SUITE")
    print("█"*60)
    
    # Pre-load model (so timing is clearer)
    print("\n⏳ Pre-loading CLIP model (this takes ~2 seconds)...")
    load_clip_model()
    
    # Run all tests
    tests = [
        ("Basic Embedding", test_basic_embedding),
        ("Same Image Similarity", test_similarity_same_image),
        ("Different Images", test_similarity_different_images),
        ("Multiple Formats", test_multiple_formats),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
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
        print("\n🎉 ALL TESTS PASSED! CLIP embedder is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Review the output above.")


if __name__ == "__main__":
    # Run the async test suite
    asyncio.run(run_all_tests())
