from datetime import datetime, timezone

from database.initdb import db


class UserCreditChangeLog(db.Model):
    __tablename__ = 'user_credit_change_logs'

    id = db.Column(db.Integer, primary_key=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    old_kredi = db.Column(db.Integer, nullable=False)
    new_kredi = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    target_user = db.relationship('User', foreign_keys=[target_user_id], lazy='joined')
    actor_user = db.relationship('User', foreign_keys=[actor_user_id], lazy='joined')
