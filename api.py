from flask import Blueprint, request, jsonify, current_app
import os
import uuid
import json
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
import openpyxl
from pywebpush import webpush
from sqlalchemy import func
from datetime import datetime
import traceback
from werkzeug.security import generate_password_hash

from database.initdb import db
from database.user import User
from database.forum_message import ForumMessage
from database.forum_like import ForumLike
from database.kayip_esya import KayipEsya
from database.kampusten import Enstantane, EnstantaneLike
from database.subscription import WebPushSubscription
from database import saatler, dersnotu, degerlendirme, pazar
from database.kulupicerik import Kulupicerik
from database.kulupyonetim import KulupYonetim
from database.kulupler import Kulupler
from database.dersnotu import DersNotuBekleyen, DersNotu
from database.istek import Istek
from database.katkida import KatkidaBulunan

from config import VAPID_PRIVATE_KEY
from utils import allowed_file, allowed_image, bildirim_gonder_kullaniciya, kayip_upload_path, enstantane_upload_path, scrape_duyurular, scrape_haberler, bildirim_gonder
from auth import token_required, token_required_api, is_club_admin, is_admin
from durak import durak_sorgula

KATKIDA_UPLOAD_FOLDER = os.path.join('uploads', 'katkida')
os.makedirs(KATKIDA_UPLOAD_FOLDER, exist_ok=True)

def _safe_http_url(url):
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    lower = url.lower()
    if lower.startswith('https://') or lower.startswith('http://'):
        return url
    return None

api_bp = Blueprint('api', __name__)

@api_bp.post('/api/kulupler')
@token_required(next_location='/Kulup-Yonetimi')
@is_club_admin
def kulup_icerik_yonetim(current_user):
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
        filepath = os.path.join(api_bp.config['KULUP_UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        yeni_icerik = Kulupicerik(
            dosya_adi=unique_filename,
            dosya_yolu=filepath,
            dosya_tipi=filename.rsplit('.', 1)[1].lower(),
            yuklenme_tarihi=datetime.now(timezone.utc),
            aciklama=request.form['aciklama'],
            kulup_id=yonetim_kaydi.kulup_id,
            user_id=current_user.id
        )
        db.session.add(yeni_icerik)
        db.session.commit()
        return jsonify({'message': 'Fotoğraf başarıyla yüklendi!'}), 201
        
    return jsonify({'message': 'Dosya yüklenirken hata oluştu!'}), 400

@api_bp.route('/api/duyurular')
def api_duyurular():
    duyurular = scrape_duyurular()
    return jsonify({"duyurular": duyurular})

@api_bp.route('/api/haberler')
def api_haberler():
    articles = scrape_haberler()
    return jsonify({"articles": articles})

@api_bp.route('/api/forum-mesajlari', methods=['GET', 'POST'])
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

    # GET isteği
    else:
        mesajlar = ForumMessage.query.order_by(ForumMessage.gonderilme_tarihi.desc()).all()
        result = []
        for mesaj in mesajlar:
            
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

@api_bp.route('/api/kayip-ekle', methods=['POST'])
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

            for abonelik in abonelikler:
                try:
                    webpush(
                        subscription_info=json.loads(abonelik.subscription_info),
                        data=payload,
                        vapid_private_key=VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": "mailto:600tuna@gmail.com"}
                    )
                except Exception as e:
                    print(f">>> TEKİL GÖNDERİM HATASI (ID: {abonelik.id}): {str(e)}")

        except Exception as push_err:
            print(f">>> GENEL BİLDİRİM HATASI: {str(push_err)}")

        return jsonify({'message': 'İlan başarıyla oluşturuldu!'}), 201

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500

@api_bp.route('/api/kayiplar', methods=['GET'])
def api_kayiplar_listele():
    tip = request.args.get('tip') 
    kategori = request.args.get('kategori') 
    q = request.args.get('q')

    query = KayipEsya.query

    if tip:
        query = query.filter_by(tip=tip)
    
    if kategori and kategori != 'Tümü':
        query = query.filter_by(kategori=kategori)
        
    if q:
        search = f"%{q}%"
        query = query.filter(KayipEsya.baslik.ilike(search) | KayipEsya.aciklama.ilike(search))

    # En yeni ilan en üstte
    kayiplar = query.order_by(KayipEsya.tarih.desc()).all()
    
    return jsonify([k.to_dict() for k in kayiplar])

@api_bp.route('/api/kayiplar/stats', methods=['GET'])
def api_kayip_stats():
    toplam_kayip = KayipEsya.query.filter_by(tip='kayip').count()
    toplam_bulunan = KayipEsya.query.filter_by(tip='bulunan').count()
    bir_hafta_once = datetime.now() - timedelta(days=7)
    bu_hafta = KayipEsya.query.filter(KayipEsya.tarih >= bir_hafta_once).count()
    
    return jsonify({
        'kayip': toplam_kayip, 
        'bulunan': toplam_bulunan,
        'bu_hafta': bu_hafta
    })

@api_bp.route('/api/enstantaneler', methods=['GET'])
@token_required(next_location='/KampusteHayat')
def api_enstantaneler_getir(current_user):
    sirali = request.args.get('sirala', 'yeni') # varsayılan: yeni
    
    query = Enstantane.query
    
    # En çok beğenilenden aza doğru
    if sirali == 'populer':
        query = query.order_by(Enstantane.begeni_sayisi.desc())
        
    # En yeniden eskiye
    else:
        query = query.order_by(Enstantane.tarih.desc())
        
    gonderiler = query.all()
    return jsonify([g.to_dict(current_user.id) for g in gonderiler])

@api_bp.route('/api/enstantane-yukle', methods=['POST'])
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

@api_bp.route('/api/enstantane-begen/<int:id>', methods=['POST'])
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
@api_bp.get('/api/ofis-saatleri')
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
    
@api_bp.get('/api/ders-notlari')
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
            "tarih": not_item.yuklenme_tarihi.isoformat()
        } for not_item in notlar
    ])
    
