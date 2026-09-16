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

## Тестирование

### Запуск E2E тестов CLI

Проект включает набор End-to-End тестов, которые эмулируют поведение реального пользователя через CLI интерфейс. Все тесты соответствуют спецификации ([cli_spec.md](specs/cli_spec.md)).

#### Требования

- Python 3.8+
- pytest: `pip install pytest`
- Приложение должно быть в рабочем состоянии

#### Запуск тестов

```bash
# Запустить все E2E тесты
pytest cli_tests/test_cli_e2e.py -v

# Запустить тесты конкретного Use Case
pytest cli_tests/test_cli_e2e.py::TestUC001_CreateChatWithAllSettings -v

# Запустить конкретный тесткейс
pytest cli_tests/test_cli_e2e.py::TestUC001_CreateChatWithAllSettings::test_tc_001_create_chat_default_settings -v

# Запустить smoke тест
python cli_tests/smoke_test.py
```

#### Принципы тестирования

1. **Без фикстур** — каждый тест полностью самодостаточен
2. **Subprocess interaction** — взаимодействие только через subprocess с stdin/stdout
3. **Трассируемость** — имена тестов соответствуют номерам тесткейсов из спецификации (`test_tc_XXX_<description>`)
4. **Test mode** — все тесты запускаются с флагом `--test` (используется Mock provider)
5. **Таймауты** — обязательные таймауты для предотвращения зависаний

#### Структура тестов

- **Тесткейсы** организованы по классам (по одному на Use Case)
- Покрытие: полное покрытие (каждый use case -> один или несколько тест кейсов в спецификации, каждый тест кейс -> e2e cli тест)
- Расположение: `cli_tests/test_cli_e2e.py`

**Подробная документация**: см. [cli_tests/README.md](cli_tests/README.md)
