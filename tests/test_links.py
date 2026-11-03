import pytest

from uoink_lite.errors import BadUrl
from uoink_lite.links import deep_link, format_timestamp, parse_video_id

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "value",
    [
        VID,
        f"  {VID}  ",
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtube.com/watch?v={VID}&t=42s&list=PL123",
        f"https://www.youtube.com/watch?feature=share&v={VID}",
        f"http://m.youtube.com/watch?v={VID}",
        f"https://music.youtube.com/watch?v={VID}",
        f"www.youtube.com/watch?v={VID}",
        f"youtube.com/watch?v={VID}",
        f"https://youtu.be/{VID}",
        f"https://youtu.be/{VID}?si=abc&t=10",
        f"youtu.be/{VID}",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://youtube.com/shorts/{VID}?feature=share",
        f"https://www.youtube.com/embed/{VID}",
        f"https://www.youtube-nocookie.com/embed/{VID}?start=5",
        f"https://www.youtube.com/live/{VID}",
        f"https://www.youtube.com/v/{VID}",
    ],
)
def test_parse_video_id_accepts(value):
    assert parse_video_id(value) == VID


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "not a url",
        "dQw4w9WgXc",  # 10 chars
        "dQw4w9WgXcQQ",  # 12 chars
        "https://vimeo.com/123456789",
        f"https://example.com/watch?v={VID}",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/@somechannel",
        "https://www.youtube.com/playlist?list=PL123",
        "https://youtu.be/",
        "../../etc/passwd",
    ],
)
def test_parse_video_id_rejects(value):
    with pytest.raises(BadUrl) as err:
        parse_video_id(value)
    assert "11-character" in str(err.value)


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (0, "00:00"),
        (5.9, "00:05"),
        (65, "01:05"),
        (599, "09:59"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3725, "1:02:05"),
        (36000, "10:00:00"),
        (-3, "00:00"),
    ],
)
def test_format_timestamp(seconds, expected):
    assert format_timestamp(seconds) == expected


def test_deep_link():
    assert deep_link(VID) == f"https://youtu.be/{VID}"
    assert deep_link(VID, 0.4) == f"https://youtu.be/{VID}"
    assert deep_link(VID, 65.7) == f"https://youtu.be/{VID}?t=65"
    assert deep_link(VID, 3725) == f"https://youtu.be/{VID}?t=3725"
