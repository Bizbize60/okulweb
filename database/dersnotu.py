from database.initdb import db
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
class DersNotu(db.Model):
    __tablename__ = 'ders_notlari'
    id = db.Column(db.Integer, primary_key=True)
    ders_adi = db.Column(db.String(200))
    dosya_adi = db.Column(db.String(255))  # "algoritma.pdf"
    dosya_yolu = db.Column(db.String(500))  # "uploads/notes/123_algoritma.pdf"
    dosya_tipi = db.Column(db.String(10))   # "pdf" veya "docx"
    yuklenme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))