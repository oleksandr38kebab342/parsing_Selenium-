"""Find product on brain.com.ua and get URL of first result."""
from load_django import *  # noqa: F401,F403 - initialize Django
from parser_app.models import *  # noqa: F401,F403 - models may be needed later
import argparse
from dataclasses import dataclass
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time


SEARCH_INPUT_SELECTOR = (By.CSS_SELECTOR, "input.quick-search-input")
SEARCH_BUTTON_SELECTOR = (By.CSS_SELECTOR, "input.qsr-submit")
FIRST_RESULT_SELECTOR = (By.CSS_SELECTOR, ".br-pp.br-pp-ex.goods-block__item[data-pid]")


@dataclass
class SearchResult:
    url: str


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    # With UI: headless mode not used
    return webdriver.Chrome(options=options)


def find_product_url(query: str, timeout: int = 20) -> Optional[SearchResult]:
    driver = build_driver()
    try:
        driver.get("https://brain.com.ua/")
        wait = WebDriverWait(driver, timeout)
        time.sleep(2.0)

        # Wait for search input to be present and visible
        search_input = wait.until(EC.presence_of_element_located(SEARCH_INPUT_SELECTOR))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_input)
        time.sleep(0.5)
        
        # Click to focus
        try:
            search_input.click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script("arguments[0].click();", search_input)
        
        time.sleep(0.3)
        
        # Clear and send keys using JavaScript as fallback
        try:
            search_input.clear()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            pass
        
        # Use JavaScript to set value if send_keys fails
        try:
            search_input.send_keys(query)
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script("arguments[0].value = arguments[1];", search_input, query)
            # Trigger input event
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
        
        time.sleep(0.5)

        search_button = wait.until(EC.element_to_be_clickable(SEARCH_BUTTON_SELECTOR))
        try:
            search_button.click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script("arguments[0].click();", search_button)
        
        time.sleep(2.0)  # Wait for search results to load

        # Wait for first product in results and click on it
        first_result = wait.until(EC.presence_of_element_located(FIRST_RESULT_SELECTOR))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first_result)
        time.sleep(0.5)
        
        # Get the link from the first product card
        try:
            product_link = first_result.find_element(By.CSS_SELECTOR, "a[href*='/ukr/']")
            product_url = product_link.get_attribute("href")
            if product_url:
                driver.get(product_url)
                time.sleep(1.0)
                return SearchResult(url=driver.current_url)
        except (NoSuchElementException, AttributeError):
            pass
        
        # Fallback: try to click on the card itself
        try:
            first_result.click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script("arguments[0].click();", first_result)

        wait.until(lambda drv: drv.current_url != "https://brain.com.ua/")
        return SearchResult(url=driver.current_url)
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Find first product by name.")
    parser.add_argument("query", nargs="?", default="Apple iPhone 15 128GB Black", help="Search query")
    args = parser.parse_args()

    result = find_product_url(args.query)
    if not result:
        print("Failed to get result.")
        return

    print(f"Found product URL: {result.url}")


if __name__ == "__main__":
    main()
