import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from backend import app, seed_default_market_listings
from database.initdb import db
from database.user import User
from database.admin_rbac import Role, Permission, UserRole
from database.credit_audit import UserCreditChangeLog
from api import _aktivite_puan_ver
from database.pazar import PazarIlani


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
            seed_default_market_listings()

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

    def test_admin_template_has_valid_role_management_bindings(self):
        template_path = Path(__file__).resolve().parents[1] / 'templates' / 'admin.html'
        template = template_path.read_text(encoding='utf-8')

        self.assertEqual(template.count("const userSearch = document.getElementById('userSearch');"), 1)
        self.assertIn("const roleSelect = document.getElementById('roleSelect');", template)
        self.assertIn("const rolesTableBody = document.getElementById('rolesTableBody');", template)
        self.assertIn("const roleUserSelect = document.getElementById('roleUserSelect');", template)
        self.assertIn("const userRoleList = document.getElementById('userRoleList');", template)

    def test_admin_credit_update_writes_audit_log(self):
        self._auth_cookie('owner@localhost')

        with self.app.app_context():
            target = User(
                public_id='target-public-id',
                name='Target User',
                email='target@localhost',
                password='pw',
                kredi=2,
            )
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        res = self.client.put(f'/api/admin/users/{target_id}/kredi', json={'kredi': 7})
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            target = User.query.get(target_id)
            self.assertEqual(target.kredi, 7)
            logs = UserCreditChangeLog.query.filter_by(target_user_id=target_id).all()
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].old_kredi, 2)
            self.assertEqual(logs[0].new_kredi, 7)

        audit_res = self.client.get('/api/admin/credit-audit')
        self.assertEqual(audit_res.status_code, 200)
        payload = audit_res.get_json()
        self.assertTrue(payload['items'])
        self.assertEqual(payload['items'][0]['new_kredi'], 7)

    def test_exam_blitz_toggle_enables_campaign_bonus(self):
        self._auth_cookie('owner@localhost')

        response = self.client.post('/api/admin/exam-blitz', json={'enabled': True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(app.config.get('EXAM_WEEK_BLITZ_ENABLED'))

        with self.app.app_context():
            user = User.query.filter_by(email='owner@localhost').first()
            user.kredi = 1
            user.ambassador_points = 0
            db.session.commit()

            _aktivite_puan_ver(user, 20, 'forum')
            db.session.refresh(user)

        self.assertEqual(user.kredi, 3)
        self.assertGreaterEqual(user.ambassador_points, 40)

    def test_yurt_season_market_has_seed_content(self):
        with self.app.app_context():
            count = PazarIlani.query.count()
            first = PazarIlani.query.first()

        self.assertGreaterEqual(count, 3)
        self.assertIsNotNone(first)
        self.assertTrue(first.fotograf_adi.startswith('http'))


if __name__ == '__main__':
    unittest.main()
