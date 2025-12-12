"""Parse brain.com.ua product page using Selenium, print and save to DB."""
from load_django import *  # noqa: F401,F403 - initialize Django
from parser_app.models import *  # noqa: F401,F403 - access to models
import argparse
import json
import re
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple

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

JSONLD_SELECTOR = (By.CSS_SELECTOR, 'script[type="application/ld+json"]')
REVIEWS_SELECTOR = (By.CSS_SELECTOR, ".comments-average-rating-stars + .br-pp-r span")
REVIEWS_ALT_SELECTOR = (By.CSS_SELECTOR, "span.forbid-click.reviews-count span")
# Use ID-based selector for characteristics container
CHAR_CONTAINER_SELECTOR = (By.ID, "br-pr-7")
CHAR_TAB_SELECTOR = (By.CSS_SELECTOR, "a.scroll-to-element-after[href='#br-characteristics']")
SEARCH_INPUT_SELECTOR = (By.CSS_SELECTOR, "input.quick-search-input")
# Alternative selector for search input (relative CSS selector instead of absolute XPath)
SEARCH_INPUT_ALT_SELECTOR = (By.CSS_SELECTOR, "header form input.quick-search-input, header input[type='text']")
SEARCH_BUTTON_SELECTOR = (By.CSS_SELECTOR, "input.qsr-submit")
FIRST_RESULT_SELECTOR = (By.CSS_SELECTOR, ".br-pp.br-pp-ex.goods-block__item[data-pid]")
# More stable selector for first product card in results
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
        time.sleep(2.0)

        # Wait for search input to be present and visible
        try:
            search_input = wait.until(EC.presence_of_element_located(SEARCH_INPUT_SELECTOR))
        except (TimeoutException, NoSuchElementException):
            try:
                search_input = wait.until(EC.presence_of_element_located(SEARCH_INPUT_ALT_SELECTOR))
            except (TimeoutException, NoSuchElementException):
                # Last resort: try to find any input in header
                search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "header input[type='text']")))
        
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
                return driver.current_url
        except (NoSuchElementException, AttributeError):
            pass
        
        # Fallback: try to click on the card itself
        try:
            first_result.click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script("arguments[0].click();", first_result)

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
    """Click on characteristics tab to scroll to characteristics section and expand all characteristics."""
    wait = WebDriverWait(driver, timeout)
    
    # Step 1: Click on characteristics tab
    try:
        tab = wait.until(EC.element_to_be_clickable(CHAR_TAB_SELECTOR))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab)
        time.sleep(0.3)
        try:
            tab.click()
        except (ElementNotInteractableException, ElementClickInterceptedException):
            driver.execute_script("arguments[0].click();", tab)
        time.sleep(1.0)  # Wait for characteristics section to load
    except (TimeoutException, NoSuchElementException):
        pass
    
    # Step 2: Click on "All characteristics" button to expand all characteristics
    try:
        # Try multiple selectors to find the button
        button = None
        
        # Method 1: Find by class and check text
        try:
            buttons = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.br-prs-button")))
            for btn in buttons:
                if btn.is_displayed():
                    btn_text = btn.text.strip()
                    # Check for button text (Ukrainian: "Всі характеристики" or "Приховати")
                    if "Всі характеристики" in btn_text or "Приховати" in btn_text:
                        button = btn
                        break
        except (TimeoutException, NoSuchElementException):
            pass
        
        # Method 2: Find by XPath with text content
        if not button:
            try:
                button = driver.find_element(By.XPATH, "//button[@class='br-prs-button']//span[contains(text(), 'Всі характеристики')]/..")
            except NoSuchElementException:
                pass
        
        # Method 3: Find by XPath with any span containing the text
        if not button:
            try:
                button = driver.find_element(By.XPATH, "//button[contains(@class, 'br-prs-button') and contains(., 'Всі характеристики')]")
            except NoSuchElementException:
                pass
        
        if button:
            # Scroll to button
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", button)
            time.sleep(0.3)
            # Try to click
            try:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                else:
                    driver.execute_script("arguments[0].click();", button)
            except (ElementNotInteractableException, ElementClickInterceptedException):
                driver.execute_script("arguments[0].click();", button)
            time.sleep(1.5)  # Wait for characteristics to expand
            print("Successfully clicked 'All characteristics' button")
        else:
            print("Warning: 'All characteristics' button not found")
            
    except (TimeoutException, NoSuchElementException, ElementNotInteractableException, ElementClickInterceptedException, AttributeError) as e:
        print(f"Error clicking 'All characteristics' button: {e}")
        pass


def _first_text(element) -> str:
    """Helper function for safe text extraction from element"""
    try:
        if element:
            return element.text.strip()
    except (AttributeError, NoSuchElementException):
        pass
    return ""


