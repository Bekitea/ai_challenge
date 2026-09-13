"""GUI модуль для представления чатов и агентов."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from agents import Agent, AgentRepository, InMemoryAgentRepository, AgentSettings
from llm_providers import YandexCloudLlmProvider, LlmResponse
from config import YANDEX_API_KEY, YANDEX_FOLDER_ID


class CollapsibleReasoningBox(QWidget):
    """Сворачиваемый блок для отображения reasoning модели."""

    def __init__(self, reasoning_text: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.toggle_btn = QPushButton("Внутренние рассуждения модели")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background-color: #3E3E42; color: #E0E0E0; border: 1px solid #555; border-radius: 8px; padding: 10px; text-align: left; font-weight: bold; }
            QPushButton:hover { background-color: #4E4E52; }
        """)
        self.toggle_btn.clicked.connect(self.toggle_content)
        layout.addWidget(self.toggle_btn)

        self.content_box = QTextEdit()
        self.content_box.setReadOnly(True)
        self.content_box.setFont(QFont("Consolas", 11))
        self.content_box.setStyleSheet("""
            QTextEdit { background-color: #252526; color: #B0B0B0; border: 1px solid #3E3E42; border-radius: 8px; padding: 10px; }
        """)
        self.content_box.setText(reasoning_text)
        self.content_box.setVisible(False)
        layout.addWidget(self.content_box)

        self.adjust_size()

    def toggle_content(self, checked):
        self.content_box.setVisible(checked)
        if checked:
            self.toggle_btn.setText("Скрыть внутренние рассуждения")
        else:
            self.toggle_btn.setText("Внутренние рассуждения модели")
        self.adjust_size()

    def adjust_size(self):
        if self.content_box.isVisible():
            self.content_box.document().adjustSize()
            height = int(self.content_box.document().size().height())
            self.content_box.setFixedHeight(max(height + 20, 60))
        else:
            self.content_box.setFixedHeight(0)


