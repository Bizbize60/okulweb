from database.initdb import db
from datetime import datetime



class PazarIlani(db.Model):
    __tablename__ = 'pazar_ilanlari'
    
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(100), nullable=False)
    aciklama = db.Column(db.Text, nullable=True)
    kategori = db.Column(db.String(50), nullable=False)
    fiyat = db.Column(db.Integer, nullable=False)
    fotograf_adi = db.Column(db.String(255), nullable=False)
    iletisim_no = db.Column(db.String(20), nullable=False)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)