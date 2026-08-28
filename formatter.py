#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ders notu isimlerini standart formata çeviren migration script'i.

Format hatırlatma:
  Çalışma-Notu:KOD-(Konular)
  Çalışma-Soruları:KOD-(Konular)
  Vize(Yıl)-KOD-Hoca   /   Final(Yıl)-KOD-Hoca   (ortak ders ise hoca yerine *)
  Quiz(Yıl)-KOD-(Konular)
  Sadece çözüm varsa başına: Çözüm-

Kural: Bilgi yoksa o alan boş bırakıldı (uydurulmadı).
       Yükleyen öğrenci adları öğretim görevlisi DEĞİLDİR; hoca alanı boş.

Kullanım:
  1. Aşağıdaki AYAR bölümünü kendi projene göre düzelt (import + tablo adı).
  2. Önce DRY_RUN = True ile çalıştır, çıktıyı incele.
  3. Doğruysa DRY_RUN = False yapıp tekrar çalıştır.
      python format_duzelt.py
"""

# ============================= AYAR =============================
DRY_RUN = True            # True iken hiçbir şey yazılmaz, sadece önizleme basar.

from database.initdb import db
from database.dersnotu import DersNotuBekleyen, DersNotu

# Hangi tabloyu düzeltiyorsun?
#   DersNotu          -> onaylanmış (herkese görünen) notlar
#   DersNotuBekleyen  -> onay bekleyen notlar
# Gerekirse MODEL'i değiştirip script'i iki tablo için ayrı ayrı çalıştır.
MODEL = DersNotu

# Flask uygulama nesneni buradan içeri al (app context için gerekli):
#   from app import app
# App factory kullanıyorsan:  from app import create_app; app = create_app()
from backend import app    # backend.py içindeki app değişkeni
# ================================================================


# id -> yeni standart isim  (uygulanacaklar)
RENAMES = {
    116: "Çalışma-Soruları:(RC Devreleri)",
    115: "Çalışma-Soruları:(Manyetizma,Manyetik Tork,Ampere Yasası,Koaksiyel Kablo)",
    114: "Quiz-(Paralel Dağıtık Hesaplama,Quiz 3)",
    113: "Vize-AEE104",                                  # Aee 104 Midterm
    112: "Vize-EEE102",                                  # EEE102 midterm
    110: "Final(2025)-CENG325",                          # 24-25 Otomata Final
    109: "Final(2025)-CENG443",                          # 24-25 Cloud Final
    108: "Çalışma-Soruları:(Manyetizma)",                # Fizik 2 manyetizma1
    107: "Vize(2026)-SENG324",                           # Seng 324 (2026) vize
    106: "Vize-SENG102",                                 # SENG102_midterm
    101: "Quiz-STAT301",                                 # Stat 301 Quiz
    99:  "Vize-MAT124",                                  # MAT124 Midterm   (NOT: 65 ile aynı -> kontrol et)
    98:  "Çalışma-Notu:MAT221-(Linear Algebra,Final)",
    97:  "Çalışma-Notu:MAT221-(Linear Algebra,Vize)",    # "Midterm" -> Vize konu etiketi
    96:  "Çalışma-Notu:(Proje Yönetimi,Vize,Final)",
    90:  "Vize(2025)-MAT224",                            # Summer 2024-2025 (çözümlü) (NOT: 89 ile aynı -> dönem farkı)
    89:  "Vize(2025)-MAT224",                            # Spring 2024-2025 (çözümlü) (NOT: 90 ile aynı -> dönem farkı)
    88:  "Çözüm-Vize(2026)-MAT224",                      # fall 2025-2026 Midterm Solutions (yalnız çözüm varsayıldı)
    87:  "Çalışma-Notu:(Yapay Zeka,Vize)",               # başlıktaki kişi adı (not yazarı) düşürüldü
    85:  "Quiz-(Kriptografi,Quiz 1)",                    # NOT: başlıkta "vize soruları da var" deniyor
    83:  "Vize(2026)-CENG112",                           # Ceng112 Midterm 2026
    82:  "Vize-ATA104",                                  # ATA 104 Midterm
    70:  "Final(2025)-MAT224",                           # MAT224 Diff Final 2024-2025
    67:  "Final-CENG305",                                # CENG305 FINAL    (NOT: 49 ile aynı -> kontrol et)
    65:  "Vize-MAT124",                                  # Mat_124_Midterm  (NOT: 99 ile aynı -> kontrol et)
    55:  "Çalışma-Soruları:AST105-(Lab Çözümleri)",      # Answer of Labs
    54:  "Vize(2022)-PHY101",                            # PHY101 2022 Fall Midterm (+ çözümlü)
    51:  "Quiz-(Yapay Zeka,Quiz 3)",
    50:  "Final-AEE172",                                 # AEE 172 Flight Performance Final
    49:  "Final-CENG305",                                # Ceng 305 Final   (NOT: 67 ile aynı -> kontrol et)
    48:  "Vize-CENG305",                                 # Ceng 305 Midterm
    46:  "Quiz-(Yapay Zeka,Quiz 2)",
    45:  "Quiz-(Yapay Zeka,Quiz 1)",
    44:  "Final-CENG111",
    43:  "Vize-CENG111",
    40:  "Vize-AEE205",                                  # Termodinamik aee205 midterm1
    38:  "Quiz(2025)-(Termodinamik,Quiz 5)",
    37:  "Quiz(2025)-(Termodinamik,Quiz 4)",
    36:  "Quiz(2025)-(Termodinamik,Quiz 3)",
    35:  "Quiz(2025)-(Termodinamik,Quiz 2)",
    34:  "Quiz-(Termodinamik,Quiz 1)",
    33:  "Vize(2025)-CENG445",                           # Cyber Security Midterm 2025
    32:  "Final(2026)-AEE203",                           # material science 25-26 Final
    28:  "Quiz(2024)-(Strength of Materials,Quiz 1-3)",
    27:  "Quiz-(Fluid Mechanics,Quiz 1-9)",
    26:  "Quiz-(Heat Transfer,Quiz 1-8)",
    25:  "Vize(2025)-EEE222",
    24:  "Final(2025)-EEE222",
    23:  "Quiz(2025)-EEE222-(Quiz 2)",
    22:  "Quiz(2025)-EEE222-(Quiz 1)",
    1:   "Çalışma-Soruları:CENG324-(Final)",             # Ceng 324 Final Study Question
}


# id -> (mevcut isim, sebep / öneri)  -> OTOMATİK UYGULANMAZ, elle bak.
# Çoğunlukla "vize/final ama ders kodu yok" durumları: kod olmadan isim ayırt edilemez.
REVIEW = {
    # --- İlk satırın ID'si veride kesik geldi (muhtemelen 117). ID'yi bulup ekle: ---
    "117?": ("Fizik 102 elektrik alan... çalışma soruları",
             "Öneri: Çalışma-Soruları:(Elektrik Alan,Elektrik Potansiyel,Gauss Yasası,Kapasitörler) — ID'yi doğrula"),

    105: ("CENG 101", "Tür belirsiz (not mu sınav mı?). Kod var: CENG101. Türü seç."),
    104: ("Malzeme bilimi 23-24 final", "Final(2024)- ... ders kodu yok, ekle."),
    103: ("Malzeme bilimi 22-23 final makeup", "Final(2023)- ... ders kodu yok, ekle (makeup notu kaybolur)."),
    102: ("Malzeme bilimi 21-22 final", "Final(2022)- ... ders kodu yok, ekle."),
    92:  ("Fizik 2 Final", "Final- ... ders kodu yok (örn. PHY102), ekle."),
    91:  ("Bilgisayar Mimarisi vize", "Vize- ... ders kodu yok, ekle."),
    86:  ("Veri Etiği - Asiye Ulaş-", "Tür belirsiz. Kod yok. Türü ve kodu belirle."),
    84:  ("Programlama Dilleri Vize (2026 ...)", "Vize(2026)- ... ders kodu yok, ekle."),
    81:  ("Ast105", "Tür belirsiz. Kod var: AST105. Türü seç."),
    80:  ("Bilim İletişimi", "Tür ve kod yok. Elle belirle."),
    79:  ("PHY2 2014 midterm", "Vize(2014)- ... net ders kodu yok (PHY102?), ekle."),
    78:  ("phy 2 2014 final", "Final(2014)- ... ders kodu yok, ekle."),
    77:  ("phy 2 2015 final", "Final(2015)- ... ders kodu yok, ekle."),
    76:  ("Phy 2 2015 midterm", "Vize(2015)- ... ders kodu yok, ekle."),
    75:  ("PHY2 2016 FİNAL", "Final(2016)- ... ders kodu yok, ekle."),
    74:  ("Phy 2 2016 midterm", "Vize(2016)- ... ders kodu yok, ekle."),
    73:  ("PHY2 2022 FİNAL", "Final(2022)- ... ders kodu yok, ekle."),
    72:  ("Phy_2_2022_Midterm", "Vize(2022)- ... ders kodu yok, ekle."),
    66:  ("Calculus 2", "Tür ve kod yok. Elle belirle."),
    64:  ("CEBİR FİNAL", "Final- ... ders kodu yok, ekle."),
    57:  ("Cebir", "Tür ve kod yok. Elle belirle."),
    47:  ("Diferansiyel vize", "Vize- ... ders kodu yok, ekle."),
    42:  ("SCN 103", "Tür belirsiz. Kod var: SCN103. Türü seç."),
    41:  ("Nesne tabanlı Programlama", "Tür ve kod yok. Elle belirle."),
    31:  ("Yapay Zeka final çözümleri", "Çözüm-Final- ... ders kodu yok, ekle."),
    30:  ("Mat 1 midterm", "Vize- ... net kod yok (MAT101?), ekle."),
    29:  ("Mat 1 Final", "Final- ... net kod yok, ekle."),
    10:  ("Fizik 1", "Tür ve kod yok. Elle belirle."),
    9:   ("Fizik 1", "Tür ve kod yok. Elle belirle (10/2 ile olası kopya)."),
    8:   ("Kimya", "Tür ve kod yok. Elle belirle."),
    7:   ("Calculus 1", "Tür ve kod yok. Elle belirle."),
    2:   ("Fizik 1", "Tür ve kod yok. Elle belirle."),
}


def main():
    with app.app_context():
        print("=" * 70)
        durum = "DRY-RUN (yazma YOK)" if DRY_RUN else "UYGULANIYOR (yazılıyor)"
        print(f"{durum} -- model: {MODEL.__name__}")
        print("=" * 70)

        applied = skipped = missing = 0
        for nid, new_name in RENAMES.items():
            kayit = db.session.get(MODEL, nid)
            if kayit is None:
                print(f"[YOK ] #{nid}: kayit bulunamadi")
                missing += 1
                continue

            old_name = kayit.ders_adi
            if old_name == new_name:
                print(f"[ATLA] #{nid}: zaten dogru")
                skipped += 1
                continue

            print(f"[{'PLAN' if DRY_RUN else 'YAZ '}] #{nid}")
            print(f"        eski: {old_name}")
            print(f"        yeni: {new_name}")
            if not DRY_RUN:
                kayit.ders_adi = new_name
            applied += 1

        if not DRY_RUN:
            db.session.commit()
            print("\n>>> Degisiklikler kaydedildi (commit).")
        else:
            print("\n>>> DRY-RUN: hicbir sey yazilmadi. Uygulamak icin DRY_RUN = False yap.")

        print(f"\nOzet: {applied} degisecek/degisti, {skipped} zaten dogru, {missing} bulunamadi.")

        # Elle bakilacaklar
        print("\n" + "-" * 70)
        print(f"ELLE GOZDEN GECIR ({len(REVIEW)} kayit) -- otomatik DOKUNULMADI:")
        print("-" * 70)
        for nid, (cur, why) in REVIEW.items():
            print(f"  #{nid}: {cur}")
            print(f"        -> {why}")


if __name__ == "__main__":
    main()
