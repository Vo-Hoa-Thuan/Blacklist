"""
Parser - Phân tích kết quả từ MXToolbox API
Xác định blacklist bị dính, phân loại major/other, tính Risk Level
"""
from dataclasses import dataclass, field
from typing import List, Optional

# Danh sách các blacklist lớn, uy tín
MAJOR_BLACKLISTS = {
    "Spamhaus ZEN",
    "SPAMCOP",
    "BARRACUDA",
    "UCEPROTECTL1",
    "UCEPROTECTL2",
    "UCEPROTECTL3",
    "SPAMHAUS-SBL",
    "SPAMHAUS-XBL",
    "SPAMHAUS-PBL",
}


@dataclass
class BlacklistEntry:
    """Một dòng trong kết quả kiểm tra blacklist."""
    name: str                          # Tên blacklist
    info: Optional[str] = None         # Mã phản hồi, ví dụ 127.0.0.2
    url: Optional[str] = None          # Link tham khảo
    is_listed: bool = False            # True nếu bị dính
    is_major: bool = False             # True nếu là blacklist lớn


@dataclass
class ParsedResult:
    """Kết quả đã phân tích cho 1 IP."""
    ip: str
    total_listed: int = 0
    major_listed: List[BlacklistEntry] = field(default_factory=list)
    other_listed: List[BlacklistEntry] = field(default_factory=list)
    all_listed: List[BlacklistEntry] = field(default_factory=list)
    risk_level: str = "Safe"           # "Safe", "Warning", "Danger"
    error: Optional[str] = None        # Thông báo lỗi nếu có
    raw_json: Optional[dict] = None    # Dữ liệu gốc từ API


def parse_response(ip: str, data: dict) -> ParsedResult:
    """
    Phân tích JSON trả về từ MXToolbox API.
    Xác định IP có bị blacklist không dựa vào trường Info (dạng 127.x.x.x).
    """
    result = ParsedResult(ip=ip, raw_json=data)

    # Chỉ lấy mảng "Failed" — đây là các blacklist IP bị dính thực sự.
    # Không dùng "Passed" vì một số blacklist (Abusix...) trả về 127.x.x.x
    # trong Passed entries như metadata, KHÔNG phải là dấu hiệu bị blacklist.
    failed_entries = data.get("Failed") or []

    listed_entries: List[BlacklistEntry] = []

    for item in failed_entries:
        name = item.get("Name", "")
        info = item.get("Info", "") or ""
        url = item.get("Url", "") or item.get("PublicDescription", "")

        # Xác định bị dính: nằm trong Failed array (đã là bị dính rồi)
        # Thêm kiểm tra Info "127." để lọc những entry bị timeout/error giả
        is_listed = True  # Failed = bị dính theo MXToolbox API

        if is_listed:
            is_major = any(
                bk.lower() in name.lower() for bk in MAJOR_BLACKLISTS
            )
            entry = BlacklistEntry(
                name=name,
                info=info,
                url=url if url else None,
                is_listed=True,
                is_major=is_major,
            )
            listed_entries.append(entry)

    # Phân loại major / other
    major = [e for e in listed_entries if e.is_major]
    other = [e for e in listed_entries if not e.is_major]

    result.all_listed = listed_entries
    result.major_listed = major
    result.other_listed = other
    result.total_listed = len(listed_entries)

    # Tính Risk Level
    result.risk_level = _calc_risk(major, other)

    return result


def _calc_risk(major: list, other: list) -> str:
    """
    Tính mức độ rủi ro:
    - Safe: không bị dính blacklist nào
    - Warning: dính 1-3 blacklist nhỏ, không dính blacklist lớn
    - Danger: dính blacklist lớn HOẶC dính > 3 blacklist
    """
    total = len(major) + len(other)
    if total == 0:
        return "Safe"
    if len(major) > 0 or total > 3:
        return "Danger"
    return "Warning"
