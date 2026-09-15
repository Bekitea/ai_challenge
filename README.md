# AI Chat CLI

Консольное приложение для взаимодействия с AI агентами.

## Documentation

- **[CLI Specification](specs/cli_spec.md)** - Полная спецификация CLI: use cases, test cases, error matrix
- **[Testing Guide](cli_tests/README.md)** - Руководство по тестированию: лучшие практики, примеры тестов, troubleshooting

## Установка

### 1. Клонирование и зависимости

```bash
cd /path/to/project
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
YANDEX_CLOUD_API_KEY=your_api_key_here
YANDEX_CLOUD_FOLDER=your_folder_id_here

DATABASE_PATH=./data/agents.db
CHAT_HISTORY_DIR=./data/chat_history
```

### 3. Инициализация базы данных

Для создания таблиц в SQLite используйте Alembic миграции:

```bash
# Инициализировать Alembic (если ещё не инициализирован)
alembic init alembic

# Создать начальную миграцию (автоматически по моделям)
alembic revision --autogenerate -m "Initial migration"

# Применить миграции (создать таблицы)
alembic upgrade head
```

### 4. Запуск приложения

```bash
# Production mode (requires API keys)
python main_cli.py

# Test mode (uses Mock provider, no keys needed)
python main_cli.py --test
```

## Работа с миграциями

### Создание новой миграции

При изменении моделей в `models.py`:

```bash
alembic revision --autogenerate -m "Описание изменений"
```

### Применение миграций

```bash
alembic upgrade head
```

### Откат миграций

```bash
# Откат на одну миграцию назад
alembic downgrade -1

# Откат к начальному состоянию (удаление всех таблиц)
alembic downgrade base
```

### Проверка статуса

```bash
# Показать текущую версию и доступные миграции
alembic current

# Показать ожидающие применения миграции
alembic heads
```
