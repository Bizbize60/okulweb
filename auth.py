from flask import Blueprint, request, jsonify, render_template, redirect, url_for, make_response, session, current_app
from functools import wraps
import jwt
from datetime import datetime, timedelta, timezone
import uuid
import secrets
import re
from werkzeug.security import generate_password_hash, check_password_hash

from config import JWT_EXPIRATION_HOURS, ADMIN_EMAILS
from database.initdb import db
from database.user import User
from database.kulupyonetim import KulupYonetim
from extensions import mail
from utils import send_verification_email

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

def is_admin(f):
    @wraps(f)
    def wrapper(current_user, *args, **kwargs):
        if current_user.email not in ADMIN_EMAILS:
            return jsonify({'message': 'Bu işlem admin yetkisi gerektirir!'}), 403
        
        return f(current_user, *args, **kwargs)
    return wrapper

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
        
        if not user or not check_password_hash(user.password, password):
            return jsonify({'message': 'Geçersiz email veya şifre'}), 401

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

    return render_template('login.html')

@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(redirect(url_for('pages.main_page')))
    response.set_cookie('jwt_token', '', expires=0)
    return response

@auth_bp.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        
        if User.query.filter_by(email=email).first():
            return "Bu email zaten kayıtlı!", 400

        session['temp_user'] = {
            'name': request.form['name'],
            'email': email,
            'password': generate_password_hash(request.form['password'])
        }

        v_code = secrets.token_hex(3).upper()
        session['verification_code'] = v_code

        send_verification_email(mail, email, v_code)

        return redirect(url_for('auth.verify_email'))

    return render_template('register.html')

@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify_email():
    temp_user_data = session.get('temp_user')
    if not temp_user_data:
        return redirect(url_for('auth.register'))
    
    if not re.match(r'^s\d{9,10}@stu\.thk\.edu\.tr$', temp_user_data.get('email', '')):
        return "Geçersiz email formatı! Lütfen THKÜ öğrenci emailinizi kullanın.", 400
    
    if request.method == 'POST':
        user_code = request.form['code']
        if user_code == session.get('verification_code'):
            user_data = session['temp_user']
            new_user = User(
                public_id=str(uuid.uuid4()),
                name=user_data['name'],
                email=user_data['email'],
                password=user_data['password']
            )
            db.session.add(new_user)
            db.session.commit()
            
            session.pop('temp_user', None)
            session.pop('verification_code', None)
            return redirect(url_for('auth.login'))
        else:
            return "Kod yanlış!", 400

    return render_template('verify.html', email=session['temp_user']['email'])