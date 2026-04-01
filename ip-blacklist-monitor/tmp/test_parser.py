import sys
import os

# Thêm thư mục gốc vào path để import core/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.parser import parse_response, BlacklistEntry

def test_parse_response():
    # Mock data from MXToolbox API
    mock_data = {
        "Failed": [
            {"Name": "Spamhaus ZEN", "Info": "127.0.0.2", "Url": "http://spamhaus.org"},
            {"Name": "SPAMCOP", "Info": "Timeout", "Url": ""},  # This should be ignored
            {"Name": "Barracuda", "Info": "127.0.0.2", "Url": "http://barracuda.com"}
        ],
        "Passed": []
    }
    
    ip = "1.2.3.4"
    result = parse_response(ip, mock_data)
    
    print(f"IP: {result.ip}")
    print(f"Total listed: {result.total_listed}")
    print(f"Risk level: {result.risk_level}")
    
    for entry in result.all_listed:
        print(f"  - {entry.name}: {entry.info} (Major: {entry.is_major})")

if __name__ == "__main__":
    test_parse_response()
