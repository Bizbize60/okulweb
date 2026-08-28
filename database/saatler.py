from database.initdb import Base, db
from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class Saatler(db.Model):
    """Ana tablo - websitede gösterilen onaylanmış veriler"""
    __tablename__ = 'ofis_saatleri'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    days: Mapped[dict] = mapped_column(JSON, nullable=False)

class SaatlerPending(db.Model):
    """Onay bekleyen veriler - otomatik gelen veriler buraya düşer"""
    __tablename__ = 'ofis_saatleri_pending'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    days: Mapped[dict] = mapped_column(JSON, nullable=False)