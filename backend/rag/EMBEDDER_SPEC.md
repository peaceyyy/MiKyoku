# CLIP Embedder Subagent Specification

**Task ID:** #3 (CLIP embedder subagent)  
**Status:** Ready for implementation  
**Assigned to:** Subagent (awaiting handoff)

---

## Objective

Implement `backend/rag/clip_embedder.py` — a production-ready module for loading CLIP models, preprocessing images, and generating L2-normalized 512-dimensional embeddings with GPU/CPU fallback.

---

## Context for Subagent

**Project:** Anime poster identification system using RAG (CLIP embeddings + FAISS)  
**Architecture:** FastAPI backend, React frontend  
**Your role:** Build the embedding engine that converts poster images → vectors

**What exists:**
- Normalized posters in `posters/` directory
- Metadata in `data/posters.json`
- Project uses Windows + RTX GPU (CUDA 12.1)

**What you're building:**
- Standalone embedder module with clear API
- Config-driven (model name, device, batch size)
- Safe GPU memory handling
- Preprocessing aligned with CLIP requirements

---

## Requirements

### 1. Module API

Create `backend/rag/clip_embedder.py` with:

```python
class CLIPEmbedder:
    def __init__(self, model_name: str = "ViT-B/32", device: str = "auto"):
        """Initialize CLIP model.
        
        Args:
            model_name: CLIP model variant (default: ViT-B/32)
            device: 'cuda', 'cpu', or 'auto' (auto-detect)
        """
        pass
    
    def embed_image(self, image_path: str | Path) -> np.ndarray:
        """Embed single image to 512-d L2-normalized vector.
        
        Args:
            image_path: Path to image file
            
        Returns:
            numpy array of shape (512,), dtype=float32, L2-normalized
        """
        pass
    
    def embed_batch(self, image_paths: List[str | Path], batch_size: int = 16) -> np.ndarray:
        """Embed multiple images in batches.
        
        Args:
            image_paths: List of image paths
            batch_size: Batch size for GPU (default: 16)
            
        Returns:
            numpy array of shape (N, 512), dtype=float32, L2-normalized
        """
        pass
    
    def preprocess(self, image: PIL.Image.Image) -> torch.Tensor:
        """Preprocess PIL image for CLIP (internal helper)."""
        pass
```

### 2. Technical Constraints

- **Model:** Use `open-clip-torch` library (already in requirements)
- **Output dimensionality:** 512 (ViT-B/32 outputs 512-d by default)
- **Normalization:** L2-normalize all embeddings (required for cosine similarity via FAISS inner product)
- **Device handling:**
  - Auto-detect GPU availability
  - Graceful CPU fallback if CUDA unavailable
  - Small batch sizes (8-16) on GPU to avoid OOM
- **Preprocessing:**
  - Resize to CLIP's expected input (typically 224x224)
  - Apply CLIP's normalization (mean/std from model)
  - Handle various image formats (JPEG, PNG, JFIF, WebP)
- **Error handling:**
  - Graceful handling of corrupt images
  - Clear error messages for missing files
  - Log warnings for preprocessing issues

### 3. Configuration

Support config via:
- Constructor arguments (model_name, device)
- Optional: load from `config.json` (future extension)

Suggested config structure:
```json
{
  "clip": {
    "model_name": "ViT-B/32",
    "pretrained": "openai",
    "device": "auto",
    "batch_size": 16
  }
}
```

### 4. Performance & Safety

- Use `torch.no_grad()` for inference (no gradients needed)
- Use `model.eval()` mode
- Optional: mixed precision (`torch.cuda.amp.autocast`) for GPU memory savings (test correctness first)
- Clear GPU cache between large batches if needed (`torch.cuda.empty_cache()`)
- Progress bar for batch processing (use `tqdm`)

### 5. Testing

Provide a simple test/demo at the bottom of the file:

```python
if __name__ == "__main__":
    # Test single image embedding
    embedder = CLIPEmbedder()
    embedding = embedder.embed_image("posters/steins_gate.png")
    print(f"Embedding shape: {embedding.shape}")
    print(f"L2 norm: {np.linalg.norm(embedding):.4f}")  # should be ~1.0
    
    # Test batch embedding
    paths = list(Path("posters").glob("*.png"))[:5]
    embeddings = embedder.embed_batch(paths, batch_size=2)
    print(f"Batch shape: {embeddings.shape}")
```

---

## Implementation Steps (Suggested)

1. **Imports & setup**
   - Import open_clip, torch, PIL, numpy, pathlib
   - Define model registry if supporting multiple variants

2. **Model loading**
   - Use `open_clip.create_model_and_transforms()`
   - Load pretrained weights
   - Move to device (GPU/CPU)
   - Set to eval mode

3. **Preprocessing**
   - Use transforms from `open_clip` (handles resize, normalize)
   - Add error handling for corrupt images

4. **Single image embedding**
   - Load image with PIL
   - Preprocess
   - Forward pass with `model.encode_image()`
   - Extract features, normalize to L2=1

5. **Batch embedding**
   - Loop over batches
   - Stack preprocessed tensors
   - Forward pass
   - Normalize all outputs

6. **Testing**
   - Run demo code
   - Verify output shape (512,)
   - Verify L2 norm ≈ 1.0
   - Test on GPU and CPU

---

## Deliverables

1. **File:** `backend/rag/clip_embedder.py` (fully documented)
2. **Test output:** Run the `if __name__ == "__main__"` block and paste results
3. **Notes:** Any issues, decisions, or edge cases discovered

---

## Edge Cases to Handle

- Corrupt/truncated image files → skip with warning
- Grayscale images → convert to RGB
- Very large images → resize without quality loss
- CUDA out of memory → reduce batch size or fallback to CPU
- Missing CUDA drivers → auto-fallback to CPU with informative message

---

## Questions for User (ask before implementing if unclear)

1. Should I support other CLIP variants (ViT-L/14, etc.) or just ViT-B/32 for MVP?
2. Should config be loaded from `config.json` or constructor args only?
3. Any preference for error logging (print, logging module, exceptions)?

---

## Success Criteria

- ✅ Single image embedding works on GPU and CPU
- ✅ Batch embedding works with progress bar
- ✅ Embeddings are L2-normalized (norm ≈ 1.0)
- ✅ Output shape is (512,) for single, (N, 512) for batch
- ✅ Handles common image formats (JPEG, PNG, WebP)
- ✅ Clear error messages for edge cases
- ✅ Demo code runs successfully

---

**Next steps after this task:**
- Implement `scripts/build_embeddings.py` (uses this embedder)
- Implement `rag/vector_store.py` (FAISS wrapper)

---

*File: [backend/rag/EMBEDDER_SPEC.md](backend/rag/EMBEDDER_SPEC.md)*