@api_bp.get('/api/user-info')
@token_required(next_location='/api/user-info')
def api_user_info(current_user):
    return jsonify({
        'name': current_user.name,
        'kredi': current_user.kredi
    })

@api_bp.get('/api/ogretmen-degerlendirmeleri')
def api_ogretmen_degerlendirmeleri():

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
    
    ogretmenler.sort(key=lambda x: x['genel_ort'], reverse=True)
    
    return jsonify(ogretmenler)

@api_bp.get('/api/pazar')
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

@api_bp.get('/api/kanatlibulten')
def api_kanatlibulten():
    """Kanatlı Bülten yazılarını tarihe göre sıralı olarak döndür.
    Optional: pass ?kulup_adi=<str> to resolve club by name; defaults to 'Kanatlı Bülten'.
    """
    try:
        kulup_adi = request.args.get('kulup_adi')
        kulup_id = 1
        if kulup_adi:
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

@api_bp.get('/api/utaa/news')
def api_utaa_news():
    """Return UTAA posts (last + archive style). If no data, return empty list.
    Frontend should pass ?kulup_adi=<str> (e.g., 'UTAA Music Club').
    """
    try:
        kulup_adi = request.args.get('kulup_adi')
        kulup = None
        if kulup_adi:
            kulup = Kulupler.query.filter_by(kulup_adi=kulup_adi).first()
            
        # Varsayılan olarak UTAA Music Club'ın id'sini kullan, ancak kulup_adi verilmişse ona göre id'yi çöz
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

@api_bp.get('/api/fsource/news')
def api_fsource_news():
    """Return FSource posts (last + archive style). If no data, return empty list.
    Frontend should pass ?kulup_adi=<str> (defaults to 'FSource').
    """
    try:
        kulup_adi = request.args.get('kulup_adi') or 'FSource'
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

