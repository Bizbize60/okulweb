from datetime import datetime
from database.initdb import db

class Istek(db.Model):
    __tablename__ = 'istekler'

    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(150), nullable=False)
    aciklama = db.Column(db.Text, nullable=False)
    kategori = db.Column(db.String(50), default='Genel')
    durum = db.Column(db.String(20), default='Gönderildi')
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'baslik': self.baslik,
            'aciklama': self.aciklama,
            'kategori': self.kategori,
            'durum': self.durum,
            'tarih': self.tarih.strftime('%d.%m.%Y %H:%M'),
            'user_id': self.user_id
        }