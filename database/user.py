from database.initdb import Base, db
from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import uuid

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(70), unique=True)
    password = db.Column(db.String(255))
    kredi = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)

    # ---- Ogrenci Elcisi Sistemi ----
    is_ambassador = db.Column(db.Boolean, default=False)
    ambassador_level = db.Column(db.Integer, default=0)  # 0=Degil, 1=Bronz, 2=Gumus, 3=Altin, 4=Elmas
    ambassador_points = db.Column(db.Integer, default=0)  # Elçi puanı (davet + aktivite)
    referral_code = db.Column(db.String(20), unique=True, index=True)  # Kişisel davet kodu (örn: TUNAHAN5)
    streak_gun = db.Column(db.Integer, default=0)  # Üst üste giriş gün sayısı
    son_giris_tarihi = db.Column(db.Date, nullable=True)

    # İlişkiler
    davet_ettikleri = relationship("Referral", foreign_keys="Referral.davet_eden_id", back_populates="davet_eden", lazy=True)
    kazandigi_oduller = relationship("EarnedReward", back_populates="user", lazy=True)
    rozetleri = relationship("UserBadge", back_populates="user", lazy=True)

    @staticmethod
    def generate_referral_code(name: str) -> str:
        """Kişisel davet kodu üret (isim + rastgele)."""
        temiz = ''.join(c for c in name.upper() if c.isalpha())[:8]
        if not temiz:
            temiz = uuid.uuid4().hex[:6].upper()
        # Benzersiz olana kadar rastgele ekle
        import secrets
        while True:
            suf = secrets.token_hex(2).upper()
            kod = f"{temiz}{suf}"
            if not User.query.filter_by(referral_code=kod).first():
                return kod[:12]

    def seviye_adi(self) -> str:
        return {0: "Üye", 1: "Bronz Elçi", 2: "Gümüş Elçi", 3: "Altın Elçi", 4: "Elmas Elçi"}.get(self.ambassador_level, "Üye")

    def seviye_renk(self) -> str:
        return {0: "#9CA3AF", 1: "#CD7F32", 2: "#C0C0C0", 3: "#FFD700", 4: "#B9F2FF"}.get(self.ambassador_level, "#9CA3AF")


class Ambassador(db.Model):
    """Elçi başvuru ve onay kayıtları"""
    __tablename__ = 'ambassadors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    bolum = db.Column(db.String(150), nullable=True)
    sinif = db.Column(db.String(20), nullable=True)
    neden_ambassador = db.Column(db.Text, nullable=True)
    sosyal_medya = db.Column(db.String(255), nullable=True)
    durum = db.Column(db.String(20), default='PENDING')  # PENDING / APPROVED / REJECTED
    basvuru_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    onaylanma_tarihi = db.Column(db.DateTime, nullable=True)
    gunluk_hedef = db.Column(db.Integer, default=2)  # Günlük davet hedefi

    user = relationship("User", foreign_keys=[user_id])


class Referral(db.Model):
    """Her bir davet kaydı (A kişisi B kişisini davet etti)"""
    __tablename__ = 'referrals'
    id = db.Column(db.Integer, primary_key=True)
    davet_eden_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    davet_edilen_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False, unique=True)
    referral_code = db.Column(db.String(20), index=True)
    kaydedilme_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    onaylandi_mi = db.Column(db.Boolean, default=True)  # Kayıt olunca otomatik onay
    puan_verildi_mi = db.Column(db.Boolean, default=False)

    davet_eden = relationship("User", foreign_keys=[davet_eden_id], back_populates="davet_ettikleri")
    davet_edilen = relationship("User", foreign_keys=[davet_edilen_id])


class Badge(db.Model):
    """Kazanılabilir rozetler (Elçi, Başarılı Davetçi vb.)"""
    __tablename__ = 'badges'
    id = db.Column(db.Integer, primary_key=True)
    kod = db.Column(db.String(50), unique=True, nullable=False)  # AMBASSADOR_BRONZ, INVITER_10
    ad = db.Column(db.String(100), nullable=False)
    aciklama = db.Column(db.String(255), nullable=True)
    ikon_emoji = db.Column(db.String(10), default="🏅")
    renk = db.Column(db.String(20), default="#FFD700")
    siralama = db.Column(db.Integer, default=0)  # UI'da gösterim sırası


class UserBadge(db.Model):
    """Kullanıcının kazandığı rozetler"""
    __tablename__ = 'user_badges'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    badge_id = db.Column(db.Integer, ForeignKey('badges.id'), nullable=False)
    kazanma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="rozetleri")
    badge = relationship("Badge")


class ReferralReward(db.Model):
    """Elçi puanlarıyla açılabilen ödül/avantajlar (sanal, nakitsiz)"""
    __tablename__ = 'referral_rewards'
    id = db.Column(db.Integer, primary_key=True)
    kod = db.Column(db.String(50), unique=True, nullable=False)  # PAZAR_ONE_CIKARMA, PROFIL_RENKLI, ONSAYFA_CIKIS
    ad = db.Column(db.String(150), nullable=False)
    aciklama = db.Column(db.String(255), nullable=True)
    maliyet_puan = db.Column(db.Integer, nullable=False)  # Kaç puanla açılıyor
    aktif_mi = db.Column(db.Boolean, default=True)


class EarnedReward(db.Model):
    """Kullanıcının satın aldığı sanal ödüller"""
    __tablename__ = 'earned_rewards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False)
    reward_id = db.Column(db.Integer, ForeignKey('referral_rewards.id'), nullable=False)
    satin_alinma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    bitis_tarihi = db.Column(db.DateTime, nullable=True)  # Örn: 1 haftalık öne çıkarma
    aktif_mi = db.Column(db.Boolean, default=True)

    user = relationship("User", back_populates="kazandigi_oduller")
    reward = relationship("ReferralReward")