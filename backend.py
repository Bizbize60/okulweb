import requests
import secrets
from bs4 import BeautifulSoup
import uuid
import datetime as dt
from functools import wraps
from datetime import datetime, timedelta, timezone
from pywebpush import webpush, WebPushException
from flask import (
    Flask, current_app, flash, make_response, redirect,
    render_template,session  ,jsonify, request, send_from_directory, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import openpyxl
import jwt
import json

# Config
from config import (
    DATABASE_URI, SECRET_KEY, JWT_EXPIRATION_HOURS,
    ALLOWED_EXTENSIONS, ALLOWED_IMAGES, MAX_CONTENT_LENGTH,
    NOTES_UPLOAD_FOLDER, PAZAR_UPLOAD_FOLDER, KULUP_UPLOAD_FOLDER,
    DEBUG, HOST, PORT, VAPID_PRIVATE_KEY, MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)

# Database modelleri
from database.initdb import db
from database.user import User
from database.forum_message import ForumMessage
from database.forum_like import ForumLike
from database.kulupyonetim import KulupYonetim
from database.kulupicerik import Kulupicerik
from database import saatler, dersnotu, degerlendirme, pazar
from database.kampusten import Enstantane, EnstantaneLike
from database.subscription import WebPushSubscription
# from durak import durak_sorgula

from database.kayip_esya import KayipEsya
from werkzeug.utils import secure_filename
import os

# =============================================================================
# Flask Uygulama Yapılandırması
# =============================================================================
app = Flask(__name__)

# Veritabanı ayarları
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Upload klasörleri
app.config['UPLOAD_FOLDER'] = NOTES_UPLOAD_FOLDER
app.config['PAZAR_UPLOAD_FOLDER'] = PAZAR_UPLOAD_FOLDER
app.config['KULUP_UPLOAD_FOLDER'] = KULUP_UPLOAD_FOLDER

# Smtp
app.config['MAIL_SERVER'] =  MAIL_SERVER
app.config['MAIL_PORT'] = MAIL_PORT
app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] =  MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_DEFAULT_SENDER

# Upload klasörlerini oluştur
os.makedirs(NOTES_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PAZAR_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(KULUP_UPLOAD_FOLDER, exist_ok=True)

# Veritabanını başlat
db.init_app(app)
# mail = Mail(app)

# =============================================================================
# Scraping Fonksiyonları
# =============================================================================
def scrape_duyurular():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www.thk.edu.tr/duyurular"
    try:
        resp = requests.get(url, timeout=10, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        duyurular = []
        items = soup.select('.col-md-6.col-lg-4.duyuru-gap')
        for item in items:
            # Başlık
            title_tag = item.select_one('h5')
            title = title_tag.get_text(strip=True) if title_tag else "Başlık Yok"
            # Orijinal detay linki: kutunun tamamı veya başlık <a> ile sarılıysa onu al
            link_tag = item.select_one('a')
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"
            # Eğer link /duyurular/ ile başlıyorsa tam URL yap
            if link.startswith('/duyurular/'):
                link = f"https://www.thk.edu.tr{link}"
            # Açıklama
            desc_tag = item.select_one('.haberler-content')
            description = desc_tag.get_text(strip=True) if desc_tag else ""
            # Tarih
            date_tag = item.select_one('.haberler-page-date .date')
            date = date_tag.get_text(strip=True) if date_tag else ""
            duyurular.append({
                "title": title,
                "description": description,
                "link": link,
                "date": date
            })
        return duyurular
    except Exception as e:
        print(f"[scrape_duyurular] HATA: {e}")
        return []

def bildirim_gonder_herkese(baslik, mesaj, url='/'):
    abonelikler = WebPushSubscription.query.all()
    payload = json.dumps({
        "title": baslik,
        "body": mesaj,
        "url": url
    })
    
    for abonelik in abonelikler:
        try:
            webpush(
                subscription_info=json.loads(abonelik.subscription_info),
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY, 
                vapid_claims={"sub": "mailto:600tuna@gmail.com"}
            )
            print(f"Bildirim gönderildi: {abonelik.id}")
        except WebPushException as ex:
            print(f"Gönderim hatası (ID: {abonelik.id}): {ex}")
            # Eğer abonelik süresi dolmuşsa (410 Gone), silebilirsin:
            # if ex.response and ex.response.status_code == 410:
            #     db.session.delete(abonelik)
            #     db.session.commit()

def scrape_haberler():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www.thk.edu.tr/haberler"
    try:
        resp = requests.get(url, timeout=10, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        items = soup.select('.col-md-6.col-lg-4.haberler-gap')
        print(f"[scrape_haberler] Bulunan haber kutusu: {len(items)}")
        for item in items:
            # Başlık
            title_tag = item.select_one('h5')
            title = title_tag.get_text(strip=True) if title_tag else "Başlık Yok"
            # Link
            link_tag = item.select_one('.haberler-page-date a')
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"
            # İçerik (detay sayfasından çekmek gerekirse, burada boş bırakıyoruz)
            content = ""
            # Thumbnail
            img_tag = item.select_one('.haberler-img img')
            thumbnail = img_tag['src'] if img_tag and img_tag.has_attr('src') else None
            # Tarih
            date_tag = item.select_one('.haberler-page-date .date')
            date = date_tag.get_text(strip=True) if date_tag else ""
            articles.append({
                "title": title,
                "link": link,
                "content": content,
                "thumbnail": thumbnail,
                "source": date
            })
        print(f"[scrape_haberler] Dönen article sayısı: {len(articles)}")
        return articles
    except Exception as e:
        print(f"[scrape_haberler] HATA: {e}")
        return []

# =============================================================================
# Yardımcı Fonksiyonlar
# =============================================================================
def allowed_file(filename):
    """Dosya uzantısının izin verilenler listesinde olup olmadığını kontrol eder."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    """Görsel uzantısının izin verilenler listesinde olup olmadığını kontrol eder."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGES

def kayip_upload_path(filename):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'kayip')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)
def enstantane_upload_path(filename):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'enstantane')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)

