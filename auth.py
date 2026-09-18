from flask import Blueprint, request, jsonify, render_template, redirect, url_for, make_response, session, current_app
from functools import wraps
import jwt
from datetime import datetime, timedelta, timezone
import uuid
import secrets
import re
from zoneinfo import ZoneInfo
from werkzeug.security import generate_password_hash, check_password_hash

from config import JWT_EXPIRATION_HOURS, ADMIN_EMAILS
from database.initdb import db
from database.user import User, Referral, Badge, UserBadge
from database.kulupyonetim import KulupYonetim
from database.admin_rbac import ensure_default_roles
from extensions import mail
from utils import send_verification_email
from admin.permissions import ROLE_DEFINITIONS

auth_bp = Blueprint('auth', __name__)

# =============================================================================
# DEKORATÖRLER (Yetki Kontrolleri)
# =============================================================================
def token_required(next_location="/"):
    """JWT token doğrulaması yapan decorator."""
    
    def decorator(f):
        
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.cookies.get('jwt_token')

            if not token:

                # Eğer istek api ise JSON formatında hata döndür, değilse login sayfasına yönlendir
                if request.path.startswith('/api/'):
                    return jsonify({'message': 'Unauthorized'}), 401

                return redirect(url_for('auth.login', next=next_location))

            try:
                data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = User.query.filter_by(public_id=data['public_id']).first()
                
                if not current_user:
                    raise Exception("Kullanıcı bulunamadı!")
            except Exception:

                # Eğer istek api ise JSON formatında hata döndür, değilse login sayfasına yönlendir
                if request.path.startswith('/api/'):
                    return jsonify({'message': 'Unauthorized'}), 401

                return redirect(url_for('auth.login', next=next_location)) # Token geçersizse de giriş sayfasına yönlendirelim böylece kullanıcı tekrar giriş yaparak yeni bir token alabilir

            return f(current_user, *args, **kwargs)
        
        return decorated

    return decorator


def token_required_api(f):
    """API istekleri için JWT doğrulaması yapan decorator."""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('jwt_token')

        if not token:
            return jsonify({'message': 'Unauthorized'}), 401

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(public_id=data['public_id']).first()

            if not current_user:
                raise Exception("Kullanıcı bulunamadı!")
        except Exception:
            return jsonify({'message': 'Unauthorized'}), 401

        return f(current_user, *args, **kwargs)

    return decorated

def user_has_permission(current_user: User, permission_key: str) -> bool:
    if not current_user:
        return False
    if current_user.has_permission(permission_key):
        return True
    if current_user.email in ADMIN_EMAILS and current_user.has_role('owner'):
        return True
    return False


def require_permission(permission_key: str):
    def decorator(f):
        @wraps(f)
        def wrapper(current_user, *args, **kwargs):
            if not user_has_permission(current_user, permission_key):
                return jsonify({'message': f"Bu işlem için '{permission_key}' izni gereklidir."}), 403
            return f(current_user, *args, **kwargs)
        return wrapper
    return decorator


def require_role(role_name: str):
    def decorator(f):
        @wraps(f)
        def wrapper(current_user, *args, **kwargs):
            if not current_user or (not current_user.has_role(role_name) and current_user.email not in ADMIN_EMAILS):
                return jsonify({'message': f"Bu işlem için '{role_name}' rolü gereklidir."}), 403
            return f(current_user, *args, **kwargs)
        return wrapper
    return decorator


def is_admin(f):
    return require_permission('system.admin')(f)


def is_club_admin(f):
    @wraps(f)
    def wrapper(current_user, *args, **kwargs):
        is_admin = KulupYonetim.query.filter_by(kullanici_id=current_user.id).first()
        if not is_admin:
            return jsonify({'message': 'Bu işlem kulüp yöneticisi yetkisi gerektirir!'}), 403
        
        return f(current_user, *args, **kwargs)
    return wrapper

# =============================================================================
# AUTH ROTALARI (Giriş, Kayıt, Çıkış, Doğrulama)
# =============================================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        # ---- Giriş yapınca streak ve son giriş güncelle ----
        if user:
            try:
                _update_streak_on_login(user)
            except Exception:
                pass  # Streak hatası kritik değil, girişe etki etmesin

        token = jwt.encode(
            {
                'public_id': user.public_id,
                'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
            },
            current_app.config['SECRET_KEY'],
            algorithm="HS256"
        )

        next_page = request.args.get('next', url_for('pages.main_page'))
        response = make_response(redirect(next_page))
        response.set_cookie('jwt_token', token)
        return response

    return render_template('auth/login.html')


