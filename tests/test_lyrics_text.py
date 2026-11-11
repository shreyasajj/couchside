from couchside.core.lyrics import LyricLine
from couchside.core.lyrics_text import is_english, romanize


def test_romanize_punjabi_lines():
    assert romanize("ਹਾਏ, ਨੀ old school ਜਿਹੀ ਏ") == "hae, ni old school jihi e"
    assert romanize("Hennessy ਦੇ ਵਾਂਗੂ ਨੀ ਤੂੰ ਘੁੰਮੇ ਸਾਰੇ town") == "Hennessy de vangu ni tun ghumme sare town"
    assert romanize("ਲਾਲ ਗੱਲਾਂ ਤੋਂ ਭੁਲੇਖਾ red wine ਦਾ ਐ ਪੈਂਦਾ") == "lal gallan ton bhulekha red wine da ai painda"


def test_romanize_other_scripts():
    assert romanize("तुम ही हो") == "tum hi ho"
    assert romanize("हैं") == "hain"
    assert romanize("Привет, как дела") == "Privet, kak dela"


def test_romanize_leaves_latin_alone():
    assert romanize("Café déjà vu — señor") == "Café déjà vu — señor"
    assert romanize("") == ""
    assert romanize("♪") == "♪"


def lines(*texts):
    return [LyricLine(float(i), t) for i, t in enumerate(texts)]


def test_is_english():
    assert is_english(lines("I will shelter you", "For days, for weeks, for years", "As long as you need"))
    assert not is_english(lines("ਹਾਏ, ਨੀ old school ਜਿਹੀ ਏ", "ਨੀ ਤੇਰਾ ਕੋਈ ਮੁਕਾਬਲਾ ਨਹੀਂ"))
    assert not is_english(lines("Despacito, quiero respirar tu cuello despacito", "Deja que te diga cosas al oído"))
    assert not is_english(lines("hae, ni old school jihi e", "ni tera koi mukabla nahin"))  # romanized Punjabi
    assert not is_english([])


def test_romanize_inherent_vowels():
    # the unwritten "a": at the start of a word before another consonant, and before a nasal
    assert romanize("ਨੀ ਤੇਰਾ ਕੋਈ ਮੁਕਾਬਲਾ ਨਹੀਂ") == "ni tera koi mukabla nahin"
    assert romanize("ਹੋਸ਼ ਕਿੱਥੇ ਰਹਿੰਦੀ") == "hosh kitthe rahindi"
    assert romanize("ਰੰਗ ਤੇਰਾ") == "rang tera"
    assert romanize("ਬੋਤਲੇ") == "botle"          # mid-word: no extra vowel
    assert romanize("ਕੰਮ") == "kamm"
    assert romanize("रंग") == "rang"
