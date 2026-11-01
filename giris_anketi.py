"""Giriş anketi: tek seferlik, istekler tablosu üzerinden."""
from __future__ import annotations

import re

from database.initdb import db
from database.istek import Istek

GIRIS_ANKETI_KATEGORI = 'Giriş Anketi'
GIRIS_ANKETI_DURUM_TAMAMLANDI = 'Gönderildi'
MIN_SITE_YORUM_KARAKTER = 10
MAX_SITE_YORUM_KARAKTER = 4000


def count_comment_characters(text: str) -> int:
    if text is None:
        return 0
    return len(str(text).strip())


_GIBBERISH_WORD = re.compile(
    r'^(?:(?:asdf)+|(?:qwer)+|(?:zxcv)+|qwerty+|asdasd+|deneme+|test+|lorem+|ipsum+|asdfgh+|qwert+|zxcvbn+)$',
    re.IGNORECASE,
)
_TR_VOWELS = set('aeıioöuü')


def comment_is_gibberish(text: str) -> bool:
    """Klavye ezmesi ve anlamsız tekrarları reddeder (asdf, qwerty, aaaa)."""
    raw = (text or '').strip().lower()
    letters = re.sub(r'[^a-zçğıöşü]', '', raw)
    if len(letters) < 8:
        return True
    if len(set(letters)) <= 3:
        return True
    if re.fullmatch(r'(.)\1+', letters):
        return True
    vowels = sum(1 for char in letters if char in _TR_VOWELS)
    if vowels / len(letters) < 0.18:
        return True
    words = re.findall(r'[a-zçğıöşü]{2,}', raw)
    if len(words) < 2:
        return True
    mashed = 0
    for word in words:
        if _GIBBERISH_WORD.match(word) or len(set(word)) <= 2:
            mashed += 1
    return mashed == len(words)


def user_completed_giris_anketi(user_id: int) -> bool:
    if not user_id:
        return False
    return (
        Istek.query.filter_by(
            user_id=user_id,
            kategori=GIRIS_ANKETI_KATEGORI,
            durum=GIRIS_ANKETI_DURUM_TAMAMLANDI,
        ).first()
        is not None
    )


def parse_google_ads_choice(baslik: str) -> str | None:
    if not baslik:
        return None
    m = re.search(r'(?:Google Ads|Sitede reklam):\s*(Evet|Hayır)\s*$', baslik)
    return m.group(1) if m else None


def build_giris_anketi_baslik(google_ads_evet: bool) -> str:
    oy = 'Evet' if google_ads_evet else 'Hayır'
    return f'Giriş anketi · Sitede reklam: {oy}'
