"""Base64 image encoder utility for MaintServe scale tests."""

import base64
import os
from config import TEST_IMAGES, FIXTURES_DIR


def encode_image(path: str) -> str:
    """Return a data URI (base64-encoded JPEG) for the given file path."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"


def get_test_images(n: int) -> list[str]:
    """
    Return n base64 data URIs from the fixtures folder.
    n must be 1, 2, or 3.
    Raises if fixtures are missing.
    """
    if n < 1 or n > len(TEST_IMAGES):
        raise ValueError(f"n must be between 1 and {len(TEST_IMAGES)}, got {n}")

    missing = [p for p in TEST_IMAGES[:n] if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            f"Missing fixture files: {missing}\n"
            f"Place img1.jpg, img2.jpg, img3.jpg (each <500KB) in: {FIXTURES_DIR}"
        )

    return [encode_image(p) for p in TEST_IMAGES[:n]]


def check_fixtures():
    """Print fixture status — call before running tests."""
    print(f"Fixtures directory: {FIXTURES_DIR}")
    for path in TEST_IMAGES:
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            status = "OK" if size_kb < 500 else "WARNING: >500KB"
            print(f"  {os.path.basename(path)}: {size_kb:.1f} KB  [{status}]")
        else:
            print(f"  {os.path.basename(path)}: MISSING")


if __name__ == "__main__":
    check_fixtures()
