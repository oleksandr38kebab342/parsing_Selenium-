"""Пошук товару на brain.com.ua та отримання URL першого результату."""
from load_django import *  # noqa: F401,F403 - необхідно ініціалізувати Django
from parser_app.models import *  # noqa: F401,F403 - моделі можуть знадобитися пізніше
import argparse
from dataclasses import dataclass
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


SEARCH_INPUT_SELECTOR = (By.CSS_SELECTOR, "input.quick-search-input")
SEARCH_BUTTON_XPATH = "/html/body/header/div[2]/div/div/div[3]/div[1]/form/input[2]"
FIRST_RESULT_XPATH = "/html/body/div[4]/div[1]/div/div/div[2]/div/div[2]/div[2]/div[1]/div/div[1]/div[1]/div[1]/div"


@dataclass
class SearchResult:
    url: str


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    # З UI: headless не використовується
    return webdriver.Chrome(options=options)


def find_product_url(query: str, timeout: int = 20) -> Optional[SearchResult]:
    driver = build_driver()
    try:
        driver.get("https://brain.com.ua/")
        wait = WebDriverWait(driver, timeout)

        search_input = wait.until(EC.presence_of_element_located(SEARCH_INPUT_SELECTOR))
        search_input.clear()
        search_input.send_keys(query)

        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, SEARCH_BUTTON_XPATH)))
        search_button.click()

        # Очікуємо перший товар у видачі та клікаємо по ньому
        first_result = wait.until(EC.element_to_be_clickable((By.XPATH, FIRST_RESULT_XPATH)))
        first_result.click()

        wait.until(lambda drv: drv.current_url != "https://brain.com.ua/")
        return SearchResult(url=driver.current_url)
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Пошук першого товару за назвою.")
    parser.add_argument("query", nargs="?", default="Apple iPhone 15 128GB Black", help="Запит для пошуку")
    args = parser.parse_args()

    result = find_product_url(args.query)
    if not result:
        print("Не вдалося отримати результат.")
        return

    print(f"URL знайденого товару: {result.url}")


if __name__ == "__main__":
    main()