@api_bp.get('/api/makinemuh/news')
def api_makinemuh_news():
    """Return Mechanical Engineering Club posts (hero + archive).
    Frontend should pass ?kulup_adi=<str>; defaults to 'Makine Mühendisliği Kulübü'.
    """
    try:
        kulup_adi = request.args.get('kulup_adi') or 'Makine Mühendisliği Kulübü'
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

@api_bp.get('/api/utaa/events')
def api_utaa_events():
    """Return UTAA events. Optional: pass ?kulup_adi=<str> to resolve id; or ?kulup_id=<int>.
    If no data or error, return empty list.
    """
    try:
        kulup_id = request.args.get('kulup_id', type=int)
        if not kulup_id:
            kulup_adi = request.args.get('kulup_adi')
            if kulup_adi:
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

@api_bp.get('/api/utaa/gallery')
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

@api_bp.get('/api/yemek-saatleri')
def yemek_saatleri():
    try:
        data_obj = openpyxl.load_workbook("yemek.xlsx", data_only=True)
        sheet = data_obj.active
    except Exception as e:
        return jsonify({"error": f"Excel dosyası okunamadı: {str(e)}"}), 500

    days_map = {
        0: "Pazartesi",
        2: "Salı",
        4: "Çarşamba",
        6: "Perşembe",
        8: "Cuma"
    }
    
    new_buffer = {day: [] for day in days_map.values()}
    excluded_words = {"Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Türk", "Toplam"}

    for idx, col in enumerate(sheet.iter_cols(values_only=True)):
        if idx not in days_map:
            continue
            
        current_day = days_map[idx]
        
        # Sadece ilk 32 satırı al
        # Bunun nedeni, yemek saatleri tablosunun genellikle 30-31 gün içerdiği ve fazlasının gereksiz olacağı varsayımıdır.
        for cell_value in col[:32]:
            if cell_value is None:
                continue
                
            if isinstance(cell_value, str):
                # Eğer hücre metni, yasaklı kelimelerden herhangi birini içeriyorsa atla
                if any(word in cell_value for word in excluded_words):
                    continue
                
                new_buffer[current_day].append(cell_value.strip())
                
            elif isinstance(cell_value, datetime):
                new_buffer[current_day].append(cell_value.strftime("%Y-%m-%d"))
                
    return jsonify(new_buffer)

@api_bp.get('/api/otobus-saatleri')
def api_otobus_saatleri():
    duraklar = ["51325", "51165", "51164"]
    sonuc = {}
    for durak in duraklar:
        try:
            otobus_listesi = durak_sorgula(durak)
            sonuc[durak] = otobus_listesi
        except Exception as e:
            traceback.print_exc()
            sonuc[durak] = []
    return jsonify(sonuc)

