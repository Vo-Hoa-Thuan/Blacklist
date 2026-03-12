"""
Email Settings Dialog - Cấu hình SMTP gửi email cảnh báo
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget
)
from PySide6.QtGui import QFont

from core.email_notifier import EmailConfig, EmailNotifier

BG    = "#0d1117"
CARD  = "#161b22"
INPUT = "#21262d"
BORD  = "#30363d"
TEXT  = "#e6edf3"
MUTED = "#8b949e"
BLUE  = "#58a6ff"
GREEN = "#3fb950"
RED   = "#f85149"


def _inp_style():
    return (f"background:{INPUT}; color:{TEXT}; border:1px solid {BORD};"
            f"border-radius:6px; padding:5px 8px; font-size:13px;")

def _lbl(t):
    l = QLabel(t)
    l.setStyleSheet(f"color:{TEXT}; background:transparent;")
    return l


class EmailSettingsDialog(QDialog):
    """Dialog cấu hình SMTP để gửi email cảnh báo."""

    def __init__(self, config: EmailConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ Cấu hình Email SMTP")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background:{BG}; color:{TEXT};
                       font-family:'Segoe UI',Arial,sans-serif; font-size:13px; }}
            QLabel {{ background:transparent; }}
            QGroupBox {{
                background:{CARD}; border:1px solid {BORD};
                border-radius:8px; margin-top:8px; padding-top:10px;
                font-weight:600; color:{TEXT};
            }}
            QGroupBox::title {{ subcontrol-origin:margin; left:10px; color:{BLUE}; }}
            QCheckBox {{ color:{TEXT}; background:transparent; }}
        """)
        self._config = config
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # SMTP Server group
        grp = QGroupBox("📡  Máy chủ SMTP")
        form = QFormLayout()
        form.setSpacing(8)

        self.inp_host = QLineEdit()
        self.inp_host.setPlaceholderText("smtp.gmail.com")
        self.inp_host.setStyleSheet(_inp_style())

        self.inp_port = QSpinBox()
        self.inp_port.setRange(1, 65535)
        self.inp_port.setValue(587)
        self.inp_port.setStyleSheet(_inp_style())

        self.chk_tls = QCheckBox("Dùng STARTTLS (port 587) — Bỏ chọn nếu dùng SSL port 465")
        self.chk_tls.setChecked(True)

        self.inp_user = QLineEdit()
        self.inp_user.setPlaceholderText("email@domain.com")
        self.inp_user.setStyleSheet(_inp_style())

        self.inp_pass = QLineEdit()
        self.inp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_pass.setPlaceholderText("App password / mật khẩu ứng dụng")
        self.inp_pass.setStyleSheet(_inp_style())

        self.inp_recipient = QLineEdit()
        self.inp_recipient.setPlaceholderText("recipient@domain.com")
        self.inp_recipient.setStyleSheet(_inp_style())

        form.addRow(_lbl("SMTP Host:"), self.inp_host)
        form.addRow(_lbl("SMTP Port:"), self.inp_port)
        form.addRow("", self.chk_tls)
        form.addRow(_lbl("Email gửi:"), self.inp_user)
        form.addRow(_lbl("Mật khẩu:"), self.inp_pass)
        form.addRow(_lbl("Email nhận:"), self.inp_recipient)
        grp.setLayout(form)
        layout.addWidget(grp)

        # Ghi chú Gmail
        note = QLabel(
            "💡 <b>Gmail:</b> Dùng App Password tại "
            "<a style='color:#58a6ff' href='https://myaccount.google.com/apppasswords'>"
            "myaccount.google.com/apppasswords</a><br>"
            "Cần bật 2FA trước. Host: smtp.gmail.com | Port: 587 | TLS: ✓"
        )
        note.setOpenExternalLinks(True)
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{MUTED}; font-size:12px; background:{INPUT};"
            f"padding:8px; border-radius:6px; border:1px solid {BORD};"
        )
        layout.addWidget(note)

        # Nút
        btn_row = QHBoxLayout()
        self.btn_test = QPushButton("📧 Gửi mail test")
        self.btn_test.setStyleSheet(
            f"QPushButton {{background:{INPUT}; color:{TEXT}; border:1px solid {BORD};"
            f"border-radius:6px; padding:7px 14px; font-weight:600;}}"
            f"QPushButton:hover {{background:{BORD};}}"
        )
        self.btn_test.clicked.connect(self._send_test)

        btn_save = QPushButton("💾 Lưu cấu hình")
        btn_save.setStyleSheet(
            f"QPushButton {{background:{BLUE}; color:#0d1117; border:none;"
            f"border-radius:6px; padding:7px 18px; font-weight:700;}}"
            f"QPushButton:hover {{background:#79c0ff;}}"
        )
        btn_save.clicked.connect(self._save_and_close)

        btn_cancel = QPushButton("Hủy")
        btn_cancel.setStyleSheet(
            f"QPushButton {{background:{INPUT}; color:{MUTED}; border:1px solid {BORD};"
            f"border-radius:6px; padding:7px 14px;}}"
            f"QPushButton:hover {{background:{BORD};}}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_test)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _load_config(self):
        c = self._config
        self.inp_host.setText(c.smtp_host)
        self.inp_port.setValue(c.smtp_port)
        self.inp_user.setText(c.username)
        self.inp_pass.setText(c.password)
        self.inp_recipient.setText(c.recipient)
        self.chk_tls.setChecked(c.use_tls)

    def _get_config(self) -> EmailConfig:
        return EmailConfig(
            smtp_host=self.inp_host.text().strip(),
            smtp_port=self.inp_port.value(),
            username=self.inp_user.text().strip(),
            password=self.inp_pass.text(),
            recipient=self.inp_recipient.text().strip(),
            use_tls=self.chk_tls.isChecked(),
        )

    def _send_test(self):
        cfg = self._get_config()
        if not cfg.is_configured():
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng điền đầy đủ cấu hình SMTP!")
            return
        self.btn_test.setText("Đang gửi...")
        self.btn_test.setEnabled(False)
        notifier = EmailNotifier(cfg)
        ok, err = notifier.send_test()
        self.btn_test.setText("📧 Gửi mail test")
        self.btn_test.setEnabled(True)
        if ok:
            QMessageBox.information(self, "Thành công", "✅ Email test đã gửi thành công!")
        else:
            QMessageBox.critical(self, "Lỗi", f"❌ Gửi mail thất bại:\n{err}")

    def _save_and_close(self):
        self._config = self._get_config()
        self.accept()

    def get_config(self) -> EmailConfig:
        return self._config
