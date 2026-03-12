"""
Alert Dialog - Popup cảnh báo khi phát hiện IP bị blacklist
Hiển thị thông tin rõ ràng và có thể kéo/di chuyển
"""
from typing import List
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QFrame
)

BG    = "#0d1117"
CARD  = "#161b22"
INPUT = "#21262d"
BORD  = "#30363d"
TEXT  = "#e6edf3"
MUTED = "#8b949e"
RED   = "#f85149"
AMBER = "#d29922"
GREEN = "#3fb950"
BLUE  = "#58a6ff"

RISK_COLORS = {"Safe": GREEN, "Warning": AMBER, "Danger": RED}


class AlertDialog(QDialog):
    """
    Popup cảnh báo hiện khi có IP bị blacklist.
    Tự đóng sau 60 giây nếu người dùng không tương tác.
    """

    def __init__(self, alerted_results: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠ Cảnh báo Blacklist")
        self.setMinimumSize(580, 420)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(f"""
            QDialog {{ background:{BG}; color:{TEXT};
                       font-family:'Segoe UI',Arial,sans-serif; font-size:13px; }}
            QLabel {{ background:transparent; }}
        """)
        self._alerted = alerted_results
        self._countdown = 60
        self._build_ui()

        # Tự đóng sau 60 giây
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        hdr = QHBoxLayout()
        icon = QLabel("🚨")
        icon.setStyleSheet(f"font-size:28px; background:transparent;")
        hdr.addWidget(icon)

        title_col = QVBoxLayout()
        title = QLabel("Phát hiện IP bị Blacklist!")
        title.setStyleSheet(f"color:{RED}; font-size:16px; font-weight:700;")
        sub = QLabel(f"{len(self._alerted)} IP cần xử lý ngay")
        sub.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        hdr.addLayout(title_col)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color:{BORD};")
        layout.addWidget(div)

        # Bảng IP bị dính
        tree = QTreeWidget()
        tree.setColumnCount(5)
        tree.setHeaderLabels(["IP", "Tổng BL", "BL Lớn", "Risk", "Blacklists lớn"])
        tree.setColumnWidth(0, 120)
        tree.setColumnWidth(1, 60)
        tree.setColumnWidth(2, 60)
        tree.setColumnWidth(3, 75)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.setStyleSheet(f"""
            QTreeWidget {{background:{CARD}; color:{TEXT}; border:1px solid {BORD}; border-radius:6px;}}
            QTreeWidget::item {{padding:6px 4px; border-bottom:1px solid {BORD};}}
            QTreeWidget::item:alternate {{background:{INPUT};}}
            QHeaderView::section {{background:{INPUT}; color:{MUTED}; border:none;
                border-right:1px solid {BORD}; border-bottom:1px solid {BORD}; padding:6px;}}
        """)

        for r in self._alerted:
            risk_color = RISK_COLORS.get(r.risk_level, TEXT)
            major_names = ", ".join(e.name for e in r.major_listed[:3]) or "—"
            item = QTreeWidgetItem(tree)
            item.setText(0, r.ip)
            item.setText(1, str(r.total_listed))
            item.setText(2, str(len(r.major_listed)))
            item.setText(3, r.risk_level)
            item.setText(4, major_names)
            item.setForeground(3, QColor(risk_color))
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(tree)

        # Gợi ý hành động
        tip = QLabel(
            "💡 Kiểm tra và gỡ IP khỏi blacklist qua các công cụ như: "
            "MXToolbox, Barracuda Lookup, Spamhaus Removal."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(
            f"color:{MUTED}; font-size:12px; background:{INPUT};"
            f"padding:8px; border-radius:6px; border:1px solid {BORD};"
        )
        layout.addWidget(tip)

        # Nút
        btn_row = QHBoxLayout()
        self.lbl_timer = QLabel(f"Tự đóng sau {self._countdown}s")
        self.lbl_timer.setStyleSheet(f"color:{MUTED}; font-size:12px;")
        btn_row.addWidget(self.lbl_timer)
        btn_row.addStretch()

        btn_close = QPushButton("Đã hiểu, Đóng")
        btn_close.setStyleSheet(
            f"QPushButton {{background:{BLUE}; color:#0d1117; border:none;"
            f"border-radius:6px; padding:7px 18px; font-weight:700;}}"
            f"QPushButton:hover {{background:#79c0ff;}}"
        )
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _tick(self):
        self._countdown -= 1
        self.lbl_timer.setText(f"Tự đóng sau {self._countdown}s")
        if self._countdown <= 0:
            self._timer.stop()
            self.accept()
