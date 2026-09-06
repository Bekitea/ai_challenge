from openai import OpenAI
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import sys

from config import API_KEY, BASE_URL, FOLDER_ID, YANDEX_CLOUD_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, project=FOLDER_ID)


class ModelWorker(QThread):
    """Рабочий поток для запроса к модели без блокировки UI"""

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
    """Основное окно приложения с одним полем ввода и ответом"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Yandex Cloud AI Chat")
        self.setGeometry(100, 100, 800, 600)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Метка для поля ввода
        input_label = QLabel("Введите ваш вопрос:")
        layout.addWidget(input_label)

        # Поле ввода пользовательского промпта (только один ввод)
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Введите ваш промпт здесь...")
        self.input_field.setMaximumHeight(150)
        layout.addWidget(self.input_field)

        # Кнопка отправки
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_prompt)
        layout.addWidget(self.send_button)

        # Метка для ответа
        response_label = QLabel("Ответ модели:")
        layout.addWidget(response_label)

        # Поле для отображения ответа
        self.response_field = QTextEdit()
        self.response_field.setReadOnly(True)
        self.response_field.setPlaceholderText("Здесь появится ответ модели...")
        layout.addWidget(self.response_field)

    def send_prompt(self):
        """Отправка промпта модели"""
        user_prompt = self.input_field.toPlainText().strip()

        if not user_prompt:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, введите текст промпта!")
            return

        # Блокируем кнопку во время запроса
        self.send_button.setEnabled(False)
        self.send_button.setText("Обработка...")
        self.response_field.clear()

        # Запускаем worker в отдельном потоке
        self.worker = ModelWorker(user_prompt)
        self.worker.response_ready.connect(self.on_response_ready)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.start()

    def on_response_ready(self, response: str):
        """Обработка успешного ответа"""
        self.response_field.setText(response)
        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")

    def on_error_occurred(self, error: str):
        """Обработка ошибки"""
        QMessageBox.critical(self, "Ошибка", error)
        self.response_field.setText(error)
        self.send_button.setEnabled(True)
        self.send_button.setText("Отправить")


def main():
    app = QApplication(sys.argv)

    # Устанавливаем стиль приложения
    app.setStyle("Fusion")

    window = ChatWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
