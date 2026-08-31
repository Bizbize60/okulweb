from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from database.initdb import db
from config import ADMIN_EMAILS


class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    label = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    roles = relationship('Role', secondary='role_permissions', back_populates='permissions')


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    label = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    users = relationship('User', secondary='user_roles', back_populates='roles')
    permissions = relationship('Permission', secondary='role_permissions', back_populates='roles')


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    __table_args__ = (UniqueConstraint('user_id', 'role_id', name='uq_user_role'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    __table_args__ = (UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),)

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ModerationCase(db.Model):
    __tablename__ = 'moderation_cases'

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    report_reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), default='open')
    priority = db.Column(db.String(20), default='normal')
    reporter_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assignee_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)


class ModerationAction(db.Model):
    __tablename__ = 'moderation_actions'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('moderation_cases.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action_type = db.Column(db.String(80), nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(120), nullable=False)
    target_type = db.Column(db.String(80), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


RBAC_ROLE_DEFINITIONS = {
    'owner': {
        'label': 'Owner',
        'description': 'Full system access',
        'permissions': [
            'system.admin', 'system.logs', 'system.debug', 'system.config', 'system.db',
            'users.view', 'users.create', 'users.update', 'users.delete',
            'moderation.view', 'moderation.manage', 'moderation.delete',
            'content.approve', 'content.reject', 'content.delete',
            'role.manage', 'audit.view'
        ],
    },
    'developer': {
        'label': 'Developer',
        'description': 'Technical access and diagnostics',
        'permissions': [
            'system.logs', 'system.debug', 'system.config', 'system.db',
            'users.view', 'moderation.view', 'content.approve', 'content.reject',
            'audit.view'
        ],
    },
    'moderator': {
        'label': 'Moderator',
        'description': 'Moderation and content operations only',
        'permissions': [
            'moderation.view', 'moderation.manage', 'content.approve', 'content.reject', 'content.delete',
            'users.view'
        ],
    },
}


def _seed_permissions() -> dict[str, Permission]:
    permissions = {}
    for role_name, meta in RBAC_ROLE_DEFINITIONS.items():
        for permission_key in meta['permissions']:
            if permission_key not in permissions:
                perm = Permission.query.filter_by(key=permission_key).first()
                if not perm:
                    perm = Permission(key=permission_key, label=permission_key, description='RBAC permission')
                    db.session.add(perm)
                permissions[permission_key] = perm
    db.session.commit()
    return permissions


def ensure_default_roles() -> None:
    table_names = set(db.inspect(db.engine).get_table_names())
    required = {'roles', 'permissions', 'role_permissions', 'user_roles', 'users'}
    if not required.issubset(table_names):
        return

    permissions = _seed_permissions()

    for role_name, meta in RBAC_ROLE_DEFINITIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, label=meta['label'], description=meta['description'])
            db.session.add(role)
            db.session.flush()

        for key in meta['permissions']:
            perm = permissions.get(key) or Permission.query.filter_by(key=key).first()
            if perm and perm not in role.permissions:
                role.permissions.append(perm)

        db.session.commit()

    # Backfill current admin emails into Owner role for compatibility
    for email in ADMIN_EMAILS:
        user = db.session.query(__import__('database.user', fromlist=['User']).User).filter_by(email=email).first()
        if user is None:
            continue
        owner_role = Role.query.filter_by(name='owner').first()
        if owner_role and owner_role not in user.roles:
            user.roles.append(owner_role)
    db.session.commit()


def assign_role_to_user(user_id: int, role_name: str) -> bool:
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return False

    from database.user import User
    user = User.query.get(user_id)
    if not user:
        return False

    if role not in user.roles:
        user.roles.append(role)
        db.session.commit()
    return True


def remove_role_from_user(user_id: int, role_name: str) -> bool:
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        return False

    from database.user import User
    user = User.query.get(user_id)
    if not user:
        return False

    if role in user.roles:
        user.roles.remove(role)
        db.session.commit()
    return True


def list_role_catalog():
    roles = []
    for role in Role.query.order_by(Role.name.asc()).all():
        roles.append({
            'id': role.id,
            'name': role.name,
            'label': role.label,
            'description': role.description,
            'permissions': [p.key for p in (role.permissions or [])],
        })
    return roles


def user_has_role(user, role_name: str) -> bool:
    if not user:
        return False
    return any(r.name == role_name for r in (user.roles or []))
