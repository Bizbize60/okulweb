import unittest
from datetime import datetime, timedelta, timezone

import jwt

from backend import app
from database.initdb import db
from database.user import User
from database.admin_rbac import Role, Permission, UserRole


class AdminRbacApiTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app
        with self.app.app_context():
            db.drop_all()
            db.create_all()

            self.owner = User(
                public_id='owner-public-id',
                name='Owner User',
                email='owner@localhost',
                password='pw',
                kredi=1,
            )
            db.session.add(self.owner)
            db.session.flush()

            permission_admin = Permission(key='system.admin', label='System admin', description='admin')
            permission_role = Permission(key='role.manage', label='Role manage', description='role management')
            db.session.add_all([permission_admin, permission_role])
            db.session.flush()

            role_owner = Role(name='owner', label='Owner', description='owner role')
            role_owner.permissions.extend([permission_admin, permission_role])
            db.session.add(role_owner)
            db.session.flush()

            self.owner.roles.append(role_owner)
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
            return token

    def test_session_endpoint_exposes_role_and_permissions(self):
        self._auth_cookie('owner@localhost')
        response = self.client.get('/api/admin/session')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('permissions', payload)
        self.assertIn('roles', payload)
        self.assertIn('system.admin', payload['permissions'])
        self.assertIn('owner', payload['roles'])

    def test_role_listing_requires_role_manage_permission(self):
        self._auth_cookie('owner@localhost')
        response = self.client.get('/api/admin/roles')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['roles'])


if __name__ == '__main__':
    unittest.main()