@api_bp.post('/api/not-ekle')
@token_required(next_location='/ders-notlari')
def api_not_ekle(current_user):
    if 'file' not in request.files:
        return jsonify({'message': 'Dosya bulunamadı'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'Dosya seçilmedi'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        yeni_not = DersNotuBekleyen(
            ders_adi=request.form.get('ders_adi', 'Bilinmeyen Ders'),
            dosya_adi=unique_filename,
            dosya_yolu=filepath,
            dosya_tipi=filename.rsplit('.', 1)[1].lower(),
            yuklenme_tarihi=datetime.now(timezone.utc),
            user_id=current_user.id,
            durum='PENDING'
        )
        db.session.add(yeni_not)
        db.session.commit()
        return jsonify({'message': 'Notunuz başarıyla yüklendi ve yönetici onayına gönderildi!'}), 201
    
    return jsonify({'message': 'Geçersiz dosya formatı'}), 400

@api_bp.get('/api/kullanici-notlari')
@token_required()
def api_kullanici_notlari(current_user):
    onaylanmislar = DersNotu.query.filter_by(user_id=current_user.id).all()
    digerleri = DersNotuBekleyen.query.filter_by(user_id=current_user.id).all()
    
    sonuc = []
    for not_item in onaylanmislar:
        sonuc.append({"id": not_item.id, "ders_adi": not_item.ders_adi, "tarih": not_item.yuklenme_tarihi.isoformat(), "durum": "APPROVED"})
        
    for not_item in digerleri:
        sonuc.append({"id": not_item.id, "ders_adi": not_item.ders_adi, "tarih": not_item.yuklenme_tarihi.isoformat(), "durum": not_item.durum})
        
    sonuc.sort(key=lambda x: x['tarih'], reverse=True)
    return jsonify(sonuc)

@api_bp.delete('/api/not-geri-cek/<int:id>')
@token_required()
def api_not_geri_cek(current_user, id):
    bekleyen_not = DersNotuBekleyen.query.filter_by(id=id, user_id=current_user.id).first()
    if not bekleyen_not:
        return jsonify({'message': 'Bu not bulunamadı veya silme yetkiniz yok.'}), 404
        
    if bekleyen_not.durum == 'PENDING':
        try:
            if os.path.exists(bekleyen_not.dosya_yolu):
                os.remove(bekleyen_not.dosya_yolu)
        except: pass

        db.session.delete(bekleyen_not)
        db.session.commit()
        return jsonify({'message': 'Not başarıyla geri çekildi.'}), 200
    
    return jsonify({'message': 'Sadece beklemede olan notlar geri çekilebilir.'}), 400

@api_bp.post('/api/degerlendirme-ekle')
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

@api_bp.post('/api/like-dislike-message/<int:message_id>')
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

@api_bp.post('/api/ilan-ekle')
@token_required(next_location='/ilan-ekle')
def api_ilan_ekle(current_user):
    try:
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
            
            kayit_yolu = os.path.join(current_app.config['PAZAR_UPLOAD_FOLDER'], unique_filename)
            
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
        traceback.print_exc() 
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500

@api_bp.post('/api/abonelik-kaydet')
@token_required(next_location='/')
def api_abonelik_kaydet(current_user):
    try:
        subscription_data = request.get_json()

        if not subscription_data:
            return jsonify({'message': 'Abonelik verisi bulunamadı!'}), 400

        endpoint = subscription_data.get('endpoint')
        
        mevcut_abonelik = WebPushSubscription.query.filter(
            WebPushSubscription.subscription_info.like(f'%{endpoint}%')
        ).first()

        if mevcut_abonelik:
            return jsonify({'message': 'Bu cihaz zaten bildirimlere abone.'}), 200

        yeni_abonelik = WebPushSubscription(
            subscription_info=json.dumps(subscription_data),
            kullanici_ajani=request.headers.get('User-Agent'),
            user_id=current_user.id
        )

        db.session.add(yeni_abonelik)
        db.session.commit()

        try:
            bildirim_gonder(
                subscription_info=subscription_data,
                baslik="Sisteme Kayıt Başarılı!",
                mesaj="Artık bildirimleri alabileceksiniz.",
                url="/kayiplar"
            )
        except Exception as push_err:
            print(f"İlk bildirim gönderilirken hata oluştu: {push_err}")

        return jsonify({'message': 'Abonelik başarıyla kaydedildi!'}), 201

    except Exception as e:
        traceback.print_exc()
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500
    
@api_bp.post('/ogretmen-ekle')
def ogretmen_ekle():
    data = request.json
    name = data.get("ad")
    surname = data.get("soyad")
    days = data.get("gun")
    
    instructor = saatler.SaatlerPending(
        name=f"{name} {surname}",
        days=days
    )
    db.session.add(instructor)
    db.session.commit()
    return jsonify({"message": "Öğretim Görevlisi Başarıyla Eklendi!--Onay Bekliyor."}), 201

# Sadece admin kullanıcıların erişebileceği endpointler
@api_bp.post('/verify-all')
@token_required(next_location='/')
@is_admin
def verify_all(current_user):
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

# --- ADMIN PANELİ API'LERİ ---

@api_bp.get('/api/admin/users')
@token_required()
@is_admin
def get_all_users(current_user):
    # Arama parametresi varsa al
    search_query = request.args.get('q', '').lower()
    
    query = User.query
    if search_query:
        query = query.filter(db.or_(
            User.name.ilike(f"%{search_query}%"),
            User.email.ilike(f"%{search_query}%")
        ))
        
    users = query.all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'kredi': u.kredi
    } for u in users])

