import unittest

import config

config.DATABASE_URI = 'sqlite:///:memory:'

from backend import app  # noqa: E402
from database.initdb import db
from database.user import User, Referral
from database.forum_message import ForumMessage
from database.istek import Istek
from user_purge import purge_user_account


class UserPurgeTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.other = User(public_id='other', name='Diger', email='other@localhost', password='pw', kredi=1)
            self.victim = User(public_id='victim', name='Hedef', email='victim@localhost', password='pw', kredi=1)
            db.session.add_all([self.other, self.victim])
            db.session.commit()
            self.other_id = self.other.id
            self.victim_id = self.victim.id
            db.session.add(ForumMessage(konu='konu', mesaj_icerigi='icerik', user_id=self.victim_id))
            db.session.add(Istek(baslik='anket', aciklama='yazi', kategori='Genel', user_id=self.victim_id))
            db.session.add(Referral(
                davet_eden_id=self.other_id,
                davet_edilen_id=self.victim_id,
                referral_code='TEST1',
            ))
            db.session.commit()

    def test_purge_removes_user_and_related_rows(self):
        with self.app.app_context():
            victim = User.query.get(self.victim_id)
            purge_user_account(victim)
            db.session.commit()
            self.assertIsNone(User.query.get(self.victim_id))
            self.assertIsNotNone(User.query.get(self.other_id))
            self.assertEqual(ForumMessage.query.filter_by(user_id=self.victim_id).count(), 0)
            self.assertEqual(Istek.query.filter_by(user_id=self.victim_id).count(), 0)
            self.assertEqual(Referral.query.filter_by(davet_edilen_id=self.victim_id).count(), 0)


if __name__ == '__main__':
    unittest.main()
