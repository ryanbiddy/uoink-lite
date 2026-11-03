import json

from conftest import FAKE_VIDEOS

from uoink_lite import store as store_mod
from uoink_lite.fetcher import FetchResult, Segment
from uoink_lite.store import Store, data_dir, query_terms, score_text, search_record


def test_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("UOINK_LITE_HOME", str(tmp_path / "x"))
    assert data_dir() == tmp_path / "x"
    monkeypatch.delenv("UOINK_LITE_HOME")
    assert data_dir().name == ".uoink-lite"


def test_save_and_load_roundtrip(store):
    record = store.save(FAKE_VIDEOS["AAAAAAAAAAA"])
    path = store.dir / "AAAAAAAAAAA.json"
    assert path.is_file()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == record
    assert set(on_disk) >= {"id", "url", "title", "lang", "fetched_at", "segments"}
    assert on_disk["url"] == "https://www.youtube.com/watch?v=AAAAAAAAAAA"
    assert on_disk["segments"][1] == {"start": 3.0, "duration": 4.0, "text": "today we feed a sourdough starter"}
    assert store.load("https://youtu.be/AAAAAAAAAAA") == record
    assert store.load("BBBBBBBBBBB") is None
    assert not list(store.dir.glob(".tmp-*"))


def test_unicode_survives(store):
    store.save(FetchResult("CCCCCCCCCCC", "ja", [Segment(0, 1, "こんにちは 世界 café")], title="テスト"))
    assert store.load("CCCCCCCCCCC")["segments"][0]["text"] == "こんにちは 世界 café"


def test_all_newest_first_and_skips_junk(store):
    store.save(FAKE_VIDEOS["AAAAAAAAAAA"])
    store.save(FAKE_VIDEOS["BBBBBBBBBBB"])
    a = store.dir / "AAAAAAAAAAA.json"
    data = json.loads(a.read_text(encoding="utf-8"))
    data["fetched_at"] = "2020-01-01T00:00:00+00:00"
    a.write_text(json.dumps(data), encoding="utf-8")
    (store.dir / "garbage.json").write_text("{not json", encoding="utf-8")
    (store.dir / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert [r["id"] for r in store.all()] == ["BBBBBBBBBBB", "AAAAAAAAAAA"]


def test_empty_store(tmp_path):
    s = Store(tmp_path / "nothing-here")
    assert s.all() == []
    assert s.search("anything") == []


def test_size_cap(store, monkeypatch):
    monkeypatch.setattr(store_mod, "MAX_SEGMENTS", 3)
    segs = [Segment(i, 1, f"line {i}") for i in range(10)]
    record = store.save(FetchResult("DDDDDDDDDDD", "en", segs))
    assert len(record["segments"]) == 3
    assert record["truncated"] is True

    monkeypatch.setattr(store_mod, "MAX_SEGMENTS", 1000)
    monkeypatch.setattr(store_mod, "MAX_TEXT_CHARS", 20)
    record = store.save(FetchResult("DDDDDDDDDDD", "en", segs))
    assert sum(len(s["text"]) for s in record["segments"]) <= 20
    assert record["truncated"] is True


def test_query_terms():
    assert query_terms("Sourdough  STARTER, sourdough!") == ["sourdough", "starter"]
    assert query_terms("a b") == ["a", "b"]
    assert query_terms("a starter") == ["starter"]
    assert query_terms("   ") == []


def test_score_text_ranking():
    terms, phrase = ["sourdough", "starter"], "sourdough starter"
    both_phrase = score_text("feed a sourdough starter", terms, phrase)
    both_apart = score_text("the starter is sourdough", terms, phrase)
    one_repeated = score_text("starter starter starter starter", terms, phrase)
    none = score_text("welcome back", terms, phrase)
    assert both_phrase > both_apart > one_repeated > none == 0
    assert score_text("STARTER", ["starter"], "starter") > 0  # case-insensitive


def test_search_record_orders_by_score_then_time(store):
    record = store.save(FAKE_VIDEOS["AAAAAAAAAAA"])
    hits = search_record(record, "sourdough starter")
    assert hits[0].text == "today we feed a sourdough starter"
    rest = [h.start for h in hits[1:]]
    assert rest == sorted(rest)
    assert search_record(record, "zebra") == []


def test_search_across_videos(store):
    store.save(FAKE_VIDEOS["AAAAAAAAAAA"])
    store.save(FAKE_VIDEOS["BBBBBBBBBBB"])
    hits = store.search("flour water")
    assert {h.video_id for h in hits} == {"AAAAAAAAAAA", "BBBBBBBBBBB"}
    assert hits[0].text == "the starter needs flour and water every day"
    assert len(store.search("the", limit=2)) == 2


def test_search_caps_lines_per_video(store):
    segs = [Segment(i, 1, "chain chain chain") for i in range(20)]
    store.save(FetchResult("EEEEEEEEEEE", "en", segs, title="All chain"))
    store.save(FAKE_VIDEOS["BBBBBBBBBBB"])
    hits = store.search("chain", limit=10)
    assert sum(h.video_id == "EEEEEEEEEEE" for h in hits) == 3
    assert any(h.video_id == "BBBBBBBBBBB" for h in hits)
