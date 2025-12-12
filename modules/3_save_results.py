"""Load JSON from results directory and save product to database."""
from load_django import *  # noqa: F401,F403 - initialize Django
from parser_app.models import *  # noqa: F401,F403 - access to models
import argparse
import json
from pathlib import Path
from typing import Any, Dict


def save_from_json(path: Path) -> None:
    if not path.exists():
        print(f"File {path} not found.")
        return
    data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
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
    print("Data from JSON saved to database.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Save JSON results to database")
    parser.add_argument(
        "--path",
        default=str(Path(__file__).resolve().parent.parent / "results" / "last_product.json"),
        help="Path to JSON results file",
    )
    args = parser.parse_args()
    save_from_json(Path(args.path))


if __name__ == "__main__":
    main()
