import sqlite3
import sys

from storage.extensions import sqlite_vec

# На Windows консоль может использовать cp1251, в которую не влезает не-ASCII
# вывод. Явно переключаем stdout на UTF-8, чтобы проверка не падала.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
