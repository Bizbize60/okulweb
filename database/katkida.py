from datetime import datetime, timezone
from database.initdb import db


class KatkidaBulunan(db.Model):
    __tablename__ = 'katkida_bulunanlar'

    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    soyad = db.Column(db.String(100), nullable=False)
    fotograf = db.Column(db.String(255), nullable=True)
    github_url = db.Column(db.String(255), nullable=True)
    aciklama = db.Column(db.String(255), nullable=True)
    sira = db.Column(db.Integer, default=0)
    olusturulma_tarihi = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            'id': self.id,
            'ad': self.ad,
            'soyad': self.soyad,
            'fotograf_url': f"/uploads/katkida/{self.fotograf}" if self.fotograf else None,
            'github_url': self.github_url,
            'aciklama': self.aciklama,
            'sira': self.sira or 0,
            'olusturulma_tarihi': self.olusturulma_tarihi.strftime('%d.%m.%Y') if self.olusturulma_tarihi else None
        }
