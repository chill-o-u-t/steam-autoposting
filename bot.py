import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# ----------------------------
# Настройка
# ----------------------------
load_dotenv()
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")
GROUPS = os.getenv("GROUPS", "").split(",")
MESSAGE = os.getenv(
    "MESSAGE",
    "🖤Send me offer🖤\n"
    ":steamthis: Open to any deals"
    "\nhttps://steamcommunity.com/tradeoffer/new/?partner=889283026&token=NhsSV1bu"
    "\n[H]"
    "\nButterfly knife | boreal forest FT"
    "\nSport gloves | bronze morph BS"
    "\nUSP-S | kill сonfirmed FT"
)
INTERVAL = int(os.getenv("INTERVAL", 300))  # 5 минут

# Логирование
logging.basicConfig(
    filename="logs.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ----------------------------
# Настройка Selenium
# ----------------------------
chrome_options = Options()
chrome_options.add_argument("--headless")  # убрать, если нужно видеть браузер
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)

# ----------------------------
# Авторизация через cookie
# ----------------------------
driver.get("https://steamcommunity.com/")
driver.delete_all_cookies()
driver.add_cookie({
    'name': 'steamLoginSecure',
    'value': STEAM_LOGIN_SECURE,
    'domain': '.steamcommunity.com'
})
driver.refresh()
time.sleep(3)  # ждём, пока авторизуется

# Проверка авторизации
try:
    driver.find_element(By.ID, "account_pulldown")  # если есть меню аккаунта
    logging.info("✅ Авторизация успешна")
except:
    logging.error("❌ Авторизация не удалась. Проверьте steamLoginSecure")
    driver.quit()
    exit(1)

# ----------------------------
# Основной цикл
# ----------------------------
cycle = 1
while True:
    logging.info(f"---- Цикл #{cycle} ----")
    for group_url in GROUPS:
        group_url = group_url.strip()
        if not group_url:
            continue
        try:
            driver.get(group_url)
            time.sleep(3)  # ждём загрузки страницы

            # Находим поле комментария
            comment_area = driver.find_element(By.ID, "quickpost_text")
            comment_area.clear()
            comment_area.send_keys(MESSAGE)
            time.sleep(1)

            # Отправляем комментарий
            submit_btn = driver.find_element(By.ID, "quickpost_submit")
            submit_btn.click()
            logging.info(f"✅ Сообщение отправлено в {group_url}")
            time.sleep(2)
        except Exception as e:
            logging.error(f"❌ Не удалось отправить комментарий в {group_url}: {e}")

    logging.info(f"Ожидание {INTERVAL} секунд до следующего цикла...")
    time.sleep(INTERVAL)
    cycle += 1