def _update_streak_on_login(user: User):
    """Her girişte streak_gun ve elçi puanını güncelle (günlük 1 kez)."""
    bugun_tr = datetime.now(ZoneInfo('Europe/Istanbul')).date()
    if not user.son_giris_tarihi:
        user.streak_gun = 1
    elif user.son_giris_tarihi == bugun_tr:
        return  # Aynı gün tekrar giriş yapıldıysa dokunma
    elif (bugun_tr - user.son_giris_tarihi).days == 1:
        user.streak_gun += 1
        # Art arda 7 gün giriş yapana 50 puan + rozet hediye
        if user.streak_gun == 7:
            _give_ambassador_points(user, 50, "7 gün üst üste giriş")
            _give_badge_if_not_exists(user, "STREAK_7", "🔥 7'li Streak", "7 gün üst üste siteye girdin!", "#EF4444")
    else:
        user.streak_gun = 1
    user.son_giris_tarihi = bugun_tr
    db.session.commit()


def _give_ambassador_points(user: User, puan: int, sebep: str = ""):
    """Kullanıcıya elçi puanı ver ve seviye atlama olup olmadığını kontrol et."""
    user.ambassador_points = (user.ambassador_points or 0) + puan
    # Seviye eşikleri (tamamen puan tabanlı, üniversite onaylı olanlara ayrıca 500 puan bonus verirsin)
    seviyeler = [
        (1, 100),    # Bronz
        (2, 500),    # Gümüş
        (3, 2000),   # Altın
        (4, 5000),   # Elmas
    ]
    for sev, esik in seviyeler:
        if user.ambassador_points >= esik and (user.ambassador_level or 0) < sev:
            user.ambassador_level = sev
            user.is_ambassador = True
            _give_badge_if_not_exists(
                user,
                f"AMBS_{sev}",
                f"{seviye_adi_str(sev)} Elçi",
                f"{seviye_adi_str(sev)} seviyesine ulaştın!",
                seviye_renk_str(sev)
            )
    db.session.commit()


def seviye_adi_str(sev: int) -> str:
    return {1: "Bronz", 2: "Gümüş", 3: "Altın", 4: "Elmas"}.get(sev, "Üye")


def seviye_renk_str(sev: int) -> str:
    return {1: "#CD7F32", 2: "#C0C0C0", 3: "#FFD700", 4: "#B9F2FF"}.get(sev, "#9CA3AF")


def _give_badge_if_not_exists(user: User, kod: str, ad: str, aciklama: str = "", renk: str = "#FFD700", ikon: str = "🏅"):
    """Rozet yoksa oluştur, kullanıcıya ekle (varsa geç)."""
    # Badge'i bul veya oluştur
    badge = Badge.query.filter_by(kod=kod).first()
    if not badge:
        badge = Badge(kod=kod, ad=ad, aciklama=aciklama, ikon_emoji=ikon, renk=renk)
        db.session.add(badge)
        db.session.flush()
    # Kullanıcı daha önce almış mı?
    var_mi = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
    if not var_mi:
        db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
        db.session.commit()


@auth_bp.route('/signup', methods=['GET', 'POST'])
def register():
    # ---- Davet kodunu URL'den session'a al ----
    ref_code = request.args.get('ref', '') or request.form.get('ref', '')
    if ref_code:
        ref_code = ref_code.strip().upper()
        davet_eden = User.query.filter_by(referral_code=ref_code).first()
        if davet_eden:
            session['davet_eden_id'] = davet_eden.id
            session['davet_kodu'] = ref_code

    if request.method == 'POST':
        email = request.form['email'].strip().lower() # Küçük harfe çevir ve boşlukları sil

        if User.query.filter_by(email=email).first():
            return "Bu email zaten kayıtlı!", 400
            
        if not re.match(r'^s\d{9,10}@stu\.thk\.edu\.tr$', email):
            return 'E-Mailinin başında "s" harfi eksik ya da okul numaranı yanlış girdin', 400

        # Kullanıcı verilerini session'a kaydet
        session['temp_user'] = {
            'name': request.form['name'],
            'email': email,
            'password': generate_password_hash(request.form['password'])
        }

        # 1. ÖNLEM: Kodun hangi e-posta için üretildiğini session'a kilitle
        v_code = secrets.token_hex(3).upper()
        session['verification_code'] = v_code
        session['verification_target_email'] = email 

        send_verification_email(mail, email, v_code)

        return redirect(url_for('auth.verify_email'))

    return render_template('auth/register.html', ref_code=ref_code)


