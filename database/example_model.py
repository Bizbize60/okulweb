"""
=============================================================================
THK Üniversite Portal - Örnek Model Dosyası
=============================================================================
Bu dosya, yeni bir veritabanı tablosu nasıl oluşturulacağını gösteren
örnek bir şablon dosyasıdır.

Yeni bir tablo eklemek için:
1. Bu dosyayı kopyalayın ve yeni_model.py olarak adlandırın
2. Model sınıfını ve alanlarını düzenleyin
3. backend.py'da import edin
4. python -m database.createtables komutu ile tabloyu oluşturun
=============================================================================
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

# NOT: db nesnesi backend.py'dan import edilir
# Bu dosya sadece örnek şablon olduğu için burada gösterilmiştir
db = SQLAlchemy()


class OrnekModel(db.Model):
    """
    Örnek bir veritabanı modeli.
    
    Tablo Adı: ornek_model (SQLAlchemy otomatik olarak sınıf adından üretir)
    Özel tablo adı için: __tablename__ = 'ozel_tablo_adi'
    """
    
    # Primary Key - Her tabloda olmalı
    id = db.Column(db.Integer, primary_key=True)
    
    # String alanı (nullable=False -> zorunlu alan)
    baslik = db.Column(db.String(255), nullable=False)
    
    # Text alanı (uzun metinler için)
    aciklama = db.Column(db.Text, nullable=True)
    
    # Integer alanı
    sayi = db.Column(db.Integer, default=0)
    
    # Boolean alanı
    aktif = db.Column(db.Boolean, default=True)
    
    # DateTime alanı (otomatik tarih)
    olusturulma_tarihi = db.Column(
        db.DateTime, 
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Foreign Key örneği (başka bir tabloya referans)
    # user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationship örneği
    # user = db.relationship('User', backref=db.backref('ornekler', lazy=True))

    def __repr__(self):
        """Model'in string gösterimi (debugging için)"""
        return f'<OrnekModel {self.id}: {self.baslik}>'
    
    def to_dict(self):
        """Model'i JSON-serializable dict'e çevir (API response için)"""
        return {
            'id': self.id,
            'baslik': self.baslik,
            'aciklama': self.aciklama,
            'sayi': self.sayi,
            'aktif': self.aktif,
            'olusturulma_tarihi': self.olusturulma_tarihi.isoformat() if self.olusturulma_tarihi else None
        }


# =============================================================================
# Kullanım Örnekleri (backend.py içinde)
# =============================================================================
"""
# 1. Yeni kayıt ekleme
yeni_kayit = OrnekModel(
    baslik="Test Başlık",
    aciklama="Test açıklama metni",
    sayi=42
)
db.session.add(yeni_kayit)
db.session.commit()

# 2. Kayıt sorgulama
tum_kayitlar = OrnekModel.query.all()
aktif_kayitlar = OrnekModel.query.filter_by(aktif=True).all()
tek_kayit = OrnekModel.query.get(1)  # ID ile

# 3. Kayıt güncelleme
kayit = OrnekModel.query.get(1)
kayit.baslik = "Yeni Başlık"
db.session.commit()

# 4. Kayıt silme
kayit = OrnekModel.query.get(1)
db.session.delete(kayit)
db.session.commit()

# 5. API endpoint örneği
@app.get('/api/ornekler')
def api_ornekler():
    ornekler = OrnekModel.query.all()
    return jsonify([o.to_dict() for o in ornekler])
"""
