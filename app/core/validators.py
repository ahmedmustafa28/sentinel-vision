import ipaddress
import urllib.parse
from app.core.config import get_settings

def validate_camera_source(source: str | int) -> str | int:
    """
    Validates a camera source value.
    Accepts:
      - Integers (>= 0) for local device indices.
      - Strings representing local device indices (e.g. "0", "1", "2").
      - Valid RTSP, RTSPS, HTTP, or HTTPS URLs.
    Blocks private IP ranges unless allow_local_rtsp config option is set to True.
    Raises ValueError with details if the source is invalid.
    """
    # 1. Handle integer input
    if isinstance(source, int):
        if source < 0:
            raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")
        return source

    # 2. Handle string input
    if not isinstance(source, str):
        raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")

    stripped_source = source.strip()

    # Check if it is a bare integer string (e.g. "0", "1")
    if stripped_source.isdigit():
        val = int(stripped_source)
        if val >= 0:
            return val
        raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")

    # Parse string as URL
    try:
        parsed = urllib.parse.urlparse(stripped_source)
    except Exception as exc:
        raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed") from exc

    scheme = parsed.scheme.lower() if parsed.scheme else ""
    if scheme not in {"rtsp", "rtsps", "http", "https"}:
        raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")

    if not parsed.netloc:
        raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")

    # Check for private IP range blocking
    is_private = False
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private:
            is_private = True
    except ValueError:
        # Not a valid IP address syntax (e.g. domain name, 'localhost', etc.)
        hostname_lower = hostname.lower()
        if hostname_lower in {"localhost", "127.0.0.1", "::1"}:
            is_private = True
        elif hostname_lower.startswith("192.168.") or hostname_lower.startswith("10."):
            is_private = True
        elif hostname_lower.startswith("172."):
            parts = hostname_lower.split(".")
            if len(parts) >= 2 and parts[0] == "172":
                try:
                    second_part = int(parts[1])
                    if 16 <= second_part <= 31:
                        is_private = True
                except ValueError:
                    pass

    if is_private:
        settings = get_settings()
        if not settings.allow_local_rtsp:
            raise ValueError("Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed")

    return stripped_source