class ChatMessageWidget(QWidget):
    """Виджет одного сообщения в чате."""

    def __init__(self, role: str, content: str, reasoning: str | None = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self.reasoning = reasoning
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(5)

        # Заголовок с ролью
        role_label = QLabel(f"**{role.capitalize()}**")
        role_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        role_label.setStyleSheet("color: #0078D4;" if role == "user" else "color: #4CAF50;")
        layout.addWidget(role_label)

        # Контент сообщения
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setFont(QFont("Segoe UI", 12))
        content_text.setStyleSheet("""
            QTextEdit { background-color: transparent; color: #FFFFFF; border: none; padding: 0px; }
        """)
        content_text.setPlainText(content)
        content_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        content_text.setFixedHeight(max(content_text.document().size().height() + 10, 40))
        layout.addWidget(content_text)

        # Reasoning (если есть)
        if reasoning:
            reasoning_box = CollapsibleReasoningBox(reasoning)
            layout.addWidget(reasoning_box)

        self.setLayout(layout)


class ChatView(QWidget):
    """Виджет отображения чата с историей сообщений."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Scroll area для сообщений
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(10, 10, 10, 10)
        self.messages_layout.setSpacing(15)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area)

    def add_message(self, role: str, content: str, reasoning: str | None = None):
        """Добавляет сообщение в чат."""
        message_widget = ChatMessageWidget(role, content, reasoning)
        # Вставляем перед stretch
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message_widget)
        
        # Прокрутка вниз
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_messages(self):
        """Очищает все сообщения."""
        while self.messages_layout.count() > 1:  # Оставляем stretch
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class AgentSettingsWidget(QWidget):
    """Виджет настроек агента."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def _make_label(self, text: str, size: int, color: str, bold: bool = True) -> QLabel:
        label = QLabel(text)
        label.setFont(
            QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        )
        label.setStyleSheet(f"color: {color};")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return label

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Температура
        temp_label = self._make_label("Температура (0.0 - 2.0):", 11, "#B0B0B0", bold=False)
        layout.addWidget(temp_label)
        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0.0, 2.0)
        self.temp_spinbox.setSingleStep(0.1)
        self.temp_spinbox.setValue(0.3)
        self.temp_spinbox.setStyleSheet("""
            QDoubleSpinBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QDoubleSpinBox:focus { border: 2px solid #0078D4; }
        """)
        layout.addWidget(self.temp_spinbox)

        # Top P
        top_p_label = self._make_label("Top P (0.0 - 1.0):", 11, "#B0B0B0", bold=False)
        layout.addWidget(top_p_label)
        self.top_p_spinbox = QDoubleSpinBox()
        self.top_p_spinbox.setRange(0.0, 1.0)
        self.top_p_spinbox.setSingleStep(0.05)
        self.top_p_spinbox.setValue(0.95)
        self.top_p_spinbox.setStyleSheet("""
            QDoubleSpinBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QDoubleSpinBox:focus { border: 2px solid #0078D4; }
        """)
        layout.addWidget(self.top_p_spinbox)

        # Top K
        top_k_label = self._make_label("Top K (опционально):", 11, "#B0B0B0", bold=False)
        layout.addWidget(top_k_label)
        self.top_k_spinbox = QSpinBox()
        self.top_k_spinbox.setRange(0, 100)
        self.top_k_spinbox.setValue(0)
        self.top_k_spinbox.setSpecialValueText("Отключено")
        self.top_k_spinbox.setStyleSheet("""
            QSpinBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QSpinBox:focus { border: 2px solid #0078D4; }
        """)
        layout.addWidget(self.top_k_spinbox)

        # Reasoning effort
        reasoning_label = self._make_label("Reasoning Effort:", 11, "#B0B0B0", bold=False)
        layout.addWidget(reasoning_label)
        self.reasoning_combobox = QComboBox()
        self.reasoning_combobox.addItems(["none", "low", "medium", "high"])
        self.reasoning_combobox.setCurrentText("none")
        self.reasoning_combobox.setStyleSheet("""
            QComboBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; }
        """)
        layout.addWidget(self.reasoning_combobox)

        # Модель
        model_label = self._make_label("Модель:", 11, "#B0B0B0", bold=False)
        layout.addWidget(model_label)
        self.model_combobox = QComboBox()
        self.model_combobox.addItems([
            "GPT OSS 120B (gpt-oss-120b/latest)",
            "Qwen3.6-35B (qwen3.6-35b-a3b/latest)",
            "Alice AI LLM Flash (aliceai-llm-flash/latest)",
        ])
        self.model_combobox.setStyleSheet("""
            QComboBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; }
        """)
        layout.addWidget(self.model_combobox)

        self.setLayout(layout)

    def get_settings(self) -> AgentSettings:
        """Получает текущие настройки из виджета."""
        model_text = self.model_combobox.currentText()
        if "gpt-oss-120b/latest" in model_text:
            model_id = "gpt-oss-120b/latest"
        elif "qwen3.6-35b-a3b/latest" in model_text:
            model_id = "qwen3.6-35b-a3b/latest"
        else:
            model_id = "aliceai-llm-flash/latest"

        top_k = self.top_k_spinbox.value() if self.top_k_spinbox.value() > 0 else None

        return AgentSettings(
            model_id=model_id,
            temperature=self.temp_spinbox.value(),
            top_p=self.top_p_spinbox.value(),
            top_k=top_k,
            reasoning_effort=self.reasoning_combobox.currentText(),
        )

    def set_settings(self, settings: AgentSettings):
        """Устанавливает настройки в виджет."""
        if settings.model_id:
            if "gpt-oss-120b" in settings.model_id:
                self.model_combobox.setCurrentIndex(0)
            elif "qwen3.6" in settings.model_id:
                self.model_combobox.setCurrentIndex(1)
            else:
                self.model_combobox.setCurrentIndex(2)
        
        if settings.temperature is not None:
            self.temp_spinbox.setValue(settings.temperature)
        if settings.top_p is not None:
            self.top_p_spinbox.setValue(settings.top_p)
        if settings.top_k is not None:
            self.top_k_spinbox.setValue(settings.top_k)
        if settings.reasoning_effort:
            self.reasoning_combobox.setCurrentText(settings.reasoning_effort)


