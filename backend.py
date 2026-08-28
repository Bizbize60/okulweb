# backend.py
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import jwt
from flask import Flask, send_from_directory, jsonify, request
from config import (
    DATABASE_URI, SECRET_KEY, MAX_CONTENT_LENGTH,
    NOTES_UPLOAD_FOLDER, PAZAR_UPLOAD_FOLDER, KULUP_UPLOAD_FOLDER,
    DEBUG, HOST, PORT, MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)

from database.initdb import db
from database.user import User
from database.daily_active import DailyActiveUser
from extensions import mail

# Blueprint'ler
from routes import pages
from auth import auth_bp, token_required
from api import api_bp

app = Flask(__name__)

# Config atamaları
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = NOTES_UPLOAD_FOLDER
app.config['PAZAR_UPLOAD_FOLDER'] = PAZAR_UPLOAD_FOLDER
app.config['KULUP_UPLOAD_FOLDER'] = KULUP_UPLOAD_FOLDER

app.config['MAIL_SERVER'] = MAIL_SERVER
app.config['MAIL_PORT'] = MAIL_PORT
app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_DEFAULT_SENDER

# Klasörleri oluştur
os.makedirs(NOTES_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PAZAR_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(KULUP_UPLOAD_FOLDER, exist_ok=True)

# Eklentileri başlat
db.init_app(app)
mail.init_app(app)

# Modülleri (Blueprint) sisteme kaydet
app.register_blueprint(pages)
app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)

_SKIP_PREFIXES = (
    '/static', '/uploads', '/sw.js', '/favicon.ico',
)


def _track_daily_active():
    """JWT cookie varsa Europe/Istanbul günü için unique aktif kullanıcı kaydı."""
    path = request.path or ''
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return
    if request.method == 'OPTIONS':
        return

    token = request.cookies.get('jwt_token')
    if not token:
        return

    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        public_id = data.get('public_id')
        if not public_id:
            return
        user = User.query.filter_by(public_id=public_id).first()
        if not user:
            return

        today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
        exists = DailyActiveUser.query.filter_by(
            user_id=user.id,
            activity_date=today,
        ).first()
        if exists:
            return

        db.session.add(DailyActiveUser(user_id=user.id, activity_date=today))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception:
        db.session.rollback()


@app.before_request
def before_request_track_active():
    _track_daily_active()


# --- DOSYA ERİŞİM ROTALARI ---
@app.route('/uploads/notes/<path:filename>', methods=['GET', 'POST'])
@token_required(next_location='/ders-notlari')
def download_note(current_user, filename):
    if current_user.kredi < 1:
        return jsonify({'message': 'Yetersiz kredi! Dosya indirmek için dosya yüklemelisiniz.'}), 403

    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])

    if not os.path.exists(os.path.join(uploads, filename)):
         return jsonify({'message': 'Dosya bulunamadı'}), 404
     
    try:
        current_user.kredi -= 1
        db.session.commit()
        return send_from_directory(uploads, filename)
    except Exception as e:
        current_user.kredi += 1
        db.session.commit()
        return jsonify({'message': 'İndirme sırasında hata oluştu'}), 500

@app.route('/uploads/pazar/<path:filename>')
def pazar_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.root_path, app.config['PAZAR_UPLOAD_FOLDER']), filename)

@app.route('/uploads/kulup/<path:filename>')
def kulup_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.root_path, app.config['KULUP_UPLOAD_FOLDER']), filename)

@app.route('/uploads/kayip/<path:filename>')
def kayip_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'kayip'), filename)

@app.route('/uploads/enstantane/<path:filename>')
def enstantane_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'enstantane'), filename)

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'kedi.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/uploads/katkida/<path:filename>')
def katkida_gorsel_indir(filename):
    return send_from_directory(os.path.join(app.root_path, 'uploads', 'katkida'), filename)


# ============================================================================
# 🌟 OGRENCI ELÇISI SISTEMI - KISA DAVET LINKI
# ============================================================================
@app.route('/r/<string:kod>')
def davet_kisa_link(kod):
    """Kısa davet linki: /r/TUNAHAN5 -> /signup?ref=TUNAHAN5"""
    from flask import redirect, url_for
    temiz = kod.strip().upper()
    # Referans kodu geçerli mi kontrol et (zorunlu değil, sadece spam için)
    return redirect(url_for('auth.register', ref=temiz))


