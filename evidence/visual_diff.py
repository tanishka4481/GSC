"""
PROVCHAIN — Visual Diff
=======================
Creates side-by-side visual comparisons of original and flagged images.
"""

import io
import logging
from PIL import Image

logger = logging.getLogger("provchain.visual_diff")


def create_visual_diff(original_bytes: bytes, flag_bytes: bytes) -> bytes:
    """
    Creates a side-by-side comparison image of the original asset and the 
    retrieved flagged asset.
    
    Args:
        original_bytes: Raw bytes of the registered asset.
        flag_bytes: Raw bytes of the image found on the web.
        
    Returns:
        PNG image bytes of the side-by-side comparison.
        Returns empty bytes if the files are not valid images.
    """
    try:
        img1 = Image.open(io.BytesIO(original_bytes)).convert("RGB")
        img2 = Image.open(io.BytesIO(flag_bytes)).convert("RGB")
        
        # Resize img2 to match img1 height while maintaining aspect ratio
        target_height = img1.height
        aspect_ratio = img2.width / img2.height
        target_width = int(target_height * aspect_ratio)
        img2 = img2.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Add a 10px black border between them
        border_width = 10
        total_width = img1.width + img2.width + border_width
        
        new_img = Image.new('RGB', (total_width, target_height), color='black')
        
        new_img.paste(img1, (0, 0))
        new_img.paste(img2, (img1.width + border_width, 0))
        
        buffer = io.BytesIO()
        new_img.save(buffer, format='PNG')
        return buffer.getvalue()
        
    except Exception as e:
        logger.warning(f"Failed to create visual diff (likely not images): {e}")
        return b""
