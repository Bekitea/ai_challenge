import os

from agents import Agent, AgentSettings, ContextWindowExceededError
from config import AVAILABLE_MODELS, REASONING_EFFORTS, YANDEX_DEFAULT_MODEL
from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
    KeyValueMemoryStrategy,
    SlidingWindowStrategy,
    SummarizationStrategy,
)
from use_cases import (
    UseCasesBundle,
)

HELP_COMMANDS = [
    "/menu - вернуться в главное меню",
    "/stop - остановить текущую генерацию",
    "/settings - показать текущие настройки и изменить их",
    "/summary - показать саммари диалога",
    "/info - показать информацию о чате (счетчики токенов, профиль задачи)",
    "/branch - создать ветку текущего чата (копируются настройки, история и саммари)",
    "/plan - перейти в фазу планирования",
    "/execute - перейти в фазу исполнения",
    "/validate - перейти в фазу тестирования",
    "/report - перейти в фазу отчета",
    "/mcp - показать подключённые к чату MCP и подключить новые",
    "/help - показать этот список команд",
]


class CLIChat:
    """Консольный интерфейс для взаимодействия с агентами."""

    def __init__(self, use_cases: UseCasesBundle):
        self.use_cases = use_cases
        self.current_agent: Agent | None = None

    def clear_screen(self):
        """Очищает экран консоли."""
        os.system("cls" if os.name == "nt" else "clear")

    def print_header(self):
        """Выводит заголовок приложения."""
        print("\n" + "=" * 60)
        print("       AI CHAT CLI - Консольный чат с AI агентами")
        print("=" * 60)

    def print_menu(self):
        """Выводит главное меню."""
        print("\n--- МЕНЮ ---")
        print("1. Новый чат")
        print("2. Выбрать чат")
        print("3. Профили задач")
        print("4. Просмотреть глобальную память")
        if self.current_agent:
            print(f"5. Вернуться в чат: {self.current_agent.name}")
        else:
            print("5. Вернуться в чат (нет активного чата)")
        print("6. Выход")
        print("-" * 40)

    def print_chat_list(self):
        """Выводит список доступных чатов."""
        previews = self.use_cases.select_chat.get_all_previews()
        if not previews:
            print("\nНет активных чатов.")
            return

        print("\n--- ВАШИ ЧАТЫ ---")
        for i, preview in enumerate(previews, 1):
            last_msg_time = ""
            if preview.last_message_timestamp:
                last_msg_time = preview.last_message_timestamp.strftime(
                    "%Y-%m-%d %H:%M"
                )

            preview_text = (
                getattr(preview, "last_message_preview", None) or "(нет сообщений)"
            )

            print(f"{i}. {preview.name}")
            print(f"   Сообщений: {preview.message_count} | Последнее: {last_msg_time}")
            print(f"   Превью: {preview_text}")
            print(f"   ID: {preview.agent_id}")
        print("-" * 40)

    def get_agent_settings(
        self, current_settings: AgentSettings | None = None
    ) -> AgentSettings:
        """Запрашивает настройки у пользователя."""
        print("\n--- НАСТРОЙКИ АГЕНТА ---")

        # Выбор модели
        print("\nВыберите модель:")
        for key, (model_id, name) in AVAILABLE_MODELS.items():
            print(f"  {key}. {name} ({model_id})")
        print("  Enter — модель по умолчанию")

        while True:
            model_choice = input("\nВаш выбор (1-3): ").strip()
            if not model_choice:
                model_id = YANDEX_DEFAULT_MODEL
                break
            if model_choice in AVAILABLE_MODELS:
                model_id = AVAILABLE_MODELS[model_choice][0]
                break
            print("Неверный выбор, попробуйте снова.")

        # Температура (отключена по умолчанию)
        temp_input = input("\nТемпература (0.0 - 2.0, Enter для отключения): ").strip()
        if temp_input:
            try:
                temp = float(temp_input)
                if not (0.0 <= temp <= 2.0):
                    print(
                        "Температура должна быть от 0.0 до 2.0. Используется значение по умолчанию (отключено)."
                    )
                    temp = None
            except ValueError:
                print(
                    "Некорректное число. Используется значение по умолчанию (отключено)."
                )
                temp = None
        else:
            temp = None

        # Top P (отключен по умолчанию)
        top_p_input = input("Top P (0.0 - 1.0, Enter для отключения): ").strip()
        if top_p_input:
            try:
                top_p = float(top_p_input)
                if not (0.0 <= top_p <= 1.0):
                    print(
                        "Top P должен быть от 0.0 до 1.0. Используется значение по умолчанию (отключено)."
                    )
                    top_p = None
            except ValueError:
                print(
                    "Некорректное число. Используется значение по умолчанию (отключено)."
                )
                top_p = None
        else:
            top_p = None

        # Top K
        while True:
            try:
                top_k_input = (
                    input("Top K (0 для отключения, по умолчанию 0): ").strip() or "0"
                )
                top_k = int(top_k_input)
                if top_k >= 0:
                    break
                print("Top K должен быть >= 0")
            except ValueError:
                print("Введите корректное число")

        # Reasoning effort
        print("\nReasoning Effort:")
        for i, effort in enumerate(REASONING_EFFORTS, 1):
            print(f"  {i}. {effort}")

        while True:
            try:
                re_choice = int(
                    input(
                        f"\nВаш выбор (1-{len(REASONING_EFFORTS)}, по умолчанию 1): "
                    ).strip()
                    or "1"
                )
                if 1 <= re_choice <= len(REASONING_EFFORTS):
                    reasoning_effort = REASONING_EFFORTS[re_choice - 1]
                    break
                print(f"Выбор должен быть от 1 до {len(REASONING_EFFORTS)}")
            except ValueError:
                print("Введите корректное число")

        # Размер контекстного окна
        print("\nРазмер контекстного окна (в токенах):")
        print("  По умолчанию: 200000 токенов (200k)")
        print("  Примеры: 4000, 8000, 32000, 128000, 200000")
        context_input = input(
            "Введите размер контекстного окна (Enter для 200k): "
        ).strip()
        if context_input:
            try:
                context_window_size = int(context_input)
                if context_window_size <= 0:
                    print("Размер должен быть положительным числом. Используется 200k.")
                    context_window_size = 200_000
            except ValueError:
                print("Некорректное число. Используется 200k.")
                context_window_size = 200_000
        else:
            context_window_size = 200_000

        return AgentSettings(
            model_id=model_id,
            temperature=temp,
            top_p=top_p,
            top_k=top_k if top_k > 0 else None,
            reasoning_effort=reasoning_effort,
            context_window_size=context_window_size,
        )

    def get_default_agent_settings(self) -> AgentSettings:
        """Возвращает настройки агента по умолчанию без ручного опроса."""
        return AgentSettings(
            model_id=YANDEX_DEFAULT_MODEL,
            temperature=None,
            top_p=None,
            top_k=None,
            reasoning_effort=REASONING_EFFORTS[0],
            context_window_size=200_000,
        )

    def _ask_configure_chat(self) -> bool:
        """Спрашивает, хочет ли пользователь настраивать чат вручную."""
        while True:
            answer = (
                input("Хотите настроить чат? (y/n, по умолчанию n): ").strip().lower()
                or "n"
            )
            if answer in ("y", "да", "д"):
                return True
            if answer in ("n", "нет", "н"):
                return False
            print("Введите 'y' (да) или 'n' (нет)")

    def create_new_chat(self):
        """Создаёт новый чат."""
        print("\n--- СОЗДАНИЕ НОВОГО ЧАТА ---")

        configure = self._ask_configure_chat()

        if configure:
            name = input("Введите название чата (по умолчанию 'Чат N'): ").strip()

            # Системный промпт
            system_prompt = input(
                "Введите системный промпт (Enter для пропуска): "
            ).strip()

            settings = self.get_agent_settings()

            # Выбор стратегии управления контекстным окном
            strategy = self._select_context_strategy()

            # Выбор профиля задачи
            task_profile_id = self._select_task_profile()
        else:
            # Быстрое создание чата с настройками по умолчанию
            print("Используются настройки по умолчанию.")
            name = ""
            system_prompt = ""
            settings = self.get_default_agent_settings()
            strategy = DefaultStrategy()
            task_profile_id = None

        # Генерируем имя если пустое
        if not name:
            previews = self.use_cases.select_chat.get_all_previews()
            chat_count = len(previews)
            name = f"Чат {chat_count + 1}"

        agent = self.use_cases.create_chat.execute(
            name=name,
            system_prompt=system_prompt if system_prompt else None,
            settings=settings,
            strategy=strategy,
            task_profile_id=task_profile_id,
        )
        self.current_agent = agent

        print(f"\n[OK] Чат '{name}' создан!")

        # Переходим к общению (история показывается в заголовке чата)
        self.chat_loop()

    def _select_context_strategy(self) -> ContextWindowStrategy:
        """Запрашивает у пользователя выбор стратегии управления контекстным окном."""
        print("\n--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---")
        print("1. DefaultStrategy (пересылка всех сообщений)")
        print("2. SummarizationStrategy (суммаризация истории)")
        print(
            "3. KeyValueMemoryStrategy (JSON-суммаризация: цель, ограничения, предпочтения, решения, договоренности)"
        )
        print("4. SlidingWindowStrategy (скользящее окно: последние N сообщений)")

        while True:
            choice = (
                input("\nВыберите стратегию (1-4, по умолчанию 1): ").strip() or "1"
            )
            if choice == "1":
                return DefaultStrategy()
            elif choice == "2":
                # Запрашиваем параметры для SummarizationStrategy
                try:
                    non_compressible = int(
                        input(
                            "Количество несжимаемых сообщений (по умолчанию 2): "
                        ).strip()
                        or "2"
                    )
                    buffer_size = int(
                        input(
                            "Размер буфера для суммаризации (по умолчанию 3): "
                        ).strip()
                        or "3"
                    )
                    return SummarizationStrategy(
                        non_compressible_count=non_compressible,
                        buffer_size=buffer_size,
                    )
                except ValueError as e:
                    print(f"Ошибка: {e}. Попробуйте снова.")
            elif choice == "3":
                # Запрашиваем параметры для KeyValueMemoryStrategy
                try:
                    non_compressible = int(
                        input(
                            "Количество несжимаемых сообщений (по умолчанию 2): "
                        ).strip()
                        or "2"
                    )
                    buffer_size = int(
                        input(
                            "Размер буфера для суммаризации (по умолчанию 3): "
                        ).strip()
                        or "3"
                    )
                    return KeyValueMemoryStrategy(
                        non_compressible_count=non_compressible,
                        buffer_size=buffer_size,
                    )
                except ValueError as e:
                    print(f"Ошибка: {e}. Попробуйте снова.")
            elif choice == "4":
                # Запрашиваем параметры для SlidingWindowStrategy
                try:
                    window_size = int(
                        input("Размер скользящего окна N (по умолчанию 10): ").strip()
                        or "10"
                    )
                    return SlidingWindowStrategy(window_size=window_size)
                except ValueError as e:
                    print(f"Ошибка: {e}. Попробуйте снова.")
            else:
                print("Неверный выбор, попробуйте снова.")

    def _select_task_profile(self) -> str | None:
        """Запрашивает у пользователя выбор профиля задачи для привязки к чату."""
        print("\n--- ПРИВЯЗКА ПРОФИЛЯ ЗАДАЧИ ---")

        profiles = self.use_cases.list_task_profiles.execute()

        if not profiles:
            print("(нет доступных профилей)")
            return None

        # Сортируем профили по первичному ключу (id) в порядке возрастания
        sorted_profiles = sorted(profiles, key=lambda p: p.id)

        print("Доступные профили задач:")
        for i, profile in enumerate(sorted_profiles, 1):
            print(f"  {i}. {profile.name}")
        print("  0. Не привязывать профиль")

        while True:
            choice = (
                input(
                    f"\nВыберите профиль задачи (0-{len(sorted_profiles)}, по умолчанию 0): "
                ).strip()
                or "0"
            )

            try:
                choice_num = int(choice)
                if choice_num == 0:
                    return None
                elif 1 <= choice_num <= len(sorted_profiles):
                    return sorted_profiles[choice_num - 1].id
                else:
                    print("[WARN] Некорректный выбор. Профиль не привязан.")
                    return None
            except ValueError:
                print("[WARN] Некорректный выбор. Профиль не привязан.")
                return None

    def select_chat(self):
        """Выбирает существующий чат."""
        self.print_chat_list()
        previews = self.use_cases.select_chat.get_all_previews()

        if not previews:
            print("\nНет доступных чатов. Создайте новый.")
            return

        while True:
            try:
                choice = int(input(f"\nВыберите чат (1-{len(previews)}): ").strip())
                if 1 <= choice <= len(previews):
                    selected_id = previews[choice - 1].agent_id
                    self.current_agent = self.use_cases.select_chat.get_agent(
                        selected_id
                    )
                    # При выборе чата загружаем память через use case
                    self.use_cases.refresh_agent_memory.execute(self.current_agent)
                    print(f"\n[OK] Выбран чат: {self.current_agent.name}")

                    # Переходим к общению (история показывается в заголовке чата)
                    self.chat_loop()
                    break
                print(f"Введите число от 1 до {len(previews)}")
            except ValueError:
                print("Введите корректное число")

    def _print_current_settings(self):
        """Выводит текущие настройки агента."""
        if not self.current_agent:
            return

        settings = self.use_cases.view_settings.execute(self.current_agent)
        if not settings:
            return

        print("\n--- ТЕКУЩИЕ НАСТРОЙКИ ---")
        print(f"  Модель: {settings.model_id}")
        print(
            f"  Температура: {settings.temperature if settings.temperature is not None else 'отключена'}"
        )
        print(
            f"  Top P: {settings.top_p if settings.top_p is not None else 'отключен'}"
        )
        print(
            f"  Top K: {settings.top_k if settings.top_k is not None else 'отключено'}"
        )
        print(f"  Reasoning Effort: {settings.reasoning_effort}")
        context_window = (
            settings.context_window_size
            if settings.context_window_size is not None
            else 200_000
        )
        print(f"  Размер контекстного окна: {context_window} токенов")
        print("-" * 40)

    def print_settings(self):
        """Показывает текущие настройки чата."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        self._print_current_settings()

    def change_settings(self):
        """Изменяет настройки текущего агента."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        print(f"\n--- НАСТРОЙКИ ДЛЯ '{self.current_agent.name}' ---")
        new_settings = self.get_agent_settings()
        self.use_cases.change_settings.execute(self.current_agent, new_settings)
        print("\n[OK] Настройки обновлены!")
        self._print_current_settings()

    def print_summary(self):
        """Показывает саммари диалога."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        summary = self.use_cases.show_summary.execute(self.current_agent)
        if summary:
            print("\n--- САММАРИ ДИАЛОГА ---")
            print(summary)
            print("-" * 40)
        else:
            print("\n[INFO] Саммари пока недоступно.")

    def print_info(self):
        """Показывает информацию о чате (счетчики токенов)."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        info = self.use_cases.show_chat_info.execute(self.current_agent)
        if not info:
            return

        print("\n--- ИНФОРМАЦИЯ О ЧАТЕ ---")
        print(f"  Название: {info.name}")
        print(f"  ID: {info.agent_id}")
        print(f"  Стратегия: {info.strategy_type}")
        print(
            f"  Профиль задачи: {info.task_profile_name if info.task_profile_name else '(не привязан)'}"
        )
        print(
            f"  Текущая фаза: {info.current_phase if info.current_phase else '(не установлена)'}"
        )
        print(f"  Сообщений: {info.message_count}")
        print(f"  Prompt токены: {info.total_prompt_tokens}")
        print(f"  Completion токены: {info.total_completion_tokens}")
        if info.has_summary:
            print("  Есть саммари: Да")
        if info.non_compressible_count is not None:
            print(f"  Несжимаемые сообщения: {info.non_compressible_count}")
        if info.buffer_size is not None:
            print(f"  Размер буфера: {info.buffer_size}")
        print("-" * 40)

    def create_branch(self):
        """Создаёт ветку текущего чата."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        print(f"\n--- СОЗДАНИЕ ВЕТКИ ОТ '{self.current_agent.name}' ---")
        new_name = input("Введите название ветки (Enter для автогенерации): ").strip()

        try:
            branched_agent = self.use_cases.create_branch.execute(
                self.current_agent, new_name if new_name else None
            )

            # Переключаемся на новую ветку
            self.current_agent = branched_agent

            # Предлагаем продолжить общение в новой ветке
            continue_in_branch = (
                input("\nПродолжить в новой ветке? (y/n): ").strip().lower()
            )
            if continue_in_branch == "y":
                self.chat_loop()
            else:
                print("\nВетка создана. Вы можете вернуться к ней через меню.")

        except Exception as e:
            print(f"\n[ERROR] Ошибка при создании ветки: {e}")

    def print_global_memory(self):
        """Показывает глобальную память (список фактов)."""
        facts = self.use_cases.view_global_memory.execute()

        print("\n--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---")
        if not facts:
            print("  (память пуста)")
        else:
            for i, fact in enumerate(facts, 1):
                print(f"  {i}. {fact}")
        print("-" * 40)

    def task_profiles_menu(self):
        """Меню управления профилями задач."""
        while True:
            print("\n--- ПРОФИЛИ ЗАДАЧ ---")
            print("1. Создать новый профиль")
            print("2. Просмотреть список профилей")
            print("3. Назад в главное меню")
            print("-" * 40)

            choice = input("\nВаш выбор (1-3): ").strip()

            if choice == "1":
                self._create_task_profile()
            elif choice == "2":
                self._view_task_profiles_list()
            elif choice == "3":
                break
            else:
                print("\n[WARN] Неверный выбор, попробуйте снова.")

    def _create_task_profile(self):
        """Создание нового профиля задачи."""
        print("\n--- СОЗДАНИЕ НОВОГО ПРОФИЛЯ ЗАДАЧИ ---")

        # Ввод названия с валидацией
        while True:
            name = input("Введите название профиля: ").strip()
            if name:
                break
            print("[ERROR] Название профиля не может быть пустым.")

        # Ввод описания с валидацией
        while True:
            description = input("Введите описание задачи: ").strip()
            if description:
                break
            print("[ERROR] Описание задачи не может быть пустым.")

        # Ввод предпочтений (опционально)
        preferences = input(
            "Введите предпочтения/инструкции (Enter для пропуска): "
        ).strip()

        # Ввод инвариантов
        print("\n--- ИНВАРИАНТЫ (строгие правила/ограничения) ---")
        print("Примеры: 'Использовать только Kotlin', 'Не использовать Java',")
        print("         'Стек: PostgreSQL + Redis', 'Пользователь — веган'")
        print("Введите инварианты по одному. Пустая строка для завершения:")
        invariants = []
        while True:
            inv = input("  > ").strip()
            if not inv:
                break
            invariants.append(inv)

        profile = self.use_cases.create_task_profile.execute(
            name, description, preferences, invariants
        )
        print(f"\n[OK] Профиль задачи '{name}' создан!")
        print(f"  ID: {profile.id}")
        print(f"  Дата создания: {profile.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if invariants:
            print(f"  Инвариантов: {len(invariants)}")
        print("-" * 40)

    def _view_task_profiles_list(self):
        """Просмотр списка профилей задач с возможностью выбора действия."""
        profiles = self.use_cases.list_task_profiles.execute()
        if not profiles:
            print("\nНет доступных профилей задач.")
            print("-" * 40)
            return

        print("\n--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---")
        for i, profile in enumerate(profiles, 1):
            created_at_str = ""
            if profile.created_at:
                created_at_str = profile.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"{i}. {profile.name}")
            print(f"   ID: {profile.id}")
            print(f"   Дата создания: {created_at_str}")
            print(f"   Фактов в памяти: {profile.facts_count}")
            print(f"   Инвариантов: {profile.invariants_count}")
            desc_preview = (
                f"{profile.description[:50]}..."
                if len(profile.description) > 50
                else profile.description
            )
            print(f"   Описание: {desc_preview}")
            print()
        print("-" * 40)
        print("Действия:")
        print("1. Просмотреть память профиля")
        print("2. Управление инвариантами")
        print("3. Удалить профиль")
        print("4. Назад к списку")

        while True:
            action = input("\nВыберите действие (1-4): ").strip()
            if action == "1":
                self._view_profile_memory(profiles)
                break
            elif action == "2":
                self._manage_invariants(profiles)
                break
            elif action == "3":
                self._delete_profile(profiles)
                break
            elif action == "4":
                break
            else:
                print("\n[WARN] Неверный выбор, попробуйте снова.")

    def _manage_invariants(self, profiles: list):
        """Управление инвариантами выбранного профиля."""
        while True:
            try:
                choice = int(input(f"Выберите профиль (1-{len(profiles)}): ").strip())
                if 1 <= choice <= len(profiles):
                    break
                print(f"Введите число от 1 до {len(profiles)}")
            except ValueError:
                print("Введите корректное число")

        profile_info = profiles[choice - 1]

        while True:
            invariants = self.use_cases.list_invariants.execute(profile_info.id)
            print(f"\n--- ИНВАРИАНТЫ ПРОФИЛЯ: {profile_info.name} ---")
            if not invariants:
                print("  (инварианты не заданы)")
            else:
                for i, inv in enumerate(invariants, 1):
                    print(f"  {i}. {inv.text}")
            print("-" * 40)
            print("Действия:")
            print("1. Добавить инвариант")
            print("2. Удалить инвариант")
            print("3. Назад")

            action = input("\nВыберите действие (1-3): ").strip()
            if action == "1":
                text = input("Введите текст инварианта: ").strip()
                if text:
                    try:
                        self.use_cases.add_invariant.execute(profile_info.id, text)
                        print("[OK] Инвариант добавлен!")
                    except ValueError as e:
                        print(f"[ERROR] {e}")
                else:
                    print("[WARN] Инвариант не может быть пустым.")
            elif action == "2":
                if not invariants:
                    print("[WARN] Нет инвариантов для удаления.")
                    continue
                try:
                    idx = int(
                        input(
                            f"Выберите номер инварианта для удаления (1-{len(invariants)}): "
                        ).strip()
                    )
                    if 1 <= idx <= len(invariants):
                        inv_id = invariants[idx - 1].id
                        if self.use_cases.remove_invariant.execute(inv_id):
                            print("[OK] Инвариант удалён!")
                        else:
                            print("[ERROR] Не удалось удалить инвариант.")
                    else:
                        print("[WARN] Некорректный номер.")
                except ValueError:
                    print("[WARN] Введите корректное число.")
            elif action == "3":
                break
            else:
                print("[WARN] Неверный выбор.")

    def _view_profile_memory(self, profiles: list):
        """Просмотр памяти и инвариантов выбранного профиля."""
        while True:
            try:
                choice = int(input(f"Выберите профиль (1-{len(profiles)}): ").strip())
                if 1 <= choice <= len(profiles):
                    break
                print(f"Введите число от 1 до {len(profiles)}")
            except ValueError:
                print("Введите корректное число")

        profile_info = profiles[choice - 1]
        profile = self.use_cases.get_task_profile_memory.execute(profile_info.id)
        if profile is None:
            print("\n[ERROR] Профиль не найден.")
            return

        print("\n--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---")
        print(f"  ID: {profile.id}")
        print(f"  Название: {profile.name}")
        print(f"  Описание: {profile.description}")
        print(f"  Дата создания: {profile.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if profile.preferences:
            print(f"  Предпочтения: {profile.preferences}")

        print("\n--- ПАМЯТЬ ПРОФИЛЯ ---")
        if not profile.facts:
            print("  (память пуста)")
        else:
            for i, fact in enumerate(profile.facts, 1):
                print(f"  {i}. {fact}")

        print("\n--- ИНВАРИАНТЫ ---")
        if not profile.invariants:
            print("  (инварианты не заданы)")
        else:
            for i, inv in enumerate(profile.invariants, 1):
                print(f"  {i}. {inv}")
        print("-" * 40)

    def _delete_profile(self, profiles: list):
        """Удаление выбранного профиля."""
        while True:
            try:
                choice = int(
                    input(
                        f"Выберите профиль для удаления (1-{len(profiles)}): "
                    ).strip()
                )
                if 1 <= choice <= len(profiles):
                    break
                print(f"Введите число от 1 до {len(profiles)}")
            except ValueError:
                print("Введите корректное число")

        profile_info = profiles[choice - 1]

        # Проверка привязки к агентам
        if self.use_cases.delete_task_profile.task_profile_repository.is_profile_linked_to_agents(
            profile_info.id
        ):
            print(
                f"\n[WARN] Невозможно удалить профиль '{profile_info.name}': он привязан к одному или нескольким агентам."
            )
            print(
                "Сначала удалите или пересоздайте агентов, использующих этот профиль."
            )
            return

        # Подтверждение удаления
        confirm = (
            input(
                f"\nВы уверены, что хотите удалить профиль '{profile_info.name}'? (y/n): "
            )
            .strip()
            .lower()
        )
        if confirm != "y":
            print("\n[INFO] Удаление отменено.")
            return

        success = self.use_cases.delete_task_profile.execute(profile_info.id)
        if success:
            print(f"\n[OK] Профиль '{profile_info.name}' успешно удалён.")
        else:
            print(f"\n[ERROR] Не удалось удалить профиль '{profile_info.name}'.")
        print("-" * 40)

    def _print_chat_header(self):
        """Отображает заголовок чата с текущей фазой и историей сообщений."""
        phase_name = self.current_agent.current_phase.name
        print(f"\n--- ЧАТ: {self.current_agent.name} [Фаза: {phase_name}] ---")

        all_messages = self.use_cases.show_history.execute(self.current_agent)
        for msg in all_messages:
            role_prefix = "[USER]" if msg.role == "user" else "[AGENT]"
            print(f"{role_prefix}: {msg.content}")
        print("-" * 40)

    def _print_hint(self):
        """Отображает подсказку о команде /help."""
        print("\n--- Подсказка ---")
        print("Введите сообщение /help и нажмите Enter для просмотра списка команд")
        print("-" * 40)

    def mcp_menu(self):
        """Обрабатывает команду /mcp.

        Показывает все MCP, подключённые к текущему чату, затем предлагает
        подключить новые. При согласии выводит список ещё не подключённых
        MCP-серверов из реестра и подключает выбранный пользователем.
        """
        agent = self.current_agent
        if not agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        print(f"\n--- MCP-СЕРВЕРЫ ЧАТА: {agent.name} ---")

        connected = self.use_cases.list_connected_mcp.execute(agent)
        if connected:
            for status in connected:
                if status.connected:
                    tools = (
                        ", ".join(status.tools) if status.tools else "нет инструментов"
                    )
                    print(
                        f"  [OK] {status.title} ({status.name}) — инструменты: {tools}"
                    )
                else:
                    print(
                        f"  [OFFLINE] {status.title} ({status.name}) — "
                        f"подключение не установлено"
                    )
        else:
            print("  К этому чату ещё не подключено ни одного MCP-сервера.")

        try:
            connect_new = input("\nПодключить новые MCP? (y/n): ").strip().lower()
        except EOFError, KeyboardInterrupt:
            print()
            return
        if connect_new != "y":
            return

        available = self.use_cases.list_available_mcp.execute(agent)
        if not available:
            print("\n[INFO] Все доступные MCP-серверы уже подключены к этому чату.")
            return

        print("\n--- ДОСТУПНЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ MCP ---")
        for idx, server in enumerate(available, start=1):
            print(f"  {idx}. {server.title} ({server.name}) — {server.description}")

        try:
            choice = input(
                "\nВведите номер сервера для подключения (или название, 0 — отмена): "
            ).strip()
        except EOFError, KeyboardInterrupt:
            print()
            return
        if not choice or choice == "0":
            print("[INFO] Подключение отменено.")
            return

        server_name = None
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(available):
                server_name = available[num - 1].name
            else:
                print("\n[ERROR] Неверный номер сервера.")
                return
        else:
            server_name = choice

        print(f"\n[INFO] Подключаю MCP '{server_name}'...", flush=True)
        success, message = self.use_cases.connect_mcp.execute(agent, server_name)
        prefix = "[OK]" if success else "[ERROR]"
        print(f"\n{prefix} {message}")

    def chat_loop(self):
        """Основной цикл общения с агентом."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        # Отображаем заголовок чата с историей сообщений и подсказку
        self._print_chat_header()
        self._print_hint()

        while True:
            try:
                user_input = input("\n[USER]: ").strip()

                if not user_input:
                    continue

                if user_input.lower() == "/menu":
                    print("\nВозврат в меню...")
                    # При выходе из чата сохраняем память через use case
                    if self.current_agent:
                        self.use_cases.save_agent_memory.execute(self.current_agent)
                    break

                if user_input.lower() == "/stop":
                    # Stop generation - check if generation is actually active
                    # In this simple implementation, we just exit the chat loop
                    print("\n[INFO] Генерация не активна.")
                    break

                if user_input.lower() == "/help":
                    print("\n--- ДОСТУПНЫЕ КОМАНДЫ ---")
                    for cmd in HELP_COMMANDS:
                        print(f"  {cmd}")
                    continue

                # Обработка команд фаз
                if user_input.lower() in ("/plan", "/execute", "/validate", "/report"):
                    success, message = self.current_agent.handle_phase_command(
                        user_input.lower()
                    )
                    print(f"\n[INFO] {message}")
                    # Обновляем отображение фазы в заголовке
                    phase_name = self.current_agent.current_phase.name
                    print(
                        f"--- ЧАТ: {self.current_agent.name} [Фаза: {phase_name}] ---"
                    )
                    continue

                if user_input.lower() == "/summary":
                    self.print_summary()
                    continue

                if user_input.lower() == "/info":
                    self.print_info()
                    continue

                if user_input.lower() == "/settings":
                    self.print_settings()
                    change = input("\nИзменить настройки? (y/n): ").strip().lower()
                    if change == "y":
                        self.change_settings()
                    continue

                if user_input.lower() == "/branch":
                    self.create_branch()
                    continue

                if user_input.lower() == "/mcp":
                    self.mcp_menu()
                    continue

                print("\n[AGENT] печатает...", end="", flush=True)

                try:
                    response, _ = self.use_cases.send_message.execute(
                        self.current_agent, user_input
                    )
                except ContextWindowExceededError as e:
                    # Очищаем строку "Агент печатает..."
                    print("\r" + " " * 40 + "\r", end="")
                    print(f"\n[ERROR] {e}")
                    print(
                        "Необходимо очистить историю сообщений или создать новый чат."
                    )
                    break

                # Очищаем строку "Агент печатает..."
                print("\r" + " " * 40 + "\r", end="")

                print(f"\n[AGENT]: {response.content}")

                # Отображаем информацию о токенах
                if (
                    response.prompt_tokens is not None
                    or response.completion_tokens is not None
                ):
                    tokens_info = []
                    if response.prompt_tokens is not None:
                        tokens_info.append(f"prompt: {response.prompt_tokens}")
                    if response.completion_tokens is not None:
                        tokens_info.append(f"completion: {response.completion_tokens}")
                    if tokens_info:
                        print(f"  [Токены: {', '.join(tokens_info)}]")

                    # Отображаем степень заполненности контекстного окна
                    if response.prompt_tokens is not None:
                        settings = self.current_agent.get_settings()
                        context_window_size = settings.context_window_size or 200_000
                        fill_percent = (
                            response.prompt_tokens / context_window_size
                        ) * 100
                        print(
                            f"  [Заполненность контекста: {response.prompt_tokens}/{context_window_size} ({fill_percent:.1f}%)]"
                        )

                if response.reasoning:
                    show_reasoning = (
                        input("\nПоказать рассуждения модели? (y/n): ").strip().lower()
                    )
                    if show_reasoning == "y":
                        print("\n[Reasoning]:")
                        for line in response.reasoning.split("\n"):
                            print(f"  {line}")

            except KeyboardInterrupt:
                print("\n\nПрервано пользователем.")
                break
            except Exception as e:
                print(f"\n[ERROR] Ошибка: {e}")
                break

    def run(self):
        """Запускает CLI приложение."""
        self.clear_screen()
        self.print_header()

        # При старте приложения достаем все агенты с несохраненными промптами
        # и у них последовательно вызываем save_memory через use case
        self.use_cases.save_unsaved_memories.execute()

        while True:
            self.print_menu()

            try:
                choice = input("\nВаш выбор (1-6): ").strip()

                if choice == "1":
                    self.create_new_chat()
                elif choice == "2":
                    self.select_chat()
                elif choice == "3":
                    self.task_profiles_menu()
                elif choice == "4":
                    self.print_global_memory()
                elif choice == "5":
                    if self.current_agent:
                        print(f"\n[OK] Возврат в чат: {self.current_agent.name}")
                        self.chat_loop()
                    else:
                        print("\n[WARN] Нет активного чата. Выберите или создайте чат.")
                elif choice == "6":
                    print("\nДо свидания!\n")
                    break
                else:
                    print("\n[WARN] Неверный выбор, попробуйте снова.")

            except KeyboardInterrupt:
                print("\n\nДо свидания!\n")
                break
            except EOFError:
                print("\n\nДо свидания!\n")
                break
