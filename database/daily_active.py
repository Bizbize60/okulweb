from database.initdb import db
from datetime import datetime, date


class DailyActiveUser(db.Model):
    """Giriş yapmış kullanıcının takvim günü (TR) aktifliği — unique(user_id, activity_date)."""
    __tablename__ = 'daily_active_users'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'activity_date', name='uq_daily_active_user_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    activity_date = db.Column(db.Date, nullable=False, index=True)
    first_seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<DailyActiveUser user={self.user_id} date={self.activity_date}>'
