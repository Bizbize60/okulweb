from .initdb import db

class KulupYonetim(db.Model):
    __tablename__ = 'kulup_yonetim'
    
    id = db.Column(db.Integer, primary_key=True)
    yetki = db.Column(db.String(50), nullable=False)  # admin, editor etc.
    kullanici_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    kulup_id = db.Column(db.Integer, db.ForeignKey('kulupler.id'), nullable=False)
    