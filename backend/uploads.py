"""Upload storage — platform-aware path and file saving."""
import re
import sys
from datetime import datetime
from pathlib import Path


def get_uploads_dir() -> Path:
    """Return the platform-appropriate uploads directory, creating it if needed."""
    home = Path.home()
    if sys.platform == "darwin":
        d = home / "Library" / "Application Support" / "Adjutant" / "uploads"
    else:
        d = home / ".local" / "share" / "Adjutant" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_uploaded_file(original_name: str, data: bytes) -> Path:
    """Save bytes to the uploads dir with a timestamp prefix. Returns the saved path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w.\-]", "_", original_name)
    filename = f"{timestamp}_{safe_name}"
    dest = get_uploads_dir() / filename
    dest.write_bytes(data)
    return dest
