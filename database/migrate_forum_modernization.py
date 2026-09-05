r"""
Forum modernizasyon migration scripti.

Eklenenler:
- forum_messages tablosuna anonimlik/GIF/soft-delete alanlari
- forum_comments tablosu (threaded yorumlar)

Calistirma:
    cd /home/ubuntu/okulweb  (veya proje klasoru)
    python -m database.migrate_forum_modernization
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import app
from database.initdb import db


def _get_columns(conn, table_name):
    dialect = conn.engine.dialect.name
    if dialect == 'postgresql':
        rows = conn.execute(
            db.text(
                "SELECT column_name FROM information_schema.columns WHERE table_name=:table_name"
            ),
            {'table_name': table_name}
        ).fetchall()
        return {row[0] for row in rows}

    rows = conn.execute(db.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _table_exists(conn, table_name):
    inspector = db.inspect(conn)
    return inspector.has_table(table_name)


def migrate():
    with app.app_context():
        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                if not _table_exists(conn, 'forum_messages'):
                    print("forum_messages tablosu bulunamadi. once create_all calistirin.")
                    trans.rollback()
                    return 1

                mevcut_sutunlar = _get_columns(conn, 'forum_messages')
                eklenecekler = [
                    ('isim_gorunsun', "BOOLEAN DEFAULT TRUE"),
                    ('gif_url', "VARCHAR(500)"),
                    ('silindi', "BOOLEAN DEFAULT FALSE"),
                ]

                print("forum_messages sutunlari kontrol ediliyor...")
                for column_name, column_type in eklenecekler:
                    if column_name in mevcut_sutunlar:
                        print(f"  - {column_name}: zaten var")
                        continue
                    conn.execute(
                        db.text(
                            f"ALTER TABLE forum_messages ADD COLUMN {column_name} {column_type}"
                        )
                    )
                    print(f"  - {column_name}: eklendi")

                if not _table_exists(conn, 'forum_comments'):
                    print("forum_comments tablosu olusturuluyor...")
                    from database.forum_comment import ForumComment
                    ForumComment.__table__.create(bind=conn)
                    print("  - forum_comments: olusturuldu")
                else:
                    print("forum_comments tablosu zaten var")

                trans.commit()
                print("\nMigration basarili.")
                return 0
            except Exception as exc:
                trans.rollback()
                print(f"\nMigration hatasi, rollback yapildi: {exc}")
                return 1


if __name__ == '__main__':
    raise SystemExit(migrate())
