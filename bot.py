import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# Повний список новин
news_list = [
  {
    "title": "Continental baut eigenen Windpark: Strom fließt direkt ins Reifenwerk Korbach - hna.de",
    "summary": "Continental baut eigenen Windpark: Strom fließt direkt ins Reifenwerk Korbach &nbsp;&nbsp; hna.de",
    "url": "https://news.google.com/rss/articles/CBMi4AFBVV95cUxNV3VrNGJva1U1N0ZiTXI4NXd1bWdIUGVjajZCUmY2NTdQdHNKZHFYR0xpN2l5VDFEZENiNVdjNzFEdXhFWG5LQmdPRGYzaG9hY0p4cDBZRXdWSnVORTV5LVkxVUFtSnNGU0NsTE5wRjJza0pXRDFwbDYtRFd3eFBKTTdZRmgwX3VDc3RFVVZVRTN1bV9DTzVsNWZkX1ZzTE9tX2hqM0VxeWNsM2FJLVhBbUxvLV9Vbzh2ZndpbkgxNGpNYnZvUG9NWVpFMW9aaFBBOGVpeFV0S0pTZzVRMEtUOA?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-25T04:00:00+00:00",
    "score": 1600,
    "category": "KORBACH_FACTORY",
    "korbach_priority": True,
    "event_family": "korbach|windpark",
    "event_id": "c6b47b6a209ed1c3f6fd43a1f5d42e9aaea85023"
  },
  {
    "title": "Continental-Chef Christian Kötz im Interview über Produktion in Deutschland - HAZ",
    "summary": "Continental-Chef Christian Kötz im Interview über Produktion in Deutschland &nbsp;&nbsp; HAZ",
    "url": "https://news.google.com/rss/articles/CBMi4gFBVV95cUxQWUJFY01JcmZxRjJ1bkJQTXhtNWhBYWNwNDVzWjIwMlBJTkRBWVZ4WFR3aUhLZS1Qa2lLN3dYa2lETGI5UlpLZUh1anQ0MFBiQm1tVWliSnI5aFRma3llVnJjcmRlZWs1YTNkVHFiUWRHM3YtY0ZhaFlZMFROdDZPQ2ZTQlBESWZWdjlRaTF4UWFKUjRRQ3dUR2xPWWdnZGtjU1MzSlpJRDk5dkFxYWNqbXhGVFhaQm0zMjQ3OHQ1bjdTTWlZM3UwQTJOZUVCZ3BpQVZkZ0tsN19tZUVEZzgzdEpB0gH-AUFVX3lxTE16V0dKZndUU0YyT2FMdXVSOWNNZVJ4YXVwNHpwdElyQVF6eUdXNHktLTdNTXNtSTk2X2hraVhMWFB4dExuSHBkOHhfZ3ZDdi1XQlpjWnQ2TFlRWjNFN0liSDlxT1lJbndrd2xPVktxM0VMcmhXcmR2R1kwcjdYSHVZZDBRSEF5VnA5c3Z5b1NZaEFnX0Fqdjd2NEthSGM5WEZ1NDZvNTNGNldwUnhzaElxR0VKeWV2TFQ0S1J3TFpvZWY3STZwcUIyUEZZaWhJaDZqRU0zRDVGX2dWZGVZdHdqQjhrUGNsdmtHWC1LOXBNU1hSU1hlTHMtdzlEWG5B?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-19T04:12:12+00:00",
    "score": 1250,
    "category": "FACTORY_PRODUCTION",
    "korbach_priority": False,
    "event_family": "continental|produktion|christian|deutschland|interview",
    "event_id": "c44fd747753207a420af883d6adef14f093d8cd7"
  },
  {
    "title": "Continental verlagert Industriereifen-Produktion in Region Asien-Pazifik – 140 Mitarbeiter betroffen - hna.de",
    "summary": "Continental verlagert Industriereifen-Produktion in Region Asien-Pazifik – 140 Mitarbeiter betroffen &nbsp;&nbsp; hna.de",
    "url": "https://news.google.com/rss/articles/CBMi_AFBVV95cUxNTkdWSFUwLTROS2lSZEptSVpYbmp5b1RVeUJMNEsyTy1vczIzX1JWWE1MQ2FfMVJrdGo4Slg5TmNDWTNQcWRvS01pdGZkbHB1cFpSXzc1M09OZUdvY21iQ1JrVnNYQTJVUm1NQmFrX091X2RUOXBRMmFaQ0NleG5DWFBOWjJKMEt4cG90WHpFUi1jSWdzdy00RFc1UVJyX1FfM21YSndvbU0wSkw1Mm1vWmxFSGxvdXYxX25IZjNybVdudzlQTENPc1QtWU9wb1QwcmUwcU1EVi1vZkRlTl9FWHRqQ2Q1OUxBTEtrQXoyNzdILTEtUUI2dWNPcjE?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-02T07:00:00+00:00",
    "score": 1300,
    "category": "FACTORY_PRODUCTION",
    "korbach_priority": False,
    "event_family": "continental|produktion|asien|betroffen|industriereifen|mitarbeiter|pazifik",
    "event_id": "8aff7c715c14aeb3dc9dff5c2fa4db22e7996d2f"
  },
  {
    "title": "Tire production without fossil heavyweights: Continental relies entirely on an alternative energy mix - PROFI Werkstatt",
    "summary": "Tire production without fossil heavyweights: Continental relies entirely on an alternative energy mix &nbsp;&nbsp; PROFI Werkstatt",
    "url": "https://news.google.com/rss/articles/CBMi9gFBVV95cUxQajV1ZXV0aEt2ZE4tT1dTMlVFMGJrQWJzc1hoUmlCd0VrOVpUaFJMNG1Wd0pONGFVRFljZ2JOYWtVNGd5NkxVN0hRQkRpbmpkOEVhaEJyWjBhYnZHVVhXZGNySDJ3MVBjZEMwWWkxX2xVaXpTLXFNWC1XT090b2Vvdkpyd29jNlJKbHowUU85TEZlYUlkaHNKQnVHeFJ0dnpyeG5uSzgyYUYwT3BDYnhUSTBQZkk4b2xCdEpCX1RDSHcyZTBiaTdZNnVtd0pkU0s0aHBlb1MzRUxscjRvZnUtTmk3TWY4SUJPN3B2S0hBcUxLZnQyWmc?oc=5",
    "source": "news.google.com",
    "published_at": "2026-08-11T07:00:00+00:00",
    "score": 1300,
    "category": "FACTORY_PRODUCTION",
    "korbach_priority": False,
    "event_family": "continental|alternative|energy|entirely|fossil|heavyweights",
    "event_id": "c5b2b07a90c94ec0fce686909c9d67935654ab31"
  },
  {
    "title": "„Viele der in China produzierten Fahrzeuge fahren auf Continental-Reifen“ - faz.net",
    "summary": "„Viele der in China produzierten Fahrzeuge fahren auf Continental-Reifen“ &nbsp;&nbsp; faz.net",
    "url": "https://news.google.com/rss/articles/CBMi2gFBVV95cUxPSk1tQnZlT0NXdkc2aDl5RGoyM2lXYlNsZEFvMkdIRnpxU3k5UkVnM1ByN0ctNmJyMEhpc283WnZBdk5YWEE0amhESl9DRHg3bndKclZXTHFWTm1ydGJKbW83YzB1NzJNMFY2eEdOTEpEZkZuNTVqWm0wZHQzMXYtNl8xaHlNZXBMVHFYT3pfWjJBNWJVQXRzR2t0a2FMRFYxSllDWlMwSWU3RHF6OEVsTGh4Ul9SdTNMRWdDTGhjcDU4VzhlUEJYUmFmZTBUT3I5cG52RHBVTkRFZw?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-17T05:39:33+00:00",
    "score": 800,
    "category": "PRODUCTION",
    "korbach_priority": False,
    "event_family": "continental|china|fahren|fahrzeuge|produzierten|viele",
    "event_id": "68c74d8d97517e346fd5ae0905d59bddd35834c9"
  },
  {
    "title": "Continental schließt strategischen Umbau ab und wird reiner Reifenhersteller - Maquinac",
    "summary": "Continental schließt strategischen Umbau ab und wird reiner Reifenhersteller &nbsp;&nbsp; Maquinac",
    "url": "https://news.google.com/rss/articles/CBMiowFBVV95cUxNX1R6MVk5aXZQZEJpLXdEWFRyUDRwd09DVDgxOVJ0M05sR3l2MzhFQ1BoNHZUNGVlcjNFX2tza1c4czRZc3FydldCVWhHRGpKdlZVNktZeUtLODdmLUctM2s0NVBkZDktVWw5LWsyMmtqMzRoTVBsanpUcExNS0JBMlJuUUR1TDBCZ2lsb3RpMlJhRmZGVm9udnpNVkVncF9IME1r?oc=5",
    "source": "news.google.com",
    "published_at": "2026-08-22T07:00:00+00:00",
    "score": 800,
    "category": "PRODUCTION",
    "korbach_priority": False,
    "event_family": "continental|maquinac|reifenhersteller|reiner|schließt|strategischen",
    "event_id": "31ae72b8eacc5cfe7834b18d65c3758c4483dcb7"
  },
  {
    "title": "Continental entwickelt Konzeptreifen aus 43 Prozent recycelten Rohstoffen - ecomento.de",
    "summary": "Continental entwickelt Konzeptreifen aus 43 Prozent recycelten Rohstoffen &nbsp;&nbsp; ecomento.de",
    "url": "https://news.google.com/rss/articles/CBMiqAFBVV95cUxOVWZ6dmdNWFZCXzFYT2tUMHp6TjlISHFVX1loYjNxUlkzZDJOcDBud2dFM19RdHE1Skl6d2RNN2dRck5uR19hU1A5S2QxcEF6Z2Q4NWxQNGZfQVJtbThwSzUtSGlQREFfM1JGaVJzUTl5d1pKWFZwRy1LdEFmdVpLR0dQX29hZDdBcjVZVkFIbHJxU0lnckJMMnp1SWhOUjRvN05nUWxybGg?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-25T07:17:22+00:00",
    "score": 200,
    "category": "CONTINENTAL_TECHNOLOGY",
    "korbach_priority": False,
    "event_family": "konzeptreifen|recycling|continental",
    "event_id": "9cc9a3282db5538305045a671c007c7aa11707a0"
  },
  {
    "title": "Continental WinterContact TS 870 gewinnt ADAC Winterreifentest 2026 - Continental AG",
    "summary": "Continental WinterContact TS 870 gewinnt ADAC Winterreifentest 2026 &nbsp;&nbsp; Continental AG",
    "url": "https://news.google.com/rss/articles/CBMikgFBVV95cUxNNmdjX0QydUFxNUtxNmxlamNKNmhCN25hVDRnODhBSG1LVWhDdW5uMnpHSXZmdVg0Z2lvbExMVEJpMTBDbWZTSkhIZzNaUE9GU0FkVUxPOGJaYnJKc1lQX0JCd1pjUVRPNUlPMnhDVXhYLUVUYVNlc1BJZWhOaFI3ZUlKa19vZUdpSmUyRDdFMlNHdw?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-22T10:25:21+00:00",
    "score": 280,
    "category": "TIRE_TEST",
    "korbach_priority": False,
    "event_family": "continental|gewinnt|wintercontact|winterreifentest",
    "event_id": "42577530ca2144a2ab433638dbc31a87a0ce41ed"
  },
  {
    "title": "Continental AllSeasonContact 2 gewinnt Ganzjahresreifentest und erhält „E-Auto-Empfehlung“ von auto motor und sport - Continental AG",
    "summary": "Continental AllSeasonContact 2 gewinnt Ganzjahresreifentest und erhält „E-Auto-Empfehlung“ von auto motor und sport &nbsp;&nbsp; Continental AG",
    "url": "https://news.google.com/rss/articles/CBMigAFBVV95cUxOMlo3SWNUdGdYeVAwMlF3V21DdUQ4Zno2Q3N3R3V4VzFHQ2EzU2tKdjhBN254aUhLaEFXdG5YUXBoNThjWFNId2VpRjRRX0J4WElPTllKdTNmczlnalpPcThyQXBDQ0dLX1dGWVlqWDhTNUtaVmJ6aExaNXpXRWg1Rg?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-10T07:00:00+00:00",
    "score": 280,
    "category": "TIRE_TEST",
    "korbach_priority": False,
    "event_family": "allseasoncontact2|test|continental",
    "event_id": "de68777234e5ddb7c2154e0024d679ddbe531123"
  }
]

