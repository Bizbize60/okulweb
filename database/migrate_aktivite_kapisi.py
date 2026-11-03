"""Aktiflik kapısı tabloları.

Eklenenler:
- email_blacklist
- ofis_saat_katkilari
- ofis_saatleri_pending.user_id
- users.activity_unlock_credited

Çalıştırma:
    python -m database.migrate_aktivite_kapisi
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import app
from database.initdb import db


def _columns(conn, table_name):
    dialect = conn.engine.dialect.name
    if dialect == 'postgresql':
        rows = conn.execute(
            db.text(
                "SELECT column_name FROM information_schema.columns WHERE table_name=:table_name"
            ),
            {'table_name': table_name},
        ).fetchall()
        return {row[0] for row in rows}
    rows = conn.execute(db.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def migrate():
    with app.app_context():
        from database.email_blacklist import EmailBlacklist
        from database.saatler import OfisSaatKatkisi

        db.create_all()
        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                inspector = db.inspect(conn)
                if inspector.has_table('ofis_saatleri_pending'):
                    columns = _columns(conn, 'ofis_saatleri_pending')
                    if 'user_id' not in columns:
                        conn.execute(db.text(
                            "ALTER TABLE ofis_saatleri_pending ADD COLUMN user_id INTEGER"
                        ))
                        print("ofis_saatleri_pending.user_id eklendi")
                    else:
                        print("ofis_saatleri_pending.user_id zaten var")
                else:
                    print("ofis_saatleri_pending yok, create_all bekleniyor")
                if inspector.has_table('users'):
                    user_cols = _columns(conn, 'users')
                    if 'activity_unlock_credited' not in user_cols:
                        default = 'FALSE' if conn.engine.dialect.name == 'postgresql' else '0'
                        conn.execute(db.text(
                            f"ALTER TABLE users ADD COLUMN activity_unlock_credited BOOLEAN DEFAULT {default} NOT NULL"
                        ))
                        print("users.activity_unlock_credited eklendi")
                    else:
                        print("users.activity_unlock_credited zaten var")
                trans.commit()
            except Exception:
                trans.rollback()
                raise
        print("email_blacklist ve ofis_saat_katkilari create_all ile hazır")
        return 0


if __name__ == '__main__':
    raise SystemExit(migrate())
