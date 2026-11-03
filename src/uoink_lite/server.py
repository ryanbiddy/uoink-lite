"""The MCP server: four tools over stdio."""

from __future__ import annotations

import inspect

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .errors import GET_UOINK_URL, UoinkLiteError
from .fetcher import Fetcher, YouTubeFetcher
from .links import deep_link, format_timestamp, parse_video_id
from .store import Store, search_record

# Keep a single tool result under what MCP clients accept by default
# (Claude Code warns above roughly 25k tokens).
MAX_OUTPUT_CHARS = 80_000
MAX_VIDEO_MATCHES = 30

INSTRUCTIONS = (
    "uoink-lite fetches YouTube captions and keeps every transcript it fetches on this computer, "
    "so earlier videos stay searchable with search_saved. "
    "Use get_transcript to read a video, search_transcript to find where something is said, "
    "search_saved to search everything fetched before, and list_saved to see what is saved. "
    "Quote timestamps and deep links when you cite a moment. "
    f"Uoink, the full desktop app, also saves podcasts, X and Reddit and transcribes caption-less videos: {GET_UOINK_URL}"
)


def _label(record: dict) -> str:
    return record.get("title") or record["id"]


def _lang_matches(record: dict, lang: str) -> bool:
    saved = (record.get("lang") or "").lower()
    want = (lang or "en").lower()
    return saved == want or saved.split("-")[0] == want.split("-")[0]


def _render_transcript(record: dict, timestamps: bool, limit: int | None = None) -> tuple[str, float | None]:
    """Body text, plus the start time where it was cut if it hit the limit."""
    limit = MAX_OUTPUT_CHARS if limit is None else limit
    out: list[str] = []
    used = 0
    for seg in record["segments"]:
        line = f"[{format_timestamp(seg['start'])}] {seg['text']}" if timestamps else seg["text"]
        if used + len(line) + 1 > limit:
            return ("\n" if timestamps else " ").join(out), seg["start"]
        out.append(line)
        used += len(line) + 1
    return ("\n" if timestamps else " ").join(out), None


def build_server(store: Store | None = None, fetcher: Fetcher | None = None) -> MCPServer:
    store = store if store is not None else Store()
    _fetcher: list[Fetcher | None] = [fetcher]

    def get_fetcher() -> Fetcher:
        if _fetcher[0] is None:
            _fetcher[0] = YouTubeFetcher()
        return _fetcher[0]

    def get_record(url: str, lang: str, any_lang: bool = False) -> tuple[dict, bool, str | None]:
        """(record, came_from_cache, note). Raises ToolError with a readable message."""
        try:
            video_id = parse_video_id(url)
            cached = store.load(video_id)
            if cached and (any_lang or _lang_matches(cached, lang)):
                return cached, True, None
            result = get_fetcher().fetch(video_id, lang)
            return store.save(result), False, result.note
        except UoinkLiteError as exc:
            raise ToolError(str(exc)) from exc

    server = MCPServer(
        name="uoink-lite",
        version=__version__,
        instructions=INSTRUCTIONS,
        website_url="https://github.com/ryanbiddy/uoink-lite",
    )

    def tool(read_only: bool):
        """Register a plain-text tool whose docstring is its description."""

        def register(fn):
            return server.tool(
                description=inspect.cleandoc(fn.__doc__ or ""),
                structured_output=False,
                annotations=ToolAnnotations(read_only_hint=read_only, open_world_hint=not read_only),
            )(fn)

        return register

    @tool(read_only=False)
    def get_transcript(url: str, lang: str = "en", timestamps: bool = True) -> str:
        """Get a YouTube video's transcript, with [mm:ss] timestamps by default.

        Accepts any YouTube video URL (watch, youtu.be, shorts, embed) or an
        11-character video id. lang is a caption language code such as "en" or
        "es". The transcript is saved locally so search_saved can find it later.
        """
        record, cached, note = get_record(url, lang)
        body, cut_at = _render_transcript(record, timestamps)
        head = [
            f"Title: {record.get('title') or '(unknown)'}",
            f"Video: {deep_link(record['id'])}",
            f"Language: {record.get('lang')}{' (auto-generated)' if record.get('auto_generated') else ''}",
            f"Saved locally: yes{' (already saved ' + record.get('fetched_at', '')[:10] + ')' if cached else ''}",
        ]
        if note:
            head.append(f"Note: {note}")
        text = "\n".join(head) + "\n\n" + body
        if cut_at is not None:
            text += (
                f"\n\n[Transcript cut at {format_timestamp(cut_at)} to fit the response limit. "
                "The full transcript is saved; use search_transcript to find specific parts.]"
            )
        elif record.get("truncated"):
            text += "\n\n[This transcript was very long and was capped when saved.]"
        return text

    @tool(read_only=False)
    def search_transcript(url: str, query: str) -> str:
        """Find where a video talks about something.

        Returns matching transcript lines with timestamps and a deep link to
        each moment (https://youtu.be/ID?t=SECONDS). Matching is
        case-insensitive keyword matching, best matches first.
        """
        record, _, _ = get_record(url, "en", any_lang=True)
        hits = search_record(record, query)
        if not hits:
            return f"No lines in \"{_label(record)}\" match {query!r}."
        shown = hits[:MAX_VIDEO_MATCHES]
        lines = [f"{len(hits)} matching line(s) in \"{_label(record)}\" for {query!r}:"]
        if len(hits) > len(shown):
            lines[0] += f" (top {len(shown)} shown)"
        for h in shown:
            lines.append(f"[{format_timestamp(h.start)}] {h.text}  {deep_link(h.video_id, h.start)}")
        return "\n".join(lines)

    @tool(read_only=True)
    def search_saved(query: str, limit: int = 10) -> str:
        """Search every transcript fetched before, across all saved videos.

        Returns the video, timestamp, matching line and a deep link for each
        hit, best matches first. Use this when the user refers to something
        they watched or asked about earlier.
        """
        limit = max(1, min(int(limit), 100))
        if not store.all():
            return (
                "Nothing saved yet. Transcripts are saved automatically whenever "
                "get_transcript or search_transcript fetches a video."
            )
        hits = store.search(query, limit)
        if not hits:
            return f"No saved transcript matches {query!r}."
        lines = [f"{len(hits)} result(s) for {query!r}:"]
        for i, h in enumerate(hits, 1):
            title = h.title or h.video_id
            lines.append(
                f"{i}. {title} [{format_timestamp(h.start)}] \"{h.text}\" {deep_link(h.video_id, h.start)}"
            )
        return "\n".join(lines)

    @tool(read_only=True)
    def list_saved(limit: int = 20) -> str:
        """List saved transcripts, newest first, with title, id and date."""
        limit = max(1, min(int(limit), 200))
        records = store.all()
        if not records:
            return "Nothing saved yet. Use get_transcript on a YouTube video to start."
        lines = [f"{len(records)} saved transcript(s), newest first:"]
        for r in records[:limit]:
            lines.append(
                f"- {_label(r)} ({r['id']}) {r.get('lang', '')}, {len(r['segments'])} lines, "
                f"saved {r.get('fetched_at', '')[:10]} {deep_link(r['id'])}"
            )
        if len(records) > limit:
            lines.append(f"...and {len(records) - limit} more.")
        lines.append("")
        lines.append(f"Stored in {store.dir}")
        lines.append(
            f"For podcasts, X, Reddit, caption-less videos and a desktop library, see Uoink: {GET_UOINK_URL}"
        )
        return "\n".join(lines)

    return server


def main() -> None:
    build_server().run("stdio")
