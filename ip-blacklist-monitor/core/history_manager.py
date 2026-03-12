"""
History Manager - Lưu lịch sử kiểm tra vào SQLite
Dùng để vẽ biểu đồ, so sánh trạng thái cũ/mới, quyết định gửi alert
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .parser import ParsedResult

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history.db")


class HistoryManager:
    """Quản lý lịch sử check vào SQLite."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Tạo bảng nếu chưa tồn tại."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip          TEXT    NOT NULL,
                    checked_at  TEXT    NOT NULL,
                    total_listed INTEGER DEFAULT 0,
                    major_count  INTEGER DEFAULT 0,
                    other_count  INTEGER DEFAULT 0,
                    risk_level   TEXT    DEFAULT 'Safe',
                    blacklists   TEXT    DEFAULT '[]',
                    error        TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ip ON checks(ip)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON checks(checked_at)")

    def add_record(self, ip: str, result: "ParsedResult") -> int:
        """Lưu 1 kết quả check vào database."""
        blacklists_json = json.dumps(
            [{"name": e.name, "info": e.info, "is_major": e.is_major}
             for e in (result.all_listed or [])],
            ensure_ascii=False
        )
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO checks
                   (ip, checked_at, total_listed, major_count, other_count,
                    risk_level, blacklists, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ip, now,
                    result.total_listed,
                    len(result.major_listed),
                    len(result.other_listed),
                    result.risk_level,
                    blacklists_json,
                    result.error,
                )
            )
            return cur.lastrowid

    def get_history_for_ip(self, ip: str, limit: int = 50) -> List[Dict]:
        """Lấy lịch sử check của 1 IP, mới nhất trước."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM checks WHERE ip = ?
                   ORDER BY checked_at DESC LIMIT ?""",
                (ip, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_latest(self) -> List[Dict]:
        """Lấy bản ghi mới nhất của mỗi IP."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT c.* FROM checks c
                   INNER JOIN (
                       SELECT ip, MAX(checked_at) AS max_time
                       FROM checks GROUP BY ip
                   ) latest ON c.ip = latest.ip AND c.checked_at = latest.max_time
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def get_timeline_for_ip(self, ip: str, limit: int = 30) -> List[Dict]:
        """Lấy dữ liệu timeline (ngược thời gian cũ→mới) cho biểu đồ line."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT checked_at, total_listed, risk_level
                   FROM checks WHERE ip = ?
                   ORDER BY checked_at ASC LIMIT ?""",
                (ip, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_risk_summary(self) -> Dict[str, int]:
        """Đếm số IP theo risk level (dùng cho biểu đồ tròn)."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT risk_level, COUNT(DISTINCT ip) as cnt
                   FROM (
                       SELECT ip, risk_level, MAX(checked_at)
                       FROM checks GROUP BY ip
                   ) GROUP BY risk_level"""
            ).fetchall()
        result = {"Safe": 0, "Warning": 0, "Danger": 0}
        for r in rows:
            level = r["risk_level"]
            if level in result:
                result[level] = r["cnt"]
        return result

    def clear_history(self, ip: Optional[str] = None):
        """Xóa lịch sử (tất cả hoặc 1 IP)."""
        with self._connect() as conn:
            if ip:
                conn.execute("DELETE FROM checks WHERE ip = ?", (ip,))
            else:
                conn.execute("DELETE FROM checks")
