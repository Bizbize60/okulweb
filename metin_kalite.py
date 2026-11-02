"""Yerel metin kalitesi.

Gibberish-Detector (https://github.com/rrenaud/Gibberish-Detector) ile aynı
fikir: temiz Türkçe metinden harf ikililerinin log olasılığı öğrenilir.
Klavye sırası ve tekrar bunu tamamlar. Dış servis veya dil modeli yok.
Kapı açıkken yüksek güvenli saçmalık hesap siler; kısa ama insan yazısı
yalnızca reddedilir.
"""
from __future__ import annotations

import math
import re

ALPHABET = "abcçdefgğhıijklmnoöprsştuüvyz "
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}

_ROWS = (
    "qwertyuıopğü",
    "asdfghjklşi",
    "zxcvbnmöç",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)

_VOWELS = set("aeıioöuü")
_PLACEHOLDERS = {
    "test", "deneme", "asdf", "qwerty", "qwert", "lorem", "ipsum",
    "asdasd", "qwe", "aaa", "asdfgh", "zxcv", "zxcvbn", "asdfasdf",
    "qwertyuiop", "loremipsum", "abc", "qaz", "wsx",
}
_CHUNK = re.compile(r"(?:asd|qwe|zxc|asdf|qwer)+")
_WORD = re.compile(r"[a-zçğıöşü]{2,}")

_CORPUS = """
merhaba millet kampüs bugün ders yemekhane hakkında konuşalım
öğrenci hoca slayt sınav quiz ödev laboratuvar kütüphane ofis saat
kayıp cüzdan telefon şarj aleti mont çanta kitap hesap makinesi anahtar
kart vizeli kimlik yemekhane menü servis otobüs durak kampüs fotoğraf
ayşe yılmaz mehmet demir elif kaya ahmet şahin zeynep çetin
fizik kimya matematik calculus lineer cebir diferansiyel programlama
arkadaşlar bu dersin notunu arıyorum final tarihi belli oldu mu
kütüphanede siyah cüzdanımı unuttum içinde kimlik ve kart var
ofis saati pazartesi öğleden sonra iki saat uygun olur mu
yemekhanede bugün menü geç çıktı servis de doluydu
lab raporunu birlikte yazalım deney sonuçları sende mi
hoca slayttan işliyor yoklama alıyor kitap şart değil
bit pazarı ilanı temiz hesap makinesi satılık pazarlık olur
bulunan eşya rektörlük önünde mavi şemsiye duruyor
kampüste akşam çektiğim fotoğraf kütüphane ışıkları çok güzeldi
yorum olarak şunu eklemek istiyorum derste bunu konuşmuştuk
ilk yorumum bu başlık hakkında şunu merak ediyorum
bir ve bu şu o da de için ile mi mı mu mü ne var yok çok daha gibi ama
ben sen biz siz her en kadar sonra önce bugün yarın şimdi lütfen olur
arkadaşlar rica ederim teşekkürler tamam peki neden nasıl nerede ne zaman
kantin yurt spor salonu amfi sınıf koridor durak servis bilet kart
vizeli kimlik anahtar şemsiye mont kulaklık laptop tablet kalem defter
final vize bütünleme ödev proje rapor slayt yoklama devam not ortalaması
satılık kiralık takas temiz kullanılmış pazarlık fiyat iletişim whatsapp
lütfen bakar mısınız yardımcı olur musunuz bilen var mı
""".strip()


def tr_lower(text: str) -> str:
    return (text or "").replace("I", "ı").replace("İ", "i").lower()


def _train(corpus: str):
    size = len(ALPHABET)
    counts = [[10 for _ in range(size)] for _ in range(size)]
    for line in corpus.splitlines():
        chars = [ch for ch in tr_lower(line) if ch in _INDEX]
        for left, right in zip(chars, chars[1:]):
            counts[_INDEX[left]][_INDEX[right]] += 1
    log_probs = []
    for row in counts:
        total = float(sum(row))
        log_probs.append([math.log(value / total) for value in row])
    return log_probs


_LOG_PROBS = _train(_CORPUS)
_KNOWN_WORDS = {token for token in _WORD.findall(tr_lower(_CORPUS)) if len(token) >= 4}


def _avg_log_prob(text: str) -> float:
    chars = [ch for ch in tr_lower(text) if ch in _INDEX]
    if len(chars) < 2:
        return -20.0
    total = 0.0
    for left, right in zip(chars, chars[1:]):
        total += _LOG_PROBS[_INDEX[left]][_INDEX[right]]
    return total / (len(chars) - 1)


def _markov_is_low(text: str) -> bool:
    # Temiz cümleler yaklaşık -2.6 ile -3.4 arasında kalır.
    # Rastgele harf dizileri -4.2 altına iner.
    return _avg_log_prob(text) < -4.05


