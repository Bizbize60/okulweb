from database.initdb import db
from datetime import datetime

class Enstantane(db.Model):
    __tablename__ = 'enstantaneler'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    foto = db.Column(db.String(256), nullable=False)
    aciklama = db.Column(db.String(256), nullable=True)
    tarih = db.Column(db.DateTime, default=datetime.utcnow)
    begeni_sayisi = db.Column(db.Integer, default=0)
    
    # İlişkiler
    user = db.relationship('User', backref='enstantaneler', lazy=True)
    begeniler = db.relationship('EnstantaneLike', backref='enstantane', lazy='dynamic')

    def to_dict(self, current_user_id=None):
        liked_by_user = False
        if current_user_id:
            liked_by_user = self.begeniler.filter_by(user_id=current_user_id).first() is not None

        return {
            'id': self.id,
            'user_name': self.user.name,
            'foto': self.foto,
            'aciklama': self.aciklama,
            'begeni_sayisi': self.begeni_sayisi,
            'liked_by_user': liked_by_user,
            'tarih': self.tarih.strftime('%d.%m.%Y')
        }

class EnstantaneLike(db.Model):
    __tablename__ = 'enstantane_likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enstantane_id = db.Column(db.Integer, db.ForeignKey('enstantaneler.id'), nullable=False)