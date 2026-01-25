# Otobüs API Sorun Giderme

## Sorun: Production'da Otobüs API'si Boş Dönüyor

API'nin boş döndüğü durumlarda aşağıdaki adımları izleyin:

### 1. Gerekli Kütüphanelerin Kontrolü

Production sunucusunda şu komutları çalıştırın:

```bash
pip install -r requirements.txt
```

veya

```bash
pip3 install -r requirements.txt
```

### 2. Test Scriptini Çalıştırın

```bash
python3 test_otobus.py
```

Bu script:
- Kütüphanelerin yüklü olup olmadığını kontrol eder
- İnternet bağlantısını test eder
- EGO web sitesine erişimi test eder
- Durak sorgulama işlevini test eder

### 3. Log Kontrolü

Production sunucusunda Flask uygulamasının loglarını kontrol edin:
- `durak_sorgula()` fonksiyonu artık detaylı log üretiyor
- Status code, response length, bulunan satır sayısı gibi bilgileri içeriyor

### 4. Olası Sorunlar ve Çözümleri

#### a) Kütüphane Eksikliği
**Belirtiler:** ImportError, ModuleNotFoundError
**Çözüm:**
```bash
pip3 install requests beautifulsoup4 lxml
```

#### b) EGO Web Sitesi Sunucu IP'sini Engelliyor
**Belirtiler:** ConnectionError, boş response, timeout
**Çözüm:**
- Proxy kullanın
- VPN kullanın
- Sunucu IP'sini değiştirin
- Farklı bir user-agent deneyin

#### c) SSL/TLS Sertifika Sorunu
**Belirtiler:** SSL verification failed
**Çözüm:**
```python
# durak.py içinde verify=False yapın (güvensiz, test için)
response = session.get(url, params=params, headers=headers, timeout=30, verify=False)
```

#### d) Timeout
**Belirtiler:** Timeout error
**Çözüm:**
- Timeout süresini artırın (30 saniye → 60 saniye)
- İnternet bağlantısını kontrol edin

#### e) HTML Parsing Sorunu
**Belirtiler:** BeautifulSoup parse edemedi, boş sonuç döndü
**Çözüm:**
- EGO web sitesi yapısı değişmiş olabilir
- HTML'i manuel kontrol edin: `curl "https://www.ego.gov.tr/tr/otobusnerede?durak_no=51164"`

### 5. Manuel Test

Sunucuda Python shell'de manuel test yapın:

```python
from durak import durak_sorgula

# Tek bir durağı test et
sonuc = durak_sorgula("51164")
print(f"Sonuç: {sonuc}")
```

### 6. Curl ile Test

```bash
curl "https://www.ego.gov.tr/tr/otobusnerede?durak_no=51164&hat_no=" -H "User-Agent: Mozilla/5.0"
```

Bu komut HTML döndürüyorsa, sorun Python kodundadır.
HTML döndürmüyorsa, sorun IP engelleme olabilir.

### 7. Production Sunucu Özel Durumları

#### Gunicorn/uWSGI kullanıyorsanız:
- Worker sayısını kontrol edin
- Timeout ayarlarını kontrol edin
- Environment variable'ları kontrol edin

#### Nginx kullanıyorsanız:
- Proxy timeout ayarlarını artırın:
```nginx
proxy_connect_timeout 60;
proxy_send_timeout 60;
proxy_read_timeout 60;
```

#### Firewall:
- Sunucunun dışarıya HTTPS (443) bağlantısı açık mı kontrol edin
- `curl https://www.ego.gov.tr` çalışıyor mu test edin

## Güncellenmiş Kod Özellikleri

Yeni versiyonda:
1. ✅ Detaylı log mesajları eklendi
2. ✅ Daha iyi hata yakalama (timeout, connection error, vs.)
3. ✅ Print statement'lar eklendi (production loglarında görebilirsiniz)
4. ✅ Daha fazla HTTP header eklendi
5. ✅ Test scripti eklendi
6. ✅ requirements.txt düzeltildi ve lxml eklendi

## Hızlı Kontrol Checklist

- [ ] `requirements.txt` ana dizinde mi?
- [ ] `pip install -r requirements.txt` çalıştırıldı mı?
- [ ] `python3 test_otobus.py` başarılı mı?
- [ ] Sunucu loglarında error mesajı var mı?
- [ ] Sunucudan `curl https://www.ego.gov.tr/tr/otobusnerede` çalışıyor mu?
- [ ] Flask uygulaması restart edildi mi?