# =============================================================================
# Decorator'lar
# =============================================================================
def is_admin(f):
    """Kullanıcının kulüp yöneticisi olup olmadığını kontrol eden decorator."""
    @wraps(f)
    def wrapper(current_user, *args, **kwargs):
        is_admin = KulupYonetim.query.filter_by(kullanici_id=current_user.id).first()
        if not is_admin:
            return jsonify({'message': 'This action requires admin privileges!'}), 403
        return f(current_user, *args, **kwargs)
    return wrapper

def token_required(next_location="/"):
    """JWT token doğrulaması yapan decorator."""
    
    def decorator(f):
        
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.cookies.get('jwt_token')

            if not token:

                # Eğer istek API endpoint'ine yapılmışsa, JSON formatında yetkisiz mesajı döndürelim
                if request.path.startswith('/api/'):
                    return jsonify({'message': 'Unauthorized'}), 401

                # Kullanıcıya bir hata mesajı göstermektense token yoksa direkt giriş sayfasına yönlendirelim
                # Ve ayrıca geldiği sayfaya geri dönebilmesi için next parametresi ekleyelim
                return redirect(url_for('login', next=next_location))

            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = User.query.filter_by(public_id=data['public_id']).first()
                
                if not current_user:
                    raise Exception("Kullanıcı bulunamadı!")
            except Exception:

                # Eğer istek API endpoint'ine yapılmışsa, JSON formatında yetkisiz mesajı döndürelim
                if request.path.startswith('/api/'):
                    return jsonify({'message': 'Unauthorized'}), 401

                return redirect(url_for('login', next=next_location)) # Token geçersizse de giriş sayfasına yönlendirelim böylece kullanıcı tekrar giriş yaparak yeni bir token alabilir

            return f(current_user, *args, **kwargs)
        
        return decorated

    return decorator

# =============================================================================
# Ana Sayfa Route'u
# =============================================================================
@app.route('/')
def main_page():
    """Ana sayfa."""
    return render_template('anasayfa.html')

# ============================================================================
# En önemli Route'lar (Forum, Ders Notları)
# ============================================================================
@app.route('/ders-notlari')
@token_required(next_location='/ders-notlari')
def ders_notlari_sayfa(current_user):
    """Ders notları sayfası."""
    return render_template('ders-notlari.html')

@app.route('/uploads/notes/<path:filename>', methods=['GET', 'POST'])
@token_required(next_location='/ders-notlari')
def download(current_user, filename):
    if current_user.kredi < 1:
        return jsonify({'message': 'Yetersiz kredi! Dosya indirmek için dosya yüklemelisiniz.'}), 403
    uploads = os.path.join(current_app.root_path, app.config['UPLOAD_FOLDER'])

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

@app.route('/not-ekle')
@token_required(next_location='/not-ekle')
def not_ekle_sayfa(current_user):
    return render_template('not-ekle.html')

# =============================================================================
# Diğer Sayfalar (Haberler, Duyurular, Ofis Saatleri, Kayıplar, Kroki, Enstantaneler)
# =============================================================================
@app.route('/haberler')
def haberler_page():
    return render_template('haberler.html')

@app.route('/duyurular')
def duyurular_page():
    return render_template('duyurular.html')

@app.route('/ofis-saatleri')
def ofis_saatleri_page():
    """Ofis saatleri sayfası."""
    return render_template('ofis-saatleri.html')

@app.route('/kayiplar')
@token_required(next_location='/kayiplar')
def kayiplar_sayfa(current_user):
    return render_template('kayip.html')

@app.route('/kroki')
def kroki_page():
    """Kampüs kroki sayfası."""
    return render_template('kroki.html')

@app.route('/KampusteHayat')
def enstantaneler_sayfa():
    return render_template('enstantaneler.html')

@app.route('/ogretmen-degerlendirme')
@token_required(next_location='/ogretmen-degerlendirme')
def ogretmen_degerlendirme_sayfa(current_user):
    return render_template('ogretmen-degerlendirme.html')

@app.route('/ogretmen-listesi')
@token_required(next_location='/ogretmen-listesi')
def ogretmen_listesi_sayfa(current_user):
    return render_template('ogretmen-listesi.html')

@app.route('/uploads/pazar/<path:filename>')
def pazar_gorsel_indir(filename):
    uploads = os.path.join(current_app.root_path, app.config['PAZAR_UPLOAD_FOLDER'])
    return send_from_directory(uploads, filename)

@app.route('/uploads/kulup/<path:filename>')
def kulup_gorsel_indir(filename):
    uploads = os.path.join(current_app.root_path, app.config['KULUP_UPLOAD_FOLDER'])
    return send_from_directory(uploads, filename)

@app.route('/ilan-ekle')
@token_required(next_location='/ilan-ekle')
def ilan_ekle_sayfa(current_user):
    return render_template('ilan-ekle.html')

@app.route('/bit-pazari')
@token_required(next_location='/bit-pazari')
def bit_pazari_sayfa(current_user):
    return render_template('pazar.html')

@app.route('/kulupler/kanatlibulten')
def kanatli_bulten_sayfa():
    return render_template('kanatlibulten.html')
    
@app.route('/kulupler/utaa-music-club')
def utaa_music_club_page():
    return render_template('utaa.html')

@app.route('/kulupler/fsource')
def fsource_page():
    return render_template('fsource.html')

@app.route('/kulupler/makine-muhendisligi')
def makine_muh_page():
    return render_template('makinemuh.html')

@app.route('/kulupler/turk-tarih-toplulugu')
def turk_tarih_page():
    return render_template('turktarih.html')

@app.route('/uploads/kayip/<path:filename>')
def kayip_gorsel_indir(filename):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'kayip')
    return send_from_directory(folder, filename)

@app.route('/uploads/enstantane/<path:filename>')
def enstantane_gorsel_indir(filename):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'enstantane')
    return send_from_directory(folder, filename)

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

