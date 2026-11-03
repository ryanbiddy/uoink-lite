"""YouTube URL parsing, timestamp formatting and deep links."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from .errors import BadUrl

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_PATH_PREFIXES = ("shorts", "embed", "live", "v", "e")


def parse_video_id(url_or_id: str) -> str:
    """Return the 11-character video id from a YouTube URL or bare id.

    Accepts youtube.com/watch?v=, youtu.be/, /shorts/, /embed/, /live/ and
    bare ids. Raises BadUrl for anything else.
    """
    text = (url_or_id or "").strip()
    if _ID_RE.match(text):
        return text

    candidate = text
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        raise BadUrl(text) from None
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]

    video_id = None
    if host == "youtu.be" and parts:
        video_id = parts[0]
    elif host in _YT_HOSTS:
        if parts[:1] == ["watch"] or not parts:
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        elif len(parts) >= 2 and parts[0] in _PATH_PREFIXES:
            video_id = parts[1]

    if video_id and _ID_RE.match(video_id):
        return video_id
    raise BadUrl(text)


def format_timestamp(seconds: float) -> str:
    """Format seconds as mm:ss, or h:mm:ss once past an hour."""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def deep_link(video_id: str, seconds: float = 0) -> str:
    """A youtu.be link that starts playback at the given second."""
    start = max(0, int(seconds))
    if start:
        return f"https://youtu.be/{video_id}?t={start}"
    return f"https://youtu.be/{video_id}"
