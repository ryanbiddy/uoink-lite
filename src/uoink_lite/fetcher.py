"""Fetching captions from YouTube.

The server only talks to YouTube through a Fetcher, so tests can swap in a
fake one and never touch the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .errors import Blocked, NoCaptions, Unavailable, UoinkLiteError


@dataclass
class Segment:
    start: float
    duration: float
    text: str


@dataclass
class FetchResult:
    video_id: str
    lang: str
    segments: list[Segment]
    title: str | None = None
    auto_generated: bool = False
    note: str | None = None


class Fetcher(Protocol):
    def fetch(self, video_id: str, lang: str) -> FetchResult: ...


def map_error(exc: Exception, video_id: str) -> UoinkLiteError:
    """Turn a youtube-transcript-api exception into a plain-language error."""
    import youtube_transcript_api as yta

    if isinstance(exc, UoinkLiteError):
        return exc
    if isinstance(exc, yta.TranscriptsDisabled):
        return NoCaptions(video_id, "captions are turned off")
    if isinstance(exc, yta.NoTranscriptFound):
        return NoCaptions(video_id)
    if isinstance(exc, (yta.RequestBlocked, yta.PoTokenRequired)):  # IpBlocked is a RequestBlocked
        return Blocked(video_id)
    if isinstance(exc, yta.YouTubeRequestFailed):
        if "429" in str(exc) or "Too Many Requests" in str(exc):
            return Blocked(video_id)
        return Unavailable(video_id, "the request to YouTube failed; retry in a moment")
    if isinstance(exc, yta.AgeRestricted):
        return Unavailable(video_id, "the video is age-restricted, so captions need a signed-in session")
    if isinstance(exc, yta.InvalidVideoId):
        return Unavailable(video_id, "that is not a valid video id")
    if isinstance(exc, yta.VideoUnavailable):
        return Unavailable(video_id, "the video is private, removed or does not exist")
    if isinstance(exc, yta.VideoUnplayable):
        return Unavailable(video_id, "YouTube says the video is unplayable here")
    if isinstance(exc, yta.CouldNotRetrieveTranscript):
        return Unavailable(video_id, type(exc).__name__)
    return Unavailable(video_id, f"unexpected error ({type(exc).__name__})")


def _oembed_title(video_id: str) -> str | None:
    """Title from YouTube's public oEmbed endpoint. Best effort, never raises."""
    try:
        import requests

        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=5,
        )
        if resp.ok:
            title = resp.json().get("title")
            return str(title) if title else None
    except Exception:
        pass
    return None


class YouTubeFetcher:
    """Real fetcher backed by youtube-transcript-api."""

    def __init__(self, api=None):
        if api is None:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
        self._api = api

    def fetch(self, video_id: str, lang: str) -> FetchResult:
        lang = (lang or "en").strip() or "en"
        note = None
        try:
            transcripts = self._api.list(video_id)
            try:
                transcript = transcripts.find_transcript([lang])
            except Exception:
                available = list(transcripts)
                if not available:
                    raise NoCaptions(video_id) from None
                transcript = available[0]
                note = f"No '{lang}' captions; returned '{transcript.language_code}' instead."
            fetched = transcript.fetch()
        except Exception as exc:  # noqa: BLE001 - mapped to friendly errors
            raise map_error(exc, video_id) from exc

        segments = [
            Segment(float(s.start), float(s.duration), " ".join(str(s.text).split()))
            for s in fetched
        ]
        segments = [s for s in segments if s.text]
        if not segments:
            raise NoCaptions(video_id, "the caption track is empty")
        return FetchResult(
            video_id=video_id,
            lang=transcript.language_code,
            segments=segments,
            title=_oembed_title(video_id),
            auto_generated=bool(getattr(transcript, "is_generated", False)),
            note=note,
        )
