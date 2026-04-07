import base64

def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 data URL."""
    # Detect MIME type
    ext = image_path.lower().split('.')[-1]
    mime_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif'
    }
    mime = mime_types.get(ext, 'image/jpeg')

    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    return f"data:{mime};base64,{b64}"

# Usage
data_url = image_to_base64("photo.jpg")