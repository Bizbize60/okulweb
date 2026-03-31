from database.initdb import db
from datetime import datetime

class WebPushSubscription(db.Model):
    __tablename__ = 'webpush_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    subscription_info = db.Column(db.Text, nullable=False)  # Tarayıcıdan gelen JSON verisini string olarak tutar
    kullanici_ajani = db.Column(db.String(255))             # İsteğe bağlı: Chrome, Safari vb. tarayıcı bilgisini tutmak istersen
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id')) # Bildirimin kime ait olduğunu bilmek için
