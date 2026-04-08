import base64
import sys

def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 data URL."""
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_B64.py <image_path>")
        sys.exit(1)
    print(image_to_base64(sys.argv[1]))