class ChatInputWidget(QWidget):
    """Виджет ввода сообщения пользователем."""

    send_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        # Поле ввода
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Введите ваше сообщение...")
        self.input_field.setFont(QFont("Segoe UI", 12))
        self.input_field.setStyleSheet("""
            QTextEdit { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 12px; padding: 15px; selection-background-color: #0078D4; }
            QTextEdit:focus { border: 2px solid #0078D4; }
            QTextEdit::placeholder { color: #808080; }
        """)
        self.input_field.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.input_field.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.input_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.input_field.setFixedHeight(80)
        layout.addWidget(self.input_field)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.send_button = QPushButton("Отправить")
        self.send_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setStyleSheet("""
            QPushButton { background-color: #0078D4; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px; font-weight: bold; }
            QPushButton:hover { background-color: #1084D8; }
            QPushButton:disabled { background-color: #3E3E42; color: #808080; }
        """)
        self.send_button.clicked.connect(self.on_send_clicked)
        btn_layout.addWidget(self.send_button)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setStyleSheet(
            "background-color: #D83B01; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px;"
        )
        self.stop_button.setVisible(False)
        btn_layout.addWidget(self.stop_button)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.input_field.document().contentsChanged.connect(
            lambda: self.update_height()
        )

    def update_height(self):
        self.input_field.document().adjustSize()
        height = int(self.input_field.document().size().height())
        self.input_field.setFixedHeight(max(height + 20, 60))

    def on_send_clicked(self):
        text = self.input_field.toPlainText().strip()
        if text:
            self.send_clicked.emit(text)
            self.input_field.clear()
            self.update_height()

    def set_stop_button_visible(self, visible: bool):
        self.stop_button.setVisible(visible)
        self.send_button.setVisible(not visible)

    def get_input(self) -> str:
        return self.input_field.toPlainText().strip()

    def clear_input(self):
        self.input_field.clear()
        self.update_height()


class AgentListWidget(QWidget):
    """Список агентов/чатов в боковой панели."""

    agent_selected = pyqtSignal(str)  # agent_id
    new_agent_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Заголовок
        title_label = QLabel("Чаты")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #E0E0E0; padding: 10px 0;")
        layout.addWidget(title_label)

        # Кнопка нового чата
        self.new_chat_button = QPushButton("+ Новый чат")
        self.new_chat_button.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.new_chat_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_button.setStyleSheet("""
            QPushButton { background-color: #0078D4; color: #FFFFFF; border: none; border-radius: 8px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #1084D8; }
        """)
        self.new_chat_button.clicked.connect(lambda: self.new_agent_requested.emit())
        layout.addWidget(self.new_chat_button)

        # Список агентов
        self.agent_list = QListWidget()
        self.agent_list.setFont(QFont("Segoe UI", 12))
        self.agent_list.setStyleSheet("""
            QListWidget { background-color: #252526; color: #E0E0E0; border: 1px solid #3E3E42; border-radius: 8px; padding: 5px; }
            QListWidget::item { padding: 10px; border-radius: 4px; }
            QListWidget::item:selected { background-color: #0078D4; }
            QListWidget::item:hover { background-color: #3E3E42; }
        """)
        self.agent_list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.agent_list)

    def on_item_clicked(self, item: QListWidgetItem):
        agent_id = item.data(Qt.ItemDataRole.UserRole)
        if agent_id:
            self.agent_selected.emit(agent_id)

    def update_list(self, repository: AgentRepository):
        """Обновляет список агентов из репозитория."""
        self.agent_list.clear()
        previews = repository.get_all_previews()
        
        for preview in previews:
            list_item = QListWidgetItem(preview.name)
            list_item.setData(Qt.ItemDataRole.UserRole, preview.agent_id)
            
            # Добавляем информацию о последнем сообщении
            if preview.last_message_timestamp:
                timestamp_str = preview.last_message_timestamp.strftime("%d.%m %H:%M")
                list_item.setToolTip(f"{preview.name}\nСообщений: {preview.message_count}\nПоследнее: {timestamp_str}")
            else:
                list_item.setToolTip(f"{preview.name}\nСообщений: {preview.message_count}")
            
            self.agent_list.addItem(list_item)

    def select_agent(self, agent_id: str):
        """Выделяет агента в списке."""
        for i in range(self.agent_list.count()):
            item = self.agent_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == agent_id:
                self.agent_list.setCurrentItem(item)
                break


