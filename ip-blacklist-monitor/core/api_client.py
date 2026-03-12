"""
API Client - Gọi MXToolbox Blacklist API
Chạy trong QThread riêng để không block giao diện
"""
import re
import requests
from typing import List, Callable, Optional

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    # Fallback cho môi trường Server (Render) không có PySide6
    class _MockSignal:
        def connect(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass
    class QThread(object):
        def __init__(self, *args, **kwargs): pass
    def Signal(*args, **kwargs):
        return _MockSignal()

from core.parser import ParsedResult, parse_response

# Timeout cho mỗi request (giây)
REQUEST_TIMEOUT = 20

# Regex kiểm tra địa chỉ IPv4 hợp lệ
IPV4_PATTERN = re.compile(
    r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)


def is_valid_ipv4(ip: str) -> bool:
    """Kiểm tra định dạng IPv4 hợp lệ."""
    return bool(IPV4_PATTERN.match(ip.strip()))


class MxToolboxClient:
    """Client gọi API MXToolbox, đồng bộ (sync). Dùng trong thread."""

    BASE_URL = "https://api.mxtoolbox.com/api/v1/Lookup/blacklist/{ip}"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key,
            "Content-Type": "application/json",
        })

    def check_ip(self, ip: str) -> ParsedResult:
        """
        Gọi API kiểm tra blacklist cho 1 IP.
        Trả về ParsedResult đã phân tích.
        """
        if not is_valid_ipv4(ip):
            result = ParsedResult(ip=ip)
            result.error = f"IP '{ip}' không đúng định dạng IPv4"
            return result

        url = self.BASE_URL.format(ip=ip.strip())
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 401:
                result = ParsedResult(ip=ip)
                result.error = "API Key không hợp lệ hoặc hết hạn (401)"
                return result
            if resp.status_code == 429:
                result = ParsedResult(ip=ip)
                result.error = "Vượt giới hạn API (429 Too Many Requests)"
                return result
            if resp.status_code != 200:
                result = ParsedResult(ip=ip)
                result.error = f"Lỗi HTTP {resp.status_code}"
                return result

            data = resp.json()
            return parse_response(ip.strip(), data)

        except requests.exceptions.Timeout:
            result = ParsedResult(ip=ip)
            result.error = "Timeout khi kết nối đến MXToolbox API"
            return result
        except requests.exceptions.ConnectionError:
            result = ParsedResult(ip=ip)
            result.error = "Không thể kết nối mạng"
            return result
        except Exception as e:
            result = ParsedResult(ip=ip)
            result.error = f"Lỗi không xác định: {str(e)}"
            return result


class CheckWorker(QThread):
    """
    QThread chạy kiểm tra blacklist cho danh sách IP.
    Phát signal khi từng IP xong và khi toàn bộ xong.
    """
    # Signal: (ip, ParsedResult)
    result_ready = Signal(str, object)
    # Signal: (message, level) - level: "info"|"success"|"error"|"warning"
    log_message = Signal(str, str)
    # Signal: phát khi tất cả IP đã check xong
    all_done = Signal()

    def __init__(self, api_key: str, ip_list: List[str], parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.ip_list = ip_list
        self._stop_flag = False

    def stop(self):
        """Yêu cầu dừng worker."""
        self._stop_flag = True

    def run(self):
        """Chạy lần lượt từng IP."""
        if not self.api_key.strip():
            self.log_message.emit("⚠ Chưa nhập API Key MXToolbox!", "error")
            self.all_done.emit()
            return

        client = MxToolboxClient(self.api_key)

        for ip in self.ip_list:
            if self._stop_flag:
                self.log_message.emit("⏹ Đã dừng kiểm tra theo yêu cầu.", "warning")
                break

            ip = ip.strip()
            if not ip:
                continue

            self.log_message.emit(f"🔍 Đang kiểm tra: {ip}", "info")
            result = client.check_ip(ip)

            if result.error:
                self.log_message.emit(f"✗ {ip} — {result.error}", "error")
            else:
                status = f"Dính {result.total_listed} blacklist" if result.total_listed > 0 else "Sạch"
                self.log_message.emit(
                    f"✓ {ip} — {status} | Risk: {result.risk_level}", "success"
                )

            self.result_ready.emit(ip, result)

        self.all_done.emit()
