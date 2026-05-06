from pywebpush import webpush, WebPushException

# VAPID anahtar çiftini oluşturur
import ecdsa
import base64

def generate_vapid_keys():
    # Özel anahtar oluşturma
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.NIST256p)
    public_key = private_key.get_verifying_key()

    # Anahtarları URL-safe base64 formatına çevirme
    private_key_base64 = base64.urlsafe_b64encode(private_key.to_string()).decode('utf-8').strip("=")
    # Kamu anahtarı için başına \x04 (uncompressed) eklenir
    public_key_base64 = base64.urlsafe_b64encode(b"\x04" + public_key.to_string()).decode('utf-8').strip("=")

    print(f"--- VAPID ANAHTARLARINIZ ---\n")
    print(f"Public Key (Frontend'de ve Backend'de kullanılır): \n{public_key_base64}\n")
    print(f"Private Key (SADECE Backend'de gizli tutulur): \n{private_key_base64}")
    print(f"\n----------------------------")

if __name__ == "__main__":
    generate_vapid_keys()
