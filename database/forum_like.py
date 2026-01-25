from database.initdb import db
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from datetime import datetime

class ForumLike(db.Model):
    __tablename__ = 'forum_likes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey('forum_messages.id'), nullable=False)
    like_type = db.Column(db.String(10), nullable=False)  # 'like' veya 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Bir kullanıcı bir mesaja sadece bir kez beğeni/beğenmeme yapabilir
    __table_args__ = (
        UniqueConstraint('user_id', 'message_id', name='unique_user_message_like'),
    )
