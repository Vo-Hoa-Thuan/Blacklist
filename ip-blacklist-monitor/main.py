"""
IP Blacklist Monitor - Entry Point
Chạy: python main.py
Build exe: pyinstaller --onefile --windowed --name "IP Blacklist Monitor" main.py
"""
import sys
import os

# Đảm bảo import được các module trong project
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IP Blacklist Monitor")
    app.setOrganizationName("BlacklistMonitor")

    # Thiết lập font mặc định
    from PySide6.QtGui import QFont
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