def send_whatsapp_message(chat_name, message_text):
    """
    Автоматична безкоштовна відправка новин у WhatsApp Web через Selenium
    """
    options = Options()
    # Зберігаємо сесію браузера, щоб не доводилося сканувати QR-код щоразу
    options.add_argument(r"--user-data-dir=C:\SeleniumWhatsAppSession") 
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://web.whatsapp.com")
        print("⏳ Завантаження WhatsApp Web. Якщо це перший запуск, скануйте QR-код...")
        time.sleep(20) # Час на завантаження сторінки та авторизацію
        
        # Шукаємо чат/канал за назвою
        search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
        search_box.click()
        search_box.clear()
        search_box.send_keys(chat_name)
        time.sleep(3)
        search_box.send_keys(Keys.ENTER)
        time.sleep(2)
        
        # Поле введення повідомлення у чаті
        message_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
        
        # Відправляємо текст із підтримкою переносів рядків
        for line in message_text.split('\n'):
            message_box.send_keys(line)
            message_box.send_keys(Keys.SHIFT, Keys.ENTER)
            
        message_box.send_keys(Keys.ENTER)
        print(f"✅ Успішно надіслано у чат: {chat_name}")
        time.sleep(3)
        
    except Exception as e:
        print(f"❌ Помилка при відправці у WhatsApp: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # Назва вашого WhatsApp каналу
    WHATSAPP_CHAT_NAME = "Continental News" 
    
    print("🚀 Початок розсилки новин у WhatsApp...")
    
    for item in news_list:
        formatted_message = f"📰 *{item['title']}*\n\n🔗 Детальніше: {item['url']}"
        
        print(f"Відправляємо: {item['title'][:40]}...")
        send_whatsapp_message(WHATSAPP_CHAT_NAME, formatted_message)
        
        # Пауза між повідомленнями, щоб захистити акаунт від блокування
        time.sleep(6)
        
    print("🏁 Усі новини успішно опрацьовані!")
