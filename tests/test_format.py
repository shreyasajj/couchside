from couchside.core.format import art_url, format_time, palette_colour


def test_format_time():
    assert format_time(None) == "0:00"
    assert format_time(-3) == "0:00"
    assert format_time(5.9) == "0:05"
    assert format_time(261) == "4:21"
    assert format_time(3725) == "1:02:05"


def test_art_url_resizes_imageproxy():
    u = "http://h:8095/imageproxy/abc?size=512&fmt=jpg"
    assert art_url(u, 1024) == "http://h:8095/imageproxy/abc?size=1024&fmt=jpg"
    assert art_url("http://h:8095/imageproxy/abc", 300) == "http://h:8095/imageproxy/abc?size=300"


def test_art_url_leaves_other_urls():
    assert art_url("https://i.scdn.co/image/x", 1024) == "https://i.scdn.co/image/x"
    assert art_url(None, 1024) == ""


def test_palette_colour():
    assert palette_colour((25, 28, 41)) == "#191c29"


def test_palette_colour_missing():
    assert palette_colour(None) == "#0d0b1a"
    assert palette_colour((300, -1, 2)) == "#0d0b1a"
