"""
CLIP Embedder Module
====================
Converts anime poster images into 512-dimensional embedding vectors using OpenAI's CLIP model.

- Embeddings: Numerical representations of images that capture visual features
- ViT-B-32: Vision Transformer model with 32x32 patch size
- Normalization: Ensures embeddings have unit length for cosine similarity
"""

import torch
import open_clip
from PIL import Image
import numpy as np
from typing import Union
import io
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Global cache for the model (loading is expensive, ~1-2 seconds)
_model_cache = None


def load_clip_model(model_name: str = "ViT-B-32", pretrained: str = "openai"):
    """
    Load and cache the CLIP model for reuse.
    
    Why cache? Loading the model takes ~1-2 seconds and uses ~500MB RAM.
    By caching, we only pay this cost once per server lifetime.
    
    Args:
        model_name: CLIP architecture variant. ViT-B-32 balances speed and accuracy.
        pretrained: Weight source. "openai" = official weights trained on 400M images.
    
    Returns:
        Tuple of (model, preprocess_transform)
    
    Technical Details:
        - ViT-B-32 = Vision Transformer with Base size, 32x32 patches
        - Output dimension: 512 floats
        - Model size: ~350MB
    """
    global _model_cache
    
    if _model_cache is None:
        logger.info(f"Loading CLIP model: {model_name} with {pretrained} weights...")
        
        # Create model and preprocessing pipeline
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name, 
            pretrained=pretrained
        )
        
        # Set to evaluation mode (disables dropout, batch norm training behavior)
        model.eval()
        
        _model_cache = (model, preprocess)
        logger.info("✅ CLIP model loaded and cached successfully")
    
    return _model_cache


async def generate_embedding(image: Union[bytes, Image.Image]) -> np.ndarray:
    """
    Generate a 512-dimensional embedding vector from an image.
        
    Example Output:
        array([0.234, -0.123, 0.567, ..., 0.890])  # 512 numbers
        
    Processing Pipeline:
        1. Load image into PIL format
        2. Preprocess (resize to 224x224, normalize colors)
        3. Convert to tensor (numerical format for neural network)
        4. Run through CLIP encoder
        5. Normalize to unit length (for cosine similarity)
    
    """
    # Load the cached model
    model, preprocess = load_clip_model()
    
    # Convert bytes to PIL Image if needed
    if isinstance(image, bytes):
        image = Image.open(io.BytesIO(image))
        logger.debug(f"Loaded image from bytes: {image.size} pixels, mode={image.mode}")
    
    # Ensure RGB mode (CLIP expects 3 color channels)
    if image.mode != 'RGB':
        image = image.convert('RGB')
        logger.debug(f"Converted image to RGB mode")
    
    # Preprocess: resize, center crop, normalize
    # This transforms the image to what CLIP expects (224x224, normalized colors)
    image_tensor = preprocess(image).unsqueeze(0)  # unsqueeze adds batch dimension
    logger.debug(f"Preprocessed image tensor shape: {image_tensor.shape}")  # Should be [1, 3, 224, 224]
    
    # Generate embedding without gradient computation (we're not training)
    with torch.no_grad():
        # Encode image through vision transformer
        embedding = model.encode_image(image_tensor)
        
        # Normalize to unit length for cosine similarity
        # Formula: embedding / sqrt(sum of squares)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
        
        logger.debug(f"Generated embedding shape: {embedding.shape}")  # Should be [1, 512]
    
    # Convert to numpy and flatten to 1D array
    embedding_array = embedding.cpu().numpy().flatten()
    
    # Verify output shape and properties
    assert embedding_array.shape == (512,), f"Unexpected embedding shape: {embedding_array.shape}"
    norm = np.linalg.norm(embedding_array)
    logger.debug(f"Embedding norm (should be ~1.0): {norm:.6f}")
    
    return embedding_array


def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    """
    # Dot product of normalized vectors = cosine similarity
    similarity = np.dot(embedding1, embedding2)
    return float(similarity)
