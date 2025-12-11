import os
from django.apps import AppConfig
from django.db import connections
from django.core.management import call_command
from django.db.utils import OperationalError


class ParserAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "parser_app"

    def ready(self):
        # Авто-ініціалізація БД: спробувати виконати migrate при старті
        # Можна вимкнути через змінну середовища AUTO_MIGRATE=0
        auto_migrate = os.environ.get("AUTO_MIGRATE", "1") == "1"
        if not auto_migrate:
            return
        try:
            # Перевірка з'єднання
            conn = connections['default']
            conn.ensure_connection()
        except OperationalError:
            return
        try:
            call_command("migrate", interactive=False, verbosity=0)
        except Exception:
            # Ігноруємо, щоб не блокувати запуск
            pass
