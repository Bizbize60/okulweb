from database.initdb import db
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
class Kulupicerik(db.Model):
    __tablename__ = 'kulup_icerik'
    id = db.Column(db.Integer, primary_key=True)
    dosya_adi = db.Column(db.String(255))  
    dosya_yolu = db.Column(db.String(500))  
    dosya_tipi = db.Column(db.String(10))   
    yuklenme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    aciklama = db.Column(db.String(500))
    kulup_id = db.Column(db.Integer, db.ForeignKey('kulup_yonetim.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))