def _letters(text: str) -> str:
    return re.sub(r"[^a-zçğıöşü]", "", tr_lower(text))


def _words(text: str) -> list[str]:
    return _WORD.findall(tr_lower(text))


def _vowel_ratio(letters: str) -> float:
    if not letters:
        return 0.0
    return sum(1 for ch in letters if ch in _VOWELS) / len(letters)


def _is_walk(chunk: str) -> bool:
    for row in _ROWS:
        if chunk in row or chunk[::-1] in row:
            return True
    return False


def _keyboard_walk(text: str) -> bool:
    for word in _words(text) or [_letters(text)]:
        if len(word) < 5:
            continue
        for index in range(len(word) - 4):
            if _is_walk(word[index:index + 5]):
                return True
    return False


def _heavy_repetition(text: str) -> bool:
    letters = _letters(text)
    if len(letters) < 6:
        return False
    if len(set(letters)) <= 2:
        return True
    return re.search(r"(.)\1{4,}", letters) is not None


def _placeholder_only(words: list[str]) -> bool:
    if not words:
        return False
    for word in words:
        if word in _PLACEHOLDERS or _CHUNK.fullmatch(word):
            continue
        return False
    return True


def classify_prose(text: str, *, min_words: int = 2, min_letters: int = 12) -> str:
    """'ok' katkı sayılır, 'thin' reddedilir, 'abuse' hesap siler."""
    raw = str(text or "").strip()
    if not raw:
        return "thin"

    words = _words(raw)
    letters = _letters(raw)
    if _keyboard_walk(raw) or _heavy_repetition(raw) or _placeholder_only(words):
        return "abuse"
    if len(letters) >= 8 and _vowel_ratio(letters) < 0.12:
        return "abuse"
    if len(letters) >= 8 and _vowel_ratio(letters) < 0.18 and _markov_is_low(raw):
        return "abuse"
    if (
        len(words) >= min_words
        and len(letters) >= min_letters
        and _vowel_ratio(letters) >= 0.22
        and any(word in _KNOWN_WORDS for word in words)
    ):
        return "ok"
    return "thin"


_NAME_TOKEN = re.compile(r"[a-zçğıöşü]{2,}(?:[ '\-][a-zçğıöşü]{2,})*")


def classify_name(ad: str, soyad: str) -> str:
    left = tr_lower(str(ad or "")).strip()
    right = tr_lower(str(soyad or "")).strip()
    if not _NAME_TOKEN.fullmatch(left) or not _NAME_TOKEN.fullmatch(right):
        blob = f"{left} {right}"
        if _keyboard_walk(blob) or _heavy_repetition(blob) or _placeholder_only(_words(blob)):
            return "abuse"
        return "thin"

    parts = _words(f"{left} {right}")
    blob = " ".join(parts)
    if _keyboard_walk(blob) or _heavy_repetition(blob) or _placeholder_only(parts):
        return "abuse"
    if any(_vowel_ratio(part) < 0.15 and len(part) >= 4 for part in parts):
        return "abuse"
    return "ok"


_WEEKDAYS = {
    "pazartesi", "salı", "sali", "çarşamba", "carsamba",
    "perşembe", "persembe", "cuma",
}
_RANGE = re.compile(
    r"^\s*(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})\s*$"
)


def _clock_verdict(value: str) -> str:
    match = _RANGE.match(value or "")
    if not match:
        return "thin"
    hour1, minute1, hour2, minute2 = (int(piece) for piece in match.groups())
    if not (0 <= hour1 <= 23 and 0 <= hour2 <= 23 and 0 <= minute1 <= 59 and 0 <= minute2 <= 59):
        return "abuse"
    start = hour1 * 60 + minute1
    end = hour2 * 60 + minute2
    if end <= start:
        return "abuse"
    if start < (7 * 60 + 30) or end > (21 * 60):
        return "abuse"
    duration = end - start
    if duration < 20 or duration > (6 * 60):
        return "abuse"
    return "ok"


def _iter_slots(days):
    if isinstance(days, dict):
        days = days.get("gun") or days.get("days") or []
    if not isinstance(days, list):
        return
    for item in days:
        if not isinstance(item, dict):
            continue
        gun = tr_lower(str(item.get("gun") or "")).strip()
        saatler = item.get("saatler")
        if saatler is None:
            saatler = item.get("saat") or []
        if isinstance(saatler, str):
            saatler = [saatler]
        if not isinstance(saatler, list):
            continue
        yield gun, [str(saat) for saat in saatler]


def classify_office_hours(days) -> str:
    saw_slot = False
    for gun, saatler in _iter_slots(days):
        if gun not in _WEEKDAYS:
            return "thin"
        if not saatler:
            return "thin"
        for saat in saatler:
            saw_slot = True
            verdict = _clock_verdict(saat)
            if verdict != "ok":
                return verdict
    if not saw_slot:
        return "thin"
    return "ok"
