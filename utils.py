import os
import requests
from bs4 import BeautifulSoup
from database.subscription import WebPushSubscription
from pywebpush import webpush, WebPushException
import json
from flask_mail import Message
import urllib3
from database.initdb import db

from config import ALLOWED_EXTENSIONS, ALLOWED_IMAGES, NOTES_UPLOAD_FOLDER, VAPID_PRIVATE_KEY

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGES

def kayip_upload_path(filename):
    folder = os.path.join(NOTES_UPLOAD_FOLDER, 'kayip')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)

def enstantane_upload_path(filename):
    folder = os.path.join(NOTES_UPLOAD_FOLDER, 'enstantane')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)

def send_verification_email(mail_app, user_email, code):
    """Doğrulama kodunu e-posta ile gönderir.

    DEBUG modunda (yerel test) gerçek SMTP'ye çıkılmaz; kod terminale
    yazdırılır ve kayıt akışı kaldığı yerden devam eder. Böylece Gmail
    kimlik bilgisi olmadan da kayıt test edilebilir.
    """
    try:
        from flask import current_app, has_app_context
        cfg = current_app.config if has_app_context() else {}
    except Exception:
        cfg = {}
    mail_user = str(cfg.get('MAIL_USERNAME') or '')
    mail_pw = str(cfg.get('MAIL_PASSWORD') or '')
    placeholder = (not mail_user or not mail_pw
                   or mail_user == 'test@gmail.com' or mail_pw == 'password')
    dev = bool(cfg.get('DEBUG', False) or cfg.get('TESTING', False) or placeholder)
    if dev:
        print(f"[DEV] SMTP atlandi. {user_email} icin dogrulama kodu: {code}")
        print("[DEV] Bu kodu /verify sayfasindaki forma girerek kaydi tamamlayabilirsin.")
        return
    try:
        msg = Message(
            subject="THKÜ Portal - Doğrulama Kodu",
            recipients=[user_email]
        )
        msg.body = f"Merhaba,\n\nDoğrulama kodunuz: {code}\n\nİyi günler dileriz."
        mail_app.send(msg)
    except Exception as ex:
        # Üretimde sessiz geçme: terminale kodu + hatayı yaz, akışı durdurma
        # (kullanıcı /verify ekranında kalır; kod logdan alınıp girilebilir).
        print(f"[MAIL-HATA] {user_email} adresine gonderilemedi: {ex}")
        print(f"[MAIL-HATA] Dogrulama kodu (gecici): {code}")
        raise

def scrape_haberler():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    url = "https://www.thk.edu.tr/haberler"
    try:
        resp = requests.get(url, timeout=10, verify=False)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        items = soup.select('.col-md-6.col-lg-4.haberler-gap')
        
        for item in items:
            # Başlık
            title_tag = item.select_one('h5')
            title = title_tag.get_text(strip=True) if title_tag else "Başlık Yok"
            
            # Link
            link_tag = item.select_one('.haberler-page-date a')
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"
            
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
        return articles
    except Exception as e:
        print(f"[scrape_haberler] HATA: {e}")
        return []

def scrape_duyurular():
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

def bildirim_gonder_herkese(baslik, mesaj, url='/', tag='genel-bildirim'):
    abonelikler = WebPushSubscription.query.all()
    payload = json.dumps({
        "title": baslik,
        "body": mesaj,
        "url": url,
        "icon": "/static/img/kedi.ico",
        "tag": tag
    })
    
    for abonelik in abonelikler:
        try:
            webpush(
                subscription_info=json.loads(abonelik.subscription_info),
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY, 
                vapid_claims={"sub": "mailto:600tuna@gmail.com"}
            )
        except WebPushException as ex:
            
            # Eğer abonelik geçersizse (örneğin kullanıcı tarayıcı bildirimlerini kapatmış veya aboneliği silmiş olabilir), veritabanından silelim
            if ex.response and ex.response.status_code == 410:
                db.session.delete(abonelik)
                db.session.commit()
                continue
            
            print(f"Gönderim hatası (ID: {abonelik.id}): {ex}")
            
            
def bildirim_gonder(subscription_info, baslik, mesaj, url='/'):
    payload = json.dumps({
        "title": baslik,
        "body": mesaj,
        "url": url
    })
    
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY, 
            vapid_claims={"sub": "mailto:600tuna@gmail.com"}
        )
    except WebPushException as ex:
        print(f"Gönderim hatası: {ex}")
        
def bildirim_gonder_kullaniciya(user_id, baslik, mesaj, url='/'):
    """Sadece belirli bir kullanıcıya Push Notification gönderir."""
    abonelikler = WebPushSubscription.query.filter_by(user_id=user_id).all()
    if not abonelikler:
        return
        
    payload = json.dumps({
        "title": baslik,
        "body": mesaj,
        "url": url,
        "icon": "/static/img/kedi.ico"
    })
    
    for abonelik in abonelikler:
        try:
            webpush(
                subscription_info=json.loads(abonelik.subscription_info),
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY, 
                vapid_claims={"sub": "mailto:600tuna@gmail.com"}
            )
        except WebPushException as ex:
            if ex.response and ex.response.status_code == 410:
                db.session.delete(abonelik)
                db.session.commit()