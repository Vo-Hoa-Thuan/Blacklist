"""
Flask Web Backend - IP Blacklist Monitor Web
Tái sử dụng toàn bộ core/ modules từ desktop app
Chạy: python app.py  →  mở http://localhost:5000
"""
import json
import os
import queue
import threading
import time
from datetime import datetime
from typing import Dict

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# Thêm thư mục gốc vào path để import core/
import sys
sys.path.insert(0, os.path.dirname(__file__))

from core.api_client import MxToolboxClient, is_valid_ipv4
from core.config_manager import ConfigManager
from core.email_notifier import EmailConfig, EmailNotifier
from core.history_manager import HistoryManager
from core.notification_tracker import NotificationTracker
from core.parser import ParsedResult

app = Flask(__name__)
app.config["SECRET_KEY"] = "ip-blacklist-monitor-2024"

# ──────────────────────── Global state ────────────────────────
config  = ConfigManager()
history = HistoryManager()
notif   = NotificationTracker()

# Kết quả mới nhất theo IP
_results: Dict[str, dict] = {}

# Hàng đợi sự kiện SSE cho từng phiên check
_check_queue: queue.Queue = queue.Queue()
_check_running = False


# ─────────────────────────── Helpers ──────────────────────────
def _result_to_dict(ip: str, result: ParsedResult) -> dict:
    return {
        "ip": ip,
        "total_listed": result.total_listed,
        "major_count": len(result.major_listed),
        "other_count": len(result.other_listed),
        "risk_level": result.risk_level,
        "error": result.error,
        "blacklists": [
            {"name": e.name, "info": e.info or "", "url": e.url or "", "is_major": e.is_major}
            for e in result.all_listed
        ],
        "raw_json": result.raw_json,
        "checked_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
    }


def _run_check_thread(api_key: str, ip_list: list):
    """Chạy check trong thread riêng, push events qua queue."""
    global _check_running, _results
    _check_running = True

    client = MxToolboxClient(api_key)

    _check_queue.put({"type": "start", "total": len(ip_list)})

    for ip in ip_list:
        ip = ip.strip()
        if not ip:
            continue

        _check_queue.put({"type": "log", "level": "info", "msg": f"🔍 Đang kiểm tra: {ip}"})

        result = client.check_ip(ip)
        d = _result_to_dict(ip, result)
        _results[ip] = d

        # Lưu history
        if not result.error:
            try:
                history.add_record(ip, result)
            except Exception:
                pass

        if result.error:
            _check_queue.put({"type": "log", "level": "error", "msg": f"✗ {ip} — {result.error}"})
        else:
            status = f"Dính {result.total_listed} BL" if result.total_listed > 0 else "Sạch"
            _check_queue.put({
                "type": "log",
                "level": "success" if result.total_listed == 0 else "warning",
                "msg": f"✓ {ip} — {status} | Risk: {result.risk_level}",
            })

        _check_queue.put({"type": "result", "data": d})

    _check_queue.put({"type": "done"})
    _check_running = False


# ───────────────────────── Routes ─────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "api_key": config.get("api_key", ""),
        "ip_list": config.get("ip_list", []),
        "auto_interval_minutes": config.get("auto_interval_minutes", 10),
        **EmailConfig.from_dict(config._config).to_dict(),
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.json or {}
    config.update(data)
    return jsonify({"ok": True})


@app.route("/api/check", methods=["POST"])
def start_check():
    global _check_running
    if _check_running:
        return jsonify({"ok": False, "error": "Đang có lần kiểm tra chạy, chờ xong."}), 409

    data = request.json or {}
    api_key = data.get("api_key", "").strip()
    ip_list = [ip.strip() for ip in data.get("ip_list", []) if ip.strip()]

    if not api_key:
        return jsonify({"ok": False, "error": "Chưa nhập API Key!"}), 400
    if not ip_list:
        return jsonify({"ok": False, "error": "Chưa nhập IP nào!"}), 400

    # Xóa queue cũ
    while not _check_queue.empty():
        try:
            _check_queue.get_nowait()
        except queue.Empty:
            break

    t = threading.Thread(target=_run_check_thread, args=(api_key, ip_list), daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/api/check/stream")
def check_stream():
    """Server-Sent Events stream — truyền kết quả real-time về browser."""
    def event_stream():
        while True:
            try:
                event = _check_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    break
            except queue.Empty:
                # Heartbeat để giữ kết nối
                yield "data: {\"type\":\"ping\"}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/results", methods=["GET"])
def get_results():
    return jsonify(list(_results.values()))


@app.route("/api/history", methods=["GET"])
def get_history():
    try:
        rows = history.get_all_latest()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/<ip>", methods=["GET"])
def get_ip_history(ip):
    try:
        rows = history.get_timeline_for_ip(ip, limit=30)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["DELETE"])
def clear_history():
    ip = request.args.get("ip")
    history.clear_history(ip or None)
    return jsonify({"ok": True})


@app.route("/api/risk-summary", methods=["GET"])
def risk_summary():
    try:
        return jsonify(history.get_risk_summary())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/email/test", methods=["POST"])
def test_email():
    data = request.json or {}
    cfg = EmailConfig.from_dict(data)
    if not cfg.is_configured():
        return jsonify({"ok": False, "error": "Chưa điền đủ cấu hình SMTP"})
    notifier = EmailNotifier(cfg)
    ok, err = notifier.send_test()
    return jsonify({"ok": ok, "error": err})


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["IP", "Tổng BL", "BL Lớn", "BL Khác", "Risk Level", "Lỗi", "Thời gian"])
    for d in _results.values():
        writer.writerow([
            d["ip"], d["total_listed"], d["major_count"], d["other_count"],
            d["risk_level"], d.get("error") or "", d.get("checked_at", ""),
        ])
    output.seek(0)
    return Response(
        "\ufeff" + output.getvalue(),  # BOM for Excel
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=blacklist_results.csv"},
    )


@app.route("/api/export/json", methods=["GET"])
def export_json():
    return Response(
        json.dumps(list(_results.values()), indent=2, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=blacklist_results.json"},
    )


if __name__ == "__main__":
    print("=" * 50)
    print("  IP Blacklist Monitor - Web Server")
    print("  Mở trình duyệt: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
