import sys

from openai import OpenAI
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import API_KEY, BASE_URL, FOLDER_ID, YANDEX_CLOUD_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, project=FOLDER_ID)


class ModelWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, user_prompt: str):
        super().__init__()
        self.user_prompt = user_prompt

    def run(self):
        try:
            response = client.chat.completions.create(
                model=f"gpt://{FOLDER_ID}/{YANDEX_CLOUD_MODEL}",
                messages=[{"role": "user", "content": self.user_prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            self.response_ready.emit(response.choices[0].message.content)
        except Exception as e:
            self.error_occurred.emit(f"Произошла ошибка при обращении к API: {e}")


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Yandex Cloud AI Chat")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        input_label = QLabel("Введите ваш вопрос:")
        input_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        input_label.setStyleSheet("color: #E0E0E0; padding: 5px;")
        layout.addWidget(input_label)

        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Введите ваш промпт здесь...")
        self.input_field.setMaximumHeight(180)
        self.input_field.setFont(QFont("Segoe UI", 12))
        self.input_field.setStyleSheet("""
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
        """)
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
            QPushButton:hover {
                background-color: #1084D8;
            }
            QPushButton:pressed {
                background-color: #006CBE;
            }
            QPushButton:disabled {
                background-color: #3E3E42;
                color: #808080;
            }
        """)
        self.send_button.clicked.connect(self.send_prompt)
        layout.addWidget(self.send_button)

        response_label = QLabel("Ответ модели:")
        response_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        response_label.setStyleSheet("color: #E0E0E0; padding: 5px;")
        layout.addWidget(response_label)

        self.response_field = QTextEdit()
        self.response_field.setReadOnly(True)
        self.response_field.setPlaceholderText("Здесь появится ответ модели...")
        self.response_field.setFont(QFont("Segoe UI", 12))
        self.response_field.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 2px solid #3E3E42;
                border-radius: 12px;
                padding: 15px;
                selection-background-color: #0078D4;
            }
            QTextEdit::placeholder {
                color: #808080;
            }
        """)
        layout.addWidget(self.response_field)

    def send_prompt(self):
        user_prompt = self.input_field.toPlainText().strip()

        if not user_prompt:
            QMessageBox.warning(
                self, "Предупреждение", "Пожалуйста, введите текст промпта!"
            )
            return

        self.send_button.setEnabled(False)
        self.send_button.setText("Обработка...")
        self.response_field.clear()

        self.worker = ModelWorker(user_prompt)
        self.worker.response_ready.connect(self.on_response_ready)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.start()

    def on_response_ready(self, response: str):
        self.response_field.setText(response)
        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")

    def on_error_occurred(self, error: str):
        QMessageBox.critical(self, "Ошибка", error)
        self.response_field.setText(error)
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
