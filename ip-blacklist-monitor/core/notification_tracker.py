"""
Notification Tracker - Chống spam popup và email
Theo dõi trạng thái cũ của từng IP để quyết định có cần thông báo lại không
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class IPState:
    """Trạng thái đã ghi nhận của 1 IP."""
    risk_level: str = "Safe"
    total_listed: int = 0
    last_notified: Optional[datetime] = None
    popup_shown: bool = False


class NotificationTracker:
    """
    Quản lý trạng thái thông báo cho từng IP.
    Quyết định có nên hiện popup / gửi email hay không.
    """

    # Thời gian tối thiểu giữa 2 lần gửi email cho cùng IP (phút)
    EMAIL_COOLDOWN_MINUTES = 60

    def __init__(self):
        self._states: Dict[str, IPState] = {}

    def should_popup(self, ip: str, result) -> bool:
        """
        Trả về True nếu cần hiện popup cảnh báo.
        - IP bị blacklist (risk không phải Safe)
        - VÀ (chưa popup trước đó HOẶC trạng thái xấu hơn)
        """
        if result.error or result.risk_level == "Safe":
            return False

        prev = self._states.get(ip)
        if prev is None:
            return True  # IP mới

        # Nếu trạng thái xấu hơn → popup
        return self._is_worse(prev.risk_level, result.risk_level) or \
               result.total_listed > prev.total_listed

    def should_send_email(self, ip: str, result) -> bool:
        """
        Trả về True nếu cần gửi email cảnh báo.
        - IP bị blacklist
        - VÀ (chưa gửi bao giờ HOẶC trạng thái thay đổi xấu hơn
               HOẶC đã qua cooldown)
        """
        if result.error or result.risk_level == "Safe":
            return False

        prev = self._states.get(ip)
        if prev is None:
            return True

        # Trạng thái xấu hơn → gửi ngay
        if self._is_worse(prev.risk_level, result.risk_level):
            return True
        if result.total_listed > prev.total_listed:
            return True

        # Nếu đã qua cooldown thì gửi lại
        if prev.last_notified:
            elapsed = datetime.now() - prev.last_notified
            if elapsed > timedelta(minutes=self.EMAIL_COOLDOWN_MINUTES):
                return True

        return False

    def update(self, ip: str, result, email_sent: bool = False):
        """Cập nhật trạng thái sau khi đã xử lý thông báo."""
        state = self._states.get(ip, IPState())
        state.risk_level = result.risk_level
        state.total_listed = result.total_listed
        if email_sent:
            state.last_notified = datetime.now()
        if result.risk_level != "Safe":
            state.popup_shown = True
        else:
            state.popup_shown = False
        self._states[ip] = state

    def reset(self, ip: str):
        """Xóa trạng thái đã theo dõi của 1 IP (ví dụ khi IP trở về Safe)."""
        self._states.pop(ip, None)

    @staticmethod
    def _is_worse(old: str, new: str) -> bool:
        """So sánh mức độ nghiêm trọng: Danger > Warning > Safe."""
        order = {"Safe": 0, "Warning": 1, "Danger": 2}
        return order.get(new, 0) > order.get(old, 0)
