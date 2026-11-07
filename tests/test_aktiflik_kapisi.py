import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import jwt

from backend import app
from database.initdb import db
from database.user import User
from database.email_blacklist import EmailBlacklist
from database.degerlendirme import OgretmenDegerlendirme
from database.kampusten import Enstantane
from database.saatler import OfisSaatKatkisi, SaatlerPending
from database.admin_rbac import Role, UserRole
from database.forum_message import ForumMessage


GOOD_POST = "Merhaba millet, kampüste bugün ders ve yemekhane hakkında konuşalım."


class AktiflikKapisiTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app
        self._old_upload = app.config['UPLOAD_FOLDER']
        self.tmp = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.tmp
        with open(os.path.join(self.tmp, 'kapinot.pdf'), 'wb') as handle:
            handle.write(b'%PDF-1.4\nkapi\n')

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.user = User(
                public_id='gate-user',
                name='Ayse Demir',
                email='s123456789@stu.thk.edu.tr',
                password='pw',
                kredi=0,
            )
            db.session.add(self.user)
            db.session.commit()

        self.client = self.app.test_client()
        self._auth('s123456789@stu.thk.edu.tr')

    def tearDown(self):
        app.config['UPLOAD_FOLDER'] = self._old_upload

    def _auth(self, email):
        with self.app.app_context():
            user = User.query.filter_by(email=email).first()
            token = jwt.encode(
                {'public_id': user.public_id, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)},
                self.app.config['SECRET_KEY'],
                algorithm='HS256',
            )
            self.client.set_cookie(key='jwt_token', value=token)
        survey = self.client.post('/api/giris-anketi', json={
            'site_yorumu': 'Güzel site, teşekkürler',
            'google_ads_evet': True,
        })
        if survey.status_code not in (200, 201):
            raise AssertionError(survey.get_data(as_text=True))

    def _user(self):
        return User.query.filter_by(email='s123456789@stu.thk.edu.tr').first()

    def _unlock(self):
        with self.app.app_context():
            user = self._user()
            db.session.add(OgretmenDegerlendirme(
                ogretmen_adi='Ayse',
                ogretmen_soyadi='Yilmaz',
                ders_anlatma_notu=4,
                sinav_zorlugu_notu=3,
                user_id=user.id,
            ))
            db.session.add(Enstantane(
                user_id=user.id,
                foto='/uploads/enstantane/x.jpg',
                aciklama='kampüs akşam',
            ))
            db.session.commit()

    def test_download_requires_two_distinct_activities(self):
        blocked = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(blocked.status_code, 403)
        payload = blocked.get_json()
        self.assertEqual(payload['code'], 'activity_required')
        self.assertIn('sömürülüp bırakılması', payload['message'])
        self.assertEqual(payload['completed'], [])
        self.assertEqual(len(payload['activities']), 6)

        with self.app.app_context():
            user = self._user()
            self.assertEqual(user.kredi, 0)
            db.session.add(OgretmenDegerlendirme(
                ogretmen_adi='Ayse',
                ogretmen_soyadi='Yilmaz',
                ders_anlatma_notu=4,
                sinav_zorlugu_notu=3,
                user_id=user.id,
            ))
            db.session.commit()

        still = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(still.status_code, 403)
        self.assertEqual(still.get_json()['completed'], ['degerlendirme'])

        with self.app.app_context():
            user = self._user()
            self.assertEqual(user.kredi, 0)
            db.session.add(ForumMessage(
                konu='Ders',
                mesaj_icerigi=GOOD_POST,
                user_id=user.id,
            ))
            db.session.commit()

        allowed = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(allowed.status_code, 200)
        with self.app.app_context():
            user = self._user()
            self.assertTrue(user.activity_unlock_credited)
            self.assertEqual(user.kredi, 0)

    def test_unlock_grants_one_credit_once(self):
        with self.app.app_context():
            user = self._user()
            db.session.add(OgretmenDegerlendirme(
                ogretmen_adi='Ayse',
                ogretmen_soyadi='Yilmaz',
                ders_anlatma_notu=4,
                sinav_zorlugu_notu=3,
                user_id=user.id,
            ))
            db.session.commit()

        post = self.client.post('/api/forum/posts', json={
            'konu': 'Ders notu',
            'mesaj_icerigi': GOOD_POST,
        })
        self.assertEqual(post.status_code, 201)
        with self.app.app_context():
            user = self._user()
            self.assertTrue(user.activity_unlock_credited)
            self.assertEqual(user.kredi, 1)

    def test_staff_can_download_without_activities(self):
        with self.app.app_context():
            user = self._user()
            user.kredi = 1
            db.session.commit()
            role = Role(name='moderator', label='Moderator', description='mod')
            db.session.add(role)
            db.session.flush()
            db.session.add(UserRole(user_id=user.id, role_id=role.id))
            db.session.commit()

        allowed = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(allowed.status_code, 200)

    def test_gibberish_forum_post_deletes_account_and_blocks_reregistration(self):
        banned = self.client.post('/api/forum/posts', json={
            'konu': 'asdfghjkl',
            'mesaj_icerigi': 'qwertyuiop',
        })
        self.assertEqual(banned.status_code, 403)
        self.assertEqual(banned.get_json()['code'], 'account_removed')
        self.assertIn('bilinçli kullanıcı', banned.get_json()['message'])

        with self.app.app_context():
            self.assertIsNone(self._user())
            self.assertIsNotNone(EmailBlacklist.query.filter_by(email='s123456789@stu.thk.edu.tr').first())

        again = self.client.post('/signup', data={
            'name': 'Ayse Demir',
            'email': 's123456789@stu.thk.edu.tr',
            'password': 'gizli123',
            'privacy_accept': '1',
        })
        self.assertEqual(again.status_code, 403)
        self.assertIn('Kara listedesiniz', again.get_data(as_text=True))

    def test_short_turkish_does_not_ban_or_count(self):
        rejected = self.client.post('/api/forum/posts', json={
            'konu': 'Selam',
            'mesaj_icerigi': 'naber',
        })
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()['code'], 'contribution_rejected')
        download = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(download.get_json()['completed'], [])
        with self.app.app_context():
            self.assertIsNotNone(self._user())

    def test_quality_gate_stops_after_two_activities(self):
        self._unlock()
        posted = self.client.post('/api/forum/posts', json={
            'konu': 'asdfghjkl',
            'mesaj_icerigi': 'qwertyuiop',
        })
        self.assertEqual(posted.status_code, 201)
        with self.app.app_context():
            self.assertIsNotNone(self._user())
            self.assertEqual(ForumMessage.query.count(), 1)

        hours = self.client.post('/ogretmen-ekle', json={
            'ad': 'Ayse',
            'soyad': 'Yilmaz',
            'gun': [{'gun': 'Pazartesi', 'saatler': ['02:00-04:00']}],
        })
        self.assertEqual(hours.status_code, 201)
        with self.app.app_context():
            self.assertIsNotNone(self._user())
            self.assertEqual(SaatlerPending.query.count(), 1)

    def test_impossible_office_hour_bans_only_during_gate(self):
        banned = self.client.post('/ogretmen-ekle', json={
            'ad': 'Ayse',
            'soyad': 'Yilmaz',
            'gun': [{'gun': 'Pazartesi', 'saatler': ['02:00-04:00']}],
        })
        self.assertEqual(banned.status_code, 403)
        self.assertEqual(banned.get_json()['code'], 'account_removed')
        with self.app.app_context():
            self.assertIsNone(self._user())
            self.assertEqual(SaatlerPending.query.count(), 0)

    def test_valid_office_hour_counts_as_activity(self):
        created = self.client.post('/ogretmen-ekle', json={
            'ad': 'Ayse',
            'soyad': 'Yilmaz',
            'gun': [{'gun': 'Pazartesi', 'saatler': ['10:00-12:00']}],
        })
        self.assertEqual(created.status_code, 201)
        with self.app.app_context():
            self.assertEqual(OfisSaatKatkisi.query.count(), 1)
        download = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(download.get_json()['completed'], ['ofis'])

        malformed = self.client.post('/ogretmen-ekle', json={
            'ad': 'Ayse',
            'soyad': 'Yilmaz',
            'gun': [{'gun': 'Pazartesi', 'saatler': ['öğleden sonra']}],
        })
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.get_json()['code'], 'contribution_rejected')
        with self.app.app_context():
            self.assertIsNotNone(self._user())

    def test_evaluation_name_gate(self):
        banned = self.client.post('/api/degerlendirme-ekle', json={
            'ad': 'Asdf',
            'soyad': 'Qwer',
            'ders_anlatma': 4,
            'sinav_zorlugu': 3,
        })
        self.assertEqual(banned.status_code, 403)
        self.assertEqual(banned.get_json()['code'], 'account_removed')

    def test_real_evaluation_is_saved(self):
        saved = self.client.post('/api/degerlendirme-ekle', json={
            'ad': 'Ayse',
            'soyad': 'Yilmaz',
            'ders_anlatma': 4,
            'sinav_zorlugu': 3,
        })
        self.assertEqual(saved.status_code, 201)
        download = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(download.get_json()['completed'], ['degerlendirme'])

    def test_garbage_listing_bans(self):
        banned = self.client.post('/api/ilan-ekle', data={
            'baslik': 'asdfghjkl',
            'aciklama': 'qwertyuiop',
            'fiyat': '40',
            'kategori': 'Diger',
            'iletisim': '5551112233',
            'file': (io.BytesIO(b'x' * 120), 'ilan.jpg'),
        })
        self.assertEqual(banned.status_code, 403)
        with self.app.app_context():
            self.assertIsNone(self._user())

    def test_gif_only_does_not_count_during_gate(self):
        rejected = self.client.post('/api/forum/posts', json={
            'konu': 'Gif',
            'mesaj_icerigi': '',
            'gif_url': 'https://media.tenor.com/demo.gif',
        })
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()['code'], 'contribution_rejected')

    def test_probe_does_not_open_the_gate_or_charge(self):
        blocked = self.client.get('/uploads/notes/kapinot.pdf?probe=1')
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.get_json()['code'], 'activity_required')
        with self.app.app_context():
            user = self._user()
            self.assertEqual(user.kredi, 0)
            self.assertFalse(user.activity_unlock_credited)

        self._unlock()
        probe = self.client.get('/uploads/notes/kapinot.pdf?probe=1')
        self.assertEqual(probe.status_code, 200)
        self.assertEqual(probe.get_json(), {'ok': True})
        self.assertIn('application/json', probe.content_type)
        with self.app.app_context():
            user = self._user()
            self.assertEqual(user.kredi, 0)
            self.assertFalse(user.activity_unlock_credited)

        downloaded = self.client.get('/uploads/notes/kapinot.pdf')
        self.assertEqual(downloaded.status_code, 200)
        self.assertIn('attachment', downloaded.headers.get('Content-Disposition', ''))
        self.assertIn('no-store', downloaded.headers.get('Cache-Control', ''))
        with self.app.app_context():
            user = self._user()
            self.assertTrue(user.activity_unlock_credited)
            self.assertEqual(user.kredi, 0)

        again = self.client.get('/uploads/notes/kapinot.pdf?probe=1')
        self.assertEqual(again.status_code, 403)
        self.assertEqual(again.get_json()['code'], 'insufficient_credit')

    def test_note_path_cannot_escape_upload_dir(self):
        self._unlock()
        with self.app.app_context():
            user = self._user()
            user.kredi = 2
            user.activity_unlock_credited = True
            db.session.commit()
        escaped = self.client.get('/uploads/notes/..%2F..%2Fconfig.py.example')
        self.assertEqual(escaped.status_code, 404)
        with self.app.app_context():
            self.assertEqual(self._user().kredi, 2)

    def test_small_photo_is_rejected_without_ban(self):
        rejected = self.client.post('/api/enstantane-yukle', data={
            'aciklama': 'kütüphane akşam ışığı',
            'file': (io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'0' * 40), 'kampus.png'),
        })
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()['code'], 'contribution_rejected')
        with self.app.app_context():
            self.assertIsNotNone(self._user())
            self.assertEqual(Enstantane.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
