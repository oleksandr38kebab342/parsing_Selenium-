"""Парсинг сторінки товару brain.com.ua через Selenium, друк і збереження у БД."""
from load_django import *  # noqa: F401,F403 - ініціалізація Django
from parser_app.models import *  # noqa: F401,F403 - доступ до моделей
import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

JSONLD_SELECTOR = (By.CSS_SELECTOR, 'script[type="application/ld+json"]')
REVIEWS_XPATH = "//*[@id=\"fast-navigation-block-static\"]/div[2]/div[1]/div/a/span"
CHAR_CONTAINER_XPATH = "//*[@id=\"br-characteristics\"]"
CHAR_SCROLL_SELECTOR = "#br-characteristics .br-pr-scroll.br-pr-no-scroll.open"
CHAR_TAB_XPATH = "//*[@id=\"fast-navigation-block-static\"]/div[1]/div/ul/li[3]/a"
SEARCH_INPUT_SELECTOR = (By.CSS_SELECTOR, "input.quick-search-input")
# Альтернативний XPATH, наданий користувачем
SEARCH_INPUT_XPATH_ALT = "/html/body/header/div[2]/div/div/div[2]/form/input[1]"
SEARCH_BUTTON_XPATH = "/html/body/header/div[2]/div/div/div[3]/div[1]/form/input[2]"
FIRST_RESULT_XPATH = "/html/body/div[4]/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[1]/div[1]/div[1]/div"
# Стабільніший селектор для першої картки товару на видачі
FIRST_CARD_SELECTOR = ".br-pp.br-pp-ex.goods-block__item.br-pcg.br-series"


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)


