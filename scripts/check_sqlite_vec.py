"""Скрипт проверки собранного расширения sqlite-vec.

Это не тест, а ручная проверка зависимости: скрипт загружает вендоренный
``vec0`` (``.so`` для Linux/musl, ``.dll`` для Windows), проверяет версию,
создаёт виртуальную таблицу и выполняет векторный поиск.

Запуск (из корня проекта):

    poetry run python scripts/check_sqlite_vec.py
"""

import sqlite3
import sys
from pathlib import Path

# На Windows консоль может использовать cp1251, в которую не влезает не-ASCII
# вывод. Явно переключаем stdout на UTF-8, чтобы проверка не падала.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Скрипт лежит в ``scripts/``, поэтому корень проекта нужно добавить в sys.path,
# чтобы импорт ``core.*`` работал при прямом запуске.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.infrastructure.persistence.extensions import sqlite_vec

# 1. Создаем соединение
conn = sqlite3.connect(":memory:")

# 2. Загружаем расширение (загрузчик сам найдет vec0.dll для Windows)
sqlite_vec.load(conn)

# 3. Проверяем версию
version = conn.execute("SELECT vec_version()").fetchone()
print(f"Версия sqlite-vec: {version}")  # Ожидается: ('v0.1.9',)

# 4. Создаем виртуальную таблицу и добавляем данные
conn.execute("CREATE VIRTUAL TABLE v USING vec0(a float[3])")
conn.execute("INSERT INTO v(rowid, a) VALUES (1, '[1, 2, 3]')")

# 5. Проверяем векторный поиск
result = conn.execute(
    "SELECT distance FROM v WHERE a MATCH '[1, 2, 3]' ORDER BY distance LIMIT 1"
).fetchone()
print(f"Результат поиска (distance): {result}")  # Ожидается: (0.0,)

print("[OK] Проверка прошла успешно!")
