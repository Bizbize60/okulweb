from datetime import datetime

from database.initdb import db

class ForumMessage(db.Model):
    __tablename__ = 'forum_messages'

    id = db.Column(db.Integer, primary_key=True)
    konu = db.Column(db.String(200), nullable=False)
    mesaj_icerigi = db.Column(db.Text, nullable=True)
    gonderilme_tarihi = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    begeni_sayisi = db.Column(db.Integer, default=0, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    isim_gorunsun = db.Column(db.Boolean, default=True, nullable=False)
    gif_url = db.Column(db.String(500), nullable=True)
    silindi = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', backref='forum_messages', lazy=True)
    likes = db.relationship(
        'ForumLike',
        backref='message',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    comments = db.relationship(
        'ForumComment',
        backref='message',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )