from database.initdb import db

class Kulupler(db.Model):

    __tablename__ = 'kulupler'

    id = db.Column(db.Integer, primary_key=True)
    kulup_adi = db.Column(db.String(100), nullable=False, unique=True)