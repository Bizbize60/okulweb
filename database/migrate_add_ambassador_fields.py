r"""
Production Guvenli Migration Scripti:
User tablosuna OGRENCI ELCISI SISTEMI alanlarini ekler (var olanlari silmeden, mevcut veriyi bozmadan).
Sadece eksik sutunlari ekler, zaten varsa atlar.
Calistirma:
    cd /home/ubuntu/okulweb  (veya proje klasoru)
    python -m database.migrate_add_ambassador_fields
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend import app
from database.initdb import db


def migrate():
    with app.app_context():
        with db.engine.connect() as conn:
            trans = conn.begin()
            try:
                print("🔍 User tablosu sutunlari kontrol ediliyor...")
                mevcut_sutunlar = [
                    r[0] for r in conn.execute(db.text(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
                    )).fetchall()
                ]
                print(f"   Mevcut {len(mevcut_sutunlar)} sutun bulundu.")

                # 1) Degisken sutunlar (default degerleri ile)
                sutunlar = [
                    ("created_at",       "TIMESTAMP",              True),
                    ("is_ambassador",    "BOOLEAN DEFAULT FALSE",  False),
                    ("ambassador_level", "INTEGER DEFAULT 0",      False),
                    ("ambassador_points","INTEGER DEFAULT 0",      False),
                    ("streak_gun",       "INTEGER DEFAULT 0",      False),
                    ("son_giris_tarihi", "DATE",                   True),
                ]
                for col, tip, null_ok in sutunlar:
                    if col not in mevcut_sutunlar:
                        conn.execute(db.text(f"ALTER TABLE users ADD COLUMN {col} {tip}"))
                        print(f"   ✅ EKLENDI  : {col} ({tip})")
                    else:
                        print(f"   ⏩ ZATEN VAR: {col}")

                # 2) referral_code (ayri - UNIQUE + index ile)
                if "referral_code" not in mevcut_sutunlar:
                    conn.execute(db.text("ALTER TABLE users ADD COLUMN referral_code VARCHAR(20)"))
                    print(f"   ✅ EKLENDI  : referral_code VARCHAR(20)")
                else:
                    print(f"   ⏩ ZATEN VAR: referral_code")

                # 3) Unique index kontrol
                idx_var = conn.execute(db.text(
                    "SELECT indexname FROM pg_indexes WHERE tablename='users' AND indexname='ix_users_referral_code'"
                )).fetchone()
                if not idx_var:
                    try:
                        conn.execute(db.text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code ON users(referral_code)"
                        ))
                        print("   ✅ INDEX olusturuldu: ix_users_referral_code")
                    except Exception as ei:
                        print(f"   ⚠️ Index hatasi (yoksayildi): {str(ei)[:200]}")
                else:
                    print("   ⏩ INDEX ZATEN VAR")

                trans.commit()
                print("\n✅ MIGRATION BASARILI — User tablosuna elci sistemi alanlari eklendi.")
                print("   Simdi calistir: python -m database.createtables (yeni tablolar icin)")
                return 0
            except Exception as e:
                trans.rollback()
                print(f"\n❌ HATA (rollback yapildi): {e}")
                return 1


if __name__ == "__main__":
    sys.exit(migrate())