def extract_characteristics(driver: webdriver.Chrome, timeout: int) -> Dict[str, str]:
    """Parse all characteristics from product page.
    
    Finds characteristics container (#br-pr-7 or #br-characteristics)
    and extracts all key-value pairs from div elements containing span children.
    
    Uses CSS selectors span:nth-child(1) and span:nth-child(2) for precise selection.
    Also tries to expand any "Show more" buttons to reveal hidden characteristics.
    
    Returns:
        Dict[str, str]: Dictionary with all characteristics {key: value}
    """
    wait = WebDriverWait(driver, timeout)
    characteristics: Dict[str, str] = {}
    
    # Try to find characteristics container
    container = None
    try:
        container = wait.until(EC.presence_of_element_located(CHAR_CONTAINER_SELECTOR))
    except (TimeoutException, NoSuchElementException):
        # Try alternative selector
        try:
            container = driver.find_element(By.ID, "br-characteristics")
        except NoSuchElementException:
            return characteristics
    
    if not container:
        return characteristics
    
    # Scroll to container to ensure all characteristics are visible
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'start', behavior: 'smooth'});", container)
        time.sleep(0.5)  # Wait for scroll to complete
    except (AttributeError, TypeError):
        pass
    
    # Try to expand any "Show more" or similar buttons inside container
    try:
        expand_buttons = container.find_elements(By.CSS_SELECTOR, "a[class*='more'], button[class*='more'], a[class*='expand'], button[class*='expand']")
        for btn in expand_buttons:
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.3)
            except (ElementNotInteractableException, ElementClickInterceptedException, AttributeError):
                pass
    except (NoSuchElementException, AttributeError):
        pass
    
    # Scroll through container to load all characteristics (lazy loading)
    try:
        last_height = driver.execute_script("return arguments[0].scrollHeight;", container)
        scroll_position = 0
        scroll_step = 300
        max_scrolls = 10
        scroll_count = 0
        
        while scroll_count < max_scrolls:
            driver.execute_script("arguments[0].scrollTop = arguments[1];", container, scroll_position)
            time.sleep(0.2)
            new_height = driver.execute_script("return arguments[0].scrollHeight;", container)
            if new_height == last_height and scroll_position > 0:
                break
            last_height = new_height
            scroll_position += scroll_step
            scroll_count += 1
        
        # Scroll back to top
        driver.execute_script("arguments[0].scrollTop = 0;", container)
        time.sleep(0.2)
    except (AttributeError, TypeError):
        pass
    
    # Get all div elements that contain characteristics
    # Strategy: find divs that have span:nth-child(1) (key) and span:nth-child(2) (value)
    rows = []
    try:
        # First, try to find divs with direct span children
        all_divs = container.find_elements(By.CSS_SELECTOR, "div")
        for div in all_divs:
            try:
                # Check if this div has the structure we expect (span:nth-child(1) and span:nth-child(2))
                key_span = div.find_element(By.CSS_SELECTOR, "span:nth-child(1)")
                if key_span:
                    rows.append(div)
            except NoSuchElementException:
                continue
    except (NoSuchElementException, AttributeError):
        pass
    
    # If no rows found with specific structure, try all divs
    if not rows:
        try:
            rows = container.find_elements(By.TAG_NAME, "div")
        except NoSuchElementException:
            return characteristics
    
    for row in rows:
        try:
            # Skip if row is empty or doesn't contain text
            row_text = row.text.strip()
            if not row_text:
                continue
            
            # Use CSS selector for direct child spans (more precise)
            key_el = None
            val_el = None
            
            try:
                key_el = row.find_element(By.CSS_SELECTOR, "span:nth-child(1)")
            except NoSuchElementException:
                # Fallback: try to get first direct child span using CSS selector
                try:
                    key_el = row.find_element(By.CSS_SELECTOR, "> span:first-child")
                except NoSuchElementException:
                    try:
                        key_el = row.find_element(By.CSS_SELECTOR, "span:first-of-type")
                    except NoSuchElementException:
                        key_el = None
            
            try:
                val_el = row.find_element(By.CSS_SELECTOR, "span:nth-child(2)")
            except NoSuchElementException:
                # Fallback: try to get second direct child span using CSS selector
                try:
                    val_el = row.find_element(By.CSS_SELECTOR, "> span:nth-of-type(2)")
                except NoSuchElementException:
                    try:
                        val_el = row.find_element(By.CSS_SELECTOR, "span:nth-of-type(2)")
                    except NoSuchElementException:
                        val_el = None
            
            key = _first_text(key_el)
            value = _first_text(val_el)
            
            # If value is empty, try to get from links
            if not value:
                try:
                    links = row.find_elements(By.TAG_NAME, "a")
                    if links:
                        link_texts = [link.text.strip() for link in links if link.text.strip()]
                        value = ", ".join([t for t in link_texts if t])
                except (NoSuchElementException, AttributeError):
                    pass
            
            # If still no value, but we have key, try to extract from row text
            if key and not value:
                # Sometimes value might be in the same text as key, separated by colon or dash
                full_text = row_text
                if ":" in full_text:
                    parts = full_text.split(":", 1)
                    if len(parts) == 2 and parts[0].strip() == key:
                        value = parts[1].strip()
            
            # Clean up whitespace
            key = ' '.join(key.split())
            value = ' '.join(value.split())
            
            # Save if key exists (value can be empty for some characteristics)
            if key:
                characteristics[key] = value
                
        except (AttributeError, NoSuchElementException, TypeError, ValueError) as e:
            # Continue to next row if this one fails
            continue
    
    return characteristics