# =============================================================================
# Giriş/Çıkış Route'ları
# =============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Kullanıcı giriş sayfası ve işlemi."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            return jsonify({'message': 'Invalid email or password'}), 401

        token = jwt.encode(
            {
                'public_id': user.public_id,
                'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
            },
            app.config['SECRET_KEY'],
            algorithm="HS256"
        )

        print(request.args, request.mimetype_params)
        next_page = request.args.get('next', url_for('main_page'))
        print(f"Giriş başarılı. Yönlendirilecek sayfa: {next_page}")
        response = make_response(redirect(next_page))
        response.set_cookie('jwt_token', token)

        return response

    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    """Kullanıcı çıkış işlemi."""
    response = make_response(redirect(url_for('main_page')))
    response.set_cookie('jwt_token', '', expires=0)
    return response

# ============================================================================
# Admin Route'ları ve API'leri
# ============================================================================
@app.post('/api/kulupler')
@token_required(next_location='/Kulup-Yonetimi')
@is_admin
def kulup_icerik_yonetim(current_user):
    # Kullanıcının yönettiği tek kulübü bul
    yonetim_kaydi = KulupYonetim.query.filter_by(kullanici_id=current_user.id).first()

    if not yonetim_kaydi:
        return jsonify({'message': 'Yönetilecek kulüp bulunamadı!'}), 403

    if 'file' not in request.files:
        return jsonify({'message': 'Dosya seçilmedi!'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'message': 'Dosya seçilmedi!'}), 400
    
    if not allowed_image(file.filename):
        return jsonify({'message': 'Sadece fotoğraf formatları (PNG, JPG, JPEG, GIF) kabul edilmektedir!'}), 400
    
    if file and allowed_image(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['KULUP_UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        yeni_icerik = Kulupicerik(
            dosya_adi=unique_filename,
            dosya_yolu=filepath,
            dosya_tipi=filename.rsplit('.', 1)[1].lower(),
            yuklenme_tarihi=datetime.now(timezone.utc),
            aciklama=request.form['aciklama'],
            kulup_id=yonetim_kaydi.kulup_id,  # Yöneticinin tek kulübünü kullan
            user_id=current_user.id
        )
        db.session.add(yeni_icerik)
        db.session.commit()
        return jsonify({'message': 'Fotoğraf başarıyla yüklendi!'}), 201
        
    return jsonify({'message': 'Dosya yüklenirken hata oluştu!'}), 400

@app.route('/Kulup-Yonetimi')
@token_required(next_location='/Kulup-Yonetimi')
@is_admin
def kulup_yonetimi_sayfa(current_user):
    return render_template('kulup-yonetimi.html')

# =============================================================================
# Kimlik Doğrulama Route'ları
# =============================================================================
@app.route('/verify', methods=['GET', 'POST'])
def verify_email():
    if 'temp_user' not in session:
        return redirect(url_for('register'))

    if request.method == 'POST':
        user_code = request.form['code']
        
        if user_code == session.get('verification_code'):
            
            # Kod doğru! Şimdi veritabanına kaydediyoruz
            user_data = session['temp_user']
            
            new_user = User(
                public_id=str(uuid.uuid4()),
                name=user_data['name'],
                email=user_data['email'],
                password=user_data['password']
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            # Geçici verileri temizle
            session.pop('temp_user', None)
            session.pop('verification_code', None)
            
            return redirect(url_for('login'))
        else:
            return "Kod yanlış!", 400

    return render_template('verify.html',email=session['temp_user']['email'])

@app.route('/signup', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        
        # Önce bu email zaten var mı diye bak
        if User.query.filter_by(email=email).first():
            return "Bu email zaten kayıtlı!", 400

        # Kullanıcı bilgilerini session'a sözlük olarak kaydet
        session['temp_user'] = {
            'name': request.form['name'],
            'email': email,
            'password': generate_password_hash(request.form['password'])
        }

        # Kodu üret ve session'a koy
        v_code = secrets.token_hex(3).upper() # 6 haneli kod
        session['verification_code'] = v_code

        # Maili gönder
        send_verification_email(email, v_code)

        return redirect(url_for('verify_email'))

    return render_template('register.html')

# =============================================================================
# API Endpoint'leri (Route'lar)
# =============================================================================
@app.route('/api/duyurular')
def api_duyurular():
    duyurular = scrape_duyurular()
    return jsonify({"duyurular": duyurular})

@app.route('/api/haberler')
def api_haberler():
    articles = scrape_haberler()
    return jsonify({"articles": articles})
@app.route('/api/forum-mesajlari', methods=['GET', 'POST'])
@token_required(next_location='/forum')
def api_forum_mesajlari(current_user):
    if request.method == 'POST':
        konu = request.json.get('konu')
        mesaj_icerigi = request.json.get('mesaj_icerigi')

        if not konu or not mesaj_icerigi:
            return jsonify({'message': 'Konu ve mesaj içeriği gereklidir!'}), 400

        yeni_mesaj = ForumMessage(
            konu=konu,
            mesaj_icerigi=mesaj_icerigi,
            user_id=current_user.id
        )
        db.session.add(yeni_mesaj)
        db.session.commit()

        return jsonify({'message': 'Mesaj başarıyla eklendi!'}), 201

    else:  # GET isteği
        mesajlar = ForumMessage.query.order_by(ForumMessage.gonderilme_tarihi.desc()).all()
        result = []
        for mesaj in mesajlar:
            # Kullanıcının bu mesaja verdiği beğeni/beğenmeme durumunu kontrol et
            user_like = ForumLike.query.filter_by(
                user_id=current_user.id,
                message_id=mesaj.id
            ).first()
            
            result.append({
                'id': mesaj.id,
                'konu': mesaj.konu,
                'mesaj_icerigi': mesaj.mesaj_icerigi,
                'gonderilme_tarihi': mesaj.gonderilme_tarihi.isoformat(),
                'begeni_sayisi': mesaj.begeni_sayisi,
                'user_action': user_like.like_type if user_like else None
            })
        return jsonify(result)

@app.route('/api/kayip-ekle', methods=['POST'])
@token_required(next_location='/ilan-ekle')
def api_kayip_ekle(current_user):
    try:
        baslik = request.form.get('baslik')
        aciklama = request.form.get('aciklama')
        tip = request.form.get('tip')
        kategori = request.form.get('kategori')
        konum = request.form.get('konum')

        if not baslik or not tip:
            return jsonify({'message': 'Başlık ve Tip zorunludur.'}), 400

        foto_path = None
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_image(file.filename):
                filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex}_{file.filename}")
                save_path = kayip_upload_path(filename)
                file.save(save_path)
                foto_path = f"/uploads/kayip/{filename}"

        yeni_ilan = KayipEsya(
            user_id=current_user.id,
            baslik=baslik,
            aciklama=aciklama,
            tip=tip,
            kategori=kategori,
            konum=konum,
            foto=foto_path
        )

        db.session.add(yeni_ilan)
        db.session.commit()

        # Bildirim Gönderimi
        try:
            if tip == 'kayip':
                bildirim_baslik = "Yeni Kayıp İlanı 📢"
                bildirim_mesaj = f"Kayıp Aranıyor: {baslik}"
            else:
                bildirim_baslik = "Yeni Bulunan Eşya 🔍"
                bildirim_mesaj = f"Bulundu: {baslik}"

            bildirim_detaylari = {
                "title": bildirim_baslik,
                "body": bildirim_mesaj,
                "url": f"/kayip-esya/{yeni_ilan.id}",
                "icon": "/static/kedi.ico"  
            }

            # İlanda fotoğraf varsa büyük resim olarak ekle
            if yeni_ilan.foto:
                bildirim_detaylari["image"] = f"https://thkuogrenci.com{yeni_ilan.foto}"

            payload = json.dumps(bildirim_detaylari)

            # Tüm aboneleri çek ve döngüyle gönder
            abonelikler = WebPushSubscription.query.all()
            print(f">>> BİLDİRİM DÖNGÜSÜ BAŞLADI. ABONE SAYISI: {len(abonelikler)}")

            for abonelik in abonelikler:
                try:
                    webpush(
                        subscription_info=json.loads(abonelik.subscription_info),
                        data=payload,
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": "mailto:600tuna@gmail.com"}
                    )
                    print(f">>> {abonelik.id} ID'li cihaza gönderildi.")
                except Exception as e:
                    print(f">>> TEKİL GÖNDERİM HATASI (ID: {abonelik.id}): {str(e)}")

        except Exception as push_err:
            print(f">>> GENEL BİLDİRİM HATASI: {str(push_err)}")

        return jsonify({'message': 'İlan başarıyla oluşturuldu!'}), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500

@app.route('/api/kayiplar', methods=['GET'])
def api_kayiplar_listele():
    tip = request.args.get('tip')  # 'kayip' veya 'bulunan'
    kategori = request.args.get('kategori') # 'Elektronik', 'Çanta' vs.
    q = request.args.get('q')  # Arama metni

    query = KayipEsya.query

    if tip:
        query = query.filter_by(tip=tip)
    
    if kategori and kategori != 'Tümü':
        query = query.filter_by(kategori=kategori)
        
    if q:
        search = f"%{q}%"
        query = query.filter(or_(KayipEsya.baslik.ilike(search), KayipEsya.aciklama.ilike(search)))

    # En yeni ilan en üstte
    kayiplar = query.order_by(KayipEsya.tarih.desc()).all()
    
    return jsonify([k.to_dict() for k in kayiplar])

@app.route('/api/kayiplar/stats', methods=['GET'])
def api_kayip_stats():
    toplam_kayip = KayipEsya.query.filter_by(tip='kayip').count()
    toplam_bulunan = KayipEsya.query.filter_by(tip='bulunan').count()
    # Bu hafta (basitçe son 7 gün)
    bir_hafta_once = datetime.now() - timedelta(days=7)
    bu_hafta = KayipEsya.query.filter(KayipEsya.tarih >= bir_hafta_once).count()
    
    return jsonify({
        'kayip': toplam_kayip, 
        'bulunan': toplam_bulunan,
        'bu_hafta': bu_hafta
    })

@app.route('/api/enstantaneler', methods=['GET'])
@token_required(next_location='/KampusteHayat')
def api_enstantaneler_getir(current_user):
    sirali = request.args.get('sirala', 'yeni') # varsayılan: yeni
    
    query = Enstantane.query
    
    if sirali == 'populer':
        # En çok beğenilenden aza doğru
        query = query.order_by(Enstantane.begeni_sayisi.desc())
    else:
        # En yeniden eskiye
        query = query.order_by(Enstantane.tarih.desc())
        
    gonderiler = query.all()
    return jsonify([g.to_dict(current_user.id) for g in gonderiler])

@app.route('/api/enstantane-yukle', methods=['POST'])
@token_required(next_location='/KampusteHayat')
def api_enstantane_yukle(current_user):
    if 'file' not in request.files:
        return jsonify({'message': 'Fotoğraf yok!'}), 400
        
    file = request.files['file']
    aciklama = request.form.get('aciklama', '')
    
    if file and allowed_image(file.filename):
        filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}")
        save_path = enstantane_upload_path(filename)
        file.save(save_path)
        
        yeni = Enstantane(
            user_id=current_user.id,
            foto=f"/uploads/enstantane/{filename}",
            aciklama=aciklama
        )
        db.session.add(yeni)
        db.session.commit()
        return jsonify({'message': 'Paylaşıldı!'}), 201
        
    return jsonify({'message': 'Hata oluştu.'}), 500

@app.route('/api/enstantane-begen/<int:id>', methods=['POST'])
@token_required(next_location='/KampusteHayat')
def api_enstantane_begen(current_user, id):
    post = Enstantane.query.get_or_404(id)
    
    existing_like = EnstantaneLike.query.filter_by(user_id=current_user.id, enstantane_id=id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        post.begeni_sayisi -= 1
        action = 'unliked'
    else:
        new_like = EnstantaneLike(user_id=current_user.id, enstantane_id=id)
        db.session.add(new_like)
        post.begeni_sayisi += 1
        action = 'liked'
        
    db.session.commit()
    return jsonify({'action': action, 'count': post.begeni_sayisi})

# =============================================================================
# API Endpoint'leri (Get, Post)
# =============================================================================
@app.get('/api/ofis-saatleri')
def ofis_saatleri():
    """Öğretim görevlilerinin ofis saatlerini döndürür."""
    instructors = saatler.Saatler.query.all()
    return jsonify([
        {
            "ad": instructor.name.split()[0],
            "soyad": instructor.name.split()[1],
            "gun": instructor.days
        } for instructor in instructors
    ])
    
@app.get('/api/ders-notlari')
@token_required(next_location='/api/ders-notlari')
def api_ders_notlari(current_user):
    """Ders notları listesini döndürür."""
    notlar = dersnotu.DersNotu.query.all()
    return jsonify([
        {
            "id": not_item.id,
            "ders_adi": not_item.ders_adi,
            "dosya_adi": not_item.dosya_adi,
            "dosya_tipi": not_item.dosya_tipi,
            "dosya_url": f"/uploads/{not_item.dosya_adi}",
            "tarih": not_item.yuklenme_tarihi.isoformat()
        } for not_item in notlar
    ])
    
@app.get('/api/user-info')
@token_required(next_location='/api/user-info')
def api_user_info(current_user):
    return jsonify({
        'name': current_user.name,
        'kredi': current_user.kredi
    })

@app.get('/api/ogretmen-degerlendirmeleri')
def api_ogretmen_degerlendirmeleri():
    from sqlalchemy import func

    # Normalizasyon: isim/soyisimdeki fazlalık boşluk ve büyük/küçük harf farklılıklarını göz ardı etmek için
    ad_norm = func.lower(func.trim(degerlendirme.OgretmenDegerlendirme.ogretmen_adi)).label('ad')
    soyad_norm = func.lower(func.trim(degerlendirme.OgretmenDegerlendirme.ogretmen_soyadi)).label('soyad')

    results = db.session.query(
        ad_norm,
        soyad_norm,
        func.avg(degerlendirme.OgretmenDegerlendirme.ders_anlatma_notu).label('ders_anlatma_ort'),
        func.avg(degerlendirme.OgretmenDegerlendirme.sinav_zorlugu_notu).label('sinav_zorlugu_ort'),
        func.count(degerlendirme.OgretmenDegerlendirme.id).label('degerlendirme_sayisi')
    ).group_by(
        ad_norm,
        soyad_norm
    ).all()
    
    ogretmenler = []
    for result in results:
        ders_ort = float(result.ders_anlatma_ort)
        sinav_ort = float(result.sinav_zorlugu_ort)

        # Aynı normalizasyon ile orijinal değerlendirmeleri al
        tum_degerlendirmeler = degerlendirme.OgretmenDegerlendirme.query.filter(
            func.lower(func.trim(degerlendirme.OgretmenDegerlendirme.ogretmen_adi)) == result.ad,
            func.lower(func.trim(degerlendirme.OgretmenDegerlendirme.ogretmen_soyadi)) == result.soyad
        ).all()
        
       
        toplam = len(tum_degerlendirmeler)
        etiketler = {
            'slayttan_isler': sum(1 for d in tum_degerlendirmeler if d.slayttan_isler) / toplam * 100 if toplam > 0 else 0,
            'yoklama_alir': sum(1 for d in tum_degerlendirmeler if d.yoklama_alir) / toplam * 100 if toplam > 0 else 0,
            'kitap_onemli': sum(1 for d in tum_degerlendirmeler if d.kitap_onemli) / toplam * 100 if toplam > 0 else 0,
            'kanaat_notu': sum(1 for d in tum_degerlendirmeler if d.kanaat_notu) / toplam * 100 if toplam > 0 else 0,
            'projeye_onem': sum(1 for d in tum_degerlendirmeler if d.projeye_onem) / toplam * 100 if toplam > 0 else 0
        }
        
       
        not_dagilimi = {}
        for d in tum_degerlendirmeler:
            if d.alinan_harf_notu:
                not_dagilimi[d.alinan_harf_notu] = not_dagilimi.get(d.alinan_harf_notu, 0) + 1
        
   
        not_dagilimi_yuzde = {}
        toplam_not = sum(not_dagilimi.values())
        if toplam_not > 0:
            for harf, sayi in not_dagilimi.items():
                not_dagilimi_yuzde[harf] = round(sayi / toplam_not * 100, 1)
        
        # Görüntülenmek üzere ad/soyadı ilk bulunan kaydın biçimiyle kullan (büyük/küçük harf korunur)
        display_ad = tum_degerlendirmeler[0].ogretmen_adi.strip() if tum_degerlendirmeler else result.ad
        display_soyad = tum_degerlendirmeler[0].ogretmen_soyadi.strip() if tum_degerlendirmeler else result.soyad

        ogretmenler.append({
            'ad': display_ad,
            'soyad': display_soyad,
            'ders_anlatma_ort': ders_ort,
            'sinav_zorlugu_ort': sinav_ort,
            'genel_ort': (ders_ort + sinav_ort) / 2,
            'degerlendirme_sayisi': result.degerlendirme_sayisi,
            'etiketler': etiketler,
            'not_dagilimi': not_dagilimi_yuzde
        })
    
    # Genel ortalamaya göre sırala (en yüksek önce)
    ogretmenler.sort(key=lambda x: x['genel_ort'], reverse=True)
    
    return jsonify(ogretmenler)

@app.get('/api/ilanlar')
def api_ilanlari_getir():
    kategori = request.args.get('kategori')
    
    if kategori and kategori != 'Tümü':
        ilanlar = pazar.PazarIlani.query.filter_by(kategori=kategori).order_by(pazar.PazarIlani.tarih.desc()).all()
    else:
        ilanlar = pazar.PazarIlani.query.order_by(pazar.PazarIlani.tarih.desc()).all()
        
    return jsonify([
        {
            "id": ilan.id,
            "baslik": ilan.baslik,
            "aciklama": ilan.aciklama,
            "fiyat": ilan.fiyat,
            "kategori": ilan.kategori,
            "resim_url": f"/uploads/pazar/{ilan.fotograf_adi}",
            "iletisim": ilan.iletisim_no,
            "tarih": ilan.tarih.strftime("%d.%m.%Y")
        } for ilan in ilanlar
    ])

@app.get('/api/kanatlibulten')
def api_kanatlibulten():
    """Kanatlı Bülten yazılarını tarihe göre sıralı olarak döndür.
    Optional: pass ?kulup_adi=<str> to resolve club by name; defaults to 'Kanatlı Bülten'.
    """
    try:
        kulup_adi = request.args.get('kulup_adi')
        kulup_id = 1
        if kulup_adi:
            from database.kulupler import Kulupler
            kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
            kulup_id = kulup.id if kulup else kulup_id

        bultenler = Kulupicerik.query.filter_by(kulup_id=kulup_id).order_by(
            Kulupicerik.yuklenme_tarihi.desc()
        ).all()

        return jsonify([
            {
                'id': item.id,
                'aciklama': item.aciklama,
                'dosya_adi': item.dosya_adi,
                'dosya_tipi': item.dosya_tipi,
                'yuklenme_tarihi': item.yuklenme_tarihi.isoformat(),
                'tarih_tr': item.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M'),
                'dosya_url': f'/uploads/kulup/{item.dosya_adi}'
            } for item in bultenler
        ])
    except Exception:
        return jsonify([]), 200

@app.get('/api/utaa/news')
def api_utaa_news():
    """Return UTAA posts (last + archive style). If no data, return empty list.
    Frontend should pass ?kulup_adi=<str> (e.g., 'UTAA Music Club').
    """
    try:
        kulup_adi = request.args.get('kulup_adi')
        from database.kulupler import Kulupler
        kulup = None
        if kulup_adi:
            kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
        # Fallback to id=2 if name not provided/found
        kulup_id = (kulup.id if kulup else 2)

        items = Kulupicerik.query.filter_by(kulup_id=kulup_id).order_by(
            Kulupicerik.yuklenme_tarihi.desc()
        ).all()
        return jsonify([
            {
                'id': i.id,
                'aciklama': i.aciklama,
                'dosya_adi': i.dosya_adi,
                'dosya_tipi': i.dosya_tipi,
                'yuklenme_tarihi': i.yuklenme_tarihi.isoformat(),
                'tarih_tr': i.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M'),
                'dosya_url': f'/uploads/kulup/{i.dosya_adi}'
            } for i in items
        ])
    except Exception:
        return jsonify([]), 200

@app.get('/api/fsource/news')
def api_fsource_news():
    """Return FSource posts (last + archive style). If no data, return empty list.
    Frontend should pass ?kulup_adi=<str> (defaults to 'FSource').
    """
    try:
        kulup_adi = request.args.get('kulup_adi') or 'FSource'
        from database.kulupler import Kulupler
        kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
        kulup_id = kulup.id if kulup else 3

        items = Kulupicerik.query.filter_by(kulup_id=kulup_id).order_by(
            Kulupicerik.yuklenme_tarihi.desc()
        ).all()
        return jsonify([
            {
                'id': i.id,
                'aciklama': i.aciklama,
                'dosya_adi': i.dosya_adi,
                'dosya_tipi': i.dosya_tipi,
                'yuklenme_tarihi': i.yuklenme_tarihi.isoformat(),
                'tarih_tr': i.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M'),
                'dosya_url': f'/uploads/kulup/{i.dosya_adi}'
            } for i in items
        ])
    except Exception:
        return jsonify([]), 200

@app.get('/api/makinemuh/news')
def api_makinemuh_news():
    """Return Mechanical Engineering Club posts (hero + archive).
    Frontend should pass ?kulup_adi=<str>; defaults to 'Makine Mühendisliği Kulübü'.
    """
    try:
        kulup_adi = request.args.get('kulup_adi') or 'Makine Mühendisliği Kulübü'
        from database.kulupler import Kulupler
        kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
        kulup_id = kulup.id if kulup else 4

        items = Kulupicerik.query.filter_by(kulup_id=kulup_id).order_by(
            Kulupicerik.yuklenme_tarihi.desc()
        ).all()
        return jsonify([
            {
                'id': i.id,
                'aciklama': i.aciklama,
                'dosya_adi': i.dosya_adi,
                'dosya_tipi': i.dosya_tipi,
                'yuklenme_tarihi': i.yuklenme_tarihi.isoformat(),
                'tarih_tr': i.yuklenme_tarihi.strftime('%d.%m.%Y %H:%M'),
                'dosya_url': f"/uploads/kulup/{i.dosya_adi}"
            } for i in items
        ])
    except Exception:
        return jsonify([]), 200

@app.get('/api/utaa/events')
def api_utaa_events():
    """Return UTAA events. Optional: pass ?kulup_adi=<str> to resolve id; or ?kulup_id=<int>.
    If no data or error, return empty list.
    """
    try:
        kulup_id = request.args.get('kulup_id', type=int)
        if not kulup_id:
            kulup_adi = request.args.get('kulup_adi')
            if kulup_adi:
                from database.kulupler import Kulupler
                kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
                kulup_id = kulup.id if kulup else None
        if kulup_id:
            items = Kulupicerik.query.filter_by(kulup_id=kulup_id).order_by(
                Kulupicerik.yuklenme_tarihi.desc()
            ).all()
            return jsonify([
                {
                    'id': i.id,
                    'baslik': i.aciklama,
                    'aciklama': i.aciklama,
                    'tarih': i.yuklenme_tarihi.isoformat(),
                } for i in items
            ])
        return jsonify([])
    except Exception:
        return jsonify([]), 200

@app.get('/api/utaa/gallery')
def api_utaa_gallery():
    """
    UTAA galeri öğelerini döndürür.
    
    Query Params:
        kulup_adi (str): Kulüp adı ile arama
        kulup_id (int): Kulüp ID ile arama
    """
    try:
        kulup_id = request.args.get('kulup_id', type=int)
        if not kulup_id:
            kulup_adi = request.args.get('kulup_adi')
            if kulup_adi:
                from database.kulupler import Kulupler
                kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
                kulup_id = kulup.id if kulup else None
        
        if kulup_id:
            items = Kulupicerik.query.filter_by(kulup_id=kulup_id).order_by(
                Kulupicerik.yuklenme_tarihi.desc()
            ).all()
            return jsonify([
                {
                    'id': i.id,
                    'image_url': f"/uploads/kulup/{i.dosya_adi}",
                    'aciklama': i.aciklama,
                    'tarih': i.yuklenme_tarihi.isoformat(),
                } for i in items
            ])
        return jsonify([])
    except Exception:
        return jsonify([]), 200

@app.get('/api/yemek-saatleri')
def yemek_saatleri():
    data_obj = openpyxl.load_workbook("yemek.xlsx")
    sheet = data_obj.active
    new_buffer = {"Pazartesi": [], "Salı": [], "Çarşamba": [], "Perşembe": [], "Cuma": []}
    a =sheet.iter_cols(values_only=True)
    b = 0
    for idx,i in  enumerate(a):
        if idx%2==1 or idx>8:
            continue
        else:
            for j in range(32):
                if i[j] is None:
                    continue
                elif isinstance(i[j],str):
                    if "Pazartesi" in i[j] or "Salı" in i[j] or "Çarşamba" in i[j] or "Perşembe" in i[j] or "Cuma" in i[j] or "Türk" in i[j] or "Toplam" in i[j]:
                        continue
                    else:
                        if idx==0:
                            new_buffer["Pazartesi"].append(i[j])
                        elif idx==2:
                            new_buffer["Salı"].append(i[j])
                        elif idx==4:
                            new_buffer["Çarşamba"].append(i[j])
                        elif idx==6:
                            new_buffer["Perşembe"].append(i[j])
                        elif idx==8:
                            new_buffer["Cuma"].append(i[j])
                elif isinstance(i[j], dt.datetime):
                    if idx==0:
                        new_buffer["Pazartesi"].append(i[j].strftime("%Y:%m:%d"))
                    elif idx==2:
                        new_buffer["Salı"].append(i[j].strftime("%Y:%m:%d"))
                    elif idx==4:
                        new_buffer["Çarşamba"].append(i[j].strftime("%Y:%m:%d"))
                    elif idx==6:
                        new_buffer["Perşembe"].append(i[j].strftime("%Y:%m:%d"))
                    elif idx==8:
                        new_buffer["Cuma"].append(i[j].strftime("%Y:%m:%d"))
    return jsonify(new_buffer)

@app.get('/api/otobus-saatleri')
def api_otobus_saatleri():
    duraklar = ["51325", "51165", "51164"]
    sonuc = {}
    for durak in duraklar:
        try:
            otobus_listesi = durak_sorgula(durak)
            sonuc[durak] = otobus_listesi
        except Exception as e:
            import traceback
            traceback.print_exc()
            sonuc[durak] = []
    return jsonify(sonuc)

@app.post('/api/not-ekle')
@token_required(next_location='/ders-notlari')
def api_not_ekle(current_user):
    if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
    file = request.files['file']
    
    if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        yeni_not = dersnotu.DersNotu(
            ders_adi=request.form['ders_adi'],
            dosya_adi=unique_filename,
            dosya_yolu=filepath,
            dosya_tipi=filename.rsplit('.', 1)[1].lower(),
            yuklenme_tarihi=datetime.now(timezone.utc),
            user_id=current_user.id
        )
        current_user.kredi += 1
        db.session.add(yeni_not)
        db.session.commit()
        
        return jsonify({'message': 'Not başarıyla yüklendi!'}), 201
    
    return jsonify({'message': 'Invalid file type'}), 400

@app.post('/api/degerlendirme-ekle')
@token_required(next_location='/')
def api_degerlendirme_ekle(current_user):
    data = request.get_json() if request.is_json else request.form
    
    ad = data.get('ad')
    soyad = data.get('soyad')
    ders_anlatma = data.get('ders_anlatma')
    sinav_zorlugu = data.get('sinav_zorlugu')
    
  
    slayttan_isler = data.get('slayttan_isler') == 'true' or data.get('slayttan_isler') == True
    yoklama_alir = data.get('yoklama_alir') == 'true' or data.get('yoklama_alir') == True
    kitap_onemli = data.get('kitap_onemli') == 'true' or data.get('kitap_onemli') == True
    kanaat_notu = data.get('kanaat_notu') == 'true' or data.get('kanaat_notu') == True
    projeye_onem = data.get('projeye_onem') == 'true' or data.get('projeye_onem') == True
    
  
    alinan_harf_notu = data.get('alinan_harf_notu')
    
    if not all([ad, soyad, ders_anlatma, sinav_zorlugu]):
        return jsonify({'message': 'Tüm alanlar gereklidir!'}), 400
    
    try:
        yeni_degerlendirme = degerlendirme.OgretmenDegerlendirme(
            ogretmen_adi=ad,
            ogretmen_soyadi=soyad,
            ders_anlatma_notu=int(ders_anlatma),
            sinav_zorlugu_notu=int(sinav_zorlugu),
            slayttan_isler=slayttan_isler,
            yoklama_alir=yoklama_alir,
            kitap_onemli=kitap_onemli,
            kanaat_notu=kanaat_notu,
            projeye_onem=projeye_onem,
            alinan_harf_notu=alinan_harf_notu,
            user_id=current_user.id
        )
        db.session.add(yeni_degerlendirme)
        db.session.commit()
        return jsonify({'message': 'Değerlendirme başarıyla eklendi!'}), 201
    except Exception as e:
        return jsonify({'message': f'Hata: {str(e)}'}), 500

@app.post('/api/like-dislike-message/<int:message_id>')
@token_required(next_location='/forum')
def like_dislike_message(current_user, message_id):
    mesaj = db.session.get(ForumMessage, message_id)
    if not mesaj:
        return jsonify({'message': 'Mesaj bulunamadı!'}), 404

    action = request.json.get('action')
    if action not in ['like', 'dislike']:
        return jsonify({'message': 'Geçersiz işlem!'}), 400


    existing_like = ForumLike.query.filter_by(
        user_id=current_user.id,
        message_id=message_id
    ).first()

    if existing_like:

        if existing_like.like_type == action:
            if action == 'like':
                mesaj.begeni_sayisi -= 1  
            elif action == 'dislike':
                mesaj.begeni_sayisi += 1 
            db.session.delete(existing_like)
            db.session.commit()
            return jsonify({
                'message': 'İşlem geri alındı!',
                'begeni_sayisi': mesaj.begeni_sayisi,
                'user_action': None
            }), 200
        else:
           
            if existing_like.like_type == 'like' and action == 'dislike':
                mesaj.begeni_sayisi -= 2  
            elif existing_like.like_type == 'dislike' and action == 'like':
                mesaj.begeni_sayisi += 2 
            
            existing_like.like_type = action
            db.session.commit()
            return jsonify({
                'message': 'İşlem güncellendi!',
                'begeni_sayisi': mesaj.begeni_sayisi,
                'user_action': action
            }), 200
    else:
        # Yeni beğeni/beğenmeme ekle
        new_like = ForumLike(
            user_id=current_user.id,
            message_id=message_id,
            like_type=action
        )
        
        if action == 'like':
            mesaj.begeni_sayisi += 1  
        elif action == 'dislike':
            mesaj.begeni_sayisi -= 1  
        
        db.session.add(new_like)
        db.session.commit()
        return jsonify({
            'message': 'İşlem başarıyla gerçekleştirildi!',
            'begeni_sayisi': mesaj.begeni_sayisi,
            'user_action': action
        }), 200

@app.post('/api/ilan-ekle')
@token_required(next_location='/ilan-ekle')
def api_ilan_ekle(current_user):
    try:
        # Form verilerini al
        baslik = request.form.get('baslik')
        aciklama = request.form.get('aciklama')
        fiyat = request.form.get('fiyat')
        kategori = request.form.get('kategori')
        iletisim = request.form.get('iletisim')


        if 'file' not in request.files:
            return jsonify({'message': 'Fotoğraf yüklenmedi!'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'message': 'Dosya seçilmedi!'}), 400
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            
            kayit_yolu = os.path.join(app.config['PAZAR_UPLOAD_FOLDER'], unique_filename)
            print(f"Kayıt Yolu: {kayit_yolu}")
            
            file.save(kayit_yolu)
            
            yeni_ilan = pazar.PazarIlani(
                baslik=baslik,
                aciklama=aciklama,
                fiyat=int(fiyat),
                kategori=kategori,
                iletisim_no=iletisim,
                fotograf_adi=unique_filename,
                user_id=current_user.id
            )
            
            db.session.add(yeni_ilan)
            db.session.commit()
            
            return jsonify({'message': 'İlan başarıyla yayınlandı!'}), 201
            
        return jsonify({'message': 'Geçersiz dosya formatı'}), 400

    except Exception as e:
        import traceback
        traceback.print_exc() 
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500

@app.post('/api/abonelik-kaydet')
@token_required(next_location='/')
def api_abonelik_kaydet(current_user):
    try:
        subscription_data = request.get_json()

        if not subscription_data:
            return jsonify({'message': 'Abonelik verisi bulunamadı!'}), 400

        endpoint = subscription_data.get('endpoint')
        
        # Mevcut abonelik kontrolü
        mevcut_abonelik = WebPushSubscription.query.filter(
            WebPushSubscription.subscription_info.like(f'%{endpoint}%')
        ).first()

        if mevcut_abonelik:
            return jsonify({'message': 'Bu cihaz zaten bildirimlere abone.'}), 200

        # Yeni abonelik kaydı
        yeni_abonelik = WebPushSubscription(
            subscription_info=json.dumps(subscription_data),
            kullanici_ajani=request.headers.get('User-Agent'),
            user_id=current_user.id
        )

        db.session.add(yeni_abonelik)
        db.session.commit()

        # Kayıt sonrası ilk test bildirimi
        try:
            bildirim_gonder_herkese(
                baslik="Sisteme Kayıt Başarılı!",
                mesaj="Artık bildirimleri alabileceksiniz.",
                url="/kayiplar"
            )
        except Exception as push_err:
            print(f"İlk bildirim gönderilirken hata oluştu: {push_err}")

        return jsonify({'message': 'Abonelik başarıyla kaydedildi!'}), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500

# =============================================================================
# Sayfa Yönlendirmeleri (Get)
# =============================================================================

@app.post('/ogretmen-ekle')
def ogretmen_ekle():
    data = request.json
    name = data["ad"]
    surname = data["soyad"]
    days = data["gun"]
    instructor = saatler.SaatlerPending(
        name=f"{name} {surname}",
        days=days
    )
    db.session.add(instructor)
    db.session.commit()
    return jsonify({"message": "Öğretim Görevlisi Başarıyla Eklendi!--Onay Bekliyor."}), 201
@app.get('/yemekhane')
def yemekhane_sayfa():
    return render_template('yemekhane.html')

@app.post('/verify-all')
@token_required(next_location='/')
@is_admin
def verify_all():
    pending_instructors = saatler.SaatlerPending.query.all()
    for pending in pending_instructors:
        approved_instructor = saatler.Saatler(
            name=pending.name,
            days=pending.days
        )
        db.session.add(approved_instructor)
        db.session.delete(pending)
    db.session.commit()
    return jsonify({"message": "Tüm Öğretim Görevlileri Onaylandı!"}), 200

@app.get('/otobus-saatleri')
def otobus_saatleri_sayfa():
    return render_template('otobus-saatleri.html')

@app.get('/forum')
def forum_sayfa():
    return render_template('forum.html')

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)

