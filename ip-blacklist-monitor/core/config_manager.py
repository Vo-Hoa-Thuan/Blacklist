"""
Config Manager - Quản lý cấu hình ứng dụng
Lưu và tải cấu hình từ file config.json
"""
import json
import os

# Đường dẫn file config mặc định
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

# Cấu hình mặc định
DEFAULT_CONFIG = {
    "api_key": "",
    "ip_list": [],
    "auto_interval_minutes": 10,
    "auto_check_enabled": False,
}


class ConfigManager:
    """Quản lý đọc/ghi cấu hình ứng dụng."""

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self._config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        """Tải cấu hình từ file JSON. Nếu không tồn tại thì dùng mặc định."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Merge với default để không thiếu key mới
                self._config = {**DEFAULT_CONFIG, **data}
            except (json.JSONDecodeError, IOError):
                self._config = dict(DEFAULT_CONFIG)
        else:
            self._config = dict(DEFAULT_CONFIG)

    def save(self):
        """Lưu cấu hình hiện tại ra file JSON."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[Config] Lỗi lưu cấu hình: {e}")

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value):
        self._config[key] = value

    def update(self, data: dict):
        """Cập nhật nhiều key cùng lúc và lưu."""
        self._config.update(data)
        self.save()
