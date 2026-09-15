import os

from agents import Agent, AgentSettings, ContextWindowExceededError
from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
    KeyValueMemoryStrategy,
    SlidingWindowStrategy,
    SummarizationStrategy,
)
from llm_providers import YandexCloudLlmProvider
from storage.agent_repositories import PersistentAgentRepository


class CLIChat:
    """Консольный интерфейс для взаимодействия с агентами."""

    def __init__(self):
        self.llm_provider = YandexCloudLlmProvider(
            api_key=YANDEX_API_KEY,
            folder_id=YANDEX_FOLDER_ID,
        )
        self.repository = PersistentAgentRepository(self.llm_provider)
        self.current_agent: Agent | None = None
        self.available_models = {
            "1": ("gpt-oss-120b/latest", "GPT OSS 120B"),
            "2": ("qwen3.6-35b-a3b/latest", "Qwen3.6-35B"),
            "3": ("aliceai-llm-flash/latest", "Alice AI LLM Flash"),
        }
        self.reasoning_efforts = ["none", "low", "medium", "high"]

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
        if self.current_agent:
            print(f"3. Вернуться в чат: {self.current_agent.name}")
        else:
            print("3. Вернуться в чат (нет активного чата)")
        print("4. Выход")
        print("-" * 40)

    def print_chat_list(self):
        """Выводит список доступных чатов."""
        previews = self.repository.get_all_previews()
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
            print(f"   ID: {preview.agent_id[:8]}...")
        print("-" * 40)

    def get_agent_settings(
        self, current_settings: AgentSettings | None = None
    ) -> AgentSettings:
        """Запрашивает настройки у пользователя."""
        print("\n--- НАСТРОЙКИ АГЕНТА ---")

        # Выбор модели
        print("\nВыберите модель:")
        for key, (model_id, name) in self.available_models.items():
            print(f"  {key}. {name} ({model_id})")

        while True:
            model_choice = input("\nВаш выбор (1-3): ").strip()
            if model_choice in self.available_models:
                model_id = self.available_models[model_choice][0]
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
        for i, effort in enumerate(self.reasoning_efforts, 1):
            print(f"  {i}. {effort}")

        while True:
            try:
                re_choice = int(
                    input(
                        f"\nВаш выбор (1-{len(self.reasoning_efforts)}, по умолчанию 1): "
                    ).strip()
                    or "1"
                )
                if 1 <= re_choice <= len(self.reasoning_efforts):
                    reasoning_effort = self.reasoning_efforts[re_choice - 1]
                    break
                print(f"Выбор должен быть от 1 до {len(self.reasoning_efforts)}")
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

    def create_new_chat(self):
        """Создаёт новый чат."""
        print("\n--- СОЗДАНИЕ НОВОГО ЧАТА ---")
        name = input("Введите название чата (по умолчанию 'Чат N'): ").strip()

        # Системный промпт
        system_prompt = input("Введите системный промпт (Enter для пропуска): ").strip()

        settings = self.get_agent_settings()

        # Выбор стратегии управления контекстным окном
        strategy = self._select_context_strategy()

        # Генерируем имя если пустое
        if not name:
            chat_count = len(self.repository.get_all_previews())
            name = f"Чат {chat_count + 1}"

        agent = self.repository.create_agent(
            name=name,
            initial_settings=settings,
            system_prompt=system_prompt if system_prompt else None,
            strategy=strategy,
        )
        self.current_agent = agent
        print(f"\n[OK] Чат '{name}' создан!")
        print(f"  ID: {agent.agent_id[:8]}...")
        print(f"  Стратегия: {strategy.strategy_type}")

        # Показываем всю историю (пустую для нового чата) и переходим к общению
        self.show_history()
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

    def select_chat(self):
        """Выбирает существующий чат."""
        self.print_chat_list()
        previews = self.repository.get_all_previews()

        if not previews:
            print("\nНет доступных чатов. Создайте новый.")
            return

        while True:
            try:
                choice = int(input(f"\nВыберите чат (1-{len(previews)}): ").strip())
                if 1 <= choice <= len(previews):
                    selected_id = previews[choice - 1].agent_id
                    self.current_agent = self.repository.get_agent(selected_id)
                    print(f"\n[OK] Выбран чат: {self.current_agent.name}")

                    # Показываем всю историю и переходим к общению
                    self.show_history()
                    self.chat_loop()
                    break
                print(f"Введите число от 1 до {len(previews)}")
            except ValueError:
                print("Введите корректное число")

    def _print_current_settings(self):
        """Выводит текущие настройки агента."""
        if not self.current_agent:
            return

        settings = self.current_agent.get_settings()
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
        self.current_agent.update_settings(new_settings)
        print("\n[OK] Настройки обновлены!")
        self._print_current_settings()

    def show_history(self):
        """Показывает историю текущего чата."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        messages = self.current_agent.get_messages_for_display()
        all_messages = self.current_agent.get_history()  # Включая системный промпт

        if not all_messages:
            print("\nИстория пуста.")
            return

        # Получаем размер контекстного окна для отображения заполненности
        settings = self.current_agent.get_settings()
        context_window_size = settings.context_window_size or 200_000

        print("\n" + "=" * 60)
        print(f"ИСТОРИЯ ЧАТА: {self.current_agent.name}")
        print("=" * 60)

        for msg in all_messages:
            timestamp = msg.timestamp.strftime("%H:%M:%S") if msg.timestamp else "N/A"
            if msg.role == "system":
                role_prefix = "[SYSTEM]"
            elif msg.role == "user":
                role_prefix = "[USER]"
            else:
                role_prefix = "[AGENT]"

            print(f"\n[{timestamp}] {role_prefix}:")
            print(f"{msg.content}")

            # Отображаем токены для assistant prompt
            if msg.role == "assistant" and (
                msg.prompt_tokens is not None or msg.completion_tokens is not None
            ):
                tokens_info = []
                if msg.prompt_tokens is not None:
                    tokens_info.append(f"prompt: {msg.prompt_tokens}")
                if msg.completion_tokens is not None:
                    tokens_info.append(f"completion: {msg.completion_tokens}")
                if tokens_info:
                    print(f"  [Токены: {', '.join(tokens_info)}]")

                # Отображаем степень заполненности контекстного окна
                if msg.prompt_tokens is not None:
                    fill_percent = (msg.prompt_tokens / context_window_size) * 100
                    print(
                        f"  [Заполненность контекста: {msg.prompt_tokens}/{context_window_size} ({fill_percent:.1f}%)])"
                    )

            if msg.reasoning:
                print("\n  [Reasoning]:")
                # Выводим reasoning с отступом
                for line in msg.reasoning.split("\n"):
                    print(f"    {line}")

        print("\n" + "=" * 60)

    def print_summary(self):
        """Выводит саммари, если оно есть."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        strategy = self.current_agent.strategy
        summary = None

        # Получаем саммари из стратегии
        if hasattr(strategy, "summary"):
            summary = strategy.summary

        if summary:
            print("\n" + "=" * 60)
            print("САММАРИ ДИАЛОГА")
            print("=" * 60)
            print(f"\n{summary}\n")
            print("=" * 60)
        else:
            print("\n[INFO] Саммари отсутствует (суммаризация ещё не выполнялась).")

    def print_info(self):
        """Выводит информацию о чате, включая счетчики токенов."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        counters = self.current_agent.token_counters

        print("\n" + "=" * 60)
        print(f"ИНФОРМАЦИЯ О ЧАТЕ: {self.current_agent.name}")
        print("=" * 60)

        # Отображаем счетчики токенов
        print("\n--- СЧЕТЧИКИ ТОКЕНОВ ---")
        print(
            f"  Чат (без технических): prompt={counters.chat_prompt_tokens}, completion={counters.chat_completion_tokens}"
        )
        print(
            f"  Технические: prompt={counters.tech_prompt_tokens}, completion={counters.tech_completion_tokens}"
        )
        print(
            f"  ОБЩИЕ: prompt={counters.total_prompt_tokens}, completion={counters.total_completion_tokens}"
        )
        print("-" * 40)

        # Информация о стратегии
        strategy = self.current_agent.strategy
        print(f"\nСтратегия: {strategy.strategy_type}")
        if hasattr(strategy, "non_compressible_count") and hasattr(
            strategy, "buffer_size"
        ):
            print(f"  Несжимаемых сообщений: {strategy.non_compressible_count}")
            print(f"  Размер буфера: {strategy.buffer_size}")
        if hasattr(strategy, "summary") and strategy.summary:
            print("  Саммари: доступно")
        print("=" * 60)

    def create_branch(self):
        """Создаёт ветку текущего чата."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        print(f"\n--- СОЗДАНИЕ ВЕТКИ ОТ '{self.current_agent.name}' ---")

        # Запрашиваем имя для новой ветки
        default_name = f"{self.current_agent.name} (branch)"
        new_name = input(
            f"Введите название для ветки (Enter для '{default_name}'): "
        ).strip()
        if not new_name:
            new_name = default_name

        try:
            # Создаём ветку через репозиторий
            branched_agent = self.repository.branch_agent(
                parent_agent=self.current_agent,
                new_name=new_name,
            )

            print(f"\n[OK] Ветка '{branched_agent.name}' создана!")
            print(f"  ID: {branched_agent.agent_id[:8]}...")
            print(f"  Сообщений скопировано: {branched_agent.message_count}")
            print(f"  Стратегия: {branched_agent.strategy.strategy_type}")

            # Проверяем наличие саммари
            if (
                hasattr(branched_agent.strategy, "summary")
                and branched_agent.strategy.summary
            ):
                print("  Саммари: скопировано")
            else:
                print("  Саммари: отсутствует")

            # Переключаемся на новую ветку
            self.current_agent = branched_agent

            # Предлагаем продолжить общение в новой ветке
            continue_in_branch = (
                input("\nПродолжить общение в новой ветке? (y/n): ").strip().lower()
            )
            if continue_in_branch == "y":
                self.show_history()
                self.chat_loop()
            else:
                print("\nВетка создана. Вы можете вернуться к ней через меню.")

        except Exception as e:
            print(f"\n[ERROR] Ошибка при создании ветки: {e}")

    def chat_loop(self):
        """Основной цикл общения с агентом."""
        if not self.current_agent:
            print("\n[WARN] Сначала выберите или создайте чат!")
            return

        print(f"\n--- ЧАТ: {self.current_agent.name} ---")
        print("Введите сообщение и нажмите Enter для отправки.")
        print("Команды:")
        print("  /menu - вернуться в меню")
        print("  /stop - остановить генерацию")
        print("  /settings - показать настройки и изменить их")
        print("  /summary - показать саммари диалога")
        print("  /info - показать информацию о чате (счетчики токенов)")
        print("  /branch - создать ветку текущего чата")
        print("  /help - показать список команд")
        print("-" * 40)

        while True:
            try:
                user_input = input("\n[USER]: ").strip()

                if not user_input:
                    continue

                if user_input.lower() == "/menu":
                    print("\nВозврат в меню...")
                    break

                if user_input.lower() == "/stop":
                    print("\nГенерация остановлена.")
                    break

                if user_input.lower() == "/help":
                    print("\n--- ДОСТУПНЫЕ КОМАНДЫ ---")
                    print("  /menu - вернуться в главное меню")
                    print("  /stop - остановить текущую генерацию")
                    print("  /settings - показать текущие настройки и изменить их")
                    print("  /summary - показать саммари диалога")
                    print("  /info - показать информацию о чате (счетчики токенов)")
                    print(
                        "  /branch - создать ветку текущего чата (копируются настройки, история и саммари)"
                    )
                    print("  /help - показать этот список команд")
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

                print("\n[AGENT] печатает...", end="", flush=True)

                try:
                    response = self.current_agent.continue_dialog(user_input)
                except ContextWindowExceededError as e:
                    # Очищаем строку "Агент печатает..."
                    print("\r" + " " * 40 + "\r", end="")
                    print(f"\n[ERROR] {e}")
                    print(
                        "Необходимо очистить историю сообщений или создать новый чат."
                    )
                    break

                # Сохраняем обновлённое состояние агента в репозиторий
                self.repository.update_agent(self.current_agent)

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

        while True:
            self.print_menu()

            try:
                choice = input("\nВаш выбор (1-4): ").strip()

                if choice == "1":
                    self.create_new_chat()
                elif choice == "2":
                    self.select_chat()
                elif choice == "3":
                    if self.current_agent:
                        print(f"\n[OK] Возврат в чат: {self.current_agent.name}")
                        self.show_history()
                        self.chat_loop()
                    else:
                        print("\n[WARN] Нет активного чата. Выберите или создайте чат.")
                elif choice == "4":
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


def main():
    """Точка входа CLI приложения."""
    cli = CLIChat()
    cli.run()


if __name__ == "__main__":
    main()
