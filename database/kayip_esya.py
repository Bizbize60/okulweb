from database.initdb import db

class KayipEsya(db.Model):
    __tablename__ = 'kayip_esya'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Tasarıma uygun yeni alanlar
    baslik = db.Column(db.String(128), nullable=False)
    aciklama = db.Column(db.Text, nullable=True)
    tip = db.Column(db.String(16), nullable=False)  # 'kayip' veya 'bulunan'
    kategori = db.Column(db.String(64), default='Diğer') # Elektronik, Kıyafet vb.
    konum = db.Column(db.String(128), nullable=True) # Bulunduğu/Kaybolduğu yer
    foto = db.Column(db.String(256), nullable=True)
    tarih = db.Column(db.DateTime, default=db.func.now())
    
    # User ilişkisi (Backend'de joinedload kullanacağız)
    user = db.relationship('User', backref='kayip_ilanlari', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'baslik': self.baslik,
            'aciklama': self.aciklama,
            'tip': self.tip,
            'kategori': self.kategori,
            'konum': self.konum,
            'foto': self.foto if self.foto else 'https://via.placeholder.com/400x300?text=Resim+Yok', # Varsayılan resim
            'tarih': self.tarih.isoformat() if self.tarih else None,
            'tarih_str': self.tarih.strftime('%d.%m.%Y') if self.tarih else '',
            'user_name': self.user.name if self.user else 'Anonim'
        }