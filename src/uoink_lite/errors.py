"""Errors with messages written for the model (and the person) to read."""

from __future__ import annotations

GET_UOINK_URL = "https://uoink.app/get"


class UoinkLiteError(Exception):
    """Base class. str(err) is the message shown to the client."""


class BadUrl(UoinkLiteError):
    def __init__(self, value: str):
        super().__init__(
            f"Not a YouTube video URL or id: {value!r}. "
            "Use a youtube.com/watch, youtu.be, shorts or embed link, or the 11-character video id."
        )


class NoCaptions(UoinkLiteError):
    def __init__(self, video_id: str, detail: str = ""):
        extra = f" ({detail})" if detail else ""
        super().__init__(
            f"No captions on this video{extra}: {video_id}. "
            "The full Uoink app transcribes caption-less videos locally with Whisper: "
            f"{GET_UOINK_URL}"
        )


class Blocked(UoinkLiteError):
    def __init__(self, video_id: str):
        super().__init__(
            f"YouTube is rate limiting or blocking transcript requests from this network (video {video_id}). "
            "This is on YouTube's side, not a problem with the video. Wait a few minutes and retry. "
            "Cloud servers and VPNs get blocked more often than home connections."
        )


class Unavailable(UoinkLiteError):
    def __init__(self, video_id: str, reason: str):
        super().__init__(f"Could not get video {video_id}: {reason}.")
