"""
Main Window - Giao diện chính của IP Blacklist Monitor
Bao gồm: cấu hình, bảng kết quả, panel chi tiết, log, auto scheduler,
         charts, email alert, popup cảnh báo
"""
import csv
import json
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSpinBox,
    QSizePolicy,
)

from core.api_client import CheckWorker, is_valid_ipv4
from core.config_manager import ConfigManager
from core.email_notifier import EmailConfig, EmailNotifier
from core.history_manager import HistoryManager
from core.notification_tracker import NotificationTracker
from core.parser import ParsedResult
from core.scheduler import AutoScheduler

from ui.alert_dialog import AlertDialog
from ui.email_settings_dialog import EmailSettingsDialog
from ui.charts_widget import ChartsWidget

# ───────────── Màu sắc chủ đề tối hiện đại ─────────────
BG_MAIN      = "#0d1117"
BG_CARD      = "#161b22"
BG_INPUT     = "#21262d"
BG_HOVER     = "#30363d"
BORDER       = "#30363d"
TEXT_PRIMARY = "#e6edf3"
TEXT_MUTED   = "#8b949e"
ACCENT_BLUE  = "#58a6ff"
ACCENT_GREEN = "#3fb950"
ACCENT_RED   = "#f85149"
ACCENT_AMBER = "#d29922"

RISK_COLORS = {
    "Safe":    "#3fb950",
    "Warning": "#d29922",
    "Danger":  "#f85149",
}

SAMPLE_IPS = ["1.1.1.1", "8.8.8.8", "74.125.224.72"]


def _card_style(radius: int = 8) -> str:
    return (
        f"background:{BG_CARD}; border:1px solid {BORDER}; "
        f"border-radius:{radius}px; padding:10px;"
    )


def _btn_style(
    bg: str = ACCENT_BLUE,
    hover: str = "#79c0ff",
    text: str = "#0d1117",
    radius: int = 6,
) -> str:
    return (
        f"QPushButton {{"
        f"  background:{bg}; color:{text}; border:none;"
        f"  border-radius:{radius}px; padding:6px 14px;"
        f"  font-weight:600; font-size:13px;}}"
        f"QPushButton:hover {{ background:{hover}; }}"
        f"QPushButton:disabled {{ background:{BG_HOVER}; color:{TEXT_MUTED}; }}"
    )


def _input_style() -> str:
    return (
        f"background:{BG_INPUT}; color:{TEXT_PRIMARY}; border:1px solid {BORDER};"
        f"border-radius:6px; padding:5px 8px; font-size:13px;"
    )


def _label(text: str, bold: bool = False, muted: bool = False) -> QLabel:
    lbl = QLabel(text)
    color = TEXT_MUTED if muted else TEXT_PRIMARY
    weight = "700" if bold else "400"
    lbl.setStyleSheet(f"color:{color}; font-weight:{weight}; background:transparent;")
    return lbl


