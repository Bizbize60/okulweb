from datetime import datetime

from database.initdb import db


class ForumComment(db.Model):
    __tablename__ = 'forum_comments'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('forum_messages.id'), nullable=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('forum_comments.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    yorum_icerigi = db.Column(db.Text, nullable=False)
    isim_gorunsun = db.Column(db.Boolean, default=True, nullable=False)
    gonderilme_tarihi = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    silindi = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', backref='forum_comments', lazy=True)
    parent = db.relationship(
        'ForumComment',
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic', cascade='all, delete-orphan')
    )
