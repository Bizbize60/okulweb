# THK Üniversite Portal 🎓

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Modern, açık kaynaklı üniversite portal uygulaması**

[Özellikler](#-özellikler) • [Hızlı Başlangıç](#-hızlı-başlangıç) • [Kurulum](#-kurulum) • [Katkıda Bulunma](#-katkıda-bulunma)

</div>

---

## ✨ Özellikler

- 🔐 **Kimlik Doğrulama** - JWT tabanlı güvenli giriş sistemi
- 📚 **Ders Notları** - Öğrenciler arası not paylaşımı
- ⭐ **Öğretmen Değerlendirme** - Anonim değerlendirme sistemi
- 💬 **Forum** - Tartışma ve soru-cevap platformu
- 🏛️ **Kulüp Yönetimi** - Üniversite kulüpleri için içerik yönetimi
- 🛒 **Bit Pazarı** - İkinci el eşya alım satım platformu
- 🚌 **Otobüs Saatleri** - Canlı otobüs takip sistemi
- 🕐 **Ofis Saatleri** - Öğretim görevlisi müsaitlik takibi

## 🛠️ Teknolojiler

- **Backend:** Flask, SQLAlchemy
- **Database:** PostgreSQL
- **Auth:** JWT (PyJWT)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)

## 🚀 Hızlı Başlangıç

```bash
# 1. Repoyu klonla
git clone https://github.com/Bizbize60/okulweb.git
cd okulweb

# 2. Sanal ortam oluştur ve aktifleştir
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. Config dosyasını oluştur
cp config.py.example config.py
# config.py'ı düzenle (DATABASE_URI ve SECRET_KEY)

# 5. Veritabanı tablolarını oluştur
python -m database.createtables

# 6. Çalıştır!
python backend.py
```

Uygulama `http://localhost:5000` adresinde çalışacaktır. 🎉

## 📦 Detaylı Kurulum

### Gereksinimler

- Python 3.9+
- PostgreSQL 15+
- pip

### Adımlar

1. **Repoyu klonlayın**
   ```bash
   git clone https://github.com/Bizbize60/okulweb.git
   cd okulweb
   ```

2. **Sanal ortam oluşturun**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # veya
   .\venv\Scripts\activate  # Windows
   ```

3. **Bağımlılıkları yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigürasyon dosyasını oluşturun**
   ```bash
   cp config.py.example config.py
   ```
   
   `config.py` dosyasını düzenleyip kendi değerlerinizi girin:
   ```python
   DATABASE_URI = "postgresql://kullanici:sifre@localhost/veritabani"
   SECRET_KEY = "guvenli-rastgele-key"  # python -c "import secrets; print(secrets.token_hex(16))"
   ```

5. **PostgreSQL veritabanını oluşturun**
   ```bash
   # PostgreSQL'de veritabanı oluşturun
   createdb veritabani_adi
   
   # Tabloları oluşturun
   python -m database.createtables
   ```

6. **(Opsiyonel) Örnek veriler ekleyin**
   ```bash
   # Seed şablonlarını kopyalayın
   cp database/seed_kulupler.py.example database/seed_kulupler.py
   cp database/seed_admins.py.example database/seed_admins.py
   
   # Şablonları düzenleyip kendi verilerinizi girin, sonra çalıştırın
   python -m database.seed_kulupler
   python -m database.seed_admins
   ```

7. **Uygulamayı çalıştırın**
   ```bash
   python backend.py
   ```
   
   Uygulama `http://localhost:5000` adresinde çalışacaktır.

## 📁 Proje Yapısı