@api_bp.get('/api/admin/pending-instructors')
@token_required()
@is_admin
def get_pending_instructors(current_user):
    pending = saatler.SaatlerPending.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'days': p.days
    } for p in pending])

@api_bp.post('/api/admin/verify-instructor/<int:id>')
@token_required()
@is_admin
def verify_single_instructor(current_user, id):
    pending = saatler.SaatlerPending.query.get_or_404(id)
    
    approved = saatler.Saatler(name=pending.name, days=pending.days)
    db.session.add(approved)
    db.session.delete(pending)
    db.session.commit()
    
    return jsonify({'message': 'Öğretim görevlisi başarıyla onaylandı!'}), 200

@api_bp.delete('/api/admin/reject-instructor/<int:id>')
@token_required()
@is_admin
def reject_single_instructor(current_user, id):
    pending = saatler.SaatlerPending.query.get_or_404(id)
    db.session.delete(pending)
    db.session.commit()
    
    return jsonify({'message': 'İstek reddedildi ve silindi!'}), 200

@api_bp.post('/api/admin/users')
@token_required()
@is_admin
def add_new_user(current_user):
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({'message': 'Tüm alanları doldurmanız gerekmektedir!'}), 400

    # Email kontrolü
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Bu email adresi ile zaten bir kayıt mevcut!'}), 400

    try:
        new_user = User(
            public_id=str(uuid.uuid4()),
            name=name,
            email=email,
            password=generate_password_hash(password),
            kredi=1 # Başlangıç kredisi
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Kullanıcı başarıyla eklendi!'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500

@api_bp.delete('/api/admin/users/<int:id>')
@token_required()
@is_admin
def delete_user(current_user, id):
    user_to_delete = User.query.get_or_404(id)
    
    # Kendi kendini silmeyi engelle
    if user_to_delete.id == current_user.id:
        return jsonify({'message': 'Kendi yönetici hesabınızı silemezsiniz!'}), 400

    try:
        # Abonelik ilişkisi kullanıcı silmeyi engellemesin
        WebPushSubscription.query.filter_by(user_id=user_to_delete.id).delete(synchronize_session=False)
        db.session.delete(user_to_delete)
        db.session.commit()
        return jsonify({'message': 'Kullanıcı başarıyla silindi!'}), 200
    except Exception as e:
        db.session.rollback()
        
        # Eğer kullanıcının sistemde bağlı verileri (notlar, mesajlar vb.) varsa silme işlemi hata verir.
        return jsonify({'message': 'Kullanıcı silinemedi! Bu öğrencinin sistemde aktif verileri (ders notu, forum mesajı vb.) olabilir.'}), 400
    
@api_bp.put('/api/admin/users/<int:id>/kredi')
@token_required()
@is_admin
def update_user_credit(current_user, id):
    data = request.json
    yeni_kredi = data.get('kredi')

    if yeni_kredi is None:
        return jsonify({'message': 'Yeni kredi miktarı belirtilmedi!'}), 400

    try:
        yeni_kredi = int(yeni_kredi)
        if yeni_kredi < 0:
            return jsonify({'message': 'Kredi 0\'dan küçük olamaz!'}), 400
    except ValueError:
        return jsonify({'message': 'Geçerli bir sayı giriniz!'}), 400

    user = User.query.get_or_404(id)
    user.kredi = yeni_kredi
    
    try:
        db.session.commit()
        return jsonify({'message': f'Kredi başarıyla {yeni_kredi} olarak güncellendi!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Sunucu hatası: {str(e)}'}), 500
    
@api_bp.get('/api/admin/pending-notes')
@token_required()
@is_admin
def get_pending_notes(current_user):
    notes = db.session.query(DersNotuBekleyen, User.name, User.email)\
        .join(User, DersNotuBekleyen.user_id == User.id)\
        .filter(DersNotuBekleyen.durum == 'PENDING').all()
    
    return jsonify([{
        'id': n[0].id,
        'ders_adi': n[0].ders_adi,
        'dosya_url': f"/uploads/notes/{n[0].dosya_adi}",
        'tarih': n[0].yuklenme_tarihi.strftime("%d.%m.%Y %H:%M"),
        'kullanici_ad': n[1],
        'kullanici_email': n[2]
    } for n in notes])

@api_bp.post('/api/admin/approve-note/<int:id>')
@token_required()
@is_admin
def approve_note(current_user, id):
    bekleyen = DersNotuBekleyen.query.get_or_404(id)
    if bekleyen.durum != 'PENDING':
        return jsonify({'message': 'Bu not zaten islenmis.'}), 400
        
    onayli_not = DersNotu(
        ders_adi=bekleyen.ders_adi,
        dosya_adi=bekleyen.dosya_adi,
        dosya_yolu=bekleyen.dosya_yolu,
        dosya_tipi=bekleyen.dosya_tipi,
        yuklenme_tarihi=bekleyen.yuklenme_tarihi,
        user_id=bekleyen.user_id
    )
    
    note_owner = User.query.get(bekleyen.user_id)
    if note_owner:
        note_owner.kredi += 2
        
        bildirim_gonder_kullaniciya(note_owner.id, "✅ Ders Notunuz Onaylandı!", f"Yüklediğiniz '{bekleyen.ders_adi}' notu onaylandı ve 2 kredi kazandınız.", "/ders-notlari")

    db.session.add(onayli_not)
    db.session.delete(bekleyen)
    db.session.commit()
    
    return jsonify({'message': 'Not başarıyla onaylandı ve kredi verildi!'}), 200

@api_bp.post('/api/admin/reject-note/<int:id>')
@token_required()
@is_admin
def reject_note(current_user, id):
    bekleyen = DersNotuBekleyen.query.get_or_404(id)
    
    bekleyen.durum = 'REJECTED'
    
    note_owner = User.query.get(bekleyen.user_id)
    if note_owner:
        bildirim_gonder_kullaniciya(note_owner.id, "❌ Notunuz Reddedildi", f"Yüklediğiniz '{bekleyen.ders_adi}' notu standartlara uymadığı için reddedildi.", "/not-ekle")

    db.session.commit()
    return jsonify({'message': 'Not reddedildi.'}), 200

@api_bp.get('/api/admin/notlar')
@token_required()
@is_admin
def get_all_notes(current_user):
    query = request.args.get('q', '').lower()
    
    notes = db.session.query(DersNotu, User.name, User.email)\
        .join(User, DersNotu.user_id == User.id)\
        .filter(db.or_(DersNotu.ders_adi.contains(query), User.name.contains(query), User.email.contains(query))).all()
        
    return jsonify([{
        'id': n[0].id,
        'ders_adi': n[0].ders_adi,
        'dosya_url': f"/uploads/notes/{n[0].dosya_adi}",
        'tarih': n[0].yuklenme_tarihi,
        'kullanici_ad': n[1],
        'kullanici_email': n[2]
    } for n in notes])
    
@api_bp.delete('/api/admin/notlar/<int:id>')
@token_required()
@is_admin
def delete_note(current_user, id):
    note = DersNotu.query.get_or_404(id)
    db.session.delete(note)
    db.session.commit()
    return jsonify({'message': 'Not başarıyla silindi!'}), 200
    
@api_bp.get('/api/admin/subscriptions')
@token_required()
@is_admin
def get_subscriptions(current_user):
    subscriptions = db.session.query(WebPushSubscription, User.name, User.email)\
        .outerjoin(User, WebPushSubscription.user_id == User.id).all()
    return jsonify([{
        'id': sub[0].id,
        'olusturulma_tarihi': sub[0].olusturulma_tarihi.strftime('%d.%m.%Y %H:%M') if sub[0].olusturulma_tarihi else None,
        'user_id': sub[0].user_id,
        'kullanici_ad': sub[1] or 'Bilinmiyor',
        'kullanici_email': sub[2] or '-',
        'kullanici_ajani': sub[0].kullanici_ajani
    } for sub in subscriptions])

@api_bp.delete('/api/admin/subscriptions/<int:id>')
@token_required()
@is_admin
def delete_subscription(current_user, id):
    sub = WebPushSubscription.query.get_or_404(id)
    try:
        db.session.delete(sub)
        db.session.commit()
        return jsonify({'message': 'Abonelik başarıyla silindi!'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'Abonelik silme hatası: {e}')
        return jsonify({'message': 'Abonelik silinirken bir hata oluştu.'}), 500

@api_bp.get('/api/admin/istekler')
@token_required()
@is_admin
def admin_istekleri_listele(current_user):
    rows = db.session.query(Istek, User.name, User.email)\
        .outerjoin(User, Istek.user_id == User.id)\
        .order_by(Istek.tarih.desc()).all()
    return jsonify([{
        **i.to_dict(),
        'kullanici_ad': name or 'Anonim',
        'kullanici_email': email or '-'
    } for i, name, email in rows]), 200

@api_bp.delete('/api/admin/istekler/<int:istek_id>')
@token_required()
@is_admin
def admin_istek_sil(current_user, istek_id):
    istek = Istek.query.get_or_404(istek_id)
    try:
        db.session.delete(istek)
        db.session.commit()
        return jsonify({'message': 'İstek başarıyla silindi.'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'İstek silme hatası: {e}')
        return jsonify({'message': 'İstek silinirken bir hata oluştu.'}), 500

@api_bp.put('/api/admin/istekler/<int:istek_id>/durum')
@token_required()
@is_admin
def admin_istek_durum(current_user, istek_id):
    istek = Istek.query.get_or_404(istek_id)
    data = request.get_json() or {}
    yeni_durum = data.get('durum')
    if not yeni_durum:
        return jsonify({'message': 'Durum belirtilmedi.'}), 400
    istek.durum = yeni_durum
    try:
        db.session.commit()
        return jsonify({'message': 'Durum güncellendi.', 'istek': istek.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        print(f'İstek durum güncelleme hatası: {e}')
        return jsonify({'message': 'Durum güncellenirken bir hata oluştu.'}), 500

@api_bp.post('/api/istekler')
@token_required()
def istek_olustur(current_user):
    data = request.get_json()
    if not data or not data.get('baslik') or not data.get('aciklama'):
        return jsonify({'message': 'Başlık ve açıklama alanları zorunludur.'}), 400

    yeni_istek = Istek(
        baslik=data['baslik'],
        aciklama=data['aciklama'],
        kategori=data.get('kategori', 'Genel'),
        user_id=current_user.id
    )
    db.session.add(yeni_istek)
    db.session.commit()
    
    return jsonify({'message': 'İsteğiniz başarıyla alındı.', 'istek': yeni_istek.to_dict()}), 201


@api_bp.get('/api/istekler')
def istekleri_listele():
    istekler = Istek.query.order_by(Istek.tarih.desc()).all()
    return jsonify([i.to_dict() for i in istekler]), 200

@api_bp.route('/api/istekler/<int:istek_id>', methods=['DELETE'])
def istek_sil(istek_id):
    try:
        istek = Istek.query.get(istek_id)
        if not istek:
            return jsonify({'status': 'error', 'message': 'İstek bulunamadı.'}), 404

        db.session.delete(istek)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'İstek başarıyla silindi.'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'İstek silme hatası: {e}')
        return jsonify({'status': 'error', 'message': 'İstek silinirken bir hata oluştu.'}), 500


# --- KATKIDA BULUNANLAR ---

@api_bp.get('/api/katkida-bulunanlar')
@token_required_api
def katkida_bulunanlari_listele(current_user):
    kisiler = KatkidaBulunan.query.order_by(KatkidaBulunan.sira.asc(), KatkidaBulunan.id.asc()).all()
    return jsonify([k.to_dict() for k in kisiler]), 200

@api_bp.post('/api/admin/katkida-bulunanlar')
@token_required()
@is_admin
def katkida_ekle(current_user):
    ad = (request.form.get('ad') or '').strip()
    soyad = (request.form.get('soyad') or '').strip()
    github_url = _safe_http_url(request.form.get('github_url'))
    aciklama = (request.form.get('aciklama') or '').strip() or None
    try:
        sira = int(request.form.get('sira') or 0)
    except ValueError:
        sira = 0

    if not ad or not soyad:
        return jsonify({'message': 'Ad ve soyad zorunludur.'}), 400

    fotograf_adi = None
    if 'fotograf' in request.files:
        file = request.files['fotograf']
        if file and file.filename:
            if not allowed_image(file.filename):
                return jsonify({'message': 'Sadece görsel dosyaları (png, jpg, jpeg, gif, webp) yüklenebilir.'}), 400
            filename = secure_filename(file.filename)
            fotograf_adi = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(KATKIDA_UPLOAD_FOLDER, fotograf_adi))

    kisi = KatkidaBulunan(
        ad=ad,
        soyad=soyad,
        fotograf=fotograf_adi,
        github_url=github_url,
        aciklama=aciklama,
        sira=sira
    )
    try:
        db.session.add(kisi)
        db.session.commit()
        return jsonify({'message': 'Katkıda bulunan eklendi.', 'kisi': kisi.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        print(f'Katkıda bulunan ekleme hatası: {e}')
        return jsonify({'message': 'Kayıt eklenirken bir hata oluştu.'}), 500

@api_bp.put('/api/admin/katkida-bulunanlar/<int:id>')
@token_required()
@is_admin
def katkida_guncelle(current_user, id):
    kisi = KatkidaBulunan.query.get_or_404(id)
    ad = (request.form.get('ad') or kisi.ad or '').strip()
    soyad = (request.form.get('soyad') or kisi.soyad or '').strip()
    if not ad or not soyad:
        return jsonify({'message': 'Ad ve soyad zorunludur.'}), 400

    kisi.ad = ad
    kisi.soyad = soyad
    if 'github_url' in request.form:
        kisi.github_url = _safe_http_url(request.form.get('github_url'))
    if 'aciklama' in request.form:
        kisi.aciklama = (request.form.get('aciklama') or '').strip() or None
    if 'sira' in request.form:
        try:
            kisi.sira = int(request.form.get('sira') or 0)
        except ValueError:
            pass

    if 'fotograf' in request.files:
        file = request.files['fotograf']
        if file and file.filename:
            if not allowed_image(file.filename):
                return jsonify({'message': 'Sadece görsel dosyaları yüklenebilir.'}), 400
            if kisi.fotograf:
                eski = os.path.join(KATKIDA_UPLOAD_FOLDER, kisi.fotograf)
                if os.path.exists(eski):
                    try:
                        os.remove(eski)
                    except OSError:
                        pass
            filename = secure_filename(file.filename)
            fotograf_adi = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(KATKIDA_UPLOAD_FOLDER, fotograf_adi))
            kisi.fotograf = fotograf_adi

    try:
        db.session.commit()
        return jsonify({'message': 'Kayıt güncellendi.', 'kisi': kisi.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        print(f'Katkıda bulunan güncelleme hatası: {e}')
        return jsonify({'message': 'Kayıt güncellenirken bir hata oluştu.'}), 500

@api_bp.delete('/api/admin/katkida-bulunanlar/<int:id>')
@token_required()
@is_admin
def katkida_sil(current_user, id):
    kisi = KatkidaBulunan.query.get_or_404(id)
    try:
        if kisi.fotograf:
            path = os.path.join(KATKIDA_UPLOAD_FOLDER, kisi.fotograf)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        db.session.delete(kisi)
        db.session.commit()
        return jsonify({'message': 'Katkıda bulunan silindi.'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'Katkıda bulunan silme hatası: {e}')
        return jsonify({'message': 'Kayıt silinirken bir hata oluştu.'}), 500