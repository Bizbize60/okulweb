from flask import Blueprint, request, jsonify, current_app
import os
import uuid
import json
import re
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
import openpyxl
import requests
from pywebpush import webpush
from sqlalchemy import func
from datetime import datetime
import traceback
from werkzeug.security import generate_password_hash

from database.initdb import db
from database.user import (
    User, Ambassador, Referral, Badge, UserBadge,
    ReferralReward, EarnedReward
)
from database.forum_message import ForumMessage
from database.forum_like import ForumLike
from database.forum_comment import ForumComment
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
from database.moderator import Moderator
from database.daily_active import DailyActiveUser

from config import VAPID_PRIVATE_KEY, ADMIN_EMAILS
try:
    from config import STATS_OWNER_EMAIL
except ImportError:
    STATS_OWNER_EMAIL = "s210444025@stu.thk.edu.tr"
from utils import allowed_file, allowed_image, bildirim_gonder_kullaniciya, kayip_upload_path, enstantane_upload_path, scrape_duyurular, scrape_haberler, bildirim_gonder
from auth import token_required, token_required_api, is_club_admin, is_admin, user_has_permission
from yemek_menu import get_menu_data, get_today_menu, legacy_days_payload
from ulasim import ulasim_overview
from zoneinfo import ZoneInfo
from database.admin_rbac import Role, Permission

KATKIDA_UPLOAD_FOLDER = os.path.join('uploads', 'katkida')
os.makedirs(KATKIDA_UPLOAD_FOLDER, exist_ok=True)

MODERATOR_UPLOAD_FOLDER = os.path.join('uploads', 'moderator')
os.makedirs(MODERATOR_UPLOAD_FOLDER, exist_ok=True)

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


def _forum_parse_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'on', 'evet'}:
        return True
    if normalized in {'0', 'false', 'no', 'off', 'hayir', 'hayır'}:
        return False
    return default


def _forum_validate_gif_url(raw_url):
    if raw_url is None:
        return True, None

    candidate = str(raw_url).strip()
    if not candidate:
        return True, None

    safe_url = _safe_http_url(candidate)
    if not safe_url:
        return False, None

    lowered = safe_url.lower()

    # Bu domainler zaten dogrudan medya sunar (yonlendirme/HTML sayfasi degil).
    direct_media_hosts = ('media.tenor.com', 'giphyusercontent.com')
    if any(host in lowered for host in direct_media_hosts):
        return True, safe_url

    # tenor.com/giphy.com "paylasim" linkleri .gif ile bitse bile aslinda HTML
    # sayfasi dondurur (gercek medya mp4/gif olabilir); bu yuzden uzantiya
    # guvenmeden her zaman gercek medya URL'sini cozumlemeye calisiyoruz.
    if 'tenor.com' in lowered or 'giphy.com' in lowered:
        try:
            response = requests.get(
                safe_url,
                timeout=7,
                allow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (ForumBot) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
                }
            )
        except requests.RequestException:
            return False, None

        final_url = (response.url or '').strip()
        content_type = (response.headers.get('Content-Type') or '').lower()
        media_extensions = ('.gif', '.webp', '.mp4', '.webm')
        if final_url and _safe_http_url(final_url):
            final_lower = final_url.lower()
            if final_lower.endswith(media_extensions):
                return True, final_url
            if content_type.startswith(('image/', 'video/')) and any(
                host in final_lower for host in direct_media_hosts
            ):
                return True, final_url

        if 'text/html' in content_type:
            html = response.text or ''
            match = re.search(
                r'https?://(?:media\.tenor\.com|i\.giphy\.com|media\d?\.giphy\.com|giphyusercontent\.com)[^"\'\s>]+\.(?:gif|webp|mp4|webm)',
                html,
                re.IGNORECASE,
            )
            if match:
                return True, match.group(0)

        return False, None

    # tenor.com/giphy.com disindaki genel URL'ler icin uzanti kontrolu yeterli.
    if lowered.endswith(('.gif', '.webp', '.mp4', '.webm')):
        return True, safe_url

    return False, None


def _forum_is_admin_or_moderator(user):
    if not user:
        return False
    if user_has_permission(user, 'system.admin'):
        return True
    if user.has_role('moderator'):
        return True
    return user.email in ADMIN_EMAILS and user.has_role('owner')


def _forum_can_delete(current_user, owner_id):
    if not current_user:
        return False
    if current_user.id == owner_id:
        return True
    return _forum_is_admin_or_moderator(current_user)


def _forum_display_name(user, isim_gorunsun):
    if not isim_gorunsun:
        return 'Anonim'
    if user and user.name:
        return user.name
    return 'Anonim'


def _serialize_forum_comment(comment, current_user):
    deleted = bool(comment.silindi)
    content = 'Bu yorum silindi.' if deleted else (comment.yorum_icerigi or '')

    return {
        'id': comment.id,
        'message_id': comment.message_id,
        'parent_comment_id': comment.parent_comment_id,
        'yorum_icerigi': content,
        'display_name': _forum_display_name(comment.user, comment.isim_gorunsun) if not deleted else 'Anonim',
        'is_deleted': deleted,
        'gonderilme_tarihi': comment.gonderilme_tarihi.isoformat() if comment.gonderilme_tarihi else None,
        'can_delete': _forum_can_delete(current_user, comment.user_id),
        'children': []
    }


def _build_forum_comment_tree(comments, current_user):
    by_parent = {}
    for comment in comments:
        by_parent.setdefault(comment.parent_comment_id, []).append(comment)

    def build(parent_id, depth=0):
        if depth > 12:
            return []
        nodes = []
        for comment in by_parent.get(parent_id, []):
            serialized = _serialize_forum_comment(comment, current_user)
            serialized['children'] = build(comment.id, depth + 1)
            nodes.append(serialized)
        return nodes

    return build(None)


def _serialize_forum_post(post, current_user, user_action=None, comment_tree=None):
    comments = comment_tree or []
    return {
        'id': post.id,
        'konu': post.konu,
        'mesaj_icerigi': post.mesaj_icerigi or '',
        'gif_url': post.gif_url,
        'display_name': _forum_display_name(post.user, post.isim_gorunsun),
        'gonderilme_tarihi': post.gonderilme_tarihi.isoformat() if post.gonderilme_tarihi else None,
        'begeni_sayisi': post.begeni_sayisi,
        'user_action': user_action,
        'can_delete': _forum_can_delete(current_user, post.user_id),
        'comment_count': len(comments),
        'comments': comments
    }

api_bp = Blueprint('api', __name__)

EXAM_WEEK_BLITZ_REWARDS = {
    'ders_notu': {'credit': 3, 'ambassador_points': 40},
    'degerlendirme': {'credit': 2, 'ambassador_points': 30},
    'forum': {'credit': 2, 'ambassador_points': 20},
}


