from __future__ import annotations

import pytest

from uoink_lite.errors import UoinkLiteError
from uoink_lite.fetcher import FetchResult, Segment
from uoink_lite.store import Store

# Made-up videos. Ids are 11 characters like real ones but point nowhere.
FAKE_VIDEOS = {
    "AAAAAAAAAAA": FetchResult(
        video_id="AAAAAAAAAAA",
        lang="en",
        title="How sourdough starters work",
        segments=[
            Segment(0.0, 3.0, "welcome back to the kitchen"),
            Segment(3.0, 4.0, "today we feed a sourdough starter"),
            Segment(65.0, 4.0, "the starter needs flour and water every day"),
            Segment(3725.0, 5.0, "keep the starter warm and it will rise"),
        ],
    ),
    "BBBBBBBBBBB": FetchResult(
        video_id="BBBBBBBBBBB",
        lang="en",
        title="Bike maintenance basics",
        auto_generated=True,
        segments=[
            Segment(0.0, 2.0, "check your tire pressure first"),
            Segment(12.5, 3.0, "then flour... no, oil the chain"),
            Segment(30.0, 3.0, "water and grime wear the chain out"),
        ],
    ),
}


class FakeFetcher:
    def __init__(self, videos=None, error: UoinkLiteError | None = None):
        self.videos = FAKE_VIDEOS if videos is None else videos
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def fetch(self, video_id: str, lang: str) -> FetchResult:
        self.calls.append((video_id, lang))
        if self.error:
            raise self.error
        return self.videos[video_id]


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "home")


@pytest.fixture
def fetcher() -> FakeFetcher:
    return FakeFetcher()
