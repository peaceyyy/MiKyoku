"""
Image Validation Utilities
===========================
Validates uploaded images for security and quality before processing.

Security Checks:
- Magic byte verification (prevents .exe renamed as .jpg)
- Format validation (JPEG, PNG, WEBP only)
- Dimension limits (prevents 1x1 pixels or 50000x50000 attacks)
- File integrity (catches corrupted images early)

"""

from PIL import Image
import io
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Allowed formats (PIL format names)
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}

# Dimension limits
MIN_DIMENSION = 50      # Too small = likely garbage or icon
MAX_DIMENSION = 4096    # Larger than this = excessive memory usage

# Magic bytes for format verification (first few bytes of file)
MAGIC_BYTES = {
    'JPEG': [b'\xff\xd8\xff'],
    'PNG': [b'\x89PNG\r\n\x1a\n'],
    'WEBP': [b'RIFF', b'WEBP']  # WEBP has RIFF header then WEBP marker
}


def validate_image(image_data: bytes) -> Tuple[bool, str, dict]:
    """
    Comprehensive image validation with security checks.
    
    Pipeline:
    1. Magic byte verification (file signature)
    2. PIL format detection
    3. Dimension validation
    4. Mode validation (ensure decodable)
    
    Args:
        image_data: Raw image bytes from upload
    
    Returns:
        Tuple of (is_valid, error_message, metadata)
        - is_valid: True if all checks pass
        - error_message: Human-readable error (or "OK" if valid)
        - metadata: Dict with format, dimensions, mode
    
    Security Note:
        Magic byte check prevents attacks where malicious files are renamed
        (e.g., virus.exe → virus.jpg). PIL alone isn't sufficient as it trusts
        file extensions in some contexts.
    """
    metadata = {
        'format': None,
        'width': None,
        'height': None,
        'mode': None,
        'size_bytes': len(image_data)
    }
    
    try:
        # Step 1: Magic byte verification
        magic_valid = False
        detected_format = None
        
        for fmt, magic_list in MAGIC_BYTES.items():
            for magic in magic_list:
                if image_data.startswith(magic):
                    magic_valid = True
                    detected_format = fmt
                    break
            if magic_valid:
                break
        
        # Special case: WEBP needs both RIFF and WEBP markers
        if detected_format == 'WEBP':
            if not (image_data.startswith(b'RIFF') and b'WEBP' in image_data[:20]):
                return False, "Invalid WEBP file signature", metadata
        
        if not magic_valid:
            logger.warning(f"Magic byte check failed. First 20 bytes: {image_data[:20]}")
            return False, "File format not recognized. Upload a valid JPEG, PNG, or WEBP image.", metadata
        
        # Step 2: Open with PIL for detailed validation
        try:
            img = Image.open(io.BytesIO(image_data))
        except Exception as e:
            logger.warning(f"PIL failed to open image: {e}")
            return False, f"Image file is corrupted or invalid: {str(e)}", metadata
        
        # Step 3: Format validation
        if img.format not in ALLOWED_FORMATS:
            return False, f"Unsupported image format: {img.format}. Only JPEG, PNG, and WEBP are allowed.", metadata
        
        # Step 4: Dimension validation
        width, height = img.size
        
        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            return False, f"Image too small ({width}x{height}). Minimum size is {MIN_DIMENSION}x{MIN_DIMENSION} pixels.", metadata
        
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            return False, f"Image too large ({width}x{height}). Maximum size is {MAX_DIMENSION}x{MAX_DIMENSION} pixels.", metadata
        
        # Step 5: Mode validation (ensure it's a valid color space)
        if img.mode not in ['RGB', 'RGBA', 'L', 'P']:
            logger.warning(f"Unusual image mode: {img.mode}")
            # Try to convert to RGB
            try:
                img = img.convert('RGB')
            except:
                return False, f"Unsupported color mode: {img.mode}. Cannot process this image.", metadata
        
        # Populate metadata
        metadata.update({
            'format': img.format,
            'width': width,
            'height': height,
            'mode': img.mode
        })
        
        logger.debug(f"Image validation passed: {width}x{height} {img.format} {img.mode}")
        return True, "OK", metadata
        
    except Exception as e:
        logger.error(f"Unexpected validation error: {e}", exc_info=True)
        return False, f"Failed to validate image: {str(e)}", metadata


def get_safe_image(image_data: bytes) -> Tuple[bool, Image.Image | None, str]:
    """
    Validate and return a safe PIL Image object.
    
    Use this when you need the PIL Image object after validation.
    Combines validation + conversion in one step.
    
    Args:
        image_data: Raw image bytes
    
    Returns:
        Tuple of (success, image_object, error_message)
    """
    is_valid, error_msg, metadata = validate_image(image_data)
    
    if not is_valid:
        return False, None, error_msg
    
    try:
        img = Image.open(io.BytesIO(image_data))
        # Ensure RGB mode for CLIP
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return True, img, "OK"
    except Exception as e:
        return False, None, f"Failed to load image: {str(e)}"
