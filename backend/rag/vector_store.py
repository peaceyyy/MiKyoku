"""
FAISS Vector Store Module
==========================
Manages fast similarity search for anime poster embeddings using FAISS.

Key Concepts:
- Vector Space: 512-dimensional space where each anime poster is a point
- Cosine Similarity: Measures angle between vectors (1.0 = identical, 0.0 = orthogonal)
- FAISS Index: Optimized data structure for fast nearest-neighbor search
- Inner Product: Dot product of normalized vectors = cosine similarity

Mathematical Background:
------------------------
Given two normalized embeddings A and B (||A|| = ||B|| = 1):

    cosine_similarity(A, B) = cos(θ) = A · B = Σ(aᵢ × bᵢ)
    
Where θ is the angle between vectors in 512D space.

FAISS IndexFlatIP computes this inner product efficiently using:
- SIMD (Single Instruction Multiple Data) operations
- Optimized memory layout for cache efficiency
- Parallel computation across dimensions
"""

import faiss
import numpy as np
import json
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Result from a similarity search.
    
    Attributes:
        slug: Normalized identifier (e.g., "steins_gate")
        anime_title: Display name (e.g., "Steins;Gate")
        similarity: Cosine similarity score [0.0, 1.0]
        poster_path: Relative path to poster image
        distance: Raw distance from FAISS (negative inner product for IndexFlatIP)
    """
    slug: str
    anime_title: str
    similarity: float
    poster_path: str
    distance: float


class VectorStore:
    """
    Manages a FAISS index for fast anime poster similarity search.
    
    Architecture:
    - Uses IndexFlatIP (Flat Index with Inner Product)
    - Stores normalized embeddings (L2 norm = 1.0)
    - Maps FAISS index positions to anime slugs
    
    Why IndexFlatIP?
    - "Flat" = exhaustive search, no approximation (100% accurate)
    - "IP" = Inner Product, which equals cosine similarity for normalized vectors
    - Perfect for our scale (235 posters → ~120K operations, runs in <1ms)
    
    For larger datasets (millions), consider:
    - IndexIVFFlat: Clusters vectors, searches subset (faster, slight accuracy loss)
    - IndexHNSW: Graph-based approximate search (very fast, 99%+ accuracy)
    """
    
    def __init__(
        self, 
        index_path: str, 
        metadata_path: str, 
        dimension: int = 512
    ):
        """
        Initialize or load vector store.
        
        Args:
            index_path: Path to FAISS index file (.faiss)
            metadata_path: Path to poster metadata JSON
            dimension: Embedding dimension (512 for ViT-B-32)
        
        Technical Details:
            - Dimension must match CLIP output (512)
            - IndexFlatIP uses 4 bytes per dimension per vector
            - Memory: 235 vectors × 512 dims × 4 bytes ≈ 480KB (tiny!)
        """
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.dimension = dimension
        
        # ID to slug mapping (FAISS uses integer IDs, we use slugs)
        self.id_to_slug: List[str] = []
        
        # Load or create FAISS index
        if self.index_path.exists():
            logger.info(f"Loading existing FAISS index from {self.index_path}")
            self.index = faiss.read_index(str(self.index_path))
            logger.info(f"[OK] Loaded index with {self.index.ntotal} vectors")
            
            # Try to load the ID mapping
            mapping_path = self.index_path.with_suffix('.mapping.json')
            if mapping_path.exists():
                logger.info(f"Loading ID mapping from {mapping_path}")
                with open(mapping_path, 'r') as f:
                    self.id_to_slug = json.load(f)
                logger.info(f"[OK] Loaded ID mapping with {len(self.id_to_slug)} entries")
                
                # Validate mapping matches index size
                if len(self.id_to_slug) != self.index.ntotal:
                    logger.error(
                        f"[ERROR] MISMATCH: Index has {self.index.ntotal} vectors "
                        f"but mapping has {len(self.id_to_slug)} entries"
                    )
                    logger.info("Attempting to rebuild mapping from metadata...")
                    self.id_to_slug = []  # Clear bad mapping
            else:
                logger.warning(f"[WARNING] Mapping file not found: {mapping_path}")
                logger.info("Will attempt to rebuild from metadata...")
        else:
            logger.info(f"Creating new FAISS IndexFlatIP (dimension={dimension})")
            # IndexFlatIP: Flat index using Inner Product metric
            # This is optimal for cosine similarity with normalized vectors
            self.index = faiss.IndexFlatIP(dimension)
            logger.info("[OK] New index created")
        
        # Load metadata
        if self.metadata_path.exists():
            logger.info(f"Loading metadata from {self.metadata_path}")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            logger.info(f"[OK] Loaded metadata for {len(self.metadata)} anime")
            
            # Rebuild ID mapping if not loaded from file OR if empty
            if not self.id_to_slug and self.index.ntotal > 0:
                logger.info("Rebuilding ID mapping from metadata...")
                self._rebuild_mapping()
        else:
            logger.warning(f"[WARNING] Metadata file not found: {metadata_path}")
            self.metadata = {}
        
        # Final validation
        if self.index.ntotal > 0 and len(self.id_to_slug) == 0:
            logger.error(
                f"[CRITICAL] Index has {self.index.ntotal} vectors "
                f"but no ID mapping! Search will fail."
            )
        elif self.index.ntotal > 0:
            logger.info(
                f"[READY] VectorStore: {self.index.ntotal} vectors, "
                f"{len(self.id_to_slug)} mappings, {len(self.metadata)} metadata entries"
            )
    
    def _rebuild_mapping(self):
        """
        Rebuild the index ID → slug mapping from metadata.
        
        FAISS assigns sequential integer IDs (0, 1, 2, ...) to vectors.
        We need to map these back to anime slugs.
        
        Strategy:
        - Only include anime that have embeddings
        - Sort by slug for deterministic ordering
        - Maintain this order when adding vectors
        """
        # Find all anime with embeddings
        anime_with_embeddings = [
            slug for slug, data in self.metadata.items()
            if data.get('embedding') is not None
        ]
        
        # Sort for deterministic ordering
        anime_with_embeddings.sort()
        
        self.id_to_slug = anime_with_embeddings
        logger.info(f"Rebuilt mapping for {len(self.id_to_slug)} vectors")
    
    def add_embedding(self, slug: str, embedding: np.ndarray) -> int:
        """
        Add a new embedding to the index.
        
        Args:
            slug: Anime identifier
            embedding: Normalized 512-dimensional vector
        
        Returns:
            FAISS index ID (sequential integer)
        
        Mathematical Requirements:
            - embedding.shape must be (512,)
            - ||embedding|| should be ≈ 1.0 (normalized)
        
        FAISS Operations:
            1. Validates dimension matches index
            2. Stores vector in optimized memory layout
            3. Assigns sequential ID
            4. Updates internal structures for search
        """
        # Validate embedding
        assert embedding.shape == (self.dimension,), \
            f"Expected shape ({self.dimension},), got {embedding.shape}"
        
        # Verify normalization (should be ~1.0)
        norm = np.linalg.norm(embedding)
        if not (0.99 < norm < 1.01):
            logger.warning(f"Embedding for {slug} not normalized: norm={norm:.6f}")
        
        # Reshape for FAISS (expects 2D array: [n_vectors, dimension])
        embedding_2d = embedding.reshape(1, -1).astype('float32')
        
        # Add to index
        self.index.add(embedding_2d)
        
        # Track mapping
        idx = len(self.id_to_slug)
        self.id_to_slug.append(slug)
        
        logger.debug(f"Added {slug} at index {idx} (total: {self.index.ntotal})")
        
        return idx
    
    def search(
        self, 
        query_embedding: np.ndarray, 
        k: int = 5,
        min_similarity: float = 0.0
    ) -> List[SearchResult]:
        """
        Find k nearest neighbors using cosine similarity.
        
        Args:
            query_embedding: Normalized 512-dim query vector
            k: Number of results to return
            min_similarity: Filter results below this threshold
        
        Returns:
            List of SearchResult, sorted by similarity (highest first)
        
        How FAISS Search Works:
        ------------------------
        1. Computes inner product: scores[i] = query · vector[i]
        2. For normalized vectors: scores[i] = cosine_similarity(query, vector[i])
        3. Returns top-k indices and scores
        4. Time complexity: O(n × d) where n=vectors, d=dimension
           - For 235 vectors × 512 dims ≈ 120K operations
           - With SIMD optimization: ~0.1-0.5 milliseconds
        
        Mathematical Detail:
            IndexFlatIP returns negative inner product as "distance"
            We convert: similarity = -distance
            Since vectors are normalized: similarity ∈ [0, 1]
        """
        # Validate query
        assert query_embedding.shape == (self.dimension,), \
            f"Query shape {query_embedding.shape} doesn't match dimension {self.dimension}"
        
        # Check if index is empty
        if self.index.ntotal == 0:
            logger.warning(
                "[ERROR] Index is empty! No vectors to search. "
                "Did the index load correctly?"
            )
            return []
        
        # Check if mapping is empty (critical error)
        if len(self.id_to_slug) == 0:
            logger.error(
                f"[CRITICAL] Index has {self.index.ntotal} vectors "
                f"but ID mapping is empty! Cannot resolve results."
            )
            return []
        
        # Validate mapping matches index
        if len(self.id_to_slug) != self.index.ntotal:
            logger.error(
                f"[ERROR] MISMATCH: Index has {self.index.ntotal} vectors "
                f"but mapping has {len(self.id_to_slug)} entries"
            )
            return []
        
        # Limit k to available vectors
        k = min(k, self.index.ntotal)
        
        # Reshape for FAISS
        query_2d = query_embedding.reshape(1, -1).astype('float32')
        
        # Perform search
        # Returns: distances (inner products), indices (FAISS IDs)
        distances, indices = self.index.search(query_2d, k)
        
        # Convert to SearchResult objects
        results = []
        for i in range(k):
            faiss_id = int(indices[0][i])
            raw_distance = float(distances[0][i])
            
            # IndexFlatIP returns inner product directly (not negated)
            # For normalized vectors, this IS the cosine similarity
            similarity = raw_distance
            
            # Skip if below threshold
            if similarity < min_similarity:
                continue
            
            # Get anime info
            if faiss_id >= len(self.id_to_slug):
                logger.error(f"Invalid FAISS ID: {faiss_id}")
                continue
            
            slug = self.id_to_slug[faiss_id]
            anime_data = self.metadata.get(slug, {})
            
            result = SearchResult(
                slug=slug,
                anime_title=anime_data.get('title', slug),
                similarity=similarity,
                poster_path=anime_data.get('path', ''),
                distance=raw_distance
            )
            results.append(result)
        
        logger.debug(f"Search returned {len(results)} results (k={k})")
        if results:
            logger.debug(f"Top match: {results[0].anime_title} (similarity={results[0].similarity:.4f})")
        
        return results
    
    def save(self):
        """
        Persist FAISS index to disk.
        
        File Format:
            - Binary format optimized for fast loading
            - Includes all vectors and index structures
            - File size: ~480KB for 235 vectors × 512 dims
        
        Note: FAISS index only stores vectors, not the slug mapping.
        The mapping is reconstructed from metadata when loading.
        
        Performance:
            - Write: ~1-2ms
            - Read: ~5-10ms
        """
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        logger.info(f"✅ Saved FAISS index to {self.index_path} ({self.index.ntotal} vectors)")
        
        # Also save the ID mapping separately for reconstruction
        mapping_path = self.index_path.with_suffix('.mapping.json')
        with open(mapping_path, 'w') as f:
            json.dump(self.id_to_slug, f, indent=2)
        logger.info(f"✅ Saved ID mapping to {mapping_path}")
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary with index statistics
        """
        return {
            'total_vectors': self.index.ntotal,
            'dimension': self.dimension,
            'index_type': 'IndexFlatIP',
            'memory_usage_mb': (self.index.ntotal * self.dimension * 4) / (1024 * 1024),
            'metadata_count': len(self.metadata),
            'mapped_ids': len(self.id_to_slug)
        }
