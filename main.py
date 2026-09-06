import json
import sys
import time
from typing import List, Optional

import openai
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import API_KEY, BASE_URL, FOLDER_ID, YANDEX_CLOUD_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, project=FOLDER_ID)


class InterruptionRequestedError(Exception):
    pass


def call_llm_with_retry(
    worker: QThread,
    messages: list,
    response_format: Optional[dict] = None,
    model_class: Optional[type] = None,
    max_retries: int = 3,
    timeout: int = 20,
    temperature: float = 0.3,
    model_id: Optional[str] = None,
) -> tuple:
    if model_id is None:
        model_id = YANDEX_CLOUD_MODEL

    for attempt in range(max_retries):
        if worker.isInterruptionRequested():
            raise InterruptionRequestedError()

        kwargs = {
            "model": f"gpt://{FOLDER_ID}/{model_id}",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1500,
            "timeout": timeout,
        }

        if model_id == "qwen3.6-35b-a3b/latest":
            kwargs["reasoning_effort"] = "none"

        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            raw_content = message.content or ""
            reasoning_text = getattr(message, "reasoning_content", None) or getattr(
                message, "reasoning", None
            )

            if model_class:
                try:
                    model_class.model_validate_json(raw_content)
                except ValidationError as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(1)
                    continue

            return raw_content, reasoning_text

        except openai.APITimeoutError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
            continue
        except openai.APIError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
            continue


class AdvisorRole(BaseModel):
    role: str = Field(
        description="Краткое название роли советника (например, 'Критик', 'Инвестор', 'Оптимист')."
    )
    perspective: str = Field(
        description="Описание точки зрения или подхода, с которой советник будет рассматривать задачу."
    )


class CouncilRoles(BaseModel):
    advisors: List[AdvisorRole] = Field(description="Список подобранных советников.")


def parse_pydantic_code(code_str: str) -> type:
    namespace = {
        "__builtins__": __builtins__,
        "BaseModel": BaseModel,
        "list": list,
        "dict": dict,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "Optional": Optional,
    }
    try:
        exec(code_str, namespace)
    except Exception as e:
        raise ValueError(f"Syntax error in code: {e}")

    model_class = None
    for _, obj in namespace.items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
        ):
            model_class = obj
            break

    if not model_class:
        raise ValueError("No BaseModel subclass found.")

    return model_class


class ResponseDTO:
    def __init__(
        self, text: str, is_valid: Optional[bool], reasoning: Optional[str] = None
    ):
        self.text = text
        self.is_valid = is_valid
        self.reasoning = reasoning


class CollapsibleReasoningBox(QWidget):
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


