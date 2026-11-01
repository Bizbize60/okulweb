import unittest
from datetime import datetime, timedelta, timezone

import jwt

import config

config.DATABASE_URI = 'sqlite:///:memory:'

from backend import app  # noqa: E402
from database.initdb import db
from database.user import User
from database.istek import Istek
from giris_anketi import (
    GIRIS_ANKETI_KATEGORI,
    count_comment_characters,
    user_completed_giris_anketi,
)


class GirisAnketiTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.user = User(
                public_id='anket-user-1',
                name='Test Kullanici',
                email='anket@localhost',
                password='pw',
                kredi=1,
            )
            db.session.add(self.user)
            db.session.commit()
            self.user_id = self.user.id

        self.client = self.app.test_client()

    def _auth_cookie(self):
        with self.app.app_context():
            user = User.query.get(self.user_id)
            token = jwt.encode(
                {'public_id': user.public_id, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)},
                self.app.config['SECRET_KEY'],
                algorithm='HS256',
            )
            self.client.set_cookie(key='jwt_token', value=token)

    def test_count_comment_characters_requires_ten(self):
        self.assertEqual(count_comment_characters(''), 0)
        self.assertEqual(count_comment_characters('123456789'), 9)
        self.assertEqual(count_comment_characters('1234567890'), 10)
        self.assertEqual(count_comment_characters('  merhaba  '), 7)

    def test_gate_blocks_forum_until_survey(self):
        self._auth_cookie()
        res = self.client.get('/forum', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/', res.headers.get('Location', ''))

    def test_submit_survey_unlocks_site(self):
        self._auth_cookie()
        short = self.client.post('/api/giris-anketi', json={
            'site_yorumu': 'cok kisa',
            'google_ads_evet': True,
        })
        self.assertEqual(short.status_code, 400)

        yorum = 'Güzel site, teşekkürler'
        ok = self.client.post('/api/giris-anketi', json={
            'site_yorumu': yorum,
            'google_ads_evet': False,
        })
        self.assertIn(ok.status_code, (200, 201))

        with self.app.app_context():
            self.assertTrue(user_completed_giris_anketi(self.user_id))
            kayit = Istek.query.filter_by(user_id=self.user_id, kategori=GIRIS_ANKETI_KATEGORI).first()
            self.assertIsNotNone(kayit)
            self.assertIn('Hayır', kayit.baslik)

        res = self.client.get('/forum', follow_redirects=False)
        self.assertNotEqual(res.status_code, 302)

    def test_istekler_endpoint_rejects_giris_anketi_category(self):
        self._auth_cookie()
        yorum = 'Güzel site, teşekkürler'
        self.client.post('/api/giris-anketi', json={
            'site_yorumu': yorum,
            'google_ads_evet': True,
        })
        res = self.client.post('/api/istekler', json={
            'baslik': 'x',
            'aciklama': 'y',
            'kategori': GIRIS_ANKETI_KATEGORI,
        })
        self.assertEqual(res.status_code, 400)


if __name__ == '__main__':
    unittest.main()