# ============================================================================
# 🔥 APP STARTUP: Eski kullanıcılara referral_code ataması + seed rozet/ödül
#    (TABLO VARLIĞI KONTROL EDİLİR - createtables henüz çalışmamışsa seed atlar)
# ============================================================================
with app.app_context():
    try:
        from database.user import User, Badge, ReferralReward
        from database.initdb import db as _db
        import uuid as _uuid

        # Her tabloya dokunmadan ONCE mevcut mu diye kontrol et (createtables olmadiysa seed gec)
        def _tablo_var(tablo_adi: str) -> bool:
            try:
                r = _db.session.execute(_db.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name=:t)"
                ), {"t": tablo_adi}).scalar()
                return bool(r)
            except Exception:
                return False

        users_var   = _tablo_var("users")
        oduller_var = _tablo_var("referral_rewards")
        rozetler_var= _tablo_var("badges")

        # 1) Eski kullanicilara referral_code (users tablosu varsa)
        if users_var:
            try:
                eksik = User.query.filter(User.referral_code == None).all()  # noqa: E711
                if eksik:
                    for u in eksik:
                        if not u.referral_code:
                            try:
                                u.referral_code = User.generate_referral_code(u.name or u.email.split('@')[0])
                            except Exception:
                                u.referral_code = _uuid.uuid4().hex[:10].upper()
                    try:
                        _db.session.commit()
                        if eksik:
                            print(f"[Elçi Sistemi] {len(eksik)} eski kullanıcıya referral_code atandı.")
                    except Exception:
                        _db.session.rollback()
            except Exception as et:
                print(f"[Elçi Sistemi] Referral kodu atlama atlandı: {type(et).__name__}")

        # 2) Varsayilan odul kataloğunu seed (referral_rewards tablosu varsa)
        if oduller_var:
            try:
                varsayilan_oduller = [
                    ('PAZAR_1HAFTA', '🛒 Bit Pazarında 1 Hafta Öne Çıkartma', 'İlanın 7 gün boyunca arama sonuçlarında ilk sırada görünür.', 300),
                    ('PROFIL_RENKLI', '🎨 Özel Renkli Profil', 'Profil kartın özel bir renkte görünür (1 ay).', 500),
                    ('OOGRENCI_DUYURU', '📣 Topluluk Duyurusunda 1 Kez Paylaşım', 'Sitenin duyuru akışında 1 kez kendi paylaşımın çıkar (onaylı).', 800),
                    ('ANASAYFA_SPOT', '🏆 Ana Sayfada 1 Günlük Ünlü Spot', 'Adın ve seviyen 24 saat boyunca ana sayfada görünür.', 1500),
                    ('ELMAS_AYRIcalik', '💎 Elmas Ayrıcalığı (3 Ay)', 'Özel rozet, destek önceliği, ekstra aktivite puanı.', 3000),
                ]
                degisiklik = False
                for kod, ad, aciklama, maliyet in varsayilan_oduller:
                    if not ReferralReward.query.filter_by(kod=kod).first():
                        _db.session.add(ReferralReward(kod=kod, ad=ad, aciklama=aciklama, maliyet_puan=maliyet, aktif_mi=True))
                        degisiklik = True
                if degisiklik:
                    _db.session.commit()
                    print("[Elçi Sistemi] Varsayılan ödül kataloğu seed edildi.")
            except Exception as et:
                _db.session.rollback()
                print(f"[Elçi Sistemi] Ödül kataloğu seed atlandı: {type(et).__name__}")

        # 3) Rozet kataloğunu seed (badges tablosu varsa)
        if rozetler_var:
            try:
                varsayilan_rozetler = [
                    ('ILK_KAYIT', '🎉 Üye', 'THKÜ Üniversite Portalına hoş geldin!', '#3B82F6', '🎉', 1),
                    ('DAVET_ILE_GELDIN', '🎁 Davetli Üye', 'Arkadaşının davetiyle katıldın!', '#10B981', '🎁', 2),
                    ('DAVET_YAPAN_1', '🤝 İlk Davet', 'İlk arkadaşını davet ettin!', '#6366F1', '🤝', 3),
                    ('NOT_1', '📚 İlk Not', 'İlk ders notunu yükledin!', '#2563EB', '📚', 4),
                    ('DEGER_1', '⭐ İlk Değerlendirme', 'İlk öğretmen değerlendirmesini yaptın!', '#F97316', '⭐', 5),
                    ('FORUM_1', '💬 Sohbetçi', 'İlk forum mesajını attın!', '#059669', '💬', 6),
                    ('STREAK_7', '🔥 7\'li Streak', '7 gün üst üste siteye girdin!', '#EF4444', '🔥', 7),
                    ('RESMI_ELCI', '⭐ Resmi Elçi', 'Yönetim tarafından onaylanmış resmi öğrenci elçisi!', '#F59E0B', '⭐', 8),
                    ('OZEL_BASARI', '🏆 Özel Başarı', 'Yönetim tarafından verilen özel başarı rozeti!', '#A855F7', '🏆', 9),
                ]
                degisiklik = False
                for kod, ad, aciklama, renk, ikon, sira in varsayilan_rozetler:
                    if not Badge.query.filter_by(kod=kod).first():
                        _db.session.add(Badge(kod=kod, ad=ad, aciklama=aciklama, ikon_emoji=ikon, renk=renk, siralama=sira))
                        degisiklik = True
                if degisiklik:
                    _db.session.commit()
                    print("[Elçi Sistemi] Varsayılan rozet kataloğu seed edildi.")
            except Exception as et:
                _db.session.rollback()
                print(f"[Elçi Sistemi] Rozet kataloğu seed atlandı: {type(et).__name__}")

        print("[Elçi Sistemi] Başlangıç denetimi tamamlandı (tablolar hazır).")
    except Exception as e:
        print(f"[Elçi Sistemi] Başlangıç seed hatası (yok say): {type(e).__name__}: {str(e)[:200]}")


if __name__ == '__main__':
    # Debug reloader çift process başlatmasın diye sadece ana süreçte scheduler
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not DEBUG:
        try:
            from push_scheduler import start_push_scheduler
            start_push_scheduler(app)
        except Exception as e:
            print(f"[backend] Push scheduler başlatılamadı: {e}")
    app.run(host=HOST, port=PORT, debug=DEBUG)
