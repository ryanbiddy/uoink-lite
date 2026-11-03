# Changelog

## 0.1.0 (2026-11-02)

First release.

- `get_transcript`: full YouTube transcript with `[mm:ss]` timestamps and the video title. Accepts watch, youtu.be, Shorts, embed and live links or a bare video id. Falls back to another caption language when the requested one is missing, and says so.
- `search_transcript`: matching lines in one video with timestamps and deep links (`https://youtu.be/ID?t=SECONDS`).
- `search_saved`: ranked keyword search across every transcript fetched before.
- `list_saved`: saved transcripts, newest first.
- Local memory: one JSON file per video under `~/.uoink-lite/` (override with `UOINK_LITE_HOME`). Repeat requests read the saved copy.
- Plain-language errors for missing captions, YouTube rate limiting or blocking, unavailable videos and bad URLs.