@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify_email():
    temp_user_data = session.get('temp_user')
    # Eğer session'da geçici kullanıcı yoksa register'a at
    if not temp_user_data:
        return redirect(url_for('auth.register'))

    # Email format kontrolü
    email = temp_user_data.get('email', '')
    if not re.match(r'^s\d{9,10}@stu\.thk\.edu\.tr$', email):
        return "Geçersiz email formatı! Lütfen THKÜ öğrenci emailinizi kullanın.", 400

    if request.method == 'POST':
        user_code = request.form['code'].strip().upper() # Boşlukları temizle ve büyük harf yap
        
        # 2. ÖNLEM: Hem kodu hem de kodun ait olduğu e-postayı eş zamanlı doğrula
        saved_code = session.get('verification_code')
        target_email = session.get('verification_target_email')

        if saved_code and target_email and user_code == saved_code and email == target_email:
            # ---- Kişisel davet kodunu otomatik üret ----
            try:
                ref_kodu = User.generate_referral_code(temp_user_data['name'])
            except Exception:
                ref_kodu = uuid.uuid4().hex[:10].upper()

            new_user = User(
                public_id=str(uuid.uuid4()),
                name=temp_user_data['name'],
                email=temp_user_data['email'],
                password=temp_user_data['password'],
                kredi=3,  # Yeni gelenlere 3 kredi bonusu
                referral_code=ref_kodu,
                streak_gun=1,
                son_giris_tarihi=datetime.now(ZoneInfo('Europe/Istanbul')).date(),
            )
            db.session.add(new_user)
            db.session.flush()  # ID alabilmek için

            # ---- Davet eden varsa işlemleri yap ----
            davet_eden_id = session.get('davet_eden_id')
            davet_kodu = session.get('davet_kodu')
            if davet_eden_id:
                davet_eden = User.query.get(davet_eden_id)
                if davet_eden and davet_eden.id != new_user.id:
                    kayit = Referral(
                        davet_eden_id=davet_eden.id,
                        davet_edilen_id=new_user.id,
                        referral_code=davet_kodu,
                        onaylandi_mi=True,
                        puan_verildi_mi=False
                    )
                    db.session.add(kayit)
                    _give_ambassador_points(davet_eden, 150, f"{new_user.name} kullanıcısını davet ettiği için")
                    davet_eden.kredi = (davet_eden.kredi or 0) + 2
                    new_user.kredi += 2
                    _give_badge_if_not_exists(new_user, "DAVET_ILE_GELDIN", "🎁 Davetli Üye",
                                             "Arkadaşının davetiyle katıldın!", "#10B981", "🎁")
                    _give_badge_if_not_exists(davet_eden, "DAVET_YAPAN_1", "🤝 İlk Davet",
                                             "İlk arkadaşını davet ettin!", "#6366F1", "🤝")

            # İlk kayıt rozeti
            _give_badge_if_not_exists(new_user, "ILK_KAYIT", "🎉 Üye",
                                     "THKÜ Üniversite Portalına hoş geldin!", "#3B82F6", "🎉")

            db.session.commit()

            # Tüm session'ları güvenle temizle
            session.pop('temp_user', None)
            session.pop('verification_code', None)
            session.pop('verification_target_email', None)
            session.pop('davet_eden_id', None)
            session.pop('davet_kodu', None)

            # Otomatik giriş: kayıt sonrası tekrar login isteme
            token = jwt.encode(
                {
                    'public_id': new_user.public_id,
                    'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
                },
                current_app.config['SECRET_KEY'],
                algorithm="HS256"
            )
            response = make_response(redirect(url_for('pages.main_page')))
            response.set_cookie('jwt_token', token)
            return response
        else:
            # 3. ÖNLEM: Kod yanlışsa brute-force'u önlemek için session'ı patlat ve sıfırla
            session.pop('temp_user', None)
            session.pop('verification_code', None)
            session.pop('verification_target_email', None)
            return "Kod yanlış veya oturum geçersiz! Güvenlik nedeniyle kaydınız iptal edildi. Lütfen tekrar üye olun.", 400

    return render_template('auth/verify.html', email=email)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(redirect(url_for('pages.main_page')))
    response.set_cookie('jwt_token', '', expires=0)
    return response
