"""Giriş anketi: tek seferlik, istekler tablosu üzerinden."""
from __future__ import annotations

import re

from database.initdb import db
from database.istek import Istek

GIRIS_ANKETI_KATEGORI = 'Giriş Anketi'
GIRIS_ANKETI_DURUM_TAMAMLANDI = 'Gönderildi'
MIN_SITE_YORUM_KELIME = 10
MAX_SITE_YORUM_KARAKTER = 4000


def count_words(text: str) -> int:
    if not text or not str(text).strip():
        return 0
    parts = str(text).split()
    return sum(1 for p in parts if re.search(r'[\w\d]', p, re.UNICODE))


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
    m = re.search(r'Google Ads:\s*(Evet|Hayır)\s*$', baslik)
    return m.group(1) if m else None


def build_giris_anketi_baslik(google_ads_evet: bool) -> str:
    oy = 'Evet' if google_ads_evet else 'Hayır'
    return f'Giriş anketi · Google Ads: {oy}'
