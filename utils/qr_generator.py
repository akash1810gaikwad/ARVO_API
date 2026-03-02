"""QR Code generation utility"""
import qrcode
import io
from PIL import Image
from typing import Optional


def generate_qr_code(data: str, size: int = 200) -> bytes:
    """
    Generate QR code as PNG bytes
    
    Args:
        data: Data to encode in QR code
        size: Size of the QR code image
        
    Returns:
        PNG image bytes
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Resize if needed
    if size != img.size[0]:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes.getvalue()
