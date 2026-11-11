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
    assert art_url("http://h:8095/imageproxy/abc", 256) == "http://h:8095/imageproxy/abc?size=256"


def test_art_url_leaves_other_urls():
    assert art_url("https://i.scdn.co/image/x", 1024) == "https://i.scdn.co/image/x"
    assert art_url(None, 1024) == ""


def test_palette_colour():
    assert palette_colour((25, 28, 41)) == "#191c29"


def test_palette_colour_missing():
    assert palette_colour(None) == "#0d0b1a"
    assert palette_colour((300, -1, 2)) == "#0d0b1a"


def test_art_url_snaps_to_sizes_the_proxy_accepts():
    # MA 2.10.9's image proxy answers 400 for any size but 256, 512 and 1024.
    u = "http://h:8095/imageproxy/abc?size=512"
    assert art_url(u, 600) == "http://h:8095/imageproxy/abc?size=1024"
    assert art_url(u, 200) == "http://h:8095/imageproxy/abc?size=256"
    assert art_url(u, 4000) == "http://h:8095/imageproxy/abc?size=1024"
