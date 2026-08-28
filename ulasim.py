"""THK servis + Başkentray sabit saatleri (Europe/Istanbul)."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TR = ZoneInfo("Europe/Istanbul")

# THK Üniversitesi kalkış → Ümitköy Metro varış
THK_SERVIS = [
    {
        "id": "thk-sabah-1",
        "kalkis": "07:20",
        "varis": "07:55",
        "kalkis_yeri": "T.H.K Üniversitesi",
        "varis_yeri": "Ümitköy Metro",
        "yon": "Ümitköy",
    },
    {
        "id": "thk-sabah-2",
        "kalkis": "07:45",
        "varis": "07:55",
        "kalkis_yeri": "T.H.K Üniversitesi",
        "varis_yeri": "Ümitköy Metro",
        "yon": "Ümitköy",
    },
    {
        "id": "thk-aksam-1",
        "kalkis": "16:45",
        "varis": "17:25",
        "kalkis_yeri": "T.H.K Üniversitesi",
        "varis_yeri": "Ümitköy Metro",
        "yon": "Ümitköy",
    },
    {
        "id": "thk-aksam-2",
        "kalkis": "17:10",
        "varis": "17:25",
        "kalkis_yeri": "T.H.K Üniversitesi",
        "varis_yeri": "Ümitköy Metro",
        "yon": "Ümitköy",
    },
]

# Başkentray — sabah/öğleden önce dilimi (kullanıcı verisi)
BASKENTRAY = {
    "sincan_kayas": {
        "label": "Sincan → Kayaş",
        "durak_notu": "Genel hat saatleri",
        "saatler": [
            "06:12", "06:24", "06:36", "06:48", "07:00", "07:12", "07:24", "07:36",
            "07:48", "08:00", "08:12", "08:24", "08:36", "08:48", "09:00", "09:12",
            "09:27", "09:42", "09:57", "10:12", "10:27", "10:42", "10:57", "11:12",
            "11:27",
        ],
    },
    "kayas_sincan_hava": {
        "label": "Kayaş → Sincan (Hava Durağı)",
        "durak_notu": "Hava Durağı kalkışları",
        "saatler": [
            "06:37", "06:49", "07:01", "07:13", "07:25", "07:37", "07:49", "08:01",
            "08:13", "08:25", "08:37", "08:49", "09:01", "09:13", "09:25", "09:37",
            "09:52", "10:07", "10:22", "10:37", "10:52", "11:07", "11:22", "11:37",
            "11:52",
        ],
    },
}

PUSH_OFFSET_MINUTES = 15


def now_tr() -> datetime:
    return datetime.now(TR)


def _parse_hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def _today_at(hhmm: str, base: datetime | None = None) -> datetime:
    base = base or now_tr()
    t = _parse_hhmm(hhmm)
    return base.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def minutes_until(hhmm: str, base: datetime | None = None) -> int | None:
    base = base or now_tr()
    target = _today_at(hhmm, base)
    delta = (target - base).total_seconds() / 60
    if delta < 0:
        return None
    return int(delta)


def next_departures(saatler: list[str], limit: int = 3, base: datetime | None = None) -> list[dict[str, Any]]:
    base = base or now_tr()
    upcoming = []
    for s in saatler:
        mins = minutes_until(s, base)
        if mins is None:
            continue
        upcoming.append({"saat": s, "dakika_kaldi": mins})
        if len(upcoming) >= limit:
            break
    return upcoming


def thk_with_countdown(base: datetime | None = None) -> list[dict[str, Any]]:
    base = base or now_tr()
    rows = []
    for trip in THK_SERVIS:
        mins = minutes_until(trip["kalkis"], base)
        rows.append({
            **trip,
            "dakika_kaldi": mins,
            "kalkti": mins is None,
        })
    return rows


def baskentray_payload(base: datetime | None = None) -> dict[str, Any]:
    base = base or now_tr()
    out = {}
    for key, meta in BASKENTRAY.items():
        out[key] = {
            "label": meta["label"],
            "durak_notu": meta["durak_notu"],
            "saatler": meta["saatler"],
            "sonraki": next_departures(meta["saatler"], limit=4, base=base),
        }
    return out


def due_thk_push_alerts(base: datetime | None = None, window_minutes: int = 1) -> list[dict[str, Any]]:
    """Kalkışa PUSH_OFFSET_MINUTES kala (yaklaşık window_minutes tolerans) bildirim üret."""
    base = base or now_tr()
    alerts = []
    for trip in THK_SERVIS:
        kalkis_dt = _today_at(trip["kalkis"], base)
        notify_at = kalkis_dt - timedelta(minutes=PUSH_OFFSET_MINUTES)
        diff_sec = (base - notify_at).total_seconds()
        if 0 <= diff_sec < window_minutes * 60:
            alerts.append({
                "key": f"{base.date().isoformat()}:{trip['id']}:{PUSH_OFFSET_MINUTES}",
                "title": "THK Servis — 15 dk kaldı",
                "body": (
                    f"{trip['kalkis']} kalkış · {trip['kalkis_yeri']} → {trip['varis_yeri']} "
                    f"(varış ~{trip['varis']})"
                ),
                "url": "/otobus-saatleri",
            })
    return alerts


def ulasim_overview(base: datetime | None = None) -> dict[str, Any]:
    base = base or now_tr()
    thk = thk_with_countdown(base)
    next_thk = next((t for t in thk if t["dakika_kaldi"] is not None), None)
    baskentray = baskentray_payload(base)
    return {
        "now": base.isoformat(),
        "thk_servis": thk,
        "sonraki_thk": next_thk,
        "baskentray": baskentray,
        "push_offset_minutes": PUSH_OFFSET_MINUTES,
    }
