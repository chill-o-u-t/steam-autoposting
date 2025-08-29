import os
import time
import random
import json
import shutil
import signal
import tempfile
from datetime import datetime

from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc

# ----------------------------
# ENV
# ----------------------------
load_dotenv()
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")
STEAM_GROUPS = [g.strip() for g in os.getenv("STEAM_GROUPS", "").split(",") if g.strip()]
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
INTERVAL = int(os.getenv("INTERVAL", "300"))
CHROME_BIN = os.getenv("CHROME_BIN", "/usr/bin/chromium-browser")
CHROMEDRIVER = os.getenv("UC_DRIVER_EXECUTABLE_PATH", "/usr/bin/chromedriver")


class SteamCommentBot:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.temp_dir = tempfile.mkdtemp(prefix="chrome_profile_")

    def _activate_textarea(self, ta):
        """Делает реальную активацию поля: клик + keydown/keyup, чтобы Steam раскрыл submit_container."""
        try:
            # иногда роль у textarea = button, жмём JS-клик и обычный клик
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});",
                                       ta)
            try:
                ta.click()
            except Exception:
                pass
            self.driver.execute_script("""
                const el = arguments[0];
                el.focus();
                el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            """, ta)
            # «укол» клавишей чтобы сработали keydown/keyup-слушатели Steam
            try:
                ta.send_keys("a")
                ta.send_keys(Keys.BACK_SPACE)
            except Exception:
                # если send_keys блокируется — синтетика
                self.driver.execute_script("""
                    const el = arguments[0];
                    ['keydown','keyup','keypress'].forEach(t=>el.dispatchEvent(new KeyboardEvent(t,{bubbles:true})));
                """, ta)
        except Exception:
            pass

    def _js_set_value_and_events(self, ta, text):
        """Вставляет любой текст (включая эмодзи) и триггерит события."""
        self.driver.execute_script("""
            const el = arguments[0], val = arguments[1];
            const desc = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            desc.set.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true}));
        """, ta, text)

    # ----------------------------
    # Human-ish helpers
    # ----------------------------
    def human_delay(self, a=0.3, b=0.9):
        time.sleep(random.uniform(a, b))

    def human_type(self, element, text):
        for ch in text:
            element.send_keys(ch)
            time.sleep(random.uniform(0.03, 0.12))
            if random.random() < 0.02:
                element.send_keys(Keys.BACK_SPACE)
                time.sleep(random.uniform(0.05, 0.2))
                element.send_keys(ch)

    def move_mouse_humanly(self, element):
        # минимальная «имитация» — достаточно скролла к элементу
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        except Exception:
            pass

    # ----------------------------
    # DOM/JS helpers
    # ----------------------------
    @staticmethod
    def has_non_bmp(s: str) -> bool:
        return any(ord(ch) > 0xFFFF for ch in s)

    def js_fill_textarea(self, element, text: str):
        self.driver.execute_script(
            """
            const el = arguments[0], val = arguments[1];
            const desc = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
            desc.set.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            """,
            element,
            text,
        )

    def is_visible_js(self, el) -> bool:
        try:
            return self.driver.execute_script(
                """
                const el = arguments[0];
                if (!el) return false;
                const st = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
                """,
                el,
            )
        except Exception:
            return False
    # ----------------------------
    # Driver
    # ----------------------------
    def get_stealth_driver(self):
        opts = uc.ChromeOptions()
        # контейнерные флаги
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        # антидетект
        opts.add_argument("--disable-blink-features=AutomationControlled")
        # профиль/кэш
        opts.add_argument(f"--user-data-dir={self.temp_dir}")
        opts.add_argument("--disable-application-cache")
        opts.add_argument("--disk-cache-size=0")
        # user-agent
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        driver = uc.Chrome(
            options=opts,
            headless=True,  # дублируем для uc
            browser_executable_path=CHROME_BIN,
            driver_executable_path=CHROMEDRIVER if os.path.exists(CHROMEDRIVER) else None,
        )
        # убрать navigator.webdriver
        driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        return driver

    # ----------------------------
    # Auth via cookies
    # ----------------------------
    def login_with_cookies(self) -> bool:
        print("🔐 Авторизация через куки...")
        self.driver.get("https://steamcommunity.com/")
        self.human_delay(1.0, 2.0)

        self.driver.delete_all_cookies()
        if STEAM_LOGIN_SECURE:
            try:
                self.driver.add_cookie(
                    {
                        "name": "steamLoginSecure",
                        "value": STEAM_LOGIN_SECURE,
                        "domain": ".steamcommunity.com",
                        "path": "/",
                        "secure": True,
                    }
                )
                print("✅ Добавлена кука: steamLoginSecure")
            except Exception as e:
                print(f"⚠️ Не удалось добавить steamLoginSecure: {e}")

        self.driver.refresh()
        self.human_delay(2.0, 3.5)

        # проверяем наличие меню/аватара
        self.driver.get("https://steamcommunity.com/")
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "global_action_menu"))
            )
            # sessionid тоже должен появиться
            if not self.driver.get_cookie("sessionid"):
                print("⚠️ sessionid не найден, но меню видно — пробую продолжить")
            print("✅ Авторизация успешна")
            return True
        except TimeoutException:
            print("❌ Авторизация не удалась — нет меню пользователя")
            return False

    # ----------------------------
    # Posting
    # ----------------------------
    def _wait_submit_container_visible(self, container_id: str, timeout=12):
        end = time.time() + timeout
        last_exc = None
        while time.time() < end:
            try:
                el = self.driver.find_element(By.ID, container_id)
                if self.is_visible_js(el):
                    return el
            except StaleElementReferenceException as e:
                last_exc = e
            except NoSuchElementException:
                pass
            time.sleep(0.2)
        raise TimeoutException(f"Submit container not visible: #{container_id}") from last_exc
    def _click_submit_by_id(self, submit_id: str):
        btn = self.driver.find_element(By.ID, submit_id)  # свежий элемент
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        self.human_delay(0.2, 0.6)
        try:
            if self.is_visible_js(btn):
                btn.click()
            else:
                self.driver.execute_script("arguments[0].click();", btn)
        except Exception:
            # повтор через JS
            btn = self.driver.find_element(By.ID, submit_id)
            self.driver.execute_script("arguments[0].click();", btn)

    def post_comment_to_group(self, group_url: str, comment_text: str) -> bool:
        try:
            print(f"🌐 Перехожу в группу: {group_url}")
            self.driver.get(group_url)
            self.human_delay(1.5, 2.5)

            # Находим textarea «быстрого поста»
            comment_area = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "textarea[id*='_textarea'].commentthread_textarea, textarea.commentthread_textarea",
                    )
                )
            )

            # Фокус/скролл
            try:
                comment_area.click()
            except Exception:
                pass
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", comment_area)
            self.human_delay(0.3, 0.8)

            # Очистка и ввод текста (JS для эмодзи)
            self._activate_textarea(comment_area)
            self.human_delay(0.3, 0.8)

            self.driver.execute_script("arguments[0].value='';", comment_area)
            self._js_set_value_and_events(comment_area, comment_text)
            self.human_delay(0.2, 0.5)

            # Из ID textarea строим ID контейнера/кнопки
            textarea_id = comment_area.get_attribute("id") or ""
            base_id = textarea_id[:-9] if textarea_id.endswith(
                "_textarea") else textarea_id
            submit_container_id = f"{base_id}_submit_container"
            submit_id = f"{base_id}_submit"

            submit_el = None
            try:
                # если Steam отреагировал — контейнер станет видимым
                submit_container = self._wait_submit_container_visible(
                    submit_container_id, timeout=8)
                submit_el = self.driver.find_element(By.ID, submit_id)
            except TimeoutException:
                # UI не раскрылся — берём кнопку напрямую, даже если контейнер скрыт
                try:
                    submit_el = self.driver.find_element(By.ID, submit_id)
                except NoSuchElementException:
                    # крайний случай: попробуем насильно показать контейнер (не всегда нужно)
                    try:
                        self.driver.execute_script(
                            "const el=document.getElementById(arguments[0]); if(el) el.style.display='block';",
                            submit_container_id)
                        submit_el = self.driver.find_element(By.ID, submit_id)
                    except Exception:
                        submit_el = None

            if not submit_el:
                raise TimeoutException(f"Не удалось найти submit: #{submit_id}")

            # 5) клик по submit (JS-путь работает и на скрытом элементе)
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});",
                                       submit_el)
            self.human_delay(0.2, 0.6)
            try:
                if self.is_visible_js(submit_el):
                    submit_el.click()
                else:
                    self.driver.execute_script("arguments[0].click();", submit_el)
            except Exception:
                self.driver.execute_script("arguments[0].click();", submit_el)

            # 6) подтверждение успеха (очистка или скрытие контейнера)
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: ((comment_area.get_attribute(
                        'value') or '').strip() == '') or
                              (self.is_visible_js(
                                  d.find_element(By.ID, submit_container_id)) is False)
                )
            except TimeoutException:
                pass

            # Находим кнопку по свежему id и кликаем (JS-фоллбэк)
            self._click_submit_by_id(submit_id)

            # Подтверждение: textarea очистилась или контейнер скрылся
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: ((comment_area.get_attribute("value") or "").strip() == "")
                    or (not self.is_visible_js(d.find_element(By.ID, submit_container_id)))
                )
            except TimeoutException:
                pass

            print("✅ Комментарий отправлен")
            self.human_delay(2.5, 5.0)
            return True

        except Exception as e:
            print(f"❌ Ошибка при отправке комментария: {e}")
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.driver.save_screenshot(f"error_{ts}.png")
                print("📸 Сделан скриншот ошибки")
            except Exception:
                pass
            return False

    # ----------------------------
    # Run
    # ----------------------------
    def run(self):
        if not STEAM_LOGIN_SECURE or not STEAM_GROUPS:
            missing = []
            if not STEAM_LOGIN_SECURE:
                missing.append("STEAM_LOGIN_SECURE")
            if not STEAM_GROUPS:
                missing.append("STEAM_GROUPS")
            print(f"❌ Отсутствуют обязательные переменные: {', '.join(missing)}")
            return

        # инициализация драйвера
        self.driver = self.get_stealth_driver()
        self.wait = WebDriverWait(self.driver, 25)

        # аккуратное завершение
        def _graceful_exit(*_):
            try:
                if self.driver:
                    self.driver.quit()
            finally:
                try:
                    shutil.rmtree(self.temp_dir, ignore_errors=True)
                except Exception:
                    pass
                os._exit(0)

        signal.signal(signal.SIGTERM, _graceful_exit)
        signal.signal(signal.SIGINT, _graceful_exit)

        # авторизация
        if not self.login_with_cookies():
            print("❌ Не удалось авторизоваться")
            _graceful_exit()

        # цикл по группам
        ok, fail = 0, 0
        print(f"📊 Начинаю отправку комментариев в {len(STEAM_GROUPS)} групп(ы)...")
        while True:
            for i, url in enumerate(STEAM_GROUPS, 1):
                if not url:
                    continue
                print(f"\n📝 Группа {i}/{len(STEAM_GROUPS)}: {url}")
                if self.post_comment_to_group(url, MESSAGE):
                    ok += 1
                    print(f"✅ Успешно: {ok}")
                else:
                    fail += 1
                    print(f"❌ Неудачно: {fail}")

                if i < len(STEAM_GROUPS):
                    wait_sec = random.randint(5, 10)
                    print(f"⏳ Ожидание {wait_sec} сек перед следующей группой…")
                    time.sleep(wait_sec)
            time.sleep(300)

        _graceful_exit()


if __name__ == "__main__":
    bot = SteamCommentBot()
    bot.run()
