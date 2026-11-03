import pytest
import youtube_transcript_api as yta
from requests import HTTPError

from uoink_lite import fetcher as fetcher_mod
from uoink_lite.errors import Blocked, NoCaptions, Unavailable
from uoink_lite.fetcher import YouTubeFetcher, map_error

VID = "AAAAAAAAAAA"


@pytest.mark.parametrize(
    "exc,kind,needle",
    [
        (yta.TranscriptsDisabled(VID), NoCaptions, "uoink.app/get"),
        (yta.NoTranscriptFound(VID, ["en"], "none"), NoCaptions, "Whisper"),
        (yta.RequestBlocked(VID), Blocked, "retry"),
        (yta.IpBlocked(VID), Blocked, "retry"),
        (yta.PoTokenRequired(VID), Blocked, "retry"),
        (yta.YouTubeRequestFailed(VID, HTTPError("429 Client Error: Too Many Requests")), Blocked, "rate limiting"),
        (yta.YouTubeRequestFailed(VID, HTTPError("500 Server Error")), Unavailable, "retry"),
        (yta.VideoUnavailable(VID), Unavailable, "private, removed"),
        (yta.AgeRestricted(VID), Unavailable, "age-restricted"),
        (yta.InvalidVideoId(VID), Unavailable, "not a valid video id"),
        (yta.VideoUnplayable(VID, "nope", []), Unavailable, "unplayable"),
        (RuntimeError("boom"), Unavailable, "unexpected"),
    ],
)
def test_map_error(exc, kind, needle):
    mapped = map_error(exc, VID)
    assert isinstance(mapped, kind)
    assert needle in str(mapped)
    assert VID in str(mapped)


def test_no_captions_message_points_to_app():
    msg = str(NoCaptions(VID))
    assert msg.startswith("No captions on this video")
    assert "https://uoink.app/get" in msg


# A stand-in for youtube-transcript-api's objects, so the real fetcher's
# language handling is tested without the network.
class _Snip:
    def __init__(self, start, duration, text):
        self.start, self.duration, self.text = start, duration, text


class _Transcript:
    def __init__(self, code, generated, snippets):
        self.language_code, self.is_generated, self._snippets = code, generated, snippets

    def fetch(self):
        return self._snippets


class _List:
    def __init__(self, transcripts):
        self._t = transcripts

    def find_transcript(self, codes):
        for t in self._t:
            if t.language_code in codes:
                return t
        raise yta.NoTranscriptFound(VID, codes, "none")

    def __iter__(self):
        return iter(self._t)


class _Api:
    def __init__(self, transcripts=None, error=None):
        self.transcripts, self.error = transcripts or [], error

    def list(self, video_id):
        if self.error:
            raise self.error
        return _List(self.transcripts)


@pytest.fixture(autouse=True)
def _no_oembed(monkeypatch):
    monkeypatch.setattr(fetcher_mod, "_oembed_title", lambda vid: "A title")


def test_fetcher_picks_requested_language():
    api = _Api([
        _Transcript("de", False, [_Snip(0, 1, "hallo")]),
        _Transcript("en", True, [_Snip(0, 1, "hello\nthere"), _Snip(1, 1, "  "), _Snip(2, 1, "world")]),
    ])
    result = YouTubeFetcher(api).fetch(VID, "en")
    assert result.lang == "en"
    assert result.auto_generated is True
    assert [s.text for s in result.segments] == ["hello there", "world"]
    assert result.title == "A title"
    assert result.note is None


def test_fetcher_falls_back_to_other_language():
    api = _Api([_Transcript("es", False, [_Snip(0, 1, "hola")])])
    result = YouTubeFetcher(api).fetch(VID, "en")
    assert result.lang == "es"
    assert "returned 'es'" in result.note


def test_fetcher_no_tracks_is_no_captions():
    with pytest.raises(NoCaptions):
        YouTubeFetcher(_Api([])).fetch(VID, "en")


def test_fetcher_empty_track_is_no_captions():
    with pytest.raises(NoCaptions):
        YouTubeFetcher(_Api([_Transcript("en", True, [_Snip(0, 1, "")])])).fetch(VID, "en")


def test_fetcher_maps_library_errors():
    with pytest.raises(Blocked):
        YouTubeFetcher(_Api(error=yta.IpBlocked(VID))).fetch(VID, "en")
