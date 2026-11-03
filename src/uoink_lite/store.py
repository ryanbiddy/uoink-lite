"""Local memory: one JSON file per video, plus simple ranked keyword search."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .fetcher import FetchResult
from .links import parse_video_id

# A 10-hour livestream is roughly 15k caption lines and well under 1 MB of
# text. These caps only stop a pathological track from filling the disk.
MAX_SEGMENTS = 40_000
MAX_TEXT_CHARS = 2_000_000

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def data_dir() -> Path:
    override = os.environ.get("UOINK_LITE_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".uoink-lite"


def query_terms(query: str) -> list[str]:
    """Lowercased unique words from the query, in order. Single letters dropped
    unless the query is nothing but single letters."""
    words = [w.lower() for w in _WORD_RE.findall(query or "")]
    kept = [w for w in words if len(w) > 1] or words
    return list(dict.fromkeys(kept))


def score_text(text: str, terms: list[str], phrase: str) -> int:
    """Score one caption line. 0 means no match.

    Each distinct term present is worth 10, each extra occurrence 1, and the
    whole query appearing as a phrase adds 25. A line that matches more of the
    query always beats one that repeats a single word.
    """
    if not terms:
        return 0
    low = text.lower()
    score = 0
    for term in terms:
        count = low.count(term)
        if count:
            score += 10 + min(count - 1, 5)
    if score and len(terms) > 1 and phrase and phrase in low:
        score += 25
    return score


@dataclass
class Hit:
    video_id: str
    title: str | None
    start: float
    text: str
    score: int
    fetched_at: str = ""


def search_record(record: dict, query: str) -> list[Hit]:
    """All matching lines in one saved video, best first, then by time."""
    terms = query_terms(query)
    phrase = " ".join((query or "").lower().split())
    title = record.get("title")
    title_bonus = 3 if title and score_text(title, terms, phrase) else 0
    hits = []
    for seg in record.get("segments", []):
        score = score_text(seg["text"], terms, phrase)
        if score:
            hits.append(
                Hit(
                    video_id=record["id"],
                    title=title,
                    start=float(seg["start"]),
                    text=seg["text"],
                    score=score + title_bonus,
                    fetched_at=record.get("fetched_at", ""),
                )
            )
    hits.sort(key=lambda h: (-h.score, h.start))
    return hits


class Store:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else data_dir()
        self.dir = self.root / "transcripts"

    def _path(self, video_id: str) -> Path:
        # parse_video_id guarantees a safe 11-char [A-Za-z0-9_-] filename.
        return self.dir / f"{parse_video_id(video_id)}.json"

    def save(self, result: FetchResult) -> dict:
        segments = []
        chars = 0
        truncated = False
        for seg in result.segments:
            if len(segments) >= MAX_SEGMENTS or chars + len(seg.text) > MAX_TEXT_CHARS:
                truncated = True
                break
            segments.append(asdict(seg))
            chars += len(seg.text)
        record = {
            "id": result.video_id,
            "url": f"https://www.youtube.com/watch?v={result.video_id}",
            "title": result.title,
            "lang": result.lang,
            "auto_generated": result.auto_generated,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "truncated": truncated,
            "segments": segments,
        }
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(result.video_id)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return record

    def load(self, video_id: str) -> dict | None:
        path = self._path(video_id)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def all(self) -> list[dict]:
        """Every readable saved record, newest first."""
        if not self.dir.is_dir():
            return []
        records = []
        for path in self.dir.glob("*.json"):
            if path.name.startswith(".tmp-"):
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(record, dict) and record.get("id") and isinstance(record.get("segments"), list):
                records.append(record)
        records.sort(key=lambda r: r.get("fetched_at", ""), reverse=True)
        return records

    def search(self, query: str, limit: int = 10) -> list[Hit]:
        """Best matching lines across every saved video.

        At most three lines per video are returned so one long video cannot
        crowd out the rest.
        """
        hits: list[Hit] = []
        for record in self.all():
            hits.extend(search_record(record, query)[:3])
        hits.sort(key=lambda h: (-h.score, -_ts(h.fetched_at), h.start))
        return hits[: max(1, limit)]


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return 0.0
