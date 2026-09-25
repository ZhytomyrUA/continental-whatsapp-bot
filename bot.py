import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# Ваш список новин, який ви надали
news_list = [
  {
    "title": "Continental baut eigenen Windpark: Strom fließt direkt ins Reifenwerk Korbach - hna.de",
    "summary": "Continental baut eigenen Windpark: Strom fließt direkt ins Reifenwerk Korbach &nbsp;&nbsp; hna.de",
    "url": "https://news.google.com/rss/articles/CBMi4AFBVV95cUxNV3VrNGJva1U1N0ZiTXI4NXd1bWdIUGVjajZCUmY2NTdQdHNKZHFYR0xpN2l5VDFEZENiNVdjNzFEdXhFWG5LQmdPRGYzaG9hY0p4cDBZRXdWSnVORTV5LVkxVUFtSnNGU0NsTE5wRjJza0pXRDFwbDYtRFd3eFBKTTdZRmgwX3VDc3RFVVZVRTN1bV9DTzVsNWZkX1ZzTE9tX2hqM0VxeWNsM2FJLVhBbUxvLV9Vbzh2ZndpbkgxNGpNYnZvUG9NWVpFMW9aaFBBOGVpeFV0S0pTZzVRMEtUOA?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-25T04:00:00+00:00",
    "category": "KORBACH_FACTORY",
    "korbach_priority": True,
  },
  {
    "title": "Continental WinterContact TS 870 gewinnt ADAC Winterreifentest 2026 - Continental AG",
    "summary": "Continental WinterContact TS 870 gewinnt ADAC Winterreifentest 2026 &nbsp;&nbsp; Continental AG",
    "url": "https://news.google.com/rss/articles/CBMikgFBVV95cUxNNmdjX0QydUFxNUtxNmxlamNKNmhCN25hVDRnODhBSG1LVWhDdW5uMnpHSXZmdVg0Z2lvbExMVEJpMTBDbWZTSkhIZzNaUE9GU0FkVUxPOGJaYnJKc1lQX0JCd1pjUVRPNUlPMnhDVXhYLUVUYVNlc1BJZWhOaFI3ZUlKa19vZUdpSmUyRDdFMlNHdw?oc=5",
    "source": "news.google.com",
    "published_at": "2026-09-22T10:25:21+00:00",
    "category": "TIRE_TEST",
    "korbach_priority": False,
  }
  # Сюди можна додати решту новин зі свого масиву за потреби
]

def send_whatsapp_message(chat_name, message_text):
    """
    Безкоштовна відправка через WhatsApp Web за допомогою Selenium
    """
    options = Options()
    # Зберігаємо сесію в папці на диску, щоб не сканувати QR-код щоразу
    options.add_argument(r"--user-data-dir=C:\SeleniumWhatsAppSession") 
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://web.whatsapp.com")
        print("⏳ Завантаження WhatsApp Web. Якщо це перший запуск, скануйте QR-код телефоном...")
        time.sleep(20) # Даємо час на завантаження сторінки / сканування QR-коду
        
        # Шукаємо чат/групу/канал за назвою
        search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
        search_box.click()
        search_box.clear()
        search_box.send_keys(chat_name)
        time.sleep(3)
        search_box.send_keys(Keys.ENTER)
        time.sleep(2)
        
        # Поле введення повідомлення у чаті
        message_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
        
        # Відправляємо текст частинами (щоб коректно працювали переноси рядків)
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
    # Назва вашого каналу або чату у WhatsApp, куди потрібно надсилати новини
    WHATSAPP_CHAT_NAME = "Мої новини Conti" 
    
    print(цію Початок розсилки новин у WhatsApp...")
    
    for item in news_list:
        # Формуємо гарне повідомлення для кожного елемента
        formatted_message = f"📰 *{item['title']}*\n\n🔗 Детальніше: {item['url']}"
        
        print(f"Відправляємо: {item['title'][:40]}...")
        send_whatsapp_message(WHATSAPP_CHAT_NAME, formatted_message)
        
        # Пауза між повідомленнями, щоб WhatsApp не заблокував за спам
        time.sleep(5)
        
    print("🏁 Усі новини успішно опрацьовані!")
