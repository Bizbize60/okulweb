"""THK yemekhane menüsü: duyuru PDF'inden parse + Türkiye saatiyle bugünün menüsü."""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, date
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TR = ZoneInfo("Europe/Istanbul")
DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
DEFAULT_DUYURU_URL = "https://www.thk.edu.tr/en/announcements/announcements-3062"
try:
    from config import YEMEK_DUYURU_URL as _CFG_URL
    if _CFG_URL:
        DEFAULT_DUYURU_URL = _CFG_URL
except Exception:
    pass

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PDF_PATH = os.path.join(DATA_DIR, "yemek.pdf")
CACHE_PATH = os.path.join(DATA_DIR, "yemek_cache.json")
CACHE_TTL_SEC = 6 * 60 * 60  # 6 saat


def now_tr() -> datetime:
    return datetime.now(TR)


def today_tr() -> date:
    return now_tr().date()


def _headers() -> dict:
    return {"User-Agent": "Mozilla/5.0 (compatible; THKUOgrenciPortal/1.0)"}


def _find_pdf_proxy_url(duyuru_url: str) -> str | None:
    r = requests.get(duyuru_url, timeout=40, headers=_headers(), verify=False)
    r.raise_for_status()
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "media-proxy" in href and ".pdf" in href.lower():
            return urljoin("https://www.thk.edu.tr", href)
    m = re.search(r"/api/media-proxy\?url=[^\s\"']+", r.text)
    if m:
        return urljoin("https://www.thk.edu.tr", m.group(0))
    return None


def download_menu_pdf(duyuru_url: str | None = None) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    url = duyuru_url or DEFAULT_DUYURU_URL
    proxy = _find_pdf_proxy_url(url)
    if not proxy:
        raise RuntimeError("Duyuru sayfasında yemek listesi PDF linki bulunamadı.")
    r = requests.get(proxy, timeout=90, headers=_headers(), verify=False)
    r.raise_for_status()
    if b"%PDF" not in r.content[:16]:
        raise RuntimeError("İndirilen dosya geçerli bir PDF değil.")
    with open(PDF_PATH, "wb") as f:
        f.write(r.content)
    return PDF_PATH


def _parse_date_cell(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    return None


def parse_menu_pdf(pdf_path: str = PDF_PATH) -> dict[str, Any]:
    import pdfplumber

    days: dict[str, list[dict[str, Any]]] = {name: [] for name in DAY_NAMES}
    by_date: dict[str, dict[str, Any]] = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table or len(table[0]) < 10:
                    continue
                current: list[dict[str, Any] | None] = [None] * 5
                for row in table:
                    if not row or len(row) < 10:
                        continue
                    # Tarih satırı?
                    dates = [_parse_date_cell(row[i]) for i in (0, 2, 4, 6, 8)]
                    if any(dates):
                        for di, d in enumerate(dates):
                            if not d:
                                current[di] = None
                                continue
                            entry = {
                                "date": d.isoformat(),
                                "date_display": d.strftime("%d.%m.%Y"),
                                "weekday": DAY_NAMES[di],
                                "items": [],
                                "total_kcal": None,
                            }
                            current[di] = entry
                            days[DAY_NAMES[di]].append(entry)
                            by_date[d.isoformat()] = entry
                        continue

                    first = (row[0] or "").strip()
                    if first.lower() == "toplam":
                        for di in range(5):
                            entry = current[di]
                            if not entry:
                                continue
                            cal = (row[di * 2 + 1] or "").strip()
                            if cal.isdigit():
                                entry["total_kcal"] = int(cal)
                        continue

                    # Başlık / boş satır
                    if not first or first in DAY_NAMES or first.upper() == "KALORİ":
                        continue
                    if "Yemek Menüsü" in first or "Türk Hava" in first:
                        continue

                    for di in range(5):
                        entry = current[di]
                        if not entry:
                            continue
                        name = (row[di * 2] or "").strip()
                        cal = (row[di * 2 + 1] or "").strip()
                        if not name or name.lower() == "toplam":
                            continue
                        item = {"name": name}
                        if cal.isdigit():
                            item["kcal"] = int(cal)
                        entry["items"].append(item)

    return {
        "source": "pdf",
        "days": days,
        "by_date": by_date,
        "updated_at": now_tr().isoformat(),
    }


def _load_cache() -> dict[str, Any] | None:
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("_cached_at", 0)
        if time.time() - ts > CACHE_TTL_SEC:
            return None
        return data
    except Exception:
        return None


def _save_cache(data: dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = dict(data)
    payload["_cached_at"] = time.time()
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def get_menu_data(force_refresh: bool = False, duyuru_url: str | None = None) -> dict[str, Any]:
    if not force_refresh:
        cached = _load_cache()
        if cached and cached.get("by_date"):
            return cached

    try:
        if force_refresh or not os.path.exists(PDF_PATH):
            download_menu_pdf(duyuru_url)
        elif time.time() - os.path.getmtime(PDF_PATH) > CACHE_TTL_SEC:
            try:
                download_menu_pdf(duyuru_url)
            except Exception as e:
                print(f"[yemek_menu] PDF yenileme başarısız, mevcut dosya kullanılacak: {e}")
        data = parse_menu_pdf(PDF_PATH)
        _save_cache(data)
        return data
    except Exception as e:
        print(f"[yemek_menu] PDF hatası: {e}")
        # Son çare: süresi dolmuş cache
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        raise


def get_today_menu(force_refresh: bool = False) -> dict[str, Any] | None:
    data = get_menu_data(force_refresh=force_refresh)
    key = today_tr().isoformat()
    entry = data.get("by_date", {}).get(key)
    if not entry:
        return None
    return entry


def legacy_days_payload(data: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Eski yemekhane.html uyumluluğu: gün -> [YYYY:MM:DD, yemek..., ...]"""
    data = data or get_menu_data()
    out: dict[str, list[str]] = {name: [] for name in DAY_NAMES}
    for name in DAY_NAMES:
        for entry in data.get("days", {}).get(name, []):
            d = date.fromisoformat(entry["date"])
            out[name].append(d.strftime("%Y:%m:%d"))
            for item in entry.get("items", []):
                label = item["name"]
                if item.get("kcal") is not None:
                    label = f"{label} ({item['kcal']} kcal)"
                out[name].append(label)
            if entry.get("total_kcal") is not None:
                out[name].append(f"Toplam: {entry['total_kcal']} kcal")
    return out
