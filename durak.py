import requests
from bs4 import BeautifulSoup

def durak_sorgula(durak_no):
    """
    EGO durak numarasını sorgular ve otobüs bilgilerini döndürür.
    
    Args:
        durak_no (str): Sorgulanacak durak numarası
    
    Returns:
        list: Hat numarası ve süre bilgilerini içeren sözlük listesi
              Örnek: [{'hat': '524', 'sure': '5 dk 53 sn'}, ...]
    """
    try:
        session = requests.Session()
        url = "https://www.ego.gov.tr/tr/otobusnerede"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.ego.gov.tr/tr/otobusnerede",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }
        
        params = {"durak_no": durak_no, "hat_no": ""}
        
        response = session.get(url, params=params, headers=headers, timeout=30, verify=True)
        
        if response.status_code != 200:
            print(f"Hata: Status code {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, "lxml") 
        
        otobus_listesi = []
        gecici_hat_no = None
        
        all_rows = soup.find_all("tr")
        
        for row in all_rows:
            cells = row.find_all("td")
            if not cells:
                continue

            satir_metni = row.get_text(separator="|", strip=True)
            
            if "Tahmini Varış Süresi" in satir_metni:
                if gecici_hat_no:
                    try:
                        kisim = satir_metni.split("Tahmini Varış Süresi:")[1]
                        sure = kisim.split("|")[0].strip()
                        
                        otobus_listesi.append({
                            "hat": gecici_hat_no,
                            "sure": sure
                        })
                    except Exception as parse_error:
                        print(f"Parse hatası: {parse_error}")
                        pass
                    
                    gecici_hat_no = None
            else:
                parcalar = satir_metni.split("|")
                if len(parcalar) > 0:
                    gecici_hat_no = parcalar[0].strip()

        return otobus_listesi

    except requests.exceptions.Timeout:
        print(f"Durak {durak_no} - Timeout hatası")
        return []
    except requests.exceptions.ConnectionError:
        print(f"Durak {durak_no} - Bağlantı hatası")
        return []
    except requests.exceptions.RequestException as e:
        print(f"Durak {durak_no} - Request hatası: {e}")
        return []
    except Exception as e:
        print(f"Durak {durak_no} - Genel hata: {e}")
        import traceback
        traceback.print_exc()
        return []