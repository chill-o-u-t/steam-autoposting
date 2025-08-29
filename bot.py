import os
import time
import requests
import logging
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")
STEAM_COMMUNITY_URL = os.getenv("STEAM_COMMUNITY_URL", "https://steamcommunity.com")
GROUPS = os.getenv("GROUPS", "").split(",")
MESSAGE = os.getenv("MESSAGE", "")
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


def get_sessionid():
    """Получаем sessionid (нужен для POST)"""
    r = session.get(STEAM_COMMUNITY_URL, headers=headers)
    if "g_sessionID" in r.text:
        return r.text.split('g_sessionID = "')[1].split('"')[0]
    return None


def get_groupid(group_url):
    """Достаём groupID из XML"""
    if not group_url.endswith("/"):
        group_url += "/"

    xml_url = group_url + "memberslistxml/?xml=1"
    r = session.get(xml_url, headers=headers)
    if r.status_code == 200:
        try:
            root = ET.fromstring(r.text)
            group_id64 = root.find("groupID64")
            if group_id64 is not None:
                return group_id64.text
        except Exception as e:
            logging.error(f"Ошибка парсинга XML {group_url}: {e}")
    else:
        logging.error(f"Ошибка {r.status_code} при получении groupID {group_url}")
    return None


def post_comment(group_url, message):
    """Отправляем комментарий в группу"""
    groupid = get_groupid(group_url)
    if not groupid:
        logging.error(f"Не удалось получить groupid для {group_url}")
        return

    sessionid = get_sessionid()
    if not sessionid:
        logging.error("Не удалось получить sessionid")
        return

    # Добавляем sessionid в cookies
    session.cookies.set("sessionid", sessionid, domain="steamcommunity.com")

    comment_url = f"https://steamcommunity.com/comment/Clan/post/{groupid}/"

    payload = {
        "comment": message,
        "count": 6,
        "sessionid": sessionid
    }

    r = session.post(comment_url, data=payload, headers=headers)
    if r.status_code == 200:
        logging.info(f"Сообщение отправлено в {group_url}")
    else:
        logging.error(f"Ошибка {r.status_code} при отправке в {group_url} | Ответ: {r.text[:200]}")


def run():
    cycle = 1
    while True:
        logging.info(f"---- Цикл #{cycle} ----")
        for group in GROUPS:
            group = group.strip()
            if group:
                post_comment(group, MESSAGE)
        logging.info(f"Ожидание {INTERVAL} секунд...")
        time.sleep(INTERVAL)
        cycle += 1


if __name__ == "__main__":
    run()