def _is_exam_week_blitz_active():
    return bool(current_app.config.get('EXAM_WEEK_BLITZ_ENABLED', False))


@api_bp.get('/api/admin/exam-blitz')
@token_required()
@is_admin
def api_admin_exam_blitz_status(current_user):
    """Sınav haftası blitz kampanyasının açık/kapalı durumunu döndürür."""
    return jsonify({
        'enabled': _is_exam_week_blitz_active(),
        'campaign': {
            'title': 'Sınav Haftası Blitz',
            'bonus_credit': EXAM_WEEK_BLITZ_REWARDS,
            'ambassador_levels': {
                'bronze': 100,
                'silver': 500,
                'gold': 2000,
                'diamond': 5000,
            }
        }
    }), 200


@api_bp.post('/api/admin/exam-blitz')
@token_required()
@is_admin
def api_admin_exam_blitz_toggle(current_user):
    """Yöneticinin sınav haftası blitz kampanyasını açıp kapatması için endpoint."""
    payload = request.get_json(force=True) or {}
    enabled = payload.get('enabled')
    if enabled is None:
        return jsonify({'message': 'enabled alanı zorunludur.'}), 400

    current_app.config['EXAM_WEEK_BLITZ_ENABLED'] = bool(enabled)
    return jsonify({
        'message': 'Sınav haftası blitz ' + ('etkinleştirildi.' if current_app.config['EXAM_WEEK_BLITZ_ENABLED'] else 'kapatıldı.'),
        'enabled': current_app.config['EXAM_WEEK_BLITZ_ENABLED'],
    }), 200


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

@api_bp.get('/api/forum/posts')
@token_required(next_location='/forum')
def api_forum_posts(current_user):
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', 8))
    except (TypeError, ValueError):
        page_size = 8

    page = max(page, 1)
    page_size = max(1, min(page_size, 20))

    base_query = ForumMessage.query.filter_by(silindi=False).order_by(ForumMessage.gonderilme_tarihi.desc())
    total_items = base_query.count()
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages

    posts = base_query.offset((page - 1) * page_size).limit(page_size).all()
    post_ids = [post.id for post in posts]

    user_like_map = {}
    if post_ids:
        likes = ForumLike.query.filter(
            ForumLike.user_id == current_user.id,
            ForumLike.message_id.in_(post_ids)
        ).all()
        user_like_map = {like.message_id: like.like_type for like in likes}

    comments_by_post = {}
    if post_ids:
        comments = ForumComment.query.filter(
            ForumComment.message_id.in_(post_ids)
        ).order_by(ForumComment.gonderilme_tarihi.asc()).all()
        for comment in comments:
            comments_by_post.setdefault(comment.message_id, []).append(comment)

    result = []
    for post in posts:
        comment_tree = _build_forum_comment_tree(comments_by_post.get(post.id, []), current_user)
        result.append(_serialize_forum_post(post, current_user, user_like_map.get(post.id), comment_tree))

    return jsonify({
        'items': result,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_items': total_items,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        }
    }), 200


@api_bp.post('/api/forum/posts')
@token_required(next_location='/forum')
def api_forum_create_post(current_user):
    payload = request.get_json(silent=True) or {}

    konu = (payload.get('konu') or '').strip()
    mesaj_icerigi = (payload.get('mesaj_icerigi') or '').strip()
    isim_gorunsun = _forum_parse_bool(payload.get('isim_gorunsun'), default=True)

    gif_valid, gif_url = _forum_validate_gif_url(payload.get('gif_url'))
    if not gif_valid:
        return jsonify({'message': 'GIF URL sadece gecerli http/https gif baglantisi olabilir.'}), 400

    if not konu:
        return jsonify({'message': 'Konu zorunludur.'}), 400
    if len(konu) > 200:
        return jsonify({'message': 'Konu en fazla 200 karakter olabilir.'}), 400
    if len(mesaj_icerigi) > 2000:
        return jsonify({'message': 'Mesaj icerigi en fazla 2000 karakter olabilir.'}), 400
    if not mesaj_icerigi and not gif_url:
        return jsonify({'message': 'Mesaj icerigi veya GIF URL alanlarindan biri gereklidir.'}), 400

    post = ForumMessage(
        konu=konu,
        mesaj_icerigi=mesaj_icerigi,
        user_id=current_user.id,
        isim_gorunsun=isim_gorunsun,
        gif_url=gif_url,
    )
    db.session.add(post)
    db.session.commit()

    _aktivite_puan_ver(current_user, 20, 'forum')

    return jsonify({
        'message': 'Mesaj basariyla eklendi!',
        'post': _serialize_forum_post(post, current_user, user_action=None, comment_tree=[])
    }), 201


@api_bp.get('/api/forum/posts/<int:post_id>')
@token_required(next_location='/forum')
def api_forum_post_detail(current_user, post_id):
    post = ForumMessage.query.filter_by(id=post_id, silindi=False).first()
    if not post:
        return jsonify({'message': 'Mesaj bulunamadi.'}), 404

    user_like = ForumLike.query.filter_by(user_id=current_user.id, message_id=post.id).first()
    comments = ForumComment.query.filter_by(message_id=post.id).order_by(ForumComment.gonderilme_tarihi.asc()).all()
    comment_tree = _build_forum_comment_tree(comments, current_user)

    return jsonify(_serialize_forum_post(post, current_user, user_like.like_type if user_like else None, comment_tree)), 200


@api_bp.post('/api/forum/posts/<int:post_id>/reactions')
@token_required(next_location='/forum')
def api_forum_react_post(current_user, post_id):
    post = db.session.get(ForumMessage, post_id)
    if not post or post.silindi:
        return jsonify({'message': 'Mesaj bulunamadi!'}), 404

    payload = request.get_json(silent=True) or {}
    action = payload.get('action')
    if action not in ['like', 'dislike']:
        return jsonify({'message': 'Gecersiz islem!'}), 400

    existing_like = ForumLike.query.filter_by(user_id=current_user.id, message_id=post_id).first()

    if existing_like:
        if existing_like.like_type == action:
            if action == 'like':
                post.begeni_sayisi -= 1
            else:
                post.begeni_sayisi += 1

            db.session.delete(existing_like)
            db.session.commit()
            return jsonify({
                'message': 'Islem geri alindi!',
                'begeni_sayisi': post.begeni_sayisi,
                'user_action': None
            }), 200

        if existing_like.like_type == 'like' and action == 'dislike':
            post.begeni_sayisi -= 2
        elif existing_like.like_type == 'dislike' and action == 'like':
            post.begeni_sayisi += 2

        existing_like.like_type = action
        db.session.commit()
        return jsonify({
            'message': 'Islem guncellendi!',
            'begeni_sayisi': post.begeni_sayisi,
            'user_action': action
        }), 200

    new_like = ForumLike(user_id=current_user.id, message_id=post_id, like_type=action)
    if action == 'like':
        post.begeni_sayisi += 1
    else:
        post.begeni_sayisi -= 1

    db.session.add(new_like)
    db.session.commit()

    return jsonify({
        'message': 'Islem basariyla gerceklestirildi!',
        'begeni_sayisi': post.begeni_sayisi,
        'user_action': action
    }), 200