def derive_field_from_characteristics(characteristics: Dict[str, str], candidates: Tuple[str, ...]) -> Optional[str]:
    """Find a characteristic value by matching key candidates."""
    for key, value in characteristics.items():
        key_lower = key.lower()
        if any(candidate.lower() in key_lower for candidate in candidates):
            return value if value else None
    return None


def parse_product(url: str, timeout: int = 25) -> Dict[str, Any]:
    missing_fields: List[str] = []

    def mark_missing(field_name: str, is_missing: bool) -> None:
        if is_missing and field_name not in missing_fields:
            missing_fields.append(field_name)

    driver = build_driver()
    try:
        driver.get(url)
        wait = WebDriverWait(driver, timeout)

        # Extract JSON-LD blocks with error handling
        jsonld = None
        try:
            jsonld_blocks = [element.get_attribute("innerHTML") for element in wait.until(EC.presence_of_all_elements_located(JSONLD_SELECTOR))]
            jsonld = load_jsonld(jsonld_blocks) or {}
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Failed to extract JSON-LD: {e}")
            jsonld = {}

        # Expand all characteristics before parsing
        expand_characteristics(driver, timeout)

        # Extract characteristics
        characteristics = {}
        try:
            characteristics = extract_characteristics(driver, timeout)
            if not characteristics:
                print("Warning: No characteristics found. Trying alternative extraction methods...")
                # Try to find characteristics in alternative locations
                try:
                    alt_container = driver.find_element(By.ID, "br-characteristics")
                    if alt_container:
                        # Try alternative extraction
                        all_text = alt_container.text
                        if all_text:
                            print(f"Found text in alternative container: {len(all_text)} characters")
                except (NoSuchElementException, AttributeError):
                    pass
        except (TimeoutException, NoSuchElementException, AttributeError, TypeError, ValueError) as e:
            print(f"Failed to extract characteristics: {e}")
            import traceback
            traceback.print_exc()
            characteristics = {}

        # Extract review count with granular error handling
        review_count = None
        try:
            # Try first selector
            try:
                review_el = wait.until(EC.presence_of_element_located(REVIEWS_SELECTOR))
                review_text = review_el.text.strip()
            except (TimeoutException, NoSuchElementException):
                # Try alternative selector
                review_el = wait.until(EC.presence_of_element_located(REVIEWS_ALT_SELECTOR))
                review_text = review_el.text.strip()
            
            if review_text and review_text.isdigit():
                review_count = int(review_text)
        except (TimeoutException, NoSuchElementException):
            review_count = None
        except (ValueError, AttributeError) as e:
            print(f"Failed to parse review count: {e}")
            review_count = None

        # Extract images with error handling
        images = []
        try:
            images = jsonld.get("image") if isinstance(jsonld.get("image"), list) else []
            if not images:
                images = [img.get_attribute("src") for img in driver.find_elements(By.CSS_SELECTOR, "img") if img.get_attribute("src")]
        except (AttributeError, NoSuchElementException) as e:
            print(f"Failed to extract images: {e}")
            images = []

        # Extract basic fields from JSON-LD with None defaults
        name = jsonld.get("name") if jsonld else None
        description = jsonld.get("description") if jsonld else None
        sku = jsonld.get("sku") if jsonld else None
        mpn = jsonld.get("mpn") if jsonld else None
        
        brand_name = None
        try:
            brand = jsonld.get("brand")
            if isinstance(brand, dict):
                brand_name = brand.get("name")
        except (AttributeError, KeyError) as e:
            print(f"Failed to extract brand: {e}")
            brand_name = None

        # Extract price and currency
        price = None
        currency = "UAH"
        try:
            offers = jsonld.get("offers") or {}
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency", "UAH")
        except (AttributeError, KeyError) as e:
            print(f"Failed to extract price: {e}")

        # Derive fields from characteristics, return None if not found
        color = derive_field_from_characteristics(characteristics, ("Колір", "колір", "цвет", "Color"))
        if not color:
            color = characteristics.get("Колір")
        
        memory = derive_field_from_characteristics(characteristics, ("Об'єм пам'яті", "пам", "память", "Memory", "Вбудована пам'ять"))
        if not memory:
            memory = characteristics.get("Вбудована пам'ять")
        
        screen_size = derive_field_from_characteristics(characteristics, ("Діагональ екрану", "Діагональ", "діагональ", "Диагональ", "Screen", "Display"))
        if not screen_size:
            screen_size = characteristics.get("Діагональ екрану")
        
        resolution = derive_field_from_characteristics(characteristics, ("Роздільна здатність дисплея", "Роздільна здатність екрану", "роздільна", "Разрешение", "Resolution"))
        if not resolution:
            resolution = characteristics.get("Роздільна здатність екрану")
        
        # Override brand if found in characteristics
        # Note: Ukrainian keys (like "Виробник", "Модель") are data from the website, not code
        if not brand_name and characteristics:
            brand_name = characteristics.get("Виробник")
        
        # Override name with model from characteristics if available
        if characteristics.get("Модель"):
            name = characteristics.get("Модель")

        # Simple heuristics if field not found in characteristics
        if not memory and name:
            match = re.search(r"(\d+\s?GB)", name, re.IGNORECASE)
            if match:
                memory = match.group(1)
        
        if not color and name:
            for candidate in ["Black", "White", "Blue", "Pink", "Green", "Red", "Yellow", "Purple"]:
                if candidate.lower() in name.lower():
                    color = candidate
                    break
        
        # Additional search by keywords in all characteristics
        for key, value in characteristics.items():
            key_lower = key.lower()
            if ("діагональ" in key_lower or "диагональ" in key_lower) and not screen_size:
                screen_size = value
            if ("розділь" in key_lower or "разреш" in key_lower) and not resolution:
                resolution = value

        # Build data dictionary with English keys
        data = {
            "name": name,
            "url": driver.current_url,
            "description": description,
            "sku": sku,
            "mpn": mpn,
            "manufacturer": brand_name,
            "color": color,
            "memory": memory,
            "price": float(price) if price else None,
            "sale_price": None,
            "currency": currency or "UAH",
            "images": images,
            "rating": None,
            "review_count": review_count,
            "screen_size": screen_size,
            "resolution": resolution,
            "characteristics": characteristics,
            "raw_jsonld": jsonld or {},
        }

        # Mark missing fields including characteristics presence
        mark_missing("name", not data.get("name"))
        mark_missing("sku", not data.get("sku"))
        mark_missing("manufacturer", not data.get("manufacturer"))
        mark_missing("color", not data.get("color"))
        mark_missing("memory", not data.get("memory"))
        mark_missing("screen_size", not data.get("screen_size"))
        mark_missing("resolution", not data.get("resolution"))
        mark_missing("characteristics", not data.get("characteristics"))
        data["missing_fields"] = missing_fields
        return data
    finally:
        driver.quit()


