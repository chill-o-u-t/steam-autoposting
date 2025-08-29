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
        chrome_options = Options()
        # headless для контейнера
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # антидетект
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # кэш/профиль (только один способ!)
        chrome_options.add_argument(f"--user-data-dir={self.temp_dir}")
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disk-cache-size=0")

        ua = random.choice([
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        ])
        chrome_options.add_argument(f"--user-agent={ua}")

        # важное для Alpine: указываем системные бинарники
        browser_bin = os.getenv("CHROME_BIN", "/usr/bin/chromium-browser")
        driver_bin = os.getenv("UC_DRIVER_EXECUTABLE_PATH", "/usr/bin/chromedriver")
        chrome_options.binary_location = browser_bin

        # если системный chromedriver существует — используем его
        driver = uc.Chrome(
            options=chrome_options,
            driver_executable_path=driver_bin if os.path.exists(driver_bin) else None,
            # НЕ указываем version_main — пусть uc сам подберёт
            # НЕ передаём user_data_dir второй раз
            headless=True,  # дублируем для надёжности внутри uc
        )

        # дополнительный шлиф
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

    def post_comment_to_group(self, group_url, comment_text):
        """Отправка комментария в группу"""
        try:
            print(f"🌐 Перехожу в группу: {group_url}")

            # Открываем группу
            self.driver.get(group_url)
            self.human_delay(3, 6)

            # Человеческая прокрутка
            self.human_scroll()
            self.human_delay(1, 2)

            # Ищем поле для комментария
            comment_selectors = [
                "textarea.commentthread_textarea",
                "textarea[name='comment']",
                "#comment_form textarea",
                ".commentthread_textarea",
                "textarea.TextArea"
            ]

            comment_area = None
            for selector in comment_selectors:
                try:
                    comment_area = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"✅ Найдено поле комментария: {selector}")
                    break
                except:
                    continue

            if not comment_area:
                print("❌ Не найдено поле для комментария")
                return False

            # Человеческое взаимодействие с полем
            self.move_mouse_humanly(comment_area)
            self.human_delay(1, 2)

            # Кликаем и вводим текст
            comment_area.click()
            self.human_delay(0.5, 1)
            self.human_type(comment_area, comment_text)
            self.human_delay(1, 2)

            # Ищем кнопку отправки
            button_selectors = [
                "input[type='submit'][value='Post Comment']",
                "button[type='submit']",
                ".commentthread_submit",
                "#comment_post",
                ".DialogButton"
            ]

            submit_button = None
            for selector in button_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"✅ Найдена кнопка отправки: {selector}")
                    break
                except:
                    continue

            if not submit_button:
                print("❌ Не найдена кнопка отправки")
                return False

            # Человеческое нажатие кнопки
            self.move_mouse_humanly(submit_button)
            self.human_delay(1, 2)
            submit_button.click()

            print("✅ Комментарий отправлен")
            self.human_delay(5, 10)  # Долгая пауза после отправки

            return True

        except Exception as e:
            print(f"❌ Ошибка при отправке комментария: {e}")
            # Делаем скриншот при ошибке
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.driver.save_screenshot(f"error_{timestamp}.png")
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
                 "🖤Send me offer🖤\n"
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
        print(f"❌ Отсутствуют обязательные переменные в .env: {', '.join(missing_vars)}")
        print("💡 Пример .env файла:")
        print("STEAM_LOGIN_SECURE=your_steam_login_secure_cookie")
        print("STEAM_SESSIONID=your_session_id")
        print("STEAM_REMEMBER_LOGIN=your_remember_login")
        print(
            "STEAM_GROUPS=https://steamcommunity.com/groups/group1,https://steamcommunity.com/groups/group2")
        print("COMMENT_TEXT=Ваш комментарий здесь")
    else:
        bot = SteamCommentBot()
        bot.run()
