import jwt
from flask import Blueprint, render_template, request, current_app
from auth import token_required, is_club_admin, is_admin

# 'pages' adında bir Blueprint oluşturuyoruz
pages = Blueprint('pages', __name__)

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
    token = request.cookies.get('jwt_token')

    if token:
        try:
            jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            is_logged_in = True
            show_contributors = True
        except Exception:
            is_logged_in = False
            show_contributors = False

    return render_template('anasayfa.html', is_logged_in=is_logged_in, show_contributors=show_contributors)

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
@token_required(next_location='/login')
def yemekhane_sayfa(current_user):
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