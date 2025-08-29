import logging
import os
import time
import random
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, \
    ElementNotInteractableException
import undetected_chromedriver as uc

# Загрузка переменных окружения
load_dotenv()


class SteamCommentBot:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.temp_dir = tempfile.mkdtemp(prefix="chrome_")

    def human_delay(self, min_seconds=1, max_seconds=3):
        """Случайная задержка между действиями"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def has_non_bmp(self, s: str) -> bool:
        return any(ord(ch) > 0xFFFF for ch in s)

    def js_fill_textarea(self, element, text: str):
        # надёжно меняет value + триггерит события
        self.driver.execute_script("""
            const el = arguments[0], val = arguments[1];
            const desc = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            desc.set.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
        """, element, text)

    def scroll_into_view(self, el):
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)

    def safe_click(self, el):
        # если элемент не кликабелен «физически» — кликаем JS
        try:
            if not el.is_displayed() or el.size.get('width', 0) == 0 or el.size.get(
                    'height', 0) == 0:
                self.driver.execute_script("arguments[0].click();", el)
            else:
                el.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", el)


    def human_type(self, element, text):
        """Человеческий ввод текста с паузами и ошибками"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
            if random.random() < 0.03:
                element.send_keys(Keys.BACK_SPACE)
                time.sleep(random.uniform(0.1, 0.3))
                element.send_keys(char)

    def human_scroll(self, scroll_min=200, scroll_max=800):
        """Человеческая прокрутка страницы"""
        scroll_amount = random.randint(scroll_min, scroll_max)
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        self.human_delay(0.5, 1.5)

    def move_mouse_humanly(self, element):
        """Движение мыши как у человека"""
        actions = ActionChains(self.driver)
        actions.move_to_element(element)
        actions.perform()
        self.human_delay(0.2, 0.5)

    def get_stealth_driver(self):
        # ВАЖНО: берём опции из uc
        chrome_options = uc.ChromeOptions()

        # контейнер/Alpine
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # антидетект: достаточно этого флага
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # КЭШ/профиль — не дублируем user_data_dir
        chrome_options.add_argument(f"--user-data-dir={self.temp_dir}")
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disk-cache-size=0")

        # user-agent
        chrome_options.add_argument(
            "--user-agent="
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        CHROME_BIN = os.getenv("CHROME_BIN", "/usr/bin/chromium-browser")
        CHROMEDRIVER = os.getenv("UC_DRIVER_EXECUTABLE_PATH", "/usr/bin/chromedriver")

        # Не указываем version_main; не используем excludeSwitches/useAutomationExtension
        driver = uc.Chrome(
            options=chrome_options,
            headless=True,
            browser_executable_path=CHROME_BIN,  # вместо options.binary_location
            driver_executable_path=CHROMEDRIVER if os.path.exists(
                CHROMEDRIVER) else None,
        )

        # Доп. шлиф — необязательно с uc, но не мешает
        driver.execute_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        return driver

    def login_with_cookies(self):
        """Авторизация через куки"""
        try:
            print("🔐 Авторизация через куки...")

            # Сначала переходим на домен steamcommunity.com
            self.driver.get("https://steamcommunity.com")
            self.human_delay(2, 4)

            # Добавляем необходимые куки
            cookies_to_add = [
                {
                    'name': 'steamLoginSecure',
                    'value': os.getenv('STEAM_LOGIN_SECURE'),
                    'domain': '.steamcommunity.com',
                    'path': '/',
                    'secure': True
                },
                {
                    'name': 'steamRememberLogin',
                    'value': os.getenv('STEAM_REMEMBER_LOGIN', ''),
                    'domain': '.steamcommunity.com',
                    'path': '/',
                    'secure': True
                }
            ]

            for cookie in cookies_to_add:
                if cookie['value']:  # Добавляем только если значение есть
                    try:
                        self.driver.add_cookie(cookie)
                        print(f"✅ Добавлена кука: {cookie['name']}")
                    except Exception as e:
                        print(f"⚠️ Не удалось добавить куку {cookie['name']}: {e}")

            # Обновляем страницу для применения кук
            self.driver.refresh()
            self.human_delay(3, 5)

            # Проверяем авторизацию
            self.driver.get("https://steamcommunity.com/my/profile")
            self.human_delay(2, 4)

            # Проверяем, что мы авторизованы
            try:
                profile_name = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "persona_name"))
                )
                print(f"✅ Успешная авторизация как: {profile_name.text}")
                return True
            except:
                print("❌ Не удалось авторизоваться через куки")
                return False

        except Exception as e:
            print(f"❌ Ошибка при авторизации через куки: {e}")
            return False

    # --- замена метода ---
    def post_comment_to_group(self, group_url, comment_text):
        try:
            print(f"🌐 Перехожу в группу: {group_url}")
            self.driver.get(group_url)

            # Ищем «быстрый пост» как в старой версии
            comment_area = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                                                "textarea[id*='quickpost_text'], .commentthread_textarea"))
            )

            self.scroll_into_view(comment_area)
            self.move_mouse_humanly(comment_area)
            self.human_delay(0.4, 1.0)

            # очищаем через JS (иногда .clear() не триггерит события)
            self.driver.execute_script("arguments[0].value='';", comment_area)

            # Ввод: если есть эмодзи — через JS, иначе «человеческий» набор
            if self.has_non_bmp(comment_text):
                self.js_fill_textarea(comment_area, comment_text)
            else:
                comment_area.click()
                self.human_type(comment_area, comment_text)

            # Находим кнопку «Отправить» как в рабочей версии
            print(1)
            submit_btn = self.wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "button[id*='quickpost_submit'], .commentthread_submit button, .commentthread_submit input[type='submit']"
                ))
            )
            print(2)
            self.scroll_into_view(submit_btn)
            self.move_mouse_humanly(submit_btn)
            self.human_delay(0.3, 0.8)

            # Клик с фоллбэком на JS (исправляет «has no size and location»)
            self.safe_click(submit_btn)
            print("3")

            # Подтверждение — textarea очистилась или появилась запись
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: (comment_area.get_attribute("value") or "").strip() == ""
                )
            except TimeoutException:
                pass

            print("✅ Комментарий отправлен")
            self.human_delay(3, 6)
            return True

        except Exception as e:
            print(f"❌ Ошибка при отправке комментария: {e}")
            try:
                print("📸 Сделан скриншот ошибки")
            except:
                pass
            return False

    def run(self):
        """Основной метод запуска бота"""
        try:
            # Инициализация драйвера
            self.driver = self.get_stealth_driver()
            self.wait = WebDriverWait(self.driver, 15)

            # Авторизация через куки
            if not self.login_with_cookies():
                print("❌ Не удалось авторизоваться")
                return

            # Чтение списка групп и комментария
            groups_to_post = os.getenv('STEAM_GROUPS', '').split(',')
            comment_text = (
                 "Send me offer\n"
                 ":steamthis: Open to any deals"
                 "\nhttps://steamcommunity.com/tradeoffer/new/?partner=889283026&token=NhsSV1bu"
                 "\n[H]"
                 "\nButterfly knife | boreal forest FT"
                 "\nSport gloves | bronze morph BS"
                 "\nUSP-S | kill сonfirmed FT"
             )

            if not groups_to_post or not comment_text:
                print("❌ Не указаны группы или текст комментария в .env")
                return

            successful_posts = 0
            failed_posts = 0

            print(f"📊 Начинаю отправку комментариев в {len(groups_to_post)} групп...")

            for i, group_url in enumerate(groups_to_post):
                group_url = group_url.strip()
                if not group_url:
                    continue

                print(
                    f"\n📝 Обрабатываю группу {i + 1}/{len(groups_to_post)}: {group_url}")

                success = self.post_comment_to_group(group_url, comment_text)

                if success:
                    successful_posts += 1
                    print(f"✅ Успешно отправлено: {successful_posts}")
                else:
                    failed_posts += 1
                    print(f"❌ Неудачных попыток: {failed_posts}")

                # Случайная задержка между группами (2-5 минут)
                if i < len(groups_to_post) - 1:
                    delay = random.randint(180, 300)
                    print(f"⏳ Ожидание {delay} секунд перед следующей группой...")
                    time.sleep(delay)

            print(f"\n🎯 Итог: Успешно {successful_posts}, Неудачно {failed_posts}")

        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")

        finally:
            if self.driver:
                print("🛑 Завершаю работу...")
                self.driver.quit()

            try:
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                print("🗑️ Временные файлы очищены")
            except:
                pass


if __name__ == "__main__":
    # Проверка обязательных переменных
    required_vars = ['STEAM_LOGIN_SECURE', 'STEAM_GROUPS']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        pass
    else:
        bot = SteamCommentBot()
        bot.run()