def save_product(data: Dict[str, Any]) -> None:
    """Save product to database. Uses create() to allow duplicates across categories."""
    Product.objects.create(
        name=data.get("name") or "",
        url=data.get("url") or "",
        sku=data.get("sku") or "",
        description=data.get("description"),
        mpn=data.get("mpn"),
        manufacturer=data.get("manufacturer"),
        color=data.get("color"),
        memory=data.get("memory"),
        price=data.get("price"),
        sale_price=data.get("sale_price"),
        currency=data.get("currency", "UAH"),
        images=data.get("images", []),
        rating=data.get("rating"),
        review_count=data.get("review_count") or 0,
        screen_size=data.get("screen_size"),
        resolution=data.get("resolution"),
        characteristics=data.get("characteristics", {}),
        missing_fields=data.get("missing_fields", []),
        raw_jsonld=data.get("raw_jsonld", {}),
    )


def write_to_file(data: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse brain.com.ua product page")
    parser.add_argument("--url", help="Direct product link")
    parser.add_argument("--query", default="Apple iPhone 15 128GB Black", help="Search query if no url provided")
    parser.add_argument("--timeout", type=int, default=25, help="Element wait timeout")
    parser.add_argument("--no-save", action="store_true", help="Do not save to database")
    args = parser.parse_args()

    target_url = args.url
    if not target_url:
        search_result = find_product_url(args.query, timeout=args.timeout)
        if not search_result:
            print("Product not found by given query.")
            return
        target_url = search_result

    data = parse_product(target_url, timeout=args.timeout)
    
    print("\n=== Parsed Product Data ===")
    pprint(data, width=120, compact=False)

    results_dir = Path(__file__).resolve().parent.parent / "results"
    write_to_file(data, results_dir / "last_product.json")

    if not args.no_save:
        save_product(data)
        print("\nData saved to database.")


if __name__ == "__main__":
    main()