class ModelWorker(QThread):
    response_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        user_prompt: str,
        system_prompt: str,
        model_class: Optional[type],
        stop_sequences: Optional[list] = None,
        temperature: float = 0.3,
        model_id: Optional[str] = None,
    ):
        super().__init__()
        self.user_prompt = user_prompt
        self.system_prompt = system_prompt
        self.model_class = model_class
        self.stop_sequences = stop_sequences or []
        self.temperature = temperature
        self.model_id = model_id if model_id else YANDEX_CLOUD_MODEL

    def run(self):
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": self.user_prompt})

        schema_dict = None
        if self.model_class:
            schema_dict = {
                "type": "json_schema",
                "json_schema": {
                    "name": "user_defined_schema",
                    "strict": True,
                    "schema": self.model_class.model_json_schema(),
                },
            }

        try:
            raw_content, reasoning_text = call_llm_with_retry(
                self,
                messages,
                response_format=schema_dict,
                model_class=self.model_class,
                temperature=self.temperature,
                model_id=self.model_id,
            )

            is_valid = None
            if self.model_class:
                try:
                    self.model_class.model_validate_json(raw_content)
                    is_valid = True
                except ValidationError as e:
                    is_valid = False

            display_text = raw_content
            try:
                parsed_json = json.loads(raw_content)
                display_text = json.dumps(parsed_json, indent=4, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

            self.response_ready.emit(
                ResponseDTO(display_text, is_valid, reasoning_text)
            )

        except InterruptionRequestedError:
            self.error_occurred.emit("Запрос прерван пользователем.")
        except Exception as e:
            self.error_occurred.emit(f"Произошла ошибка при обращении к API: {e}")


class StandardChatTab(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def _make_label(
        self, text: str, size: int, color: str, bold: bool = True
    ) -> QLabel:
        label = QLabel(text)
        label.setFont(
            QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        )
        label.setStyleSheet(f"color: {color};")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return label

    def init_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 40, 40, 40)

        system_label = self._make_label(
            "Системный промпт (опционально):", 12, "#A0A0A0"
        )
        layout.addWidget(system_label)

        self.system_prompt_field = QTextEdit()
        self.system_prompt_field.setPlaceholderText(
            "Задайте роль или инструкции для модели..."
        )
        self.system_prompt_field.setFont(QFont("Segoe UI", 12))
        self.system_prompt_field.setStyleSheet(self._get_text_edit_style())
        self.system_prompt_field.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.system_prompt_field.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.system_prompt_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.system_prompt_field)

        input_label = self._make_label("Введите ваш вопрос:", 14, "#E0E0E0")
        input_label.setStyleSheet("color: #E0E0E0; padding-top: 10px;")
        layout.addWidget(input_label)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Введите ваш промпт здесь...")
        self.input_field.setFont(QFont("Segoe UI", 12))
        self.input_field.setStyleSheet(self._get_text_edit_style())
        self.input_field.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.input_field.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.input_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()

        self.send_button = QPushButton("Отправить")
        self.send_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setStyleSheet("""
            QPushButton { background-color: #0078D4; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px; font-weight: bold; }
            QPushButton:hover { background-color: #1084D8; }
            QPushButton:disabled { background-color: #3E3E42; color: #808080; }
        """)
        self.send_button.clicked.connect(self.send_prompt)
        btn_layout.addWidget(self.send_button)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setStyleSheet(
            "background-color: #D83B01; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px;"
        )
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_generation)
        btn_layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setStyleSheet(
            "background-color: #3E3E42; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px;"
        )
        self.clear_button.setVisible(False)
        self.clear_button.clicked.connect(self.clear_tab)
        btn_layout.addWidget(self.clear_button)

        layout.addLayout(btn_layout)

        model_label = self._make_label("Выбор модели:", 12, "#B0B0B0", bold=False)
        layout.addWidget(model_label)

        self.model_combobox = QComboBox()
        self.model_combobox.addItems(
            [
                "GPT OSS 120B (gpt-oss-120b/latest)",
                "Qwen3.6-35B (qwen3.6-35b-a3b/latest)",
                "Alice AI LLM Flash (aliceai-llm-flash/latest)",
            ]
        )
        self.model_combobox.setStyleSheet("""
            QComboBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; }
        """)
        layout.addWidget(self.model_combobox)

        self.settings_button = QPushButton("Дополнительные настройки")
        self.settings_button.setCheckable(True)
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setStyleSheet("""
            QPushButton { background-color: #2D2D30; color: #E0E0E0; border: 1px solid #3E3E42; border-radius: 8px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background-color: #3E3E42; }
        """)
        self.settings_button.clicked.connect(self.toggle_settings)
        layout.addWidget(self.settings_button)

        self.settings_frame = QFrame()
        self.settings_frame.setVisible(False)
        self.settings_frame.setStyleSheet("""
            QFrame { background-color: #252526; border: 1px solid #3E3E42; border-radius: 10px; padding: 15px; }
        """)

        settings_layout = QVBoxLayout(self.settings_frame)
        settings_layout.setContentsMargins(15, 15, 15, 15)

        temp_label = self._make_label(
            "Температура модели (0.0 - 2.0):",
            11,
            "#B0B0B0",
            bold=False,
        )
        settings_layout.addWidget(temp_label)

        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0.0, 2.0)
        self.temp_spinbox.setSingleStep(0.1)
        self.temp_spinbox.setValue(0.3)
        self.temp_spinbox.setStyleSheet("""
            QDoubleSpinBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 13px; }
            QDoubleSpinBox:focus { border: 2px solid #0078D4; }
        """)
        settings_layout.addWidget(self.temp_spinbox)

        self.use_schema_checkbox = QCheckBox(
            "Использовать структурированный вывод (Pydantic схема)"
        )
        self.use_schema_checkbox.setStyleSheet(
            "QCheckBox { color: #E0E0E0; spacing: 10px; font-size: 13px; }"
        )
        self.use_schema_checkbox.toggled.connect(self.toggle_schema_input)
        settings_layout.addWidget(self.use_schema_checkbox)

        self.schema_label = self._make_label(
            "Код Pydantic модели (должен содержать класс, наследующийся от BaseModel):",
            11,
            "#B0B0B0",
            bold=False,
        )
        self.schema_label.setEnabled(False)
        settings_layout.addWidget(self.schema_label)

        self.schema_field = QTextEdit()
        self.schema_field.setPlaceholderText(
            "class MyModel(BaseModel):\n    name: str\n    age: int"
        )
        self.schema_field.setFont(QFont("Consolas", 11))
        self.schema_field.setStyleSheet(self._get_text_edit_style())
        self.schema_field.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.schema_field.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.schema_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.schema_field.setEnabled(False)
        settings_layout.addWidget(self.schema_field)

        stop_label = self._make_label(
            "Stop-последовательности (по одной на строку, опционально):",
            11,
            "#B0B0B0",
            bold=False,
        )
        settings_layout.addWidget(stop_label)

        self.stop_field = QTextEdit()
        self.stop_field.setPlaceholderText("Например:\nEND\n---")
        self.stop_field.setFont(QFont("Consolas", 11))
        self.stop_field.setStyleSheet(self._get_text_edit_style())
        self.stop_field.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.stop_field.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.stop_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        settings_layout.addWidget(self.stop_field)

        layout.addWidget(self.settings_frame)

        response_label = self._make_label("Ответ модели:", 14, "#E0E0E0")
        response_label.setStyleSheet("color: #E0E0E0; padding-top: 10px;")
        layout.addWidget(response_label)

        self.validation_label = QLabel("")
        self.validation_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.validation_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.validation_label.hide()
        layout.addWidget(self.validation_label)

        self.response_container = QWidget()
        self.response_container_layout = QVBoxLayout(self.response_container)
        self.response_container_layout.setContentsMargins(0, 0, 0, 0)
        self.response_container_layout.setSpacing(10)
        layout.addWidget(self.response_container)

        self.reasoning_box = None

        self.response_field = QTextEdit()
        self.response_field.setReadOnly(True)
        self.response_field.setPlaceholderText("Здесь появится ответ модели...")
        self.response_field.setFont(QFont("Consolas", 12))
        self.response_field.setStyleSheet(self._get_text_edit_style())
        self.response_field.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.response_field.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.response_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.response_container_layout.addWidget(self.response_field)

        layout.addStretch()
        scroll_area.setWidget(central_widget)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        self.system_prompt_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.system_prompt_field)
        )
        self.input_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.input_field)
        )
        self.schema_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.schema_field)
        )
        self.stop_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.stop_field)
        )
        self.response_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.response_field)
        )

    def _get_text_edit_style(self) -> str:
        return """
            QTextEdit { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 12px; padding: 15px; selection-background-color: #0078D4; }
            QTextEdit:focus { border: 2px solid #0078D4; }
            QTextEdit::placeholder { color: #808080; }
        """

    def update_text_edit_height(self, edit: QTextEdit):
        edit.document().adjustSize()
        height = int(edit.document().size().height())
        edit.setFixedHeight(max(height + 42, 60))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "system_prompt_field"):
            self.update_text_edit_height(self.system_prompt_field)
        if hasattr(self, "input_field"):
            self.update_text_edit_height(self.input_field)
        if hasattr(self, "schema_field"):
            self.update_text_edit_height(self.schema_field)
        if hasattr(self, "stop_field"):
            self.update_text_edit_height(self.stop_field)
        if hasattr(self, "response_field"):
            self.update_text_edit_height(self.response_field)

    def toggle_settings(self, checked: bool):
        self.settings_frame.setVisible(checked)
        self.settings_button.setText(
            "Скрыть настройки" if checked else "Дополнительные настройки"
        )

    def toggle_schema_input(self, checked: bool):
        self.schema_field.setEnabled(checked)
        self.schema_label.setEnabled(checked)
        if not checked:
            self.schema_field.clear()
            self.update_text_edit_height(self.schema_field)

    def send_prompt(self):
        user_prompt = self.input_field.toPlainText().strip()
        if not user_prompt:
            QMessageBox.warning(
                self, "Предупреждение", "Пожалуйста, введите текст промпта!"
            )
            return

        system_prompt = self.system_prompt_field.toPlainText().strip()
        use_schema = self.use_schema_checkbox.isChecked()
        schema_code = self.schema_field.toPlainText().strip()
        stop_sequences = [
            line.strip()
            for line in self.stop_field.toPlainText().split("\n")
            if line.strip()
        ]
        temperature = self.temp_spinbox.value()

        selected_model_text = self.model_combobox.currentText()
        if "gpt-oss-120b/latest" in selected_model_text:
            selected_model_id = "gpt-oss-120b/latest"
        elif "qwen3.6-35b-a3b/latest" in selected_model_text:
            selected_model_id = "qwen3.6-35b-a3b/latest"
        else:
            selected_model_id = "aliceai-llm-flash/latest"

        model_class = None
        if use_schema:
            if not schema_code:
                QMessageBox.warning(
                    self, "Предупреждение", "Введите код Pydantic-схемы!"
                )
                return
            try:
                model_class = parse_pydantic_code(schema_code)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", "Схема не прошла валидацию.")
                return

        self.send_button.setVisible(False)
        self.stop_button.setVisible(True)
        self.clear_button.setVisible(False)

        self.response_field.clear()
        self.update_text_edit_height(self.response_field)

        if self.reasoning_box is not None:
            self.response_container_layout.removeWidget(self.reasoning_box)
            self.reasoning_box.deleteLater()
            self.reasoning_box = None

        self.validation_label.setText("Ожидание ответа...")
        self.validation_label.setStyleSheet("color: #808080;")
        self.validation_label.show()

        self.worker = ModelWorker(
            user_prompt,
            system_prompt,
            model_class,
            stop_sequences,
            temperature,
            selected_model_id,
        )
        self.worker.response_ready.connect(self.on_response_ready)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.start()

    def on_response_ready(self, response_dto: ResponseDTO):
        if self.reasoning_box is not None:
            self.response_container_layout.removeWidget(self.reasoning_box)
            self.reasoning_box.deleteLater()
            self.reasoning_box = None

        if response_dto.reasoning:
            self.reasoning_box = CollapsibleReasoningBox(response_dto.reasoning)
            self.response_container_layout.insertWidget(0, self.reasoning_box)

        self.response_field.setText(response_dto.text)
        self.update_text_edit_height(self.response_field)

        if response_dto.is_valid is True:
            self.validation_label.setText("Формат соблюден")
            self.validation_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.validation_label.show()
        elif response_dto.is_valid is False:
            self.validation_label.setText("Формат НЕ соблюден")
            self.validation_label.setStyleSheet("color: #F44336; font-weight: bold;")
            self.validation_label.show()
        else:
            self.validation_label.hide()

        self.send_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.clear_button.setVisible(True)

    def on_error_occurred(self, error: str):
        if "прерван пользователем" not in error:
            QMessageBox.critical(self, "Ошибка", error)
        self.response_field.setText(error)
        self.update_text_edit_height(self.response_field)
        self.validation_label.hide()

        self.send_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.clear_button.setVisible(True)

    def stop_generation(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.stop_button.setEnabled(False)
            self.stop_button.setText("Останавливаем...")

    def clear_tab(self):
        self.input_field.clear()
        self.system_prompt_field.clear()
        self.response_field.clear()
        self.validation_label.hide()

        if self.reasoning_box is not None:
            self.response_container_layout.removeWidget(self.reasoning_box)
            self.reasoning_box.deleteLater()
            self.reasoning_box = None

        self.update_text_edit_height(self.input_field)
        self.update_text_edit_height(self.system_prompt_field)
        self.update_text_edit_height(self.response_field)

        self.clear_button.setVisible(False)


class CouncilWorker(QThread):
    status_updated = pyqtSignal(str)
    advisor_responded = pyqtSignal(str, str)
    judge_responded = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished_successfully = pyqtSignal()

    def __init__(self, user_task: str, num_advisors: int):
        super().__init__()
        self.user_task = user_task
        self.num_advisors = num_advisors

    def run(self):
        try:
            self.status_updated.emit("Шаг 1/3: Подбираем роли советников...")

            s1_system = "Ты — эксперт по организации мозговых штурмов. Твоя задача — подобрать идеальный состав совета для решения задачи пользователя."
            s1_user = f"Задача пользователя: {self.user_task}\n\nПодбери ровно {self.num_advisors} советников, которые рассмотрят эту задачу с максимально разных и полезных точек зрения. Верни JSON со списком их ролей."

            schema_dict = {
                "type": "json_schema",
                "json_schema": {
                    "name": "council_roles",
                    "strict": True,
                    "schema": CouncilRoles.model_json_schema(),
                },
            }

            raw_roles_json, _ = call_llm_with_retry(
                self,
                [
                    {"role": "system", "content": s1_system},
                    {"role": "user", "content": s1_user},
                ],
                response_format=schema_dict,
                model_class=CouncilRoles,
            )

            council = CouncilRoles.model_validate_json(raw_roles_json)

            advisors_responses = []

            for i, advisor in enumerate(council.advisors):
                if self.isInterruptionRequested():
                    raise InterruptionRequestedError()

                self.status_updated.emit(
                    f"Шаг 2/3: Опрашиваем советника {i+1} из {len(council.advisors)} ({advisor.role})..."
                )

                s2_system = f"Ты участвуешь в совете. Твоя роль: {advisor.role}. Твоя точка зрения: {advisor.perspective}. Отвечай подробно и аргументированно."
                s2_user = f"Задача, которую мы обсуждаем: {self.user_task}\n\nДай свой совет и анализ, исходя из своей роли."

                a_response, _ = call_llm_with_retry(
                    self,
                    [
                        {"role": "system", "content": s2_system},
                        {"role": "user", "content": s2_user},
                    ],
                )
                advisors_responses.append(
                    {"role": advisor.role, "response": a_response}
                )
                self.advisor_responded.emit(advisor.role, a_response)

            self.status_updated.emit("Шаг 3/3: Судья выносит финальный вердикт...")

            formatted_responses = "\n\n".join(
                [
                    f"--- Мнение советника '{r['role']}' ---\n{r['response']}"
                    for r in advisors_responses
                ]
            )

            s3_system = "Ты — мудрый и объективный судья. Твоя задача — проанализировать мнения всех советников, отбросить слабые идеи и синтезировать лучшие в итоговый вердикт."
            s3_user = f"Задача: {self.user_task}\n\nМнения советников:\n{formatted_responses}\n\nВынеси свой финальный вердикт."

            j_response, _ = call_llm_with_retry(
                self,
                [
                    {"role": "system", "content": s3_system},
                    {"role": "user", "content": s3_user},
                ],
            )

            self.judge_responded.emit(j_response)
            self.finished_successfully.emit()

        except InterruptionRequestedError:
            self.error_occurred.emit("Генерация совета прервана пользователем.")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка при проведении совета: {e}")


class CouncilTab(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def _make_label(
        self, text: str, size: int, color: str, bold: bool = True
    ) -> QLabel:
        label = QLabel(text)
        label.setFont(
            QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        )
        label.setStyleSheet(f"color: {color};")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return label

    def init_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(40, 40, 40, 40)

        task_label = self._make_label("Задача или вопрос для совета:", 14, "#E0E0E0")
        layout.addWidget(task_label)

        self.task_field = QTextEdit()
        self.task_field.setPlaceholderText("Опишите проблему, которую нужно решить...")
        self.task_field.setFont(QFont("Segoe UI", 12))
        self.task_field.setStyleSheet(self._get_text_edit_style())
        self.task_field.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.task_field.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.task_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.task_field)

        count_layout = QHBoxLayout()
        count_label = self._make_label("Количество советников:", 12, "#A0A0A0")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(2, 10)
        self.count_spin.setValue(3)
        self.count_spin.setStyleSheet("""
            QSpinBox { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 8px; padding: 5px; font-size: 14px; }
            QSpinBox:focus { border: 2px solid #0078D4; }
        """)
        count_layout.addWidget(count_label)
        count_layout.addWidget(self.count_spin)
        count_layout.addStretch()
        layout.addLayout(count_layout)

        btn_layout = QHBoxLayout()

        self.start_button = QPushButton("Запустить совет")
        self.start_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setStyleSheet("""
            QPushButton { background-color: #0078D4; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px; font-weight: bold; }
            QPushButton:hover { background-color: #1084D8; }
            QPushButton:disabled { background-color: #3E3E42; color: #808080; }
        """)
        self.start_button.clicked.connect(self.start_council)
        btn_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setStyleSheet(
            "background-color: #D83B01; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px;"
        )
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_council)
        btn_layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("Очистить")
        self.clear_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setStyleSheet(
            "background-color: #3E3E42; color: #FFFFFF; border: none; border-radius: 10px; padding: 15px 40px;"
        )
        self.clear_button.setVisible(False)
        self.clear_button.clicked.connect(self.clear_tab)
        btn_layout.addWidget(self.clear_button)

        layout.addLayout(btn_layout)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #0078D4; padding-top: 10px;")
        layout.addWidget(self.status_label)

        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(False)
        self.result_browser.setFont(QFont("Segoe UI", 12))
        self.result_browser.setStyleSheet("""
            QTextBrowser { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 12px; padding: 15px; }
            QTextBrowser:focus { border: 2px solid #0078D4; }
        """)
        self.result_browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.result_browser)

        scroll_area.setWidget(central_widget)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        self.task_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.task_field)
        )

    def _get_text_edit_style(self) -> str:
        return """
            QTextEdit { background-color: #2D2D30; color: #FFFFFF; border: 2px solid #3E3E42; border-radius: 12px; padding: 15px; selection-background-color: #0078D4; }
            QTextEdit:focus { border: 2px solid #0078D4; }
            QTextEdit::placeholder { color: #808080; }
        """

    def update_text_edit_height(self, edit: QTextEdit):
        edit.document().adjustSize()
        height = int(edit.document().size().height())
        edit.setFixedHeight(max(height + 42, 60))

    def append_html(self, html: str):
        self.result_browser.append(html)
        sb = self.result_browser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_council(self):
        task = self.task_field.toPlainText().strip()
        if not task:
            QMessageBox.warning(
                self, "Предупреждение", "Пожалуйста, введите задачу для совета!"
            )
            return

        self.start_button.setVisible(False)
        self.stop_button.setVisible(True)
        self.stop_button.setEnabled(True)
        self.stop_button.setText("Стоп")
        self.clear_button.setVisible(False)

        self.result_browser.clear()
        self.status_label.setText("Запуск...")

        self.worker = CouncilWorker(task, self.count_spin.value())
        self.worker.status_updated.connect(self.on_status_updated)
        self.worker.advisor_responded.connect(self.on_advisor_responded)
        self.worker.judge_responded.connect(self.on_judge_responded)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.finished_successfully.connect(self.on_finished)
        self.worker.start()

    def on_status_updated(self, text: str):
        self.status_label.setText(text)
        self.append_html(f"<p style='color: #808080; font-style: italic;'>{text}</p>")

    def on_advisor_responded(self, role: str, text: str):
        safe_text = text.replace("\n", "<br>")
        html = f"<h3 style='color: #4CAF50; margin-top: 15px;'>Советник: {role}</h3><p>{safe_text}</p><hr style='border: 1px solid #3E3E42;'>"
        self.append_html(html)

    def on_judge_responded(self, text: str):
        safe_text = text.replace("\n", "<br>")
        html = f"<h2 style='color: #FFC107; margin-top: 20px;'>Вердикт Судьи</h2><p style='font-size: 14px; font-weight: 500;'>{safe_text}</p>"
        self.append_html(html)

    def on_error_occurred(self, error: str):
        self.status_label.setText(f"Статус: {error}")
        self.status_label.setStyleSheet("color: #F44336;")
        self.append_html(f"<p style='color: #F44336; font-weight: bold;'>{error}</p>")

        self.start_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.clear_button.setVisible(True)

    def on_finished(self):
        self.status_label.setText("Совет успешно завершен!")
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.append_html(
            "<p style='color: #4CAF50; font-weight: bold; margin-top: 20px;'>Процесс завершен.</p>"
        )

        self.start_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.clear_button.setVisible(True)

    def stop_council(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.stop_button.setEnabled(False)
            self.stop_button.setText("Останавливаем...")
            self.status_label.setText("Останавливаем процесс...")

    def clear_tab(self):
        self.task_field.clear()
        self.result_browser.clear()
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #0078D4; padding-top: 10px;")
        self.clear_button.setVisible(False)
        self.update_text_edit_height(self.task_field)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yandex Cloud AI Chat")

        self.tabs = QTabWidget()
        self.tabs.addTab(StandardChatTab(), "Обычный режим")
        self.tabs.addTab(CouncilTab(), "Режим совета")

        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3E3E42; background-color: #131314; }
            QTabBar::tab {
                background: #252526;
                color: #E0E0E0;
                padding: 12px 20px;
                border: 1px solid #3E3E42;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background: #131314;
                color: #0078D4;
                border-bottom: 2px solid #0078D4;
            }
            QTabBar::tab:hover {
                background: #2D2D30;
            }
        """)

        self.setCentralWidget(self.tabs)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.ColorRole.Window, QColor(19, 19, 20))
    dark_palette.setColor(dark_palette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(dark_palette.ColorRole.Base, QColor(32, 32, 32))
    dark_palette.setColor(dark_palette.ColorRole.AlternateBase, QColor(45, 45, 48))
    dark_palette.setColor(dark_palette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(dark_palette.ColorRole.Button, QColor(45, 45, 48))
    dark_palette.setColor(dark_palette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(dark_palette.ColorRole.Highlight, QColor(0, 120, 212))
    dark_palette.setColor(dark_palette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
