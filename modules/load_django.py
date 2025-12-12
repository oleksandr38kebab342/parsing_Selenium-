"""Configure Django environment for standalone scripts in modules."""
import os
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR / "parser_app"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parser_app.settings")

try:
    import django

    django.setup()
except ImportError as exc:
    raise ImportError("Django is not installed. Activate your venv and install dependencies.") from exc