```
okulweb/
├── backend.py              # Ana Flask uygulaması (rotalar: routes, auth, api)
├── auth.py                 # Giriş/kayıt/doğrulama (templates/auth/* kullanır)
├── routes.py               # Sayfa rotaları (templates/pages|clubs|admin/* kullanır)
├── api.py                  # JSON API uçları
├── config.py.example       # Örnek konfigürasyon (şablonu kopyalayın)
├── requirements.txt        # Python bağımlılıkları
├── database/               # SQLAlchemy modelleri + kurulum scriptleri
│   ├── initdb.py           # Veritabanı başlatma
│   ├── createtables.py     # Tablo oluşturma scripti
│   ├── user.py             # Kullanıcı modeli
│   ├── ...                 # Diğer modeller (forum, kulüp, pazar, ders notu...)
│   └── seed_*.example      # Örnek seed şablonları
├── templates/              # HTML şablonları (gruplu)
│   ├── auth/               # login, register, verify
│   ├── pages/              # İçerik sayfaları (anasayfa, forum, pazar...)
│   ├── clubs/              # Kulüp sayfaları (fsource, utaamc...)
│   └── admin/              # Yönetim panelleri
├── static/
│   ├── css/
│   │   ├── tokens.css      # THK tasarım jetonları (renk/font - tek kaynak)
│   │   ├── ui.css          # Genel arayüz (tokens.css'i içe aktarır)
│   │   └── pages/
│   │       └── auth.css    # Giriş/kayıt/doğrulama ortak stili
│   ├── js/
│   │   └── components.js   # Navbar/footer + ortak istemci davranışları
│   ├── img/                # Site görselleri (logo, kulüp, kroki...)
│   └── sw.js               # Bildirim service worker (kökten sunulur)
└── uploads/                # Kullanıcı yüklemeleri
    ├── kulup/              # Kulüp görselleri
    ├── notes/              # Ders notları
    └── pazar/              # Pazar ilanları
```

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! 

### Nasıl Katkıda Bulunabilirim?

1. **Projeyi fork edin**
   ```bash
   # GitHub'da "Fork" butonuna tıklayın
   git clone https://github.com/KULLANICI_ADINIZ/okulweb.git
   cd okulweb
   ```

2. **Feature branch oluşturun**
   ```bash
   git checkout -b feature/yeni-ozellik
   ```

3. **Değişikliklerinizi yapın ve test edin**
   ```bash
   # Kodunuzu yazın
   # Test edin: python backend.py
   ```

4. **Commit edin**
   ```bash
   git add .
   git commit -m "feat: Yeni özellik açıklaması"
   ```

5. **Push edin ve PR açın**
   ```bash
   git push origin feature/yeni-ozellik
   # GitHub'da Pull Request açın
   ```

### Yeni Veritabanı Modeli Ekleme

Yeni bir veritabanı tablosu eklemek için `database/example_model.py` dosyasını şablon olarak kullanın:

```bash
# 1. Örnek modeli kopyalayın
cp database/example_model.py database/yeni_model.py

# 2. Modeli düzenleyin (sınıf adı, alanlar vs.)

# 3. backend.py'da import edin
# from database.yeni_model import YeniModel

# 4. Tabloyu oluşturun
python -m database.createtables
```

### Geliştirme İpuçları

- 🔧 `DEBUG = True` ile çalıştırın (config.py)
- 📝 Yeni route eklerken docstring yazın
- 🧪 Değişiklikleri test ettikten sonra commit edin
- 🌿 Her özellik için ayrı branch kullanın

### İhtiyaç Duyulan Özellikler

Katkıda bulunmak isteyenler için fikirler:
- [ ] Duyuru sistemi
- [ ] Etkinlik takvimi
- [ ] Mobil uygulama (Flutter/React Native)
- [ ] Email bildirimleri
- [ ] Karanlık/Aydınlık tema geçişi
- [ ] Çoklu dil desteği (i18n)

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 👥 Geliştiriciler

- **Tunahan Turgut** - *Ana Geliştirici* - [@Bizbize60](https://github.com/Bizbize60)

## 🙏 Teşekkürler

- THK Üniversitesi öğrencilerine
- Açık kaynak topluluğuna
- Katkıda bulunan herkese

---

<div align="center">
  
**⭐ Projeyi beğendiyseniz yıldız vermeyi unutmayın!**

THK Üniversitesi için ❤️ ile yapıldı

</div>