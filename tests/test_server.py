"""In-process MCP tests: a real client talks to the server, no network."""

import asyncio

from conftest import FakeFetcher

from mcp import Client

from uoink_lite import server as server_mod
from uoink_lite.errors import Blocked, NoCaptions
from uoink_lite.server import build_server

TOOLS = {"get_transcript", "search_transcript", "search_saved", "list_saved"}


def call(server, name, args=None):
    async def go():
        async with Client(server) as client:
            result = await client.call_tool(name, args or {})
            text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
            return result.is_error, text

    return asyncio.run(go())


def test_lists_tools_and_instructions(store, fetcher):
    server = build_server(store, fetcher)

    async def go():
        async with Client(server) as client:
            tools = await client.list_tools()
            return tools

    tools = asyncio.run(go())
    tool_list = getattr(tools, "tools", tools)
    assert {t.name for t in tool_list} == TOOLS
    for t in tool_list:
        assert t.description and len(t.description) < 400
    assert "uoink.app/get" in server.instructions
    get = next(t for t in tool_list if t.name == "get_transcript")
    assert get.input_schema["required"] == ["url"]


def test_get_transcript_with_timestamps_and_saves(store, fetcher):
    server = build_server(store, fetcher)
    err, text = call(server, "get_transcript", {"url": "https://youtu.be/AAAAAAAAAAA"})
    assert not err
    assert "Title: How sourdough starters work" in text
    assert "[00:03] today we feed a sourdough starter" in text
    assert "[1:02:05] keep the starter warm" in text
    assert "uoink.app" not in text  # no nagging in normal results
    assert store.load("AAAAAAAAAAA") is not None


def test_get_transcript_without_timestamps(store, fetcher):
    err, text = call(build_server(store, fetcher), "get_transcript", {"url": "AAAAAAAAAAA", "timestamps": False})
    assert not err
    assert "welcome back to the kitchen today we feed" in text
    assert "[00:" not in text


def test_get_transcript_uses_saved_copy(store, fetcher):
    server = build_server(store, fetcher)
    call(server, "get_transcript", {"url": "AAAAAAAAAAA"})
    err, text = call(server, "get_transcript", {"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA"})
    assert not err
    assert "already saved" in text
    assert len(fetcher.calls) == 1


def test_get_transcript_cuts_long_output(store, fetcher, monkeypatch):
    monkeypatch.setattr(server_mod, "MAX_OUTPUT_CHARS", 60)
    err, text = call(build_server(store, fetcher), "get_transcript", {"url": "AAAAAAAAAAA"})
    assert not err
    assert "Transcript cut at" in text
    assert "keep the starter warm" not in text


def test_bad_url_is_clear_error(store, fetcher):
    err, text = call(build_server(store, fetcher), "get_transcript", {"url": "https://vimeo.com/1"})
    assert err
    assert "Not a YouTube video URL" in text
    assert fetcher.calls == []


def test_no_captions_error_points_to_app(store):
    server = build_server(store, FakeFetcher(error=NoCaptions("ZZZZZZZZZZZ")))
    err, text = call(server, "get_transcript", {"url": "ZZZZZZZZZZZ"})
    assert err
    assert "No captions on this video" in text
    assert "https://uoink.app/get" in text


def test_blocked_error_says_retry(store):
    server = build_server(store, FakeFetcher(error=Blocked("ZZZZZZZZZZZ")))
    err, text = call(server, "search_transcript", {"url": "ZZZZZZZZZZZ", "query": "x"})
    assert err
    assert "rate limiting or blocking" in text and "retry" in text


def test_search_transcript_deep_links(store, fetcher):
    err, text = call(build_server(store, fetcher), "search_transcript", {"url": "AAAAAAAAAAA", "query": "starter"})
    assert not err
    assert "3 matching line(s)" in text
    assert "[01:05] the starter needs flour and water every day  https://youtu.be/AAAAAAAAAAA?t=65" in text
    assert "https://youtu.be/AAAAAAAAAAA?t=3725" in text


def test_search_transcript_no_match(store, fetcher):
    err, text = call(build_server(store, fetcher), "search_transcript", {"url": "AAAAAAAAAAA", "query": "zebra"})
    assert not err
    assert "No lines" in text


def test_search_saved_remembers_across_videos(store, fetcher):
    server = build_server(store, fetcher)
    err, text = call(server, "search_saved", {"query": "flour"})
    assert "Nothing saved yet" in text
    call(server, "get_transcript", {"url": "AAAAAAAAAAA"})
    call(server, "get_transcript", {"url": "BBBBBBBBBBB"})

    # A fresh server over the same folder still remembers.
    err, text = call(build_server(store, FakeFetcher(videos={})), "search_saved", {"query": "flour water", "limit": 5})
    assert not err
    lines = text.splitlines()
    assert lines[1].startswith('1. How sourdough starters work [01:05] "the starter needs flour and water every day"')
    assert lines[1].endswith("https://youtu.be/AAAAAAAAAAA?t=65")
    assert "Bike maintenance basics" in text


def test_list_saved_with_footer(store, fetcher):
    server = build_server(store, fetcher)
    err, text = call(server, "list_saved")
    assert "Nothing saved yet" in text
    call(server, "get_transcript", {"url": "AAAAAAAAAAA"})
    call(server, "get_transcript", {"url": "BBBBBBBBBBB"})
    err, text = call(server, "list_saved", {"limit": 1})
    assert not err
    assert "2 saved transcript(s)" in text
    assert "...and 1 more." in text
    assert "https://uoink.app/get" in text
