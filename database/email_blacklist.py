from datetime import datetime

from database.initdb import db


class EmailBlacklist(db.Model):
    """Silinen hesapların e-postaları. Yeni kayıt bu listeye bakılır."""

    __tablename__ = 'email_blacklist'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
