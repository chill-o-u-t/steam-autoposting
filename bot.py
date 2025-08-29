import os
import time
import requests
import logging
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")
STEAM_COMMUNITY_URL = os.getenv("STEAM_COMMUNITY_URL", "https://steamcommunity.com")
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
INTERVAL = int(os.getenv("INTERVAL", 300))  # 300 секунд = 5 минут

# Логирование
logging.basicConfig(
    filename="logs.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Сессия с cookies
session = requests.Session()
session.cookies.set("steamLoginSecure", STEAM_LOGIN_SECURE, domain="steamcommunity.com")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": STEAM_COMMUNITY_URL
}

def post_comment(group_url, message):
    """Отправка комментария в группу"""
    if not group_url.endswith("/"):
        group_url += "/"
    comment_url = group_url + "comment/"

    payload = {
        "comment": message,
        "count": 6,
        "sessionid": None
    }

    # Берём sessionid со страницы группы
    resp = session.get(group_url, headers=headers)
    if "g_sessionID" in resp.text:
        sessionid = resp.text.split("g_sessionID = \"")[1].split("\"")[0]
        payload["sessionid"] = sessionid
    else:
        logging.error(f"Не найден sessionid для {group_url}")
        return

    r = session.post(comment_url, data=payload, headers=headers)
    if r.status_code == 200:
        logging.info(f"Сообщение отправлено в {group_url}")
    else:
        logging.error(f"Ошибка {r.status_code} при отправке в {group_url}")

def run():
    while True:
        logging.info("---- Новый цикл отправки ----")
        for group in GROUPS:
            group = group.strip()
            if group:
                post_comment(group, MESSAGE)
        logging.info(f"Ожидание {INTERVAL} секунд до следующего цикла...")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run()
