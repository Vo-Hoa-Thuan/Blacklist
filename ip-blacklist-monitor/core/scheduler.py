"""
Scheduler - Tự động chạy lại kiểm tra theo chu kỳ
Sử dụng QTimer của PySide6, an toàn với GUI thread
"""
from datetime import datetime, timedelta
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal


class AutoScheduler(QObject):
    """
    Scheduler tự động kích hoạt callback theo chu kỳ.
    Chống chạy chồng: nếu lần check trước chưa xong, sẽ bỏ qua.
    """
    # Signal phát khi đến lúc chạy
    trigger = Signal()
    # Signal cập nhật UI thời gian
    status_updated = Signal(str, str)  # (last_run_str, next_run_str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._interval_ms: int = 10 * 60 * 1000   # Mặc định 10 phút
        self._is_running: bool = False
        self._is_busy: bool = False                 # Flag chống chạy chồng
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_interval_minutes(self, minutes: int):
        """Đặt chu kỳ tự động (phút)."""
        self._interval_ms = max(1, minutes) * 60 * 1000
        # Nếu đang chạy thì restart timer với interval mới
        if self._is_running:
            self._timer.start(self._interval_ms)
            self._update_next_run()

    def start(self):
        """Bắt đầu auto scheduler."""
        if self._is_running:
            return
        self._is_running = True
        self._is_busy = False
        self._timer.start(self._interval_ms)
        self._update_next_run()
        self.status_updated.emit(
            self._fmt(self._last_run),
            self._fmt(self._next_run),
        )

    def stop(self):
        """Dừng auto scheduler."""
        self._is_running = False
        self._timer.stop()
        self._next_run = None
        self.status_updated.emit(
            self._fmt(self._last_run),
            "—",
        )

    def mark_busy(self):
        """Đánh dấu đang bận check, tránh chạy chồng."""
        self._is_busy = True

    def mark_idle(self):
        """Đánh dấu đã xong, cập nhật thời gian."""
        self._is_busy = False
        self._last_run = datetime.now()
        self._update_next_run()
        self.status_updated.emit(
            self._fmt(self._last_run),
            self._fmt(self._next_run),
        )

    def _on_tick(self):
        """Gọi khi timer hết giờ."""
        if self._is_busy:
            # Đang bận, bỏ qua lần này
            return
        self.mark_busy()
        self.trigger.emit()

    def _update_next_run(self):
        """Tính thời điểm chạy tiếp theo."""
        if self._is_running:
            self._next_run = datetime.now() + timedelta(
                milliseconds=self._interval_ms
            )
        else:
            self._next_run = None

    @staticmethod
    def _fmt(dt: Optional[datetime]) -> str:
        if dt is None:
            return "—"
        return dt.strftime("%H:%M:%S %d/%m/%Y")
