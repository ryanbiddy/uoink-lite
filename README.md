# uoink-lite: YouTube transcript MCP server that remembers

[![CI](https://github.com/ryanbiddy/uoink-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanbiddy/uoink-lite/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Give your AI assistant a YouTube link and it reads the captions, and every transcript it fetches stays on your computer so you can search across all of them later.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). Nothing else: `uvx` downloads and runs the server for you.

**Claude Code**

```sh
claude mcp add uoink-lite -- uvx --from git+https://github.com/ryanbiddy/uoink-lite uoink-lite
```

Add `--scope user` after `add` to make it available in every project, not just the current one.

Once uoink-lite is published to PyPI, the shorter form will work:

```sh
claude mcp add uoink-lite -- uvx uoink-lite
```

**Claude Desktop, Cursor, Windsurf and other clients that use `mcpServers` JSON**

Claude Desktop: Settings > Developer > Edit Config (`claude_desktop_config.json`). Cursor: `~/.cursor/mcp.json`, or `.cursor/mcp.json` in a project.

```json
{
  "mcpServers": {
    "uoink-lite": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ryanbiddy/uoink-lite", "uoink-lite"]
    }
  }
}
```

Restart the app after saving. If it says `uvx` was not found, replace `"uvx"` with its full path (run `which uvx` on macOS/Linux or `where uvx` on Windows).

**VS Code** (Copilot agent mode)

Put this in `.vscode/mcp.json` in your workspace, or run **MCP: Open User Configuration** to use it everywhere:

```json
{
  "servers": {
    "uoink-lite": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ryanbiddy/uoink-lite", "uoink-lite"]
    }
  }
}
```

## Tools

| Tool | What it does |
| --- | --- |
| `get_transcript(url, lang="en", timestamps=True)` | The full transcript with `[mm:ss]` timestamps, plus the video title. Saves it locally. |
| `search_transcript(url, query)` | Lines in one video that match, each with its timestamp and a link that starts playback at that moment. |
| `search_saved(query, limit=10)` | Searches every transcript you have fetched before and returns the video, timestamp, line and link for each hit. |
| `list_saved(limit=20)` | What is saved, newest first. |

`url` can be a `youtube.com/watch` link, a `youtu.be` link, a Shorts or embed link, or just the 11-character video id. If the video has no captions in the language you ask for, you get a language it does have and a note saying so.

## Things to ask

- "Summarize https://youtu.be/jNQXAC9IVRw"
- "Where in this talk do they explain the pricing change? Give me timestamps."
- "Pull the three best quotes from this interview, with links to each moment."
- "Which of the videos I looked at this week mentioned vector databases?"
- "What did that cooking video say about resting the dough? I don't remember which one it was."

The last two are what the memory is for. Most YouTube transcript servers fetch, answer and forget. uoink-lite keeps what it fetched, so a question in next week's chat can still find it.

## How the memory works

Each video you fetch becomes one JSON file in `~/.uoink-lite/transcripts/` (set `UOINK_LITE_HOME` to put it somewhere else). The file holds the video id, URL, title, caption language, when it was fetched, and every caption line with its start time. Asking for the same video again reads the saved copy instead of going back to YouTube.

Search is plain keyword matching, case-insensitive. A line that contains more of your words ranks higher, and a line with your exact phrase ranks highest. No embeddings, no model downloads, no database. You can open the files, back them up, or delete them whenever you like.

A single reply is capped at about 80,000 characters, which MCP clients accept without complaint. That is a bit over an hour of speech with timestamps. The full transcript is still saved, and `search_transcript` finds anything past the cut.

## When it can't get a transcript

- **No captions.** Some videos have none, not even auto-generated ones. uoink-lite says so; it does not transcribe audio.
- **Blocked or rate limited.** YouTube sometimes refuses caption requests, more often from cloud servers and VPNs than from home connections. uoink-lite tells you plainly. Waiting a few minutes and retrying usually works. If you need a proxy, set the standard `HTTPS_PROXY` environment variable in the server's config.
- **Private, removed or age-restricted videos** return a short error that says which.

## Want podcasts, X, Reddit, caption-less videos and a desktop library? Get Uoink

uoink-lite is the small version of [Uoink](https://github.com/ryanbiddy/uoink), a free, MIT-licensed app for Windows and macOS. Uoink saves YouTube videos, podcasts, X posts and Reddit threads to a local library with transcripts, transcribes videos that have no captions using Whisper on your own machine, and gives your assistant the whole library over MCP.

Download it at [uoink.app/get](https://uoink.app/get).

## Privacy

uoink-lite only talks to YouTube: once for the captions, and once to YouTube's public oEmbed endpoint for the title. Transcripts are stored on your computer and nowhere else. There is no account, no telemetry and no API key.

## Development

```sh
git clone https://github.com/ryanbiddy/uoink-lite
cd uoink-lite
uv run --with pytest --with-editable . pytest
```

The tests never touch the network; they swap in a fake fetcher. To point a client at your local checkout instead of GitHub:

```sh
claude mcp add uoink-lite-dev -- uvx --from /path/to/uoink-lite uoink-lite
```

Captions come from [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api). The server is built on the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

## License

MIT. See [LICENSE](LICENSE).
