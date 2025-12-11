"""Завантаження JSON з results та збереження товару у базу даних."""
from load_django import *  # noqa: F401,F403 - ініціалізація Django
from parser_app.models import *  # noqa: F401,F403 - доступ до моделей
import argparse
import json
from pathlib import Path
from typing import Any, Dict


def save_from_json(path: Path) -> None:
    if not path.exists():
        print(f"Файл {path} не знайдено.")
        return
    data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    Product.objects.update_or_create(
        sku=data.get("sku", ""),
        defaults={
            "name": data.get("name", ""),
            "url": data.get("url", ""),
            "description": data.get("description", ""),
            "mpn": data.get("mpn", ""),
            "manufacturer": data.get("manufacturer", ""),
            "color": data.get("color", ""),
            "memory": data.get("memory", ""),
            "price": data.get("price"),
            "sale_price": data.get("sale_price"),
            "currency": data.get("currency", "UAH"),
            "images": data.get("images", []),
            "rating": data.get("rating"),
            "review_count": data.get("review_count", 0),
            "screen_size": data.get("screen_size", ""),
            "resolution": data.get("resolution", ""),
            "characteristics": data.get("characteristics", {}),
            "missing_fields": data.get("missing_fields", []),
            "raw_jsonld": data.get("raw_jsonld", {}),
        },
    )
    print("Дані з JSON збережено у базу даних (update_or_create по SKU).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Збереження JSON результатів у БД")
    parser.add_argument(
        "--path",
        default=str(Path(__file__).resolve().parent.parent / "results" / "last_product.json"),
        help="Шлях до JSON з результатами",
    )
    args = parser.parse_args()
    save_from_json(Path(args.path))


if __name__ == "__main__":
    main()
