"""Not indirme kapısı ve ilk iki katkı süresince kalite kontrolü.

İki farklı katkı türü tamamlanınca kalite kontrolü bir daha çalışmaz.
"""
from __future__ import annotations

from flask import jsonify

from database.initdb import db
from database.email_blacklist import EmailBlacklist
from database.forum_message import ForumMessage
from database.forum_comment import ForumComment
from database.kampusten import Enstantane
from database.kayip_esya import KayipEsya
from database.pazar import PazarIlani
from database.degerlendirme import OgretmenDegerlendirme
from database.saatler import OfisSaatKatkisi
from metin_kalite import classify_name, classify_office_hours, classify_prose
from user_purge import purge_user_account

REQUIRED_TYPES = 2
MIN_PHOTO_BYTES = 8 * 1024
STAFF_ROLES = {"owner", "developer", "moderator"}

GATE_MESSAGE = (
    "Sitenin sömürülüp bırakılması topluluğa zarar veriyor. "
    "O yüzden aktiflik gösterin, yoksa bir anlamı kalmayacak."
)
BAN_MESSAGE = (
    "Madem siteyi yararlı buluyorsunuz, o zaman sömürmek yerine bilinçli kullanıcı olun. "
    "Hesabınız silinmiştir."
)

ACTIVITIES = (
    {"id": "degerlendirme", "label": "Öğretmen değerlendirmesi", "href": "/ogretmen-degerlendirme"},
    {"id": "forum", "label": "Forumda mesaj", "href": "/forum"},
    {"id": "enstantane", "label": "Kampüste Hayat fotoğrafı", "href": "/KampusteHayat"},
    {"id": "kayip", "label": "Kayıp eşya ilanı", "href": "/kayiplar"},
    {"id": "pazar", "label": "Bit pazarı ilanı", "href": "/ilan-ekle"},
    {"id": "ofis", "label": "Öğretmen ofis saati", "href": "/ofis-saatleri"},
)

_THIN = {
    "forum": "Bu yazı topluluk katkısı sayılmadı. Ne sorduğunu veya anlattığını birkaç cümleyle yaz.",
    "listing": "İlanın başlığını ve açıklamasını anlaşılır yaz. Rastgele metin katkı sayılmaz.",
    "name": "Ad ve soyadı gerçek bir isim gibi yaz.",
    "hours": "Saati 10:00-12:00 biçiminde, hafta içi bir güne yaz.",
    "photo": "Fotoğraf çok küçük. Kampüsten gerçek bir fotoğraf yükle.",
    "gif": "Forum katkısı sayılması için bir mesaj yazmalısın.",
}


def is_staff(user) -> bool:
    if not user:
        return False
    roles = {role.name for role in (user.roles or [])}
    return bool(roles & STAFF_ROLES)


def qualifying_types(user_id: int) -> set[str]:
    found = set()
    if OgretmenDegerlendirme.query.filter_by(user_id=user_id).first():
        found.add("degerlendirme")
    has_post = ForumMessage.query.filter_by(user_id=user_id, silindi=False).first()
    has_comment = ForumComment.query.filter_by(user_id=user_id, silindi=False).first()
    if has_post or has_comment:
        found.add("forum")
    if Enstantane.query.filter_by(user_id=user_id).first():
        found.add("enstantane")
    if KayipEsya.query.filter_by(user_id=user_id).first():
        found.add("kayip")
    if PazarIlani.query.filter_by(user_id=user_id).first():
        found.add("pazar")
    if OfisSaatKatkisi.query.filter_by(user_id=user_id).first():
        found.add("ofis")
    return found


def needs_quality_gate(user) -> bool:
    if is_staff(user):
        return False
    return len(qualifying_types(user.id)) < REQUIRED_TYPES


def email_is_blacklisted(email: str) -> bool:
    cleaned = (email or "").strip().lower()
    if not cleaned:
        return False
    return EmailBlacklist.query.filter_by(email=cleaned).first() is not None


def ban_response(user, reason: str):
    email = (user.email or "").strip().lower()
    if email and not EmailBlacklist.query.filter_by(email=email).first():
        db.session.add(EmailBlacklist(email=email, reason=(reason or "")[:250]))
    purge_user_account(user)
    db.session.commit()
    response = jsonify({"code": "account_removed", "message": BAN_MESSAGE})
    response.status_code = 403
    response.set_cookie("jwt_token", "", expires=0)
    return response


def thin_response(kind: str):
    return jsonify({
        "code": "contribution_rejected",
        "message": _THIN[kind],
    }), 400


def download_block_response(user):
    if is_staff(user):
        return None
    done = qualifying_types(user.id)
    if len(done) >= REQUIRED_TYPES:
        return None
    return jsonify({
        "code": "activity_required",
        "message": GATE_MESSAGE,
        "required": REQUIRED_TYPES,
        "completed": sorted(done),
        "activities": list(ACTIVITIES),
    }), 403


def gate_forum_post(user, konu: str, mesaj: str, gif_url: str | None):
    if not needs_quality_gate(user):
        return None
    if not str(mesaj or "").strip() and gif_url:
        return thin_response("gif")
    for piece in (konu, mesaj):
        if piece and classify_prose(piece) == "abuse":
            return ban_response(user, "forum")
    if classify_prose(mesaj) != "ok":
        return thin_response("forum")
    return None


def gate_forum_comment(user, text: str):
    if not needs_quality_gate(user):
        return None
    verdict = classify_prose(text)
    if verdict == "abuse":
        return ban_response(user, "forum")
    if verdict != "ok":
        return thin_response("forum")
    return None


def gate_listing(user, baslik: str, aciklama: str):
    if not needs_quality_gate(user):
        return None
    for piece in (baslik, aciklama):
        if piece and classify_prose(piece, min_words=1, min_letters=4) == "abuse":
            return ban_response(user, "listing")
    combined = f"{baslik or ''} {aciklama or ''}".strip()
    if classify_prose(combined, min_words=2, min_letters=8) != "ok":
        return thin_response("listing")
    return None


def gate_name(user, ad: str, soyad: str):
    if not needs_quality_gate(user):
        return None
    verdict = classify_name(ad, soyad)
    if verdict == "abuse":
        return ban_response(user, "degerlendirme")
    if verdict != "ok":
        return thin_response("name")
    return None


def gate_hours(user, days):
    if not needs_quality_gate(user):
        return None
    verdict = classify_office_hours(days)
    if verdict == "abuse":
        return ban_response(user, "ofis")
    if verdict != "ok":
        return thin_response("hours")
    return None


def gate_photo(user, size_bytes: int, caption: str):
    if not needs_quality_gate(user):
        return None
    if caption and classify_prose(caption, min_words=1, min_letters=4) == "abuse":
        return ban_response(user, "enstantane")
    if size_bytes < MIN_PHOTO_BYTES:
        return thin_response("photo")
    return None


def record_office_contribution(user_id: int) -> None:
    db.session.add(OfisSaatKatkisi(user_id=user_id))