# ─────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("IP Blacklist Monitor")
        self.setMinimumSize(1100, 750)
        self.resize(1360, 900)

        self.config    = ConfigManager()
        self.history   = HistoryManager()
        self.scheduler = AutoScheduler(self)
        self.notif     = NotificationTracker()
        self._email_cfg = EmailConfig.from_dict(self.config._config)

        self._worker: Optional[CheckWorker] = None
        # Lưu kết quả mới nhất theo IP
        self._results: Dict[str, ParsedResult] = {}

        self._build_ui()
        self._connect_signals()
        self._apply_global_style()
        self._load_config_to_ui()

    # ──────────────────── BUILD UI ────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        # Tiêu đề + toolbar
        title_row = QHBoxLayout()
        title = QLabel("🛡  IP Blacklist Monitor")
        title.setStyleSheet(
            f"color:{ACCENT_BLUE}; font-size:20px; font-weight:700; background:transparent;"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        self.btn_email_settings = QPushButton("📧 Cài SMTP")
        self.btn_email_settings.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        self.btn_email_settings.setToolTip("Cấu hình gửi email cảnh báo")
        title_row.addWidget(self.btn_email_settings)

        root_layout.addLayout(title_row)

        # Tabs: Monitor | Charts
        self.main_tabs = QTabWidget()
        self.main_tabs.setStyleSheet(
            f"QTabWidget::pane {{ background:{BG_MAIN}; border:none; }}"
            f"QTabBar::tab {{ background:{BG_INPUT}; color:{TEXT_MUTED}; padding:8px 18px; "
            f"border-radius:6px 6px 0 0; margin-right:2px; font-size:13px; }}"
            f"QTabBar::tab:selected {{ background:{BG_CARD}; color:{TEXT_PRIMARY}; font-weight:700; }}"
        )
        root_layout.addWidget(self.main_tabs, stretch=1)

        # Tab 1: Monitor
        monitor_widget = self._build_monitor_tab()
        self.main_tabs.addTab(monitor_widget, "🖥  Monitor")

        # Tab 2: Charts
        self.charts_widget = ChartsWidget()
        self.main_tabs.addTab(self.charts_widget, "📊  Biểu đồ")

    def _build_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # Main splitter: top area + log
        vsplit = QSplitter(Qt.Orientation.Vertical)
        vsplit.setChildrenCollapsible(False)
        layout.addWidget(vsplit, stretch=1)

        # Top area: horizontal splitter (left config + right result+detail)
        hsplit = QSplitter(Qt.Orientation.Horizontal)
        hsplit.setChildrenCollapsible(False)
        vsplit.addWidget(hsplit)

        # ── Left panel ──
        left = self._build_left_panel()
        hsplit.addWidget(left)

        # ── Right panel: result + detail ──
        right = self._build_right_panel()
        hsplit.addWidget(right)

        hsplit.setStretchFactor(0, 1)
        hsplit.setStretchFactor(1, 3)

        # ── Log panel ──
        log_widget = self._build_log_panel()
        vsplit.addWidget(log_widget)

        vsplit.setStretchFactor(0, 3)
        vsplit.setStretchFactor(1, 1)

        return tab

    def _build_left_panel(self) -> QWidget:
        """Panel trái: API key, danh sách IP, auto scheduler."""
        panel = QWidget()
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        # ── Group: API Key ──
        grp_api = self._make_group("🔑  API Key MXToolbox")
        api_layout = QVBoxLayout()

        key_row = QHBoxLayout()
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_api_key.setPlaceholderText("Nhập API Key...")
        self.input_api_key.setStyleSheet(_input_style())
        key_row.addWidget(self.input_api_key)

        self.btn_toggle_key = QPushButton("👁")
        self.btn_toggle_key.setFixedSize(34, 34)
        self.btn_toggle_key.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        self.btn_toggle_key.setToolTip("Hiện/ẩn API key")
        key_row.addWidget(self.btn_toggle_key)
        api_layout.addLayout(key_row)
        grp_api.layout().addLayout(api_layout)
        layout.addWidget(grp_api)

        # ── Group: Danh sách IP ──
        grp_ip = self._make_group("🌐  Danh sách IP (mỗi dòng 1 IP)")
        ip_layout = QVBoxLayout()

        self.input_ips = QPlainTextEdit()
        self.input_ips.setPlaceholderText("Nhập địa chỉ IP IPv4...\nVí dụ:\n1.1.1.1\n8.8.8.8")
        self.input_ips.setStyleSheet(
            f"background:{BG_INPUT}; color:{TEXT_PRIMARY}; border:1px solid {BORDER};"
            f"border-radius:6px; padding:6px; font-size:13px; font-family:monospace;"
        )
        self.input_ips.setMinimumHeight(120)
        ip_layout.addWidget(self.input_ips)

        btn_row = QHBoxLayout()
        self.btn_sample = QPushButton("+ IP Mẫu")
        self.btn_sample.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        self.btn_clear_ip = QPushButton("Xóa hết")
        self.btn_clear_ip.setStyleSheet(_btn_style(BG_HOVER, ACCENT_RED, ACCENT_RED))
        btn_row.addWidget(self.btn_sample)
        btn_row.addWidget(self.btn_clear_ip)
        ip_layout.addLayout(btn_row)

        self.btn_check = QPushButton("🔍  Kiểm tra ngay")
        self.btn_check.setStyleSheet(_btn_style(ACCENT_BLUE, "#79c0ff"))
        self.btn_check.setMinimumHeight(38)
        ip_layout.addWidget(self.btn_check)

        grp_ip.layout().addLayout(ip_layout)
        layout.addWidget(grp_ip)

        # ── Group: Auto Scheduler ──
        grp_auto = self._make_group("⏱  Tự động kiểm tra")
        auto_layout = QVBoxLayout()
        auto_layout.setSpacing(8)

        interval_row = QHBoxLayout()
        interval_row.addWidget(_label("Chu kỳ:"))
        self.combo_interval = QComboBox()
        self.combo_interval.addItems(["1 phút", "5 phút", "10 phút", "30 phút", "60 phút"])
        self.combo_interval.setCurrentIndex(2)
        self.combo_interval.setStyleSheet(
            f"background:{BG_INPUT}; color:{TEXT_PRIMARY}; border:1px solid {BORDER};"
            f"border-radius:6px; padding:4px 8px; font-size:13px;"
        )
        interval_row.addWidget(self.combo_interval)
        auto_layout.addLayout(interval_row)

        auto_btn_row = QHBoxLayout()
        self.btn_auto_start = QPushButton("▶  Start Auto")
        self.btn_auto_start.setStyleSheet(_btn_style(ACCENT_GREEN, "#56d364", "#0d1117"))
        self.btn_auto_stop = QPushButton("⏹  Stop")
        self.btn_auto_stop.setStyleSheet(_btn_style(ACCENT_RED, "#ff7b72", "#fff"))
        self.btn_auto_stop.setEnabled(False)
        auto_btn_row.addWidget(self.btn_auto_start)
        auto_btn_row.addWidget(self.btn_auto_stop)
        auto_layout.addLayout(auto_btn_row)

        self.lbl_auto_status = _label("⏹ Đã dừng", muted=True)
        self.lbl_last_run    = _label("Lần cuối: —", muted=True)
        self.lbl_next_run    = _label("Lần tiếp: —", muted=True)
        auto_layout.addWidget(self.lbl_auto_status)
        auto_layout.addWidget(self.lbl_last_run)
        auto_layout.addWidget(self.lbl_next_run)

        grp_auto.layout().addLayout(auto_layout)
        layout.addWidget(grp_auto)

        layout.addStretch()

        # Nút xuất dữ liệu
        export_row = QHBoxLayout()
        self.btn_export_csv = QPushButton("⬇ Xuất CSV")
        self.btn_export_csv.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        self.btn_save_json = QPushButton("💾 Lưu JSON")
        self.btn_save_json.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        export_row.addWidget(self.btn_export_csv)
        export_row.addWidget(self.btn_save_json)
        layout.addLayout(export_row)

        return panel

    def _build_right_panel(self) -> QWidget:
        """Panel phải: bảng kết quả + chi tiết IP."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        vbox.addWidget(splitter)

        # ── Bảng kết quả ──
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        header_row.addWidget(_label("📊  Kết quả kiểm tra", bold=True))
        header_row.addStretch()
        self.lbl_checking = _label("", muted=True)
        header_row.addWidget(self.lbl_checking)
        result_layout.addLayout(header_row)

        self.result_tree = QTreeWidget()
        self.result_tree.setColumnCount(7)
        self.result_tree.setHeaderLabels([
            "IP", "Tổng BL", "BL Lớn", "BL Khác", "Risk Level", "Thời gian", "Trạng thái"
        ])
        self.result_tree.setColumnWidth(0, 130)
        self.result_tree.setColumnWidth(1, 65)
        self.result_tree.setColumnWidth(2, 65)
        self.result_tree.setColumnWidth(3, 65)
        self.result_tree.setColumnWidth(4, 90)
        self.result_tree.setColumnWidth(5, 155)
        self.result_tree.setColumnWidth(6, 120)
        self.result_tree.setRootIsDecorated(False)
        self.result_tree.setSortingEnabled(True)
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.setStyleSheet(self._table_style())
        result_layout.addWidget(self.result_tree)

        splitter.addWidget(result_widget)

        # ── Panel chi tiết ──
        detail_widget = self._build_detail_panel()
        splitter.addWidget(detail_widget)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        return container

    def _build_detail_panel(self) -> QWidget:
        """Panel chi tiết cho IP được chọn."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(_label("🔎  Chi tiết IP: ", bold=True))
        self.lbl_detail_ip = _label("(Chọn 1 dòng trong bảng)", muted=True)
        header.addWidget(self.lbl_detail_ip)
        header.addStretch()
        layout.addLayout(header)

        tab = QTabWidget()
        tab.setStyleSheet(
            f"QTabWidget::pane {{ background:{BG_CARD}; border:1px solid {BORDER}; border-radius:6px; }}"
            f"QTabBar::tab {{ background:{BG_INPUT}; color:{TEXT_MUTED}; padding:6px 14px; border-radius:4px 4px 0 0; }}"
            f"QTabBar::tab:selected {{ background:{BG_CARD}; color:{TEXT_PRIMARY}; }}"
        )
        layout.addWidget(tab)

        # Tab: Blacklists bị dính
        self.detail_tree = QTreeWidget()
        self.detail_tree.setColumnCount(3)
        self.detail_tree.setHeaderLabels(["Tên Blacklist", "Mã Info", "Link tham khảo"])
        self.detail_tree.setColumnWidth(0, 200)
        self.detail_tree.setColumnWidth(1, 100)
        self.detail_tree.setRootIsDecorated(False)
        self.detail_tree.setStyleSheet(self._table_style())
        tab.addTab(self.detail_tree, "Blacklists bị dính")

        # Tab: Raw JSON
        self.detail_json = QPlainTextEdit()
        self.detail_json.setReadOnly(True)
        self.detail_json.setStyleSheet(
            f"background:{BG_INPUT}; color:{ACCENT_GREEN}; border:none;"
            f"font-family:monospace; font-size:12px; padding:6px;"
        )
        tab.addTab(self.detail_json, "Raw JSON")

        return widget

    def _build_log_panel(self) -> QWidget:
        """Khung log ở dưới — dùng QTextEdit để hỗ trợ màu."""
        widget = QWidget()
        widget.setMinimumHeight(130)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.addWidget(_label("📋  Log hoạt động", bold=True))
        header.addStretch()
        self.btn_clear_log = QPushButton("Xóa log")
        self.btn_clear_log.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        self.btn_export_log = QPushButton("Xuất log")
        self.btn_export_log.setStyleSheet(_btn_style(BG_HOVER, BORDER, TEXT_PRIMARY))
        header.addWidget(self.btn_clear_log)
        header.addWidget(self.btn_export_log)
        layout.addLayout(header)

        # QTextEdit thay vì QPlainTextEdit để hỗ trợ HTML
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(
            f"background:{BG_CARD}; color:{TEXT_MUTED}; border:1px solid {BORDER};"
            f"border-radius:6px; font-family:monospace; font-size:12px; padding:6px;"
        )
        layout.addWidget(self.log_box)

        return widget

    # ──────────────────── CONNECT SIGNALS ────────────────────

    def _connect_signals(self):
        self.btn_toggle_key.clicked.connect(self._toggle_api_key_visibility)
        self.btn_sample.clicked.connect(self._add_sample_ips)
        self.btn_clear_ip.clicked.connect(self.input_ips.clear)
        self.btn_check.clicked.connect(self._start_check)
        self.btn_auto_start.clicked.connect(self._start_auto)
        self.btn_auto_stop.clicked.connect(self._stop_auto)
        self.btn_clear_log.clicked.connect(self.log_box.clear)
        self.btn_export_log.clicked.connect(self._export_log)
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_save_json.clicked.connect(self._save_json)
        self.btn_email_settings.clicked.connect(self._open_email_settings)
        self.result_tree.currentItemChanged.connect(self._on_row_selected)

        # Scheduler
        self.scheduler.trigger.connect(self._on_auto_trigger)
        self.scheduler.status_updated.connect(self._on_scheduler_status)

        # Lưu config khi thay đổi
        self.input_api_key.textChanged.connect(self._save_config)
        self.input_ips.textChanged.connect(self._save_config)
        self.combo_interval.currentIndexChanged.connect(self._on_interval_changed)

        # Chart tab: cập nhật khi chuyển sang
        self.main_tabs.currentChanged.connect(self._on_tab_changed)

    # ──────────────────── LOGIC EVENTS ────────────────────

    def _toggle_api_key_visibility(self):
        if self.input_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("🙈")
        else:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("👁")

    def _add_sample_ips(self):
        current = self.input_ips.toPlainText().strip()
        existing = {l.strip() for l in current.splitlines() if l.strip()}
        to_add = [ip for ip in SAMPLE_IPS if ip not in existing]
        if to_add:
            combined = (current + "\n" + "\n".join(to_add)).strip()
            self.input_ips.setPlainText(combined)

    def _get_ip_list(self) -> List[str]:
        raw = self.input_ips.toPlainText()
        seen, result = set(), []
        for line in raw.splitlines():
            ip = line.strip()
            if ip and ip not in seen:
                seen.add(ip)
                result.append(ip)
        return result

    def _start_check(self):
        if self._worker and self._worker.isRunning():
            self._log("⚠ Đang có lần kiểm tra đang chạy, vui lòng chờ.", "warning")
            return
        self._run_check()

    def _run_check(self):
        ip_list = self._get_ip_list()
        if not ip_list:
            self._log("⚠ Chưa nhập địa chỉ IP nào!", "warning")
            return

        api_key = self.input_api_key.text().strip()
        if not api_key:
            self._log("⚠ Chưa nhập API Key MXToolbox!", "error")
            return

        self._log(
            f"▶ Bắt đầu kiểm tra {len(ip_list)} IP lúc {datetime.now().strftime('%H:%M:%S')}",
            "info"
        )
        self.btn_check.setEnabled(False)
        self.lbl_checking.setText("⏳ Đang kiểm tra...")

        self._worker = CheckWorker(api_key, ip_list, self)
        self._worker.result_ready.connect(self._on_result_ready)
        self._worker.log_message.connect(self._log)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_result_ready(self, ip: str, result: ParsedResult):
        """Cập nhật bảng khi có kết quả từ 1 IP."""
        self._results[ip] = result
        self._update_table_row(ip, result)

        # Lưu vào history
        if not result.error:
            try:
                self.history.add_record(ip, result)
            except Exception as e:
                self._log(f"⚠ Lỗi lưu history: {e}", "warning")

        # Kiểm tra xem có cần popup/email không
        if self.notif.should_popup(ip, result):
            self._show_alert([result])

        if self.notif.should_send_email(ip, result):
            email_sent = self._try_send_email([result])
            self.notif.update(ip, result, email_sent=email_sent)
        else:
            self.notif.update(ip, result, email_sent=False)

    def _on_all_done(self):
        self.btn_check.setEnabled(True)
        self.lbl_checking.setText("")
        self._log(f"✅ Hoàn thành lúc {datetime.now().strftime('%H:%M:%S')}", "success")
        self.scheduler.mark_idle()
        self._save_config()

    def _on_auto_trigger(self):
        self._log(f"🔄 Auto check kích hoạt lúc {datetime.now().strftime('%H:%M:%S')}", "info")
        self._run_check()

    def _on_scheduler_status(self, last: str, nxt: str):
        self.lbl_last_run.setText(f"Lần cuối: {last}")
        self.lbl_next_run.setText(f"Lần tiếp: {nxt}")

    def _start_auto(self):
        self.scheduler.start()
        self.btn_auto_start.setEnabled(False)
        self.btn_auto_stop.setEnabled(True)
        self.lbl_auto_status.setText("▶ Đang chạy tự động")
        self.lbl_auto_status.setStyleSheet(f"color:{ACCENT_GREEN}; background:transparent;")
        self._log(f"⏱ Auto check đã bật, chu kỳ: {self._get_interval_minutes()} phút", "info")

    def _stop_auto(self):
        self.scheduler.stop()
        self.btn_auto_start.setEnabled(True)
        self.btn_auto_stop.setEnabled(False)
        self.lbl_auto_status.setText("⏹ Đã dừng")
        self.lbl_auto_status.setStyleSheet(f"color:{TEXT_MUTED}; background:transparent;")
        self._log("⏹ Auto check đã dừng.", "warning")

    def _on_interval_changed(self):
        mins = self._get_interval_minutes()
        self.scheduler.set_interval_minutes(mins)
        self._save_config()

    def _get_interval_minutes(self) -> int:
        text = self.combo_interval.currentText()
        return int(text.split()[0])

    def _on_row_selected(self, current, _previous):
        if not current:
            return
        ip = current.text(0)
        result = self._results.get(ip)
        if not result:
            return
        self._show_detail(result)

    def _on_tab_changed(self, index: int):
        """Cập nhật biểu đồ khi chuyển sang tab Charts."""
        if index == 1 and self._results:
            try:
                risk_summary = self.history.get_risk_summary()
                ip_histories = {
                    ip: self.history.get_timeline_for_ip(ip)
                    for ip in self._results
                }
                self.charts_widget.refresh(self._results, risk_summary, ip_histories)
            except Exception as e:
                self._log(f"⚠ Lỗi cập nhật biểu đồ: {e}", "warning")

    # ──────────────────── ALERT & EMAIL ────────────────────

    def _show_alert(self, results: list):
        """Hiện popup cảnh báo."""
        try:
            dlg = AlertDialog(results, self)
            dlg.exec()
        except Exception as e:
            self._log(f"⚠ Lỗi hiện popup: {e}", "warning")

    def _try_send_email(self, results: list) -> bool:
        """Gửi email nếu đã cấu hình. Trả về True nếu thành công."""
        if not self._email_cfg.is_configured():
            return False
        try:
            notifier = EmailNotifier(self._email_cfg)
            ok, err = notifier.send_alert(results)
            if ok:
                self._log("📧 Đã gửi email cảnh báo.", "success")
                return True
            else:
                self._log(f"⚠ Gửi email thất bại: {err}", "warning")
                return False
        except Exception as e:
            self._log(f"⚠ Lỗi gửi email: {e}", "warning")
            return False

    def _open_email_settings(self):
        """Mở dialog cấu hình SMTP."""
        dlg = EmailSettingsDialog(self._email_cfg, self)
        if dlg.exec():
            self._email_cfg = dlg.get_config()
            # Lưu vào config
            self.config.update(self._email_cfg.to_dict())
            self._log("✅ Đã lưu cấu hình email.", "success")

    # ──────────────────── TABLE ────────────────────

    def _update_table_row(self, ip: str, result: ParsedResult):
        item = self._find_table_item(ip)
        if item is None:
            item = QTreeWidgetItem(self.result_tree)

        now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

        if result.error:
            item.setText(0, ip)
            item.setText(1, "—")
            item.setText(2, "—")
            item.setText(3, "—")
            item.setText(4, "Lỗi")
            item.setText(5, now_str)
            item.setText(6, result.error[:50])
            item.setForeground(4, QColor(ACCENT_AMBER))
        else:
            risk  = result.risk_level
            color = QColor(RISK_COLORS.get(risk, TEXT_PRIMARY))
            item.setText(0, ip)
            item.setText(1, str(result.total_listed))
            item.setText(2, str(len(result.major_listed)))
            item.setText(3, str(len(result.other_listed)))
            item.setText(4, risk)
            item.setText(5, now_str)
            item.setText(6, "✓ Sạch" if result.total_listed == 0 else f"⚠ Dính {result.total_listed} BL")
            for col in range(7):
                item.setForeground(col, QColor(TEXT_PRIMARY))
            item.setForeground(4, color)
            item.setForeground(6, QColor(ACCENT_GREEN) if result.total_listed == 0 else QColor(ACCENT_RED))

        for col in range(1, 4):
            item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)
        item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)

    def _find_table_item(self, ip: str) -> Optional[QTreeWidgetItem]:
        for i in range(self.result_tree.topLevelItemCount()):
            item = self.result_tree.topLevelItem(i)
            if item.text(0) == ip:
                return item
        return None

    # ──────────────────── DETAIL PANEL ────────────────────

    def _show_detail(self, result: ParsedResult):
        self.lbl_detail_ip.setText(
            f"<b style='color:{RISK_COLORS.get(result.risk_level, TEXT_PRIMARY)}'>"
            f"{result.ip}</b> — Risk: <b>{result.risk_level}</b>"
        )
        self.lbl_detail_ip.setTextFormat(Qt.TextFormat.RichText)

        self.detail_tree.clear()
        if result.error:
            err_item = QTreeWidgetItem(self.detail_tree)
            err_item.setText(0, "LỖI")
            err_item.setText(1, result.error)
            err_item.setForeground(0, QColor(ACCENT_RED))
        else:
            for entry in result.all_listed:
                it = QTreeWidgetItem(self.detail_tree)
                badge = "🔴 " if entry.is_major else "🟡 "
                it.setText(0, badge + entry.name)
                it.setText(1, entry.info or "—")
                it.setText(2, entry.url or "—")
                color = QColor(ACCENT_RED if entry.is_major else ACCENT_AMBER)
                it.setForeground(0, color)

            if not result.all_listed:
                clean = QTreeWidgetItem(self.detail_tree)
                clean.setText(0, "✅ Không bị dính blacklist nào")
                clean.setForeground(0, QColor(ACCENT_GREEN))

        if result.raw_json:
            try:
                txt = json.dumps(result.raw_json, indent=2, ensure_ascii=False)
                if len(txt) > 8000:
                    txt = txt[:8000] + "\n... (truncated)"
                self.detail_json.setPlainText(txt)
            except Exception:
                self.detail_json.setPlainText("Không thể hiển thị JSON")
        else:
            self.detail_json.setPlainText(result.error or "—")

    # ──────────────────── LOG ────────────────────

    def _log(self, message: str, level: str = "info"):
        """Ghi vào khung log với màu sắc theo level (dùng QTextEdit)."""
        colors = {
            "info":    TEXT_MUTED,
            "success": ACCENT_GREEN,
            "error":   ACCENT_RED,
            "warning": ACCENT_AMBER,
        }
        color = colors.get(level, TEXT_MUTED)
        ts = datetime.now().strftime("%H:%M:%S")
        html = (
            f"<span style='color:{TEXT_MUTED}'>[{ts}]</span> "
            f"<span style='color:{color}'>{message}</span>"
        )
        self.log_box.append(html)
        # Cuộn xuống dưới
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

        # Giới hạn số dòng
        doc = self.log_box.document()
        if doc.blockCount() > 500:
            cursor = self.log_box.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    # ──────────────────── EXPORT ────────────────────

    def _export_csv(self):
        if not self._results:
            self._log("⚠ Chưa có dữ liệu để xuất CSV.", "warning")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu CSV", "blacklist_results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["IP", "Tổng BL", "BL Lớn", "BL Khác", "Risk Level", "Lỗi"])
                for ip, r in self._results.items():
                    writer.writerow([
                        ip,
                        r.total_listed,
                        len(r.major_listed),
                        len(r.other_listed),
                        r.risk_level,
                        r.error or "",
                    ])
            self._log(f"✅ Đã xuất CSV: {path}", "success")
        except Exception as e:
            self._log(f"✗ Lỗi xuất CSV: {e}", "error")

    def _save_json(self):
        if not self._results:
            self._log("⚠ Chưa có dữ liệu để lưu JSON.", "warning")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu JSON", "blacklist_results.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            output = {}
            for ip, r in self._results.items():
                output[ip] = {
                    "total_listed": r.total_listed,
                    "risk_level": r.risk_level,
                    "major_blacklists": [
                        {"name": e.name, "info": e.info, "url": e.url}
                        for e in r.major_listed
                    ],
                    "other_blacklists": [
                        {"name": e.name, "info": e.info, "url": e.url}
                        for e in r.other_listed
                    ],
                    "error": r.error,
                    "raw_json": r.raw_json,
                }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            self._log(f"✅ Đã lưu JSON: {path}", "success")
        except Exception as e:
            self._log(f"✗ Lỗi lưu JSON: {e}", "error")

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất log", "blacklist_log.txt", "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_box.toPlainText())
            self._log(f"✅ Đã xuất log: {path}", "success")
        except Exception as e:
            self._log(f"✗ Lỗi xuất log: {e}", "error")

    # ──────────────────── CONFIG ────────────────────

    def _load_config_to_ui(self):
        self.input_api_key.setText(self.config.get("api_key", ""))
        ips = self.config.get("ip_list", [])
        if ips:
            self.input_ips.setPlainText("\n".join(ips))

        interval = self.config.get("auto_interval_minutes", 10)
        options = [1, 5, 10, 30, 60]
        idx = options.index(interval) if interval in options else 2
        self.combo_interval.setCurrentIndex(idx)
        self.scheduler.set_interval_minutes(interval)

        # Tải email config
        self._email_cfg = EmailConfig.from_dict(self.config._config)

    def _save_config(self):
        ips = [l.strip() for l in self.input_ips.toPlainText().splitlines() if l.strip()]
        data = {
            "api_key": self.input_api_key.text().strip(),
            "ip_list": ips,
            "auto_interval_minutes": self._get_interval_minutes(),
        }
        # Gộp thêm email config
        data.update(self._email_cfg.to_dict())
        self.config.update(data)

    # ──────────────────── STYLE ────────────────────

    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {BG_MAIN};
                color: {TEXT_PRIMARY};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }}
            QGroupBox {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
                font-weight: 600;
                color: {TEXT_PRIMARY};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: {ACCENT_BLUE};
            }}
            QSplitter::handle {{
                background: {BORDER};
            }}
            QScrollBar:vertical {{
                background: {BG_MAIN};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {BG_HOVER};
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {BG_MAIN};
                height: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {BG_HOVER};
                border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
            QToolTip {{
                background: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                padding: 4px;
            }}
        """)

    def _table_style(self) -> str:
        return f"""
            QTreeWidget {{
                background: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                outline: none;
                gridline-color: {BORDER};
            }}
            QTreeWidget::item {{
                padding: 5px 4px;
                border-bottom: 1px solid {BORDER};
            }}
            QTreeWidget::item:alternate {{
                background: {BG_INPUT};
            }}
            QTreeWidget::item:selected {{
                background: {ACCENT_BLUE}33;
                color: {TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background: {BG_INPUT};
                color: {TEXT_MUTED};
                border: none;
                border-right: 1px solid {BORDER};
                border-bottom: 1px solid {BORDER};
                padding: 6px 4px;
                font-weight: 600;
                font-size: 12px;
            }}
        """

    @staticmethod
    def _make_group(title: str) -> QGroupBox:
        grp = QGroupBox(title)
        grp.setLayout(QVBoxLayout())
        grp.layout().setContentsMargins(10, 14, 10, 10)
        grp.layout().setSpacing(6)
        return grp

    # ──────────────────── CLOSE ────────────────────

    def closeEvent(self, event):
        """Lưu config và dừng worker trước khi đóng."""
        self._save_config()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(2000)
        self.scheduler.stop()
        event.accept()