def find_product_url(query: str, timeout: int = 20) -> Optional[str]:
    driver = build_driver()
    try:
        driver.get("https://brain.com.ua/")
        wait = WebDriverWait(driver, timeout)
        time.sleep(1.0)

        # Дочекаємося видимості та клікабельності інпуту
        try:
            search_input = wait.until(EC.visibility_of_element_located(SEARCH_INPUT_SELECTOR))
        except Exception:
            search_input = wait.until(EC.visibility_of_element_located((By.XPATH, SEARCH_INPUT_XPATH_ALT)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_input)
        time.sleep(0.5)
        search_input.click()
        time.sleep(0.3)
        try:
            search_input.clear()
        except Exception:
            pass
        search_input.send_keys(query)

        time.sleep(0.5)
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, SEARCH_BUTTON_XPATH)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_button)
        time.sleep(0.3)
        try:
            search_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", search_button)

        time.sleep(1.0)
        # Спроба через стабільний селектор: взяти href і перейти напряму
        try:
            first_card = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, FIRST_CARD_SELECTOR)))
            link = first_card.find_element(By.CSS_SELECTOR, "a[href]")
            href = link.get_attribute("href")
            if href:
                driver.get(href)
                time.sleep(0.8)
                wait.until(lambda drv: "/search" not in drv.current_url)
                return driver.current_url
        except Exception:
            pass

        # Фолбек: клік по попередньому XPATH
        first_result = wait.until(EC.element_to_be_clickable((By.XPATH, FIRST_RESULT_XPATH)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_result)
        time.sleep(0.3)
        try:
            first_result.click()
        except Exception:
            driver.execute_script("arguments[0].click();", first_result)

        time.sleep(0.8)
        wait.until(lambda drv: "/search" not in drv.current_url)
        return driver.current_url
    finally:
        driver.quit()


def load_jsonld(blocks: List[str]) -> Optional[Dict[str, Any]]:
    for block in blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Product":
                    return item
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    return None


def expand_characteristics(driver: webdriver.Chrome, timeout: int) -> None:
    """Перейти на вкладку характеристик через навігацію і (за потреби) розкрити список."""
    wait = WebDriverWait(driver, timeout)
    # 1) Клікнути на вкладку "Характеристики" через верхню навігацію
    try:
        tab = wait.until(EC.element_to_be_clickable((By.XPATH, CHAR_TAB_XPATH)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab)
        time.sleep(0.2)
        try:
            tab.click()
        except Exception:
            driver.execute_script("arguments[0].click();", tab)
        time.sleep(0.6)
    except Exception:
        pass

    # 2) За наявності — натиснути "Всі характеристики" для повного списку
    try:
        btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.br-prs-button")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        time.sleep(0.2)
        try:
            btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.4)
    except Exception:
        # Якщо кнопки немає — ігноруємо
        pass


def extract_characteristics(driver: webdriver.Chrome, timeout: int) -> Dict[str, str]:
    wait = WebDriverWait(driver, timeout)
    characteristics: Dict[str, str] = {}
    try:
        container = wait.until(EC.presence_of_element_located((By.XPATH, CHAR_CONTAINER_XPATH)))
    except Exception:
        return characteristics
    # Знайти скрол-контейнер із відкритими характеристиками, якщо присутній
    scroll_container = None
    try:
        scroll_container = container.find_element(By.CSS_SELECTOR, CHAR_SCROLL_SELECTOR)
    except Exception:
        scroll_container = container

    # Елементи характеристик представлені як блоки .br-pr-chr-item
    items = scroll_container.find_elements(By.CSS_SELECTOR, ".br-pr-chr-item")
    for item in items:
        # Кожен item містить кілька внутрішніх <div>, де кожен має два <span>
        rows = item.find_elements(By.XPATH, ".//div[span] | .//div[contains(@class, 'flex')]")
        for row in rows:
            spans = row.find_elements(By.TAG_NAME, "span")
            if len(spans) < 2:
                continue
            key = spans[0].text.strip()
            value = spans[1].text.strip()
            if key:
                characteristics[key] = value
    return characteristics


def derive_field_from_characteristics(characteristics: Dict[str, str], candidates: Tuple[str, ...]) -> str:
    for key, value in characteristics.items():
        key_lower = key.lower()
        if any(candidate.lower() in key_lower for candidate in candidates):
            return value
    return ""


def parse_product(url: str, timeout: int = 25) -> Dict[str, Any]:
    driver = build_driver()
    try:
        driver.get(url)
        wait = WebDriverWait(driver, timeout)

        jsonld_blocks = [element.get_attribute("innerHTML") for element in wait.until(EC.presence_of_all_elements_located(JSONLD_SELECTOR))]
        jsonld = load_jsonld(jsonld_blocks) or {}

        # Розгорнути усі характеристики перед парсингом
        expand_characteristics(driver, timeout)

        characteristics = extract_characteristics(driver, timeout)
        review_count = 0
        try:
            review_el = wait.until(EC.presence_of_element_located((By.XPATH, REVIEWS_XPATH)))
            review_text = review_el.text.strip()
            if review_text.isdigit():
                review_count = int(review_text)
        except Exception:
            review_count = 0

        images = jsonld.get("image") if isinstance(jsonld.get("image"), list) else []
        if not images:
            images = [img.get_attribute("src") for img in driver.find_elements(By.CSS_SELECTOR, "img") if img.get_attribute("src")]

        name = jsonld.get("name", "")
        description = jsonld.get("description", "")
        sku = jsonld.get("sku", "")
        mpn = jsonld.get("mpn", "")
        brand_name = ""
        brand = jsonld.get("brand")
        if isinstance(brand, dict):
            brand_name = brand.get("name", "")

        offers = jsonld.get("offers") or {}
        price = offers.get("price") if isinstance(offers, dict) else None
        currency = offers.get("priceCurrency") if isinstance(offers, dict) else "UAH"

        color = derive_field_from_characteristics(characteristics, ("Колір", "колір", "цвет"))
        memory = derive_field_from_characteristics(characteristics, ("Об'єм пам'яті", "пам", "память"))
        screen_size = derive_field_from_characteristics(characteristics, ("Діагональ екрану", "Діагональ", "діагональ", "Диагональ"))
        resolution = derive_field_from_characteristics(characteristics, ("Роздільна здатність дисплея", "Роздільна здатність екрану", "роздільна", "Разрешение"))

        # Прості евристики, якщо поле не знайшлося у характеристиках
        if not memory:
            match = re.search(r"(\d+\s?GB)", name, re.IGNORECASE)
            if match:
                memory = match.group(1)
        if not color:
            for candidate in ["Black", "White", "Blue", "Pink", "Green"]:
                if candidate.lower() in name.lower():
                    color = candidate
                    break

        # Перелік відсутніх полів більше не виводимо

        data = {
            "Повна назва товару": name,
            "Посилання": driver.current_url,
            "Опис": description,
            "Код товару": sku,
            "MPN": mpn,
            "Виробник": brand_name,
            "Колір": color,
            "Об'єм пам'яті": memory,
            "Ціна звичайна": float(price) if price else None,
            "Ціна акційна": None,
            "Валюта": currency or "UAH",
            "Усі фото товару": images,
            "Рейтинг": None,
            "Кількість відгуків": review_count,
            "Діагональ екрану": screen_size,
            "Роздільна здатність дисплея": resolution,
            "Характеристики товару": characteristics,
        }
        return data
    finally:
        driver.quit()


def save_product(data: Dict[str, Any]) -> None:
    # Перетворити українські ключі назад до моделі перед збереженням
    Product.objects.update_or_create(
        sku=data.get("Код товару", ""),
        defaults={
            "name": data.get("Повна назва товару", ""),
            "url": data.get("Посилання", ""),
            "description": data.get("Опис", ""),
            "mpn": data.get("MPN", ""),
            "manufacturer": data.get("Виробник", ""),
            "color": data.get("Колір", ""),
            "memory": data.get("Об'єм пам'яті", ""),
            "price": data.get("Ціна звичайна"),
            "sale_price": data.get("Ціна акційна"),
            "currency": data.get("Валюта", "UAH"),
            "images": data.get("Усі фото товару", []),
            "rating": data.get("Рейтинг"),
            "review_count": data.get("Кількість відгуків", 0),
            "screen_size": data.get("Діагональ екрану", ""),
            "resolution": data.get("Роздільна здатність дисплея", ""),
            "characteristics": data.get("Характеристики товару", {}),
        },
    )


def write_to_file(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Парсинг сторінки товару brain.com.ua")
    parser.add_argument("--url", help="Пряме посилання на товар")
    parser.add_argument("--query", default="Apple iPhone 15 128GB Black", help="Запит для пошуку, якщо немає url")
    parser.add_argument("--timeout", type=int, default=25, help="Таймаут очікування елементів")
    parser.add_argument("--no-save", action="store_true", help="Не зберігати у базу даних")
    args = parser.parse_args()

    target_url = args.url
    if not target_url:
        search_result = find_product_url(args.query, timeout=args.timeout)
        if not search_result:
            print("Не знайдено товар за заданим запитом.")
            return
        target_url = search_result

    data = parse_product(target_url, timeout=args.timeout)
    print(json.dumps(data, ensure_ascii=False, indent=4))

    results_dir = Path(__file__).resolve().parent.parent / "results"
    write_to_file(data, results_dir / "last_product.json")

    if not args.no_save:
        save_product(data)
        print("Дані збережено у базу даних (update_or_create по SKU).")


if __name__ == "__main__":
    main()
