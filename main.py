"""Главный файл приложения Yandex Cloud AI Chat."""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QFont

from gui import MainWindow


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
