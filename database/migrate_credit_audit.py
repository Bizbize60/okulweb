"""
Kredi değişiklik geçmişi tablosunu oluşturur (mevcut veriye dokunmaz).

    python -m database.migrate_credit_audit
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import app
from database.initdb import db
from database.credit_audit import UserCreditChangeLog  # noqa: F401


def migrate():
    with app.app_context():
        db.create_all()
        print('user_credit_change_logs tablosu hazır.')


if __name__ == '__main__':
    migrate()