class AgentWorker(QThread):
    """Worker для асинхронного вызова агента."""

    response_ready = pyqtSignal(str, str, str)  # role, content, reasoning
    error_occurred = pyqtSignal(str)

    def __init__(self, agent: Agent, user_prompt: str):
        super().__init__()
        self.agent = agent
        self.user_prompt = user_prompt

    def run(self):
        try:
            response = self.agent.continue_dialog(self.user_prompt)
            self.response_ready.emit("assistant", response.content, response.reasoning or "")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка: {e}")


class ChatTab(QWidget):
    """Основная вкладка чата с агентом."""

    def __init__(self, agent: Agent, repository: AgentRepository, parent=None):
        super().__init__(parent)
        self.agent = agent
        self.repository = repository
        self.worker = None
        self.init_ui()

    def _make_label(self, text: str, size: int, color: str, bold: bool = True) -> QLabel:
        label = QLabel(text)
        label.setFont(
            QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        )
        label.setStyleSheet(f"color: {color};")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return label

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок с именем агента
        self.agent_name_label = QLabel(self.agent.name)
        self.agent_name_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.agent_name_label.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(self.agent_name_label)

        # Кнопка настроек
        self.settings_button = QPushButton("Настройки агента")
        self.settings_button.setCheckable(True)
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setStyleSheet("""
            QPushButton { background-color: #2D2D30; color: #E0E0E0; border: 1px solid #3E3E42; border-radius: 8px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #3E3E42; }
        """)
        self.settings_button.clicked.connect(self.toggle_settings)
        layout.addWidget(self.settings_button)

        # Панель настроек (скрыта по умолчанию)
        self.settings_frame = QFrame()
        self.settings_frame.setVisible(False)
        self.settings_frame.setStyleSheet("""
            QFrame { background-color: #252526; border: 1px solid #3E3E42; border-radius: 10px; padding: 15px; }
        """)
        self.settings_layout = QVBoxLayout(self.settings_frame)
        
        self.settings_widget = AgentSettingsWidget()
        self.settings_widget.set_settings(self.agent.get_settings())
        self.settings_layout.addWidget(self.settings_widget)

        # Кнопка сохранения настроек
        self.save_settings_button = QPushButton("Сохранить настройки")
        self.save_settings_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: #FFFFFF; border: none; border-radius: 8px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #45A049; }
        """)
        self.save_settings_button.clicked.connect(self.save_settings)
        self.settings_layout.addWidget(self.save_settings_button)

        layout.addWidget(self.settings_frame)

        # Область чата
        self.chat_view = ChatView()
        layout.addWidget(self.chat_view, stretch=1)

        # Загрузка истории
        self.load_history()

        # Поле ввода
        self.input_widget = ChatInputWidget()
        self.input_widget.send_clicked.connect(self.send_message)
        self.input_widget.stop_button.clicked.connect(self.stop_generation)
        layout.addWidget(self.input_widget)

    def load_history(self):
        """Загружает историю сообщений агента."""
        messages = self.agent.get_messages_for_display()
        for msg in messages:
            self.chat_view.add_message(msg.role, msg.content, msg.reasoning)

    def toggle_settings(self, checked: bool):
        self.settings_frame.setVisible(checked)
        self.settings_button.setText(
            "Скрыть настройки" if checked else "Настройки агента"
        )

    def save_settings(self):
        """Сохраняет настройки агента."""
        new_settings = self.settings_widget.get_settings()
        self.agent.update_settings(new_settings)
        QMessageBox.information(self, "Успех", "Настройки агента сохранены!")

    def send_message(self, user_text: str):
        """Отправляет сообщение пользователя агенту."""
        # Добавляем сообщение пользователя в чат
        self.chat_view.add_message("user", user_text)
        
        # Блокируем ввод
        self.input_widget.set_stop_button_visible(True)
        self.input_widget.send_button.setEnabled(False)

        # Запускаем worker
        self.worker = AgentWorker(self.agent, user_text)
        self.worker.response_ready.connect(self.on_response_ready)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.start()

    def on_response_ready(self, role: str, content: str, reasoning: str):
        """Обработка ответа от агента."""
        self.chat_view.add_message(role, content, reasoning)
        self.input_widget.set_stop_button_visible(False)
        self.input_widget.send_button.setEnabled(True)

    def on_error_occurred(self, error: str):
        """Обработка ошибки."""
        QMessageBox.critical(self, "Ошибка", error)
        self.input_widget.set_stop_button_visible(False)
        self.input_widget.send_button.setEnabled(True)

    def stop_generation(self):
        """Останавливает генерацию."""
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()


class MainWindow(QMainWindow):
    """Главное окно приложения с поддержкой нескольких чатов."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yandex Cloud AI Chat")
        
        # Инициализация репозитория и провайдера
        self.llm_provider = YandexCloudLlmProvider(
            api_key=YANDEX_API_KEY,
            folder_id=YANDEX_FOLDER_ID
        )
        self.repository: AgentRepository = InMemoryAgentRepository()
        
        self.current_agent_id: str | None = None
        self.chat_tabs: dict[str, ChatTab] = {}
        
        self.init_ui()

    def init_ui(self):
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter для боковой панели и контента
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель со списком агентов
        self.agent_list_widget = AgentListWidget()
        self.agent_list_widget.agent_selected.connect(self.select_agent)
        self.agent_list_widget.new_agent_requested.connect(self.create_new_agent)
        splitter.addWidget(self.agent_list_widget)
        splitter.setCollapsible(0, False)
        
        # Правая панель с чатом
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(0)

        self.welcome_label = QLabel("Выберите чат или создайте новый")
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setFont(QFont("Segoe UI", 14))
        self.welcome_label.setStyleSheet("color: #808080;")
        self.chat_layout.addWidget(self.welcome_label)
        self.chat_layout.addStretch()
        
        splitter.addWidget(self.chat_container)
        splitter.setCollapsible(1, False)
        
        # Размеры splitter
        splitter.setSizes([250, 800])
        
        main_layout.addWidget(splitter)
        
        # Обновляем список агентов
        self.refresh_agent_list()

    def create_new_agent(self):
        """Создает нового агента."""
        name = f"Чат {self.repository.get_all_previews().__len__() + 1}"
        agent = self.repository.create_agent(
            name=name,
            llm_provider=self.llm_provider,
            initial_settings=AgentSettings(),
            system_prompt=None
        )
        
        self.refresh_agent_list()
        self.select_agent(agent.agent_id)

    def select_agent(self, agent_id: str):
        """Выбирает агента для отображения."""
        if agent_id in self.chat_tabs:
            # Переключаемся на существующую вкладку
            pass
        else:
            # Создаем новую вкладку
            agent = self.repository.get_agent(agent_id)
            if agent:
                chat_tab = ChatTab(agent, self.repository)
                self.chat_tabs[agent_id] = chat_tab
        
        # Очищаем контейнер
        while self.chat_layout.count() > 0:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Добавляем выбранный чат
        if agent_id in self.chat_tabs:
            self.chat_layout.addWidget(self.chat_tabs[agent_id])
            self.current_agent_id = agent_id
            self.welcome_label.setVisible(False)
        
        # Выделяем в списке
        self.agent_list_widget.select_agent(agent_id)

    def refresh_agent_list(self):
        """Обновляет список агентов."""
        self.agent_list_widget.update_list(self.repository)
