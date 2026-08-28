import jwt
from flask import Blueprint, render_template, request, current_app
from auth import token_required, is_club_admin, is_admin
from database.user import User, Referral
from sqlalchemy import func
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 'pages' adında bir Blueprint oluşturuyoruz
pages = Blueprint('pages', __name__)


def _haftanin_elcisi_ve_liderler():
    """Son 7 günde en çok davet yapan + puan alan ilk 5 kişi + haftanın elçisi."""
    try:
        bir_hafta_once = datetime.now(ZoneInfo('Europe/Istanbul')).date() - timedelta(days=7)
        # Son 7 günün davet sayılarına göre sırala
        satirlar = (
            Referral.query
            .with_entities(
                Referral.davet_eden_id,
                func.count(Referral.id).label('davet_sayisi')
            )
            .filter(func.date(Referral.kaydedilme_tarihi) >= bir_hafta_once)
            .group_by(Referral.davet_eden_id)
            .order_by(func.count(Referral.id).desc())
            .limit(10)
            .all()
        )
        liderler = []
        for satir in satirlar:
            u = User.query.get(satir.davet_eden_id)
            if u:
                liderler.append({
                    'id': u.id,
                    'ad': u.name.split()[0] if u.name else u.email,
                    'seviye': u.ambassador_level or 0,
                    'seviye_adi': u.seviye_adi(),
                    'seviye_renk': u.seviye_renk(),
                    'puan': u.ambassador_points or 0,
                    'haftanin_davet_sayisi': int(satir.davet_sayisi),
                })
        # Ana sayfa için ilk 5 + 1.'si haftanın elçisi
        top5 = liderler[:5]
        haftanin_elcisi = liderler[0] if liderler else None
        return top5, haftanin_elcisi
    except Exception:
        return [], None


# Admin sayfaları
@pages.route('/admin')
@token_required(next_location='/login')
@is_admin
def admin_page(current_user):
    return render_template('admin.html')

# Genel sayfalar
@pages.route('/')
def main_page():
    is_logged_in = False
    show_contributors = False
    current_user_obj = None
    token = request.cookies.get('jwt_token')

    if token:
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            public_id = data.get('public_id')
            current_user_obj = User.query.filter_by(public_id=public_id).first()
            is_logged_in = True
            show_contributors = True
        except Exception:
            is_logged_in = False
            show_contributors = False

    top_5_ambassador, haftanin_elcisi = _haftanin_elcisi_ve_liderler()

    return render_template(
        'anasayfa.html',
        is_logged_in=is_logged_in,
        show_contributors=show_contributors,
        current_user=current_user_obj,
        top_5_ambassador=top_5_ambassador,
        haftanin_elcisi=haftanin_elcisi,
    )

@pages.route('/ders-notlari')
@token_required(next_location='/login')
def ders_notlari_page(current_user):
    return render_template('ders-notlari.html')

@pages.route('/not-ekle')
@token_required(next_location='/not-ekle')
def not_ekle_sayfa(current_user):
    return render_template('not-ekle.html')

@pages.route('/haberler')
def haberler_page():
    return render_template('haberler.html')

@pages.route('/duyurular')
def duyurular_page():
    return render_template('duyurular.html')

@pages.route('/ofis-saatleri')
@token_required(next_location='/login')
def ofis_saatleri_page(current_user):
    return render_template('ofis-saatleri.html')

@pages.route('/kroki')
def kroki_page():
    return render_template('kroki.html')

@pages.route('/kayiplar')
@token_required(next_location='/login')
def kayiplar_page(current_user):
    return render_template('kayiplar.html')

@pages.route('/KampusteHayat')
@token_required(next_location='/login')
def enstantaneler_sayfa(current_user):
    return render_template('enstantaneler.html')

@pages.route('/yemekhane')
def yemekhane_sayfa():
    return render_template('yemekhane.html')

@pages.route('/otobus-saatleri')
def otobus_saatleri_sayfa():
    return render_template('otobus-saatleri.html')

@pages.route('/forum')
@token_required(next_location='/login')
def forum_sayfa(current_user):
    return render_template('forum.html')

@pages.route('/ogretmen-degerlendirme')
@token_required(next_location='/ogretmen-degerlendirme')
def ogretmen_degerlendirme_sayfa(current_user):
    return render_template('ogretmen-degerlendirme.html')

@pages.route('/ogretmen-listesi')
@token_required(next_location='/login')
def ogretmen_listesi_sayfa(current_user):
    return render_template('ogretmen-listesi.html')

@pages.route('/ilan-ekle')
@token_required(next_location='/ilan-ekle')
def ilan_ekle_sayfa(current_user):
    return render_template('ilan-ekle.html')

@pages.route('/bit-pazari')
@token_required(next_location='/login')
def bit_pazari_sayfa(current_user):
    return render_template('pazar.html')

# Kulüp Sayfaları
@pages.route('/Kulup-Yonetimi')
@token_required(next_location='/Kulup-Yonetimi')
@is_club_admin
def kulup_yonetimi_sayfa(current_user):
    return render_template('kulup-yonetimi.html')

@pages.route('/kulupler/kanatlibulten')
def kanatli_bulten_sayfa():
    return render_template('kanatlibulten.html')
    
@pages.route('/kulupler/utaa-music-club')
def utaa_music_club_page():
    return render_template('utaamc.html')

@pages.route('/kulupler/fsource')
def fsource_page():
    return render_template('fsource.html')

@pages.route('/kulupler/makine-muhendisligi')
def makine_muh_page():
    return render_template('makinemuh.html')

@pages.route('/kulupler/turk-tarih-toplulugu')
def turk_tarih_page():
    return render_template('turktarih.html')


@pages.route('/istekler')
@token_required(next_location='/login')
def istekler_page(current_user):
    return render_template('istekler.html')

@pages.route('/katkida-bulunanlar')
@token_required(next_location='/katkida-bulunanlar')
def katkida_bulunanlar_page(current_user):
    return render_template('katkida-bulunanlar.html')

@pages.route('/moderatorler')
def moderatorler_page():
    return render_template('moderatorler.html')


# ============================================================================
# OGRENCI ELÇISI SİSTEMİ SAYFALARI
# ============================================================================

@pages.route('/profilim')
@token_required(next_location='/login')
def profilim_sayfa(current_user):
    """Kullanıcının kendi profili (rozetler, puan, seviye, davet linki)."""
    return render_template('profilim.html', user=current_user)


@pages.route('/ogrenci-elcisi')
def ogrenci_elcisi_tanitimi():
    """Elçi programının ne olduğunu anlatan tanıtım + başvuru formu."""
    is_logged_in = False
    token = request.cookies.get('jwt_token')
    if token:
        try:
            jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            is_logged_in = True
        except Exception:
            is_logged_in = False
    return render_template('ogrenci-elcisi.html', is_logged_in=is_logged_in)


@pages.route('/elci-paneli')
@token_required(next_location='/login')
def elci_paneli_sayfa(current_user):
    """Kullanıcının elçi paneli (istatistik, davet linki, ödül dükkanı)."""
    return render_template('ambassador_panel.html', user=current_user)


@pages.route('/liderlik-tablosu')
def elci_liderlik_tablosu():
    """Tüm öğrencilerin görebildiği Elçiler Liderlik Tablosu."""
    return render_template('liderlik-tablosu.html')