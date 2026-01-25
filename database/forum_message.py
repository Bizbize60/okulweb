from database.initdb import db
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class ForumMessage(db.Model):
    __tablename__ = 'forum_messages'
    id = db.Column(db.Integer, primary_key=True)
    konu = db.Column(db.String(200))
    mesaj_icerigi = db.Column(db.String(2000))
    gonderilme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    begeni_sayisi = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))