@api_bp.post('/api/forum/posts/<int:post_id>/comments')
@token_required(next_location='/forum')
def api_forum_add_comment(current_user, post_id):
    post = ForumMessage.query.filter_by(id=post_id, silindi=False).first()
    if not post:
        return jsonify({'message': 'Mesaj bulunamadi.'}), 404

    payload = request.get_json(silent=True) or {}
    yorum_icerigi = (payload.get('yorum_icerigi') or '').strip()
    isim_gorunsun = _forum_parse_bool(payload.get('isim_gorunsun'), default=True)
    parent_comment_id = payload.get('parent_comment_id')

    if not yorum_icerigi:
        return jsonify({'message': 'Yorum icerigi zorunludur.'}), 400
    if len(yorum_icerigi) > 1200:
        return jsonify({'message': 'Yorum en fazla 1200 karakter olabilir.'}), 400

    parent_comment = None
    if parent_comment_id is not None:
        try:
            parent_comment_id = int(parent_comment_id)
        except (TypeError, ValueError):
            return jsonify({'message': 'Gecersiz parent_comment_id.'}), 400

        parent_comment = db.session.get(ForumComment, parent_comment_id)
        if not parent_comment or parent_comment.message_id != post_id:
            return jsonify({'message': 'Ust yorum bulunamadi.'}), 400
        if parent_comment.silindi:
            return jsonify({'message': 'Silinmis yoruma cevap verilemez.'}), 400

    comment = ForumComment(
        message_id=post_id,
        parent_comment_id=parent_comment_id,
        user_id=current_user.id,
        yorum_icerigi=yorum_icerigi,
        isim_gorunsun=isim_gorunsun,
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'message': 'Yorum basariyla eklendi.',
        'comment': _serialize_forum_comment(comment, current_user)
    }), 201


@api_bp.delete('/api/forum/posts/<int:post_id>')
@token_required(next_location='/forum')
def api_forum_delete_post(current_user, post_id):
    post = ForumMessage.query.filter_by(id=post_id, silindi=False).first()
    if not post:
        return jsonify({'message': 'Mesaj bulunamadi.'}), 404

    if not _forum_can_delete(current_user, post.user_id):
        return jsonify({'message': 'Bu mesaji silme yetkiniz yok.'}), 403

    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Mesaj silindi.'}), 200


