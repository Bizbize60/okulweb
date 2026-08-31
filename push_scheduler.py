"""Arka plan: THK servis 15 dk kala + öğle yemek menüsü push bildirimleri."""
from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from ulasim import due_thk_push_alerts
from yemek_menu import get_today_menu, now_tr
from utils import bildirim_gonder_herkese

TR = ZoneInfo("Europe/Istanbul")
_sent_keys: set[str] = set()
_scheduler: BackgroundScheduler | None = None
_app = None


def _prune_sent_keys(today: str) -> None:
    stale = [k for k in _sent_keys if not k.startswith(today)]
    for k in stale:
        _sent_keys.discard(k)


def check_thk_push() -> None:
    if _app is None:
        return
    with _app.app_context():
        today = now_tr().date().isoformat()
        _prune_sent_keys(today)
        for alert in due_thk_push_alerts(window_minutes=2):
            key = alert["key"]
            if key in _sent_keys:
                continue
            try:
                bildirim_gonder_herkese(
                    alert["title"], alert["body"], alert["url"], tag="thk-servis"
                )
                _sent_keys.add(key)
                print(f"[push_scheduler] THK push gönderildi: {key}")
            except Exception as e:
                print(f"[push_scheduler] THK push hata: {e}")


def check_lunch_menu_push() -> None:
    """Hafta içi 11:00'de bugünün menüsünü hatırlat."""
    if _app is None:
        return
    with _app.app_context():
        now = now_tr()
        if now.weekday() >= 5:
            return
        key = f"{now.date().isoformat()}:lunch-menu"
        if key in _sent_keys:
            return
        menu = get_today_menu()
        if not menu or not menu.get("items"):
            return
        names = ", ".join(i["name"] for i in menu["items"][:4])
        total = menu.get("total_kcal")
        body = names if not total else f"{names} · Toplam {total} kcal"
        try:
            bildirim_gonder_herkese(
                "Bugünün yemekhanesi", body, "/yemekhane", tag="yemek-menu"
            )
            _sent_keys.add(key)
            print(f"[push_scheduler] Öğle menü push gönderildi: {key}")
        except Exception as e:
            print(f"[push_scheduler] Menü push hata: {e}")


def start_push_scheduler(app) -> BackgroundScheduler:
    global _scheduler, _app
    _app = app
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone=TR)
    sched.add_job(check_thk_push, "interval", minutes=1, id="thk-push", replace_existing=True)
    sched.add_job(
        check_lunch_menu_push,
        "cron",
        day_of_week="mon-fri",
        hour=11,
        minute=0,
        id="lunch-menu-push",
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched
    print("[push_scheduler] Başlatıldı (THK 15dk + öğle menü)")
    return sched
