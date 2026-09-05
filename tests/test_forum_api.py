import unittest
from datetime import datetime, timedelta, timezone

import jwt

from backend import app
from database.initdb import db
from database.user import User


class ForumApiTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            self.user1 = User(
                public_id='forum-user-1',
                name='Ali Veli',
                email='ali@localhost',
                password='pw',
                kredi=1,
            )
            self.user2 = User(
                public_id='forum-user-2',
                name='Ayse Demo',
                email='ayse@localhost',
                password='pw',
                kredi=1,
            )
            db.session.add_all([self.user1, self.user2])
            db.session.commit()

        self.client = self.app.test_client()

    def _auth_cookie(self, user_email):
        with self.app.app_context():
            user = User.query.filter_by(email=user_email).first()
            token = jwt.encode(
                {'public_id': user.public_id, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)},
                self.app.config['SECRET_KEY'],
                algorithm='HS256',
            )
            self.client.set_cookie(key='jwt_token', value=token)

    def _create_post(self, konu='Forum Konusu', mesaj='Merhaba millet', isim_gorunsun=True, gif_url=None):
        payload = {
            'konu': konu,
            'mesaj_icerigi': mesaj,
            'isim_gorunsun': isim_gorunsun,
            'gif_url': gif_url,
        }
        return self.client.post('/api/forum/posts', json=payload)

    def test_anonymous_post_hides_author_name(self):
        self._auth_cookie('ali@localhost')

        create_res = self._create_post(isim_gorunsun=False)
        self.assertEqual(create_res.status_code, 201)

        list_res = self.client.get('/api/forum/posts')
        self.assertEqual(list_res.status_code, 200)
        payload = list_res.get_json()
        posts = payload['items']

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]['display_name'], 'Anonim')

    def test_posts_list_supports_pagination(self):
        self._auth_cookie('ali@localhost')

        for i in range(10):
            res = self._create_post(konu=f'Konu {i}', mesaj=f'Mesaj {i}')
            self.assertEqual(res.status_code, 201)

        first_page = self.client.get('/api/forum/posts?page=1&page_size=4')
        self.assertEqual(first_page.status_code, 200)
        first_payload = first_page.get_json()

        self.assertEqual(len(first_payload['items']), 4)
        self.assertEqual(first_payload['pagination']['page'], 1)
        self.assertEqual(first_payload['pagination']['page_size'], 4)
        self.assertEqual(first_payload['pagination']['total_items'], 10)
        self.assertEqual(first_payload['pagination']['total_pages'], 3)
        self.assertTrue(first_payload['pagination']['has_next'])
        self.assertFalse(first_payload['pagination']['has_prev'])

        third_page = self.client.get('/api/forum/posts?page=3&page_size=4')
        self.assertEqual(third_page.status_code, 200)
        third_payload = third_page.get_json()

        self.assertEqual(len(third_payload['items']), 2)
        self.assertEqual(third_payload['pagination']['page'], 3)
        self.assertFalse(third_payload['pagination']['has_next'])
        self.assertTrue(third_payload['pagination']['has_prev'])

    def test_gif_url_validation(self):
        self._auth_cookie('ali@localhost')

        invalid_res = self._create_post(gif_url='https://example.com/photo.jpg')
        self.assertEqual(invalid_res.status_code, 400)

        valid_res = self._create_post(gif_url='https://media.tenor.com/demo.gif')
        self.assertEqual(valid_res.status_code, 201)

    def test_threaded_comments_can_be_created(self):
        self._auth_cookie('ali@localhost')
        post_res = self._create_post()
        self.assertEqual(post_res.status_code, 201)
        post_id = post_res.get_json()['post']['id']

        top_comment_res = self.client.post(
            f'/api/forum/posts/{post_id}/comments',
            json={'yorum_icerigi': 'Ilk yorum', 'isim_gorunsun': True},
        )
        self.assertEqual(top_comment_res.status_code, 201)
        top_comment_id = top_comment_res.get_json()['comment']['id']

        reply_res = self.client.post(
            f'/api/forum/posts/{post_id}/comments',
            json={
                'yorum_icerigi': 'Yanit yorum',
                'parent_comment_id': top_comment_id,
                'isim_gorunsun': True,
            },
        )
        self.assertEqual(reply_res.status_code, 201)

        detail_res = self.client.get(f'/api/forum/posts/{post_id}')
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.get_json()

        self.assertEqual(len(detail['comments']), 1)
        self.assertEqual(len(detail['comments'][0]['children']), 1)

    def test_only_owner_can_delete_post_without_admin_privilege(self):
        self._auth_cookie('ali@localhost')
        post_res = self._create_post(konu='Silinecek Konu')
        self.assertEqual(post_res.status_code, 201)
        post_id = post_res.get_json()['post']['id']

        self._auth_cookie('ayse@localhost')
        forbidden = self.client.delete(f'/api/forum/posts/{post_id}')
        self.assertEqual(forbidden.status_code, 403)

        self._auth_cookie('ali@localhost')
        allowed = self.client.delete(f'/api/forum/posts/{post_id}')
        self.assertEqual(allowed.status_code, 200)


if __name__ == '__main__':
    unittest.main()
