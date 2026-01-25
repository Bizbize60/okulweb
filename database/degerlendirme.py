from database.initdb import db
from datetime import datetime

class OgretmenDegerlendirme(db.Model):
    __tablename__ = 'ogretmen_degerlendirmeleri'
    
    id = db.Column(db.Integer, primary_key=True)
    ogretmen_adi = db.Column(db.String(100), nullable=False)
    ogretmen_soyadi = db.Column(db.String(100), nullable=False)
    ders_anlatma_notu = db.Column(db.Integer, nullable=False)  # 1-5 arası
    sinav_zorlugu_notu = db.Column(db.Integer, nullable=False)  # 1-5 arası
    
    # Etiketler
    slayttan_isler = db.Column(db.Boolean, default=False)
    yoklama_alir = db.Column(db.Boolean, default=False)
    kitap_onemli = db.Column(db.Boolean, default=False)
    kanaat_notu = db.Column(db.Boolean, default=False)
    projeye_onem = db.Column(db.Boolean, default=False)
    
    # Alınan harf notu
    alinan_harf_notu = db.Column(db.String(2), nullable=True)  # AA, BA, BB, CB, CC, DC, DD, FD, FF
    
    degerlendirme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def __repr__(self):
        return f'<Degerlendirme {self.ogretmen_adi} {self.ogretmen_soyadi}>'
