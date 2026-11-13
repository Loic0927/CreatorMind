"""Safe, bounded media loading for multimodal model inputs."""

from __future__ import annotations

import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from typing import Any


MediaInput = tuple[bytes, str]


def load_media_input(media: Any) -> MediaInput | None:
    """Download one bounded Meta media asset for a multimodal model call.

    Video posts use the source media URL. Other posts use the thumbnail first,
    with the media URL as a fallback. URLs are restricted to HTTPS Instagram or
    Meta CDN hosts and the bytes are never persisted by this helper.
    """

    media_type = str(getattr(media, "media_type", "") or "").upper()
    url = (
        getattr(media, "media_url", None)
        if media_type in {"VIDEO", "REELS"}
        else getattr(media, "thumbnail_url", None) or getattr(media, "media_url", None)
    )
    if not url:
        return None

    parsed = urlparse(str(url))
    hostname = (parsed.hostname or "").lower()
    allowed_host = (
        hostname == "instagram.com"
        or hostname.endswith((".instagram.com", ".cdninstagram.com", ".fbcdn.net"))
    )
    if parsed.scheme != "https" or not allowed_host:
        return None

    maximum = int(os.getenv("POSTBRIDGE_FEEDBACK_MEDIA_BYTES", str(10 * 1024 * 1024)))
    timeout = max(1, int(os.getenv("POSTBRIDGE_FEEDBACK_MEDIA_TIMEOUT_SECONDS", "8")))
    request = Request(str(url), headers={"User-Agent": "PostBridge/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            allowed_types = {
                "image/jpeg", "image/png", "image/webp",
                "video/mp4", "video/webm", "video/quicktime",
            }
            if content_type not in allowed_types:
                return None
            length = response.headers.get("Content-Length")
            if length and int(length) > maximum:
                return None
            content = response.read(maximum + 1)
    except (HTTPError, URLError, OSError, ValueError):
        return None

    return (content, content_type) if content and len(content) <= maximum else None
