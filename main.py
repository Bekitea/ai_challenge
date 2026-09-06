import json
import logging
import sys
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import API_KEY, BASE_URL, FOLDER_ID, YANDEX_CLOUD_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, project=FOLDER_ID)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


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
    def __init__(self, text: str, is_valid: Optional[bool]):
        self.text = text
        self.is_valid = is_valid


class ModelWorker(QThread):
    response_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(
        self, user_prompt: str, system_prompt: str, model_class: Optional[type]
    ):
        super().__init__()
        self.user_prompt = user_prompt
        self.system_prompt = system_prompt
        self.model_class = model_class

    def run(self):
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": self.user_prompt})

        kwargs = {
            "model": f"gpt://{FOLDER_ID}/{YANDEX_CLOUD_MODEL}",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1500,
        }

        if self.model_class:
            schema_dict = {
                "type": "json_schema",
                "json_schema": {
                    "name": "user_defined_schema",
                    "strict": True,
                    "schema": self.model_class.model_json_schema(),
                },
            }
            kwargs["response_format"] = schema_dict

        log_kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}
        logging.info(f"API Request DTO: {json.dumps(log_kwargs, ensure_ascii=False)}")
        if "response_format" in kwargs:
            logging.info(f"Response Format Schema: {kwargs['response_format']}")

        try:
            response = client.chat.completions.create(**kwargs)
            raw_content = response.choices[0].message.content or ""

            logging.info(f"API Response DTO: {raw_content}")

            is_valid = None

            if self.model_class:
                try:
                    self.model_class.model_validate_json(raw_content)
                    is_valid = True
                except ValidationError as e:
                    is_valid = False
                    logging.error(f"Validation error: {e}")

            display_text = raw_content
            try:
                parsed_json = json.loads(raw_content)
                display_text = json.dumps(parsed_json, indent=4, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

            self.response_ready.emit(ResponseDTO(display_text, is_valid))

        except Exception as e:
            self.error_occurred.emit(f"Произошла ошибка при обращении к API: {e}")


class ChatWindow(QMainWindow):
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
        self.setWindowTitle("Yandex Cloud AI Chat")

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

        self.send_button = QPushButton("Отправить")
        self.send_button.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 15px 40px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1084D8; }
            QPushButton:pressed { background-color: #006CBE; }
            QPushButton:disabled { background-color: #3E3E42; color: #808080; }
        """)
        self.send_button.clicked.connect(self.send_prompt)
        layout.addWidget(self.send_button)

        self.settings_button = QPushButton("Дополнительные настройки")
        self.settings_button.setCheckable(True)
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #E0E0E0;
                border: 1px solid #3E3E42;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3E3E42; }
        """)
        self.settings_button.clicked.connect(self.toggle_settings)
        layout.addWidget(self.settings_button)

        self.settings_frame = QFrame()
        self.settings_frame.setVisible(False)
        self.settings_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3E3E42;
                border-radius: 10px;
                padding: 15px;
            }
        """)

        settings_layout = QVBoxLayout(self.settings_frame)
        settings_layout.setContentsMargins(15, 15, 15, 15)

        self.use_schema_checkbox = QCheckBox(
            "Использовать структурированный вывод (Pydantic схема)"
        )
        self.use_schema_checkbox.setStyleSheet("""
            QCheckBox {
                color: #E0E0E0;
                spacing: 10px;
                font-size: 13px;
            }
        """)
        self.use_schema_checkbox.toggled.connect(self.toggle_schema_input)
        settings_layout.addWidget(self.use_schema_checkbox)

        self.schema_label = self._make_label(
            "Код Pydantic модели (должен содержать класс, наследующийся от BaseModel):",
            11,
            "#B0B0B0",
            bold=False,
        )
        self.schema_label.setStyleSheet("color: #B0B0B0; padding-top: 10px;")
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
        layout.addWidget(self.response_field)

        layout.addStretch()

        scroll_area.setWidget(central_widget)
        self.setCentralWidget(scroll_area)

        self.system_prompt_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.system_prompt_field)
        )
        self.input_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.input_field)
        )
        self.schema_field.document().contentsChanged.connect(
            lambda: self.update_text_edit_height(self.schema_field)
        )

        self.update_text_edit_height(self.system_prompt_field)
        self.update_text_edit_height(self.input_field)
        self.update_text_edit_height(self.schema_field)
        self.update_text_edit_height(self.response_field)

    def _get_text_edit_style(self) -> str:
        return """
            QTextEdit {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 2px solid #3E3E42;
                border-radius: 12px;
                padding: 15px;
                selection-background-color: #0078D4;
            }
            QTextEdit:focus {
                border: 2px solid #0078D4;
            }
            QTextEdit::placeholder {
                color: #808080;
            }
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
                logging.error(f"Schema parsing/validation error: {e}")
                QMessageBox.critical(self, "Ошибка", "Схема не прошла валидацию.")
                return

        self.send_button.setEnabled(False)
        self.send_button.setText("Обработка...")
        self.response_field.clear()
        self.update_text_edit_height(self.response_field)

        self.validation_label.setText("Ожидание ответа...")
        self.validation_label.setStyleSheet("color: #808080;")
        self.validation_label.show()

        self.worker = ModelWorker(user_prompt, system_prompt, model_class)
        self.worker.response_ready.connect(self.on_response_ready)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.start()

    def on_response_ready(self, response_dto: ResponseDTO):
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

        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")

    def on_error_occurred(self, error: str):
        logging.error(f"API Error: {error}")
        QMessageBox.critical(self, "Ошибка", error)
        self.response_field.setText(error)
        self.update_text_edit_height(self.response_field)
        self.validation_label.hide()
        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")


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

    window = ChatWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