@api_bp.delete('/api/forum/comments/<int:comment_id>')
@token_required(next_location='/forum')
def api_forum_delete_comment(current_user, comment_id):
    comment = db.session.get(ForumComment, comment_id)
    if not comment:
        return jsonify({'message': 'Yorum bulunamadi.'}), 404

    if not _forum_can_delete(current_user, comment.user_id):
        return jsonify({'message': 'Bu yorumu silme yetkiniz yok.'}), 403

    comment.silindi = True
    comment.yorum_icerigi = ''
    comment.isim_gorunsun = False
    db.session.commit()

    return jsonify({
        'message': 'Yorum silindi.',
        'comment': _serialize_forum_comment(comment, current_user)
    }), 200

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
    davet_sayisi = Referral.query.filter_by(davet_eden_id=current_user.id, onaylandi_mi=True).count()
    return jsonify({
        'name': current_user.name,
        'kredi': current_user.kredi,
        # Sadece sahibi/owner yetkisi olan kullanıcılar istatistik görebilir
        'show_stats': user_has_permission(current_user, 'system.admin') and current_user.has_role('owner'),
        'roles': [role.name for role in (current_user.roles or [])],
        'permissions': sorted({
            permission.key
            for role in (current_user.roles or [])
            for permission in (role.permissions or [])
        }),
        'id': current_user.id,
        'email': current_user.email,
        'is_ambassador': bool(current_user.is_ambassador),
        'ambassador_level': current_user.ambassador_level or 0,
        'ambassador_level_name': current_user.seviye_adi(),
        'ambassador_level_color': current_user.seviye_renk(),
        'ambassador_points': current_user.ambassador_points or 0,
        'referral_code': current_user.referral_code or '',
        'referral_count': davet_sayisi,
        'streak_gun': current_user.streak_gun or 0,
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
            "resim": ilan.fotograf_adi if ilan.fotograf_adi.startswith('http') else f"/uploads/pazar/{ilan.fotograf_adi}",
            "resim_url": ilan.fotograf_adi if ilan.fotograf_adi.startswith('http') else f"/uploads/pazar/{ilan.fotograf_adi}",
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
    """Haftalık menü (eski şablon uyumlu gün listesi) + bugün (TR saati)."""
    try:
        data = get_menu_data()
        payload = legacy_days_payload(data)
        payload["bugun"] = get_today_menu()
        payload["kaynak"] = data.get("source", "pdf")
        payload["guncelleme"] = data.get("updated_at")
        return jsonify(payload)
    except Exception as e:
        traceback.print_exc()
        # Geriye dönük: yerel Excel varsa dene
        try:
            data_obj = openpyxl.load_workbook("yemek.xlsx", data_only=True)
            sheet = data_obj.active
            days_map = {0: "Pazartesi", 2: "Salı", 4: "Çarşamba", 6: "Perşembe", 8: "Cuma"}
            new_buffer = {day: [] for day in days_map.values()}
            excluded_words = {"Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Türk", "Toplam"}
            for idx, col in enumerate(sheet.iter_cols(values_only=True)):
                if idx not in days_map:
                    continue
                current_day = days_map[idx]
                for cell_value in col[:32]:
                    if cell_value is None:
                        continue
                    if isinstance(cell_value, str):
                        if any(word in cell_value for word in excluded_words):
                            continue
                        new_buffer[current_day].append(cell_value.strip())
                    elif isinstance(cell_value, datetime):
                        new_buffer[current_day].append(cell_value.strftime("%Y-%m-%d"))
            new_buffer["bugun"] = None
            new_buffer["kaynak"] = "excel"
            return jsonify(new_buffer)
        except Exception:
            return jsonify({"error": f"Menü okunamadı: {str(e)}"}), 500


@api_bp.get('/api/yemek-bugun')
def api_yemek_bugun():
    try:
        menu = get_today_menu()
        if not menu:
            return jsonify({"bugun": None, "message": "Bugün için menü bulunamadı (hafta sonu veya tatil)."}), 200
        return jsonify({"bugun": menu})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.get('/api/ulasim')
def api_ulasim():
    """THK servis + Başkentray sabit saatler."""
    try:
        return jsonify(ulasim_overview())
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.get('/api/kampus-ozet')
def api_kampus_ozet():
    """Anasayfa tek bakış: bugünün menüsü + sonraki THK / Başkentray."""
    try:
        menu = None
        try:
            menu = get_today_menu()
        except Exception as e:
            print(f"[kampus-ozet] menü: {e}")
        ulasim = ulasim_overview()
        return jsonify({
            "yemek": menu,
            "ulasim": ulasim,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.get('/api/otobus-saatleri')
def api_otobus_saatleri():
    return jsonify({"ulasim": ulasim_overview()})

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
        # --- Aktivite Puanı: Değerlendirme 60 puan ---
        _aktivite_puan_ver(current_user, 60, 'degerlendirme')
        return jsonify({'message': 'Değerlendirme başarıyla eklendi!'}), 201
    except Exception as e:
        return jsonify({'message': f'Hata: {str(e)}'}), 500

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
                baslik="Bildirimler açıldı!",
                mesaj="Kayıp eşya, THK servis (15 dk kala) ve yemek menüsü bildirimlerini alacaksınız.",
                url="/otobus-saatleri"
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

@api_bp.get('/api/admin/session')
@token_required()
def api_admin_session(current_user):
    """Yöneticinin oturum bilgilerini ve erişilebilir izinlerini döndürür."""
    if not user_has_permission(current_user, 'system.admin'):
        return jsonify({'message': 'Forbidden'}), 403

    role_names = [role.name for role in (current_user.roles or [])]
    permission_keys = sorted({
        permission.key
        for role in (current_user.roles or [])
        for permission in (role.permissions or [])
    })
    if current_user.email in ADMIN_EMAILS:
        from admin.permissions import DEFAULT_PERMISSION_KEYS
        permission_keys = sorted(set(permission_keys) | set(DEFAULT_PERMISSION_KEYS))

    return jsonify({
        'user_id': current_user.id,
        'email': current_user.email,
        'name': current_user.name,
        'roles': role_names,
        'permissions': permission_keys,
        'is_admin': user_has_permission(current_user, 'system.admin')
    }), 200


@api_bp.get('/api/admin/roles')
@token_required()
def api_admin_roles(current_user):
    """Tüm roller ve izin listesi."""
    if not user_has_permission(current_user, 'role.manage'):
        return jsonify({'message': 'Bu işlem için role.manage izni gereklidir.'}), 403

    rows = []
    for role in Role.query.order_by(Role.name.asc()).all():
        rows.append({
            'id': role.id,
            'name': role.name,
            'label': role.label,
            'description': role.description,
            'permissions': [permission.key for permission in (role.permissions or [])],
        })
    return jsonify({'roles': rows}), 200


@api_bp.get('/api/admin/permissions')
@token_required()
def api_admin_permissions(current_user):
    if not user_has_permission(current_user, 'role.manage'):
        return jsonify({'message': 'Bu işlem için role.manage izni gereklidir.'}), 403

    permissions = sorted({
        permission.key
        for role in Role.query.all()
        for permission in (role.permissions or [])
    })
    return jsonify({'permissions': permissions}), 200


@api_bp.get('/api/admin/users/<int:user_id>/roles')
@token_required()
def api_user_roles(current_user, user_id):
    if not user_has_permission(current_user, 'role.manage'):
        return jsonify({'message': 'Bu işlem için role.manage izni gereklidir.'}), 403

    user = User.query.get_or_404(user_id)
    return jsonify({
        'user_id': user.id,
        'name': user.name,
        'email': user.email,
        'roles': [role.name for role in (user.roles or [])],
    }), 200


@api_bp.post('/api/admin/users/<int:user_id>/roles')
@token_required()
def api_assign_user_role(current_user, user_id):
    if not user_has_permission(current_user, 'role.manage'):
        return jsonify({'message': 'Bu işlem için role.manage izni gereklidir.'}), 403

    data = request.get_json(force=True) or {}
    role_name = (data.get('role_name') or '').strip()
    if not role_name:
        return jsonify({'message': 'Rol adı zorunludur.'}), 400

    if not assign_role_to_user(user_id, role_name):
        return jsonify({'message': 'Geçersiz rol adı.'}), 400

    user = User.query.get_or_404(user_id)
    return jsonify({
        'message': f"'{role_name}' rolü kullanıcıya eklendi.",
        'roles': [role.name for role in (user.roles or [])],
    }), 200


@api_bp.delete('/api/admin/users/<int:user_id>/roles/<string:role_name>')
@token_required()
def api_remove_user_role(current_user, user_id, role_name):
    if not user_has_permission(current_user, 'role.manage'):
        return jsonify({'message': 'Bu işlem için role.manage izni gereklidir.'}), 403

    if not remove_role_from_user(user_id, role_name):
        return jsonify({'message': 'Rol bulunamadı veya kullanıcıya ait değil.'}), 404

    user = User.query.get_or_404(user_id)
    return jsonify({
        'message': f"'{role_name}' rolü kullanıcıdan kaldırıldı.",
        'roles': [role.name for role in (user.roles or [])],
    }), 200


@api_bp.get('/api/admin/stats/daily-active')
@token_required()
@is_admin
def api_admin_daily_active(current_user):
    """Yalnızca STATS_OWNER_EMAIL — bugün / dün / son 7 gün unique aktif kullanıcı."""
    if current_user.email != STATS_OWNER_EMAIL:
        return jsonify({'message': 'Forbidden'}), 403

    today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
    yesterday = today - timedelta(days=1)

    def _count_for(d):
        return DailyActiveUser.query.filter_by(activity_date=d).count()

    last_7 = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        last_7.append({
            'date': d.isoformat(),
            'label': d.strftime('%d.%m'),
            'count': _count_for(d),
        })

    today_count = last_7[-1]['count'] if last_7 else _count_for(today)
    yesterday_count = _count_for(yesterday)
    delta = today_count - yesterday_count

    return jsonify({
        'today': today_count,
        'yesterday': yesterday_count,
        'delta': delta,
        'last_7_days': last_7,
        'timezone': 'Europe/Istanbul',
        'as_of': datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),
    })


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

        # --- Aktivite Puanı: Not onaylanınca 80 puan ---
        _aktivite_puan_ver(note_owner, 80, 'ders_notu')

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
@token_required(next_location='/login')
def istekleri_listele(current_user):
    istekler = Istek.query.filter_by(user_id=current_user.id).order_by(Istek.tarih.desc()).all()
    return jsonify([i.to_dict() for i in istekler]), 200

@api_bp.route('/api/istekler/<int:istek_id>', methods=['DELETE'])
@token_required(next_location='/login')
def istek_sil(current_user, istek_id):
    try:
        istek = Istek.query.get(istek_id)
        if not istek:
            return jsonify({'status': 'error', 'message': 'İstek bulunamadı.'}), 404

        if istek.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Bu isteği silme yetkiniz yok.'}), 403

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
# ─── Moderatör Ekibi ────────────────────────────────────────────────────────

@api_bp.get('/api/moderatorler')
def moderatorleri_listele():
    kisiler = Moderator.query.order_by(Moderator.sira.asc(), Moderator.id.asc()).all()
    return jsonify([k.to_dict() for k in kisiler]), 200

@api_bp.post('/api/admin/moderatorler')
@token_required()
@is_admin
def moderator_ekle(current_user):
    ad = (request.form.get('ad') or '').strip()
    soyad = (request.form.get('soyad') or '').strip()
    email = (request.form.get('email') or '').strip() or None
    unvan = (request.form.get('unvan') or '').strip() or None
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
            if not filename:
                return jsonify({'message': 'Geçersiz dosya adı.'}), 400
            fotograf_adi = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(MODERATOR_UPLOAD_FOLDER, fotograf_adi))

    kisi = Moderator(
        ad=ad,
        soyad=soyad,
        fotograf=fotograf_adi,
        email=email,
        unvan=unvan,
        sira=sira
    )
    try:
        db.session.add(kisi)
        db.session.commit()
        return jsonify({'message': 'Moderatör eklendi.', 'kisi': kisi.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        print(f'Moderatör ekleme hatası: {e}')
        return jsonify({'message': 'Kayıt eklenirken bir hata oluştu.'}), 500

@api_bp.put('/api/admin/moderatorler/<int:id>')
@token_required()
@is_admin
def moderator_guncelle(current_user, id):
    kisi = Moderator.query.get_or_404(id)
    ad = (request.form.get('ad') or kisi.ad or '').strip()
    soyad = (request.form.get('soyad') or kisi.soyad or '').strip()
    if not ad or not soyad:
        return jsonify({'message': 'Ad ve soyad zorunludur.'}), 400

    kisi.ad = ad
    kisi.soyad = soyad
    if 'email' in request.form:
        kisi.email = (request.form.get('email') or '').strip() or None
    if 'unvan' in request.form:
        kisi.unvan = (request.form.get('unvan') or '').strip() or None
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
                eski = os.path.join(MODERATOR_UPLOAD_FOLDER, kisi.fotograf)
                if os.path.exists(eski):
                    try:
                        os.remove(eski)
                    except OSError:
                        pass
            filename = secure_filename(file.filename)
            if not filename:
                return jsonify({'message': 'Geçersiz dosya adı.'}), 400
            fotograf_adi = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(MODERATOR_UPLOAD_FOLDER, fotograf_adi))
            kisi.fotograf = fotograf_adi

    try:
        db.session.commit()
        return jsonify({'message': 'Moderatör güncellendi.', 'kisi': kisi.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        print(f'Moderatör güncelleme hatası: {e}')
        return jsonify({'message': 'Kayıt güncellenirken bir hata oluştu.'}), 500

@api_bp.delete('/api/admin/moderatorler/<int:id>')
@token_required()
@is_admin
def moderator_sil(current_user, id):
    kisi = Moderator.query.get_or_404(id)
    try:
        if kisi.fotograf:
            path = os.path.join(MODERATOR_UPLOAD_FOLDER, kisi.fotograf)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        db.session.delete(kisi)
        db.session.commit()
        return jsonify({'message': 'Moderatör silindi.'}), 200
    except Exception as e:
        db.session.rollback()
        print(f'Moderatör silme hatası: {e}')
        return jsonify({'message': 'Kayıt silinirken bir hata oluştu.'}), 500


# =============================================================================
# 🌟 OGRENCI ELÇISI SISTEMI - API ENDPOINTLERI
# =============================================================================
# Yardımcı fonksiyonlar (auth.py'daki ile aynı, circular import önlemek için tekrar)
def _give_ambassador_points_api(user: User, puan: int):
    user.ambassador_points = (user.ambassador_points or 0) + puan
    seviyeler = [(1, 100), (2, 500), (3, 2000), (4, 5000)]
    for sev, esik in seviyeler:
        if user.ambassador_points >= esik and (user.ambassador_level or 0) < sev:
            user.ambassador_level = sev
            user.is_ambassador = True
            _give_badge_api(user, f"AMBS_{sev}",
                            {1: "🥉 Bronz Elçi", 2: "🥈 Gümüş Elçi", 3: "🥇 Altın Elçi", 4: "💎 Elmas Elçi"}[sev],
                            f"{seviye_adi_str_api(sev)} seviyesine ulaştın!",
                            seviye_renk_str_api(sev),
                            {1: "🥉", 2: "🥈", 3: "🥇", 4: "💎"}[sev])
    db.session.commit()


def seviye_adi_str_api(s): return {1: "Bronz", 2: "Gümüş", 3: "Altın", 4: "Elmas"}.get(s, "Üye")
def seviye_renk_str_api(s): return {1: "#CD7F32", 2: "#C0C0C0", 3: "#FFD700", 4: "#B9F2FF"}.get(s, "#9CA3AF")


def _give_badge_api(user: User, kod: str, ad: str, aciklama: str = "", renk: str = "#FFD700", ikon: str = "🏅"):
    badge = Badge.query.filter_by(kod=kod).first()
    if not badge:
        badge = Badge(kod=kod, ad=ad, aciklama=aciklama, ikon_emoji=ikon, renk=renk)
        db.session.add(badge)
        db.session.flush()
    var_mi = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
    if not var_mi:
        db.session.add(UserBadge(user_id=user.id, badge_id=badge.id))
        db.session.commit()


# ------------ KULLANICI ENDPOINTLERI ------------

@api_bp.get('/api/ambassador/me')
@token_required_api
def api_ambassador_me(current_user):
    """Kullanıcının elçi paneli ve profilim sayfası için TÜM istatistikleri TEK yanıtta döner."""
    # 1) Temel davet sayilari
    toplam_davet = Referral.query.filter_by(davet_eden_id=current_user.id, onaylandi_mi=True).count()
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    yedi_gun_once = datetime.now(ZoneInfo('Europe/Istanbul')).date() - timedelta(days=7)
    haftanin_davet_sayisi = (
        Referral.query
        .filter_by(davet_eden_id=current_user.id, onaylandi_mi=True)
        .filter(func.date(Referral.kaydedilme_tarihi) >= yedi_gun_once)
        .count()
    )

    # 2) Rozetler
    rozetler = db.session.query(Badge, UserBadge).join(UserBadge, UserBadge.badge_id == Badge.id)\
        .filter(UserBadge.user_id == current_user.id)\
        .order_by(Badge.siralama.asc(), UserBadge.kazanma_tarihi.desc()).all()

    # 3) Aktif oduller
    aktif_oduller = EarnedReward.query.filter_by(user_id=current_user.id, aktif_mi=True).all()

    # 4) Seviye hesaplari
    seviye = current_user.ambassador_level or 0
    puan = current_user.ambassador_points or 0
    esikler = [(0, 0, "Üye"), (1, 100, "Bronz Elçi"), (2, 500, "Gümüş Elçi"),
               (3, 2000, "Altın Elçi"), (4, 5000, "Elmas Elçi")]
    # Sonraki esik
    sonraki_esik, sonraki_seviye_adi = 5000, "Tebrikler, en üst seviyedesin!"
    for i, (sv, es, ad) in enumerate(esikler):
        if seviye == sv:
            if i + 1 < len(esikler):
                sonraki_esik = esikler[i + 1][1]
                sonraki_seviye_adi = esikler[i + 1][2]
            break
    if sonraki_esik <= puan:
        sonraki_esik = puan  # Kalansin 0 gosterilsin
    ilerleme_yuzde = min(100, int(puan / sonraki_esik * 100)) if sonraki_esik > 0 else 100
    kalan_puan = max(0, sonraki_esik - puan)
    sev_ikon = {"Üye": "●", "Bronz Elçi": "🥉", "Gümüş Elçi": "🥈", "Altın Elçi": "🥇", "Elmas Elçi": "💎"}[current_user.seviye_adi()]

    # 5) Genel SIRALAMA (kac kisi senden daha cok puan toplamis = siralama)
    sira_query = db.session.query(func.count(User.id)).filter(
        func.coalesce(User.ambassador_points, 0) > puan
    ).scalar()
    siralama = (sira_query or 0) + 1

    # 6) Son davet ettiklerim listesi (detayli)
    davet_listesi = Referral.query.filter_by(davet_eden_id=current_user.id)\
        .order_by(Referral.kaydedilme_tarihi.desc()).limit(20).all()
    davet_ettiklerim = []
    for r in davet_listesi:
        d = User.query.get(r.davet_edilen_id)
        if d:
            davet_ettiklerim.append({
                'name': d.name,
                'email': d.email,
                'created_at': r.kaydedilme_tarihi.isoformat() if r.kaydedilme_tarihi else None,
                'onaylandi': bool(r.onaylandi_mi),
                'puan_verildi': bool(r.puan_verildi_mi),
            })

    # 7) Odul kataloğu (Puan Dukkani - aktif olanlar)
    oduller = ReferralReward.query.filter_by(aktif_mi=True).order_by(ReferralReward.maliyet_puan.asc()).all()

    # 8) User objesi (FE tarafindan d.user.* olarak bekleniyor - tum alanlar)
    #    created_at icin DB henuz migration gecmediyse None dondur (hata yoksay)
    created_at_val = None
    try:
        if hasattr(current_user, 'created_at') and current_user.created_at:
            created_at_val = current_user.created_at.isoformat()
    except Exception:
        created_at_val = None
    user_obj = {
        'id': current_user.id,
        'name': current_user.name,
        'email': current_user.email,
        'kredi': current_user.kredi or 0,
        'created_at': created_at_val,
        'is_ambassador': bool(current_user.is_ambassador),
        'ambassador_level': seviye,
        'ambassador_points': puan,
        'seviye_adi': current_user.seviye_adi(),
        'seviye_ikon': sev_ikon,
        'seviye_renk': current_user.seviye_renk(),
        'streak_gun': current_user.streak_gun or 0,
        'son_giris_tarihi': current_user.son_giris_tarihi.isoformat() if current_user.son_giris_tarihi else None,
        'referral_code': current_user.referral_code or '',
        'referral_count': toplam_davet,
    }

    # 9) Davet linkleri
    base = request.host_url.rstrip('/')
    referral_link = f"{base}/signup?ref={current_user.referral_code or ''}"
    short_link = f"{base}/r/{current_user.referral_code or ''}"

    return jsonify({
        # --- ESKI API UYUMLULUK ICIN (geriye donuk) ---
        'is_ambassador': bool(current_user.is_ambassador),
        'level': seviye,
        'level_name': current_user.seviye_adi(),
        'level_color': current_user.seviye_renk(),
        'points': puan,
        'streak': current_user.streak_gun or 0,
        'next_threshold': sonraki_esik,
        'progress_pct': ilerleme_yuzde,
        'points_to_next': kalan_puan,
        'referral_code': current_user.referral_code or '',
        'referral_link': referral_link,
        'short_link': short_link,
        'total_invites': toplam_davet,
        'weekly_invites': haftanin_davet_sayisi,
        'badges': [
            {'kod': b.kod, 'ad': b.ad, 'aciklama': b.aciklama, 'ikon_emoji': b.ikon_emoji, 'renk': b.renk, 'siralama': b.siralama}
            for b, _ in rozetler
        ],
        'active_rewards': [
            {'kod': er.reward.kod, 'ad': er.reward.ad, 'bitis_tarihi': er.bitis_tarihi.isoformat() if er.bitis_tarihi else None, 'aktif_mi': True}
            for er in aktif_oduller if er.reward
        ],
        'recent_invites': davet_ettiklerim,
        # --- YENI: Frontend (profilim.html / ambassador_panel.html) BEKLENTISI ---
        'user': user_obj,
        'ilerleme_yuzde': ilerleme_yuzde,
        'kalan_puan': kalan_puan,
        'sonraki_seviye': sonraki_seviye_adi,
        'siralama': siralama,
        'hafta_davet': haftanin_davet_sayisi,
        'invites': davet_ettiklerim,
        'rewards': [
            {'id': r.id, 'kod': r.kod, 'ad': r.ad, 'aciklama': r.aciklama,
             'maliyet_puan': r.maliyet_puan, 'aktif_mi': bool(r.aktif_mi)}
            for r in oduller
        ],
    })


@api_bp.get('/api/ambassador/referral-link')
@token_required_api
def api_get_referral_link(current_user):
    """Kullanıcıya özel davet linkini döndür (link yoksa oluştur)."""
    if not current_user.referral_code:
        try:
            current_user.referral_code = User.generate_referral_code(current_user.name)
        except Exception:
            current_user.referral_code = uuid.uuid4().hex[:10].upper()
        db.session.commit()
    base = request.host_url.rstrip('/')
    return jsonify({
        'code': current_user.referral_code,
        'link': f"{base}/signup?ref={current_user.referral_code}",
        'short_link': f"{base}/r/{current_user.referral_code}",
    })


@api_bp.post('/api/ambassador/basvuru')
@token_required_api
def api_ambassador_basvuru(current_user):
    """Kullanıcıdan gelen elçi başvurusunu kaydet."""
    data = request.get_json() or request.form
    bolum = (data.get('bolum') or '').strip()[:150]
    sinif = (data.get('sinif') or '').strip()[:20]
    neden = (data.get('neden') or '').strip()[:1000]
    sosyal = (data.get('sosyal') or '').strip()[:255]

    if not bolum or not neden:
        return jsonify({'message': 'Bölüm ve "Neden elçi olmak istiyorsun?" alanları zorunludur.'}), 400

    # Daha önce başvuru yapmış mı?
    eski = Ambassador.query.filter_by(user_id=current_user.id).first()
    if eski:
        if eski.durum == 'APPROVED':
            return jsonify({'message': 'Zaten onaylanmış bir elçisin!'}), 400
        if eski.durum == 'PENDING':
            return jsonify({'message': 'Başvurunuz zaten inceleniyor, lütfen bekleyin.'}), 400
        # Reddedildiyse tekrar başvurabilir

    yeni = Ambassador(
        user_id=current_user.id,
        bolum=bolum,
        sinif=sinif,
        neden_ambassador=neden,
        sosyal_medya=sosyal,
        durum='PENDING',
        gunluk_hedef=2,
    )
    db.session.add(yeni)
    db.session.commit()
    return jsonify({'message': 'Başvurunuz alındı! İncelendikten sonra size bildirim gönderilecek.'}), 201


@api_bp.get('/api/ambassador/leaderboard')
def api_ambassador_leaderboard():
    """Genel liderlik tablosu (top 50)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    yedi_gun_once = datetime.now(ZoneInfo('Europe/Istanbul')).date() - timedelta(days=7)

    # Önce toplam puan, sonra haftalık davet sayısına göre sırala
    kullanicilar = User.query.filter(User.ambassador_points > 0)\
        .order_by(User.ambassador_points.desc()).limit(50).all()

    sonuc = []
    sira = 0
    for u in kullanicilar:
        sira += 1
        hafta_davet = Referral.query.filter_by(davet_eden_id=u.id, onaylandi_mi=True)\
            .filter(func.date(Referral.kaydedilme_tarihi) >= yedi_gun_once).count()
        toplam_davet = Referral.query.filter_by(davet_eden_id=u.id, onaylandi_mi=True).count()
        sonuc.append({
            'sira': sira,
            'ad_soyad_kisa': ' '.join(u.name.split()[:2]) if u.name else u.email.split('@')[0],
            'level': u.ambassador_level or 0,
            'level_name': u.seviye_adi(),
            'level_color': u.seviye_renk(),
            'points': u.ambassador_points or 0,
            'total_invites': toplam_davet,
            'weekly_invites': hafta_davet,
            'streak': u.streak_gun or 0,
        })
    return jsonify(sonuc)


@api_bp.get('/api/ambassador/haftanin-elcisi')
def api_haftanin_elcisi():
    """Haftanın elçisi + ilk 5 (anasayfa için)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    yedi_gun_once = datetime.now(ZoneInfo('Europe/Istanbul')).date() - timedelta(days=7)

    satirlar = (
        Referral.query
        .with_entities(Referral.davet_eden_id, func.count(Referral.id).label('ds'))
        .filter(func.date(Referral.kaydedilme_tarihi) >= yedi_gun_once)
        .group_by(Referral.davet_eden_id)
        .order_by(func.count(Referral.id).desc())
        .limit(5)
        .all()
    )
    top5 = []
    for s in satirlar:
        u = User.query.get(s.davet_eden_id)
        if u:
            top5.append({
                'ad': u.name.split()[0] if u.name else 'Öğrenci',
                'level_name': u.seviye_adi(),
                'level_color': u.seviye_renk(),
                'haftanin_davet': int(s.ds),
            })
    return jsonify({
        'haftanin_elcisi': top5[0] if top5 else None,
        'top5': top5,
    })


@api_bp.get('/api/ambassador/badges')
@token_required_api
def api_my_badges(current_user):
    satirlar = db.session.query(Badge, UserBadge).join(UserBadge, UserBadge.badge_id == Badge.id)\
        .filter(UserBadge.user_id == current_user.id)\
        .order_by(Badge.siralama.asc(), UserBadge.kazanma_tarihi.desc()).all()
    return jsonify([
        {'kod': b.kod, 'ad': b.ad, 'aciklama': b.aciklama, 'ikon': b.ikon_emoji,
         'renk': b.renk, 'tarih': ub.kazanma_tarihi.strftime("%d.%m.%Y")}
        for b, ub in satirlar
    ])


@api_bp.get('/api/ambassador/rewards')
def api_rewards_katalogu():
    """Puanla alınabilecek sanal ödüllerin listesi (nakitsiz)."""
    # Katalog boşsa varsayılanları doldur (ilk çalıştırmada seed)
    varsayilan = [
        ('PAZAR_1HAFTA', '🛒 Bit Pazarında 1 Hafta Öne Çıkartma',
         'İlanın 7 gün boyunca arama sonuçlarında ilk sırada görünür.', 300),
        ('PROFIL_RENKLI', '🎨 Özel Renkli Profil',
         'Profil kartın özel bir renkte görünür (1 ay).', 500),
        ('OOGRENCI_DUYURU', '📣 Topluluk Duyurusunda 1 Kez Paylaşım Hakkı',
         'Sitenin duyuru akışında 1 kez kendi paylaşımın çıkar (onaylı).', 800),
        ('ANASAYFA_SPOT', '🏆 Ana Sayfada 1 Günlük Ünlü Spot',
         'Adın ve seviyen 24 saat boyunca ana sayfada "Ünlü Öğrenci" olarak görünür.', 1500),
        ('ELMAS_AYRIcalik', '💎 Elmas Ayrıcalığı (3 Ay)',
         'Tüm pazarda %25 indirim (puan kazancında), özel rozet, destek önceliği.', 3000),
    ]
    for kod, ad, aciklama, maliyet in varsayilan:
        if not ReferralReward.query.filter_by(kod=kod).first():
            db.session.add(ReferralReward(kod=kod, ad=ad, aciklama=aciklama, maliyet_puan=maliyet, aktif_mi=True))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    oduller = ReferralReward.query.filter_by(aktif_mi=True).order_by(ReferralReward.maliyet_puan.asc()).all()
    return jsonify([
        {'id': o.id, 'kod': o.kod, 'ad': o.ad, 'aciklama': o.aciklama, 'maliyet_puan': o.maliyet_puan}
        for o in oduller
    ])


@api_bp.post('/api/ambassador/rewards/<int:reward_id>/satinal')
@token_required_api
def api_reward_satinal(current_user, reward_id):
    """Puanla ödül satın al."""
    reward = ReferralReward.query.get_or_404(reward_id)
    if not reward.aktif_mi:
        return jsonify({'message': 'Bu ödül şu anda satın alınamaz.'}), 400

    puan = current_user.ambassador_points or 0
    if puan < reward.maliyet_puan:
        return jsonify({
            'message': f'Yetersiz puan! {reward.maliyet_puan - puan} daha puan gerekli.'
        }), 400

    # Aynı aktif ödülden önceden var mı? (tek seferlikleri engellemek için)
    mevcut = EarnedReward.query.filter_by(user_id=current_user.id, reward_id=reward.id, aktif_mi=True).first()
    if mevcut and reward.kod in ('ANASAYFA_SPOT',):
        return jsonify({'message': 'Bu ödülü henüz kullanmadan tekrar satın alamazsın.'}), 400

    # Puanı düş
    current_user.ambassador_points = puan - reward.maliyet_puan

    # Bitiş tarihi hesapla (çoğu ödül 1 ay geçerli)
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    simdi = datetime.now(ZoneInfo('Europe/Istanbul'))
    bitis = None
    if reward.kod == 'PAZAR_1HAFTA':
        bitis = simdi + timedelta(days=7)
    elif reward.kod == 'ANASAYFA_SPOT':
        bitis = simdi + timedelta(days=1)
    else:
        bitis = simdi + timedelta(days=30)

    kazanilan = EarnedReward(
        user_id=current_user.id,
        reward_id=reward.id,
        satin_alinma_tarihi=simdi,
        bitis_tarihi=bitis,
        aktif_mi=True
    )
    db.session.add(kazanilan)
    db.session.commit()
    return jsonify({
        'message': f'✅ "{reward.ad}" başarıyla satın alındı!',
        'kalan_puan': current_user.ambassador_points,
        'bitis_tarihi': bitis.strftime("%d.%m.%Y")
    }), 201


# ------------ ADMIN ENDPOINTLERI ------------

@api_bp.get('/api/admin/ambassador/basvurular')
@token_required()
@is_admin
def api_admin_ambassador_basvurular(current_user):
    """Admin: Bekleyen/onaylanmış tüm elçi başvuruları."""
    durum = request.args.get('durum', 'PENDING')  # PENDING / APPROVED / ALL
    q = Ambassador.query
    if durum != 'ALL':
        q = q.filter_by(durum=durum)
    liste = q.order_by(Ambassador.basvuru_tarihi.desc()).all()
    sonuc = []
    for b in liste:
        u = User.query.get(b.user_id)
        davet_sayisi = Referral.query.filter_by(davet_eden_id=b.user_id, onaylandi_mi=True).count()
        sonuc.append({
            'id': b.id,
            'durum': b.durum,
            'basvuru_tarihi': b.basvuru_tarihi.strftime("%d.%m.%Y %H:%M"),
            'kullanici': {'ad': u.name if u else '-', 'email': u.email if u else '-',
                          'puan': u.ambassador_points if u else 0, 'level': u.seviye_adi() if u else '-'},
            'bolum': b.bolum,
            'sinif': b.sinif,
            'neden': b.neden_ambassador,
            'sosyal': b.sosyal_medya,
            'gunluk_hedef': b.gunluk_hedef,
            'toplam_davet': davet_sayisi,
        })
    return jsonify(sonuc)


@api_bp.post('/api/admin/ambassador/basvuru/<int:basvuru_id>/onayla')
@token_required()
@is_admin
def api_admin_ambassador_onayla(current_user, basvuru_id):
    """Admin: Elçi başvurusunu onayla + 500 puan bonus + rozet."""
    b = Ambassador.query.get_or_404(basvuru_id)
    u = User.query.get(b.user_id)
    if not u:
        return jsonify({'message': 'Kullanıcı bulunamadı.'}), 404

    b.durum = 'APPROVED'
    b.onaylanma_tarihi = datetime.now(timezone.utc)
    u.is_ambassador = True
    # Onay bonusu
    _give_ambassador_points_api(u, 500)
    _give_badge_api(u, "RESMI_ELCI", "⭐ Resmi Elçi",
                    "Yönetim tarafından onaylanmış resmi öğrenci elçisi!", "#F59E0B", "⭐")

    db.session.commit()
    return jsonify({'message': f'{u.name} onaylandı ve 500 puan + Resmi Elçi rozeti verildi!'}), 200


@api_bp.post('/api/admin/ambassador/basvuru/<int:basvuru_id>/reddiet')
@token_required()
@is_admin
def api_admin_ambassador_reddet(current_user, basvuru_id):
    b = Ambassador.query.get_or_404(basvuru_id)
    data = request.get_json(silent=True) or {}
    b.durum = 'REJECTED'
    # Not: Reddetme sebebi için ayrı alan eklenebilir
    db.session.commit()
    return jsonify({'message': 'Başvuru reddedildi.'}), 200


@api_bp.post('/api/admin/ambassador/kullanici/<int:kullanici_id>/puan-ver')
@token_required()
@is_admin
def api_admin_elci_puan_ver(current_user, kullanici_id):
    """Admin: Elçiye manüel puan ver (kampanya veya ek görev için)."""
    u = User.query.get_or_404(kullanici_id)
    data = request.get_json() or request.form
    try:
        puan = int(data.get('puan') or 0)
    except ValueError:
        return jsonify({'message': 'Geçersiz puan miktarı.'}), 400
    if puan <= 0 or puan > 5000:
        return jsonify({'message': 'Puan 1-5000 arasında olmalıdır.'}), 400

    sebep = (data.get('sebep') or 'Admin puanlaması').strip()[:200]
    _give_ambassador_points_api(u, puan)
    _give_badge_api(u, "OZEL_BASARI", "🏆 Özel Başarı", sebep, "#A855F7", "🏆")
    return jsonify({
        'message': f'{u.name} kullanıcısına {puan} puan verildi. (Sebep: {sebep})',
        'yeni_toplam': u.ambassador_points
    }), 200


# ------------ AKTIVITE PUANI (Not/Değerlendirme/Forum) HOOKLARI ------------
# Mevcut not yükleme / değerlendirme / forum endpointlerine puan kazandırmak için çağrılan ortak fonksiyon
def _aktivite_puan_ver(current_user: User, puan: int, aktivite_turu: str):
    """Günlük maksimum 5 aktivite puan sınırı ile puan ver; kampanya açıkken ekstra kredi ve elçi puanı ver."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        _give_ambassador_points_api(current_user, puan)

        if _is_exam_week_blitz_active():
            kampanya = EXAM_WEEK_BLITZ_REWARDS.get(aktivite_turu, {})
            bonus_puan = int(kampanya.get('ambassador_points', 0))
            bonus_kredi = int(kampanya.get('credit', 0))
            if bonus_puan:
                _give_ambassador_points_api(current_user, bonus_puan)
            if bonus_kredi:
                current_user.kredi = (current_user.kredi or 0) + bonus_kredi

        # Aktivite rozetleri
        if aktivite_turu == 'ders_notu':
            _give_badge_api(current_user, 'NOT_1', '📚 İlk Not', 'İlk ders notunu yükledin!', '#2563EB', '📚')
        if aktivite_turu == 'degerlendirme':
            _give_badge_api(current_user, 'DEGER_1', '⭐ İlk Değerlendirme', 'İlk öğretmen değerlendirmesini yaptın!', '#F97316', '⭐')
        if aktivite_turu == 'forum':
            _give_badge_api(current_user, 'FORUM_1', '💬 Sohbetçi', 'İlk forum mesajını attın!', '#059669', '💬')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[aktivite-puan] hata: {e}")
