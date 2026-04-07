from PIL import Image
import base64
from io import BytesIO

def resize_and_encode(image_path: str, max_size: int = 1024) -> str:
    """Resize image and convert to base64."""
    img = Image.open(image_path)

    # Resize if larger than max_size
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = tuple(int(dim * ratio) for dim in img.size)
        img = img.resize(new_size, Image.LANCZOS)

    # Convert to JPEG
    buffer = BytesIO()
    img.convert('RGB').save(buffer, format='JPEG', quality=85)
    b64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/jpeg;base64,{b64}"