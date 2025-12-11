
Проєкт для парсингу товарів з brain.com.ua та збереження даних у Django + Postgres.



```powershell
# Запустити базу даних через Docker
docker compose up -d db

python -m venv .venv
. ./.venv/Scripts/Activate.ps1

pip install -r requirements.txt

python modules/2_parse_product.py



