"""
Email Notifier - Gửi email cảnh báo qua SMTP
Hỗ trợ SSL/TLS, app password, chống gửi lặp
"""
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional


class EmailConfig:
    """Cấu hình SMTP email."""
    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        recipient: str = "",
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        return bool(
            self.smtp_host and self.username and
            self.password and self.recipient
        )

    def to_dict(self) -> dict:
        return {
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_username": self.username,
            "smtp_password": self.password,
            "smtp_recipient": self.recipient,
            "smtp_use_tls": self.use_tls,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EmailConfig":
        return cls(
            smtp_host=d.get("smtp_host", ""),
            smtp_port=d.get("smtp_port", 587),
            username=d.get("smtp_username", ""),
            password=d.get("smtp_password", ""),
            recipient=d.get("smtp_recipient", ""),
            use_tls=d.get("smtp_use_tls", True),
        )


class EmailNotifier:
    """Gửi email cảnh báo khi phát hiện IP bị blacklist."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send_alert(self, results: list) -> tuple[bool, str]:
        """
        Gửi email cảnh báo cho danh sách IP bị blacklist.
        Trả về (success, error_message)
        """
        if not self.config.is_configured():
            return False, "Chưa cấu hình SMTP đầy đủ"

        subject = self._build_subject(results)
        body_html = self._build_html_body(results)

        return self._send(subject, body_html)

    def send_test(self) -> tuple[bool, str]:
        """Gửi email test để kiểm tra cấu hình SMTP."""
        subject = "✅ [IP Blacklist Monitor] Email Test Thành Công"
        body_html = """
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
        <div style="background:#1a1a2e;padding:20px;border-radius:8px">
          <h2 style="color:#58a6ff;margin:0 0 16px">🛡 IP Blacklist Monitor</h2>
          <div style="background:#21262d;padding:16px;border-radius:6px;color:#e6edf3">
            <p>✅ Cấu hình SMTP đã hoạt động chính xác!</p>
            <p style="color:#8b949e;font-size:13px">
              Thời gian: {now}<br>
              Gửi từ: {sender}
            </p>
          </div>
        </div>
        </div>
        """.format(
            now=datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
            sender=self.config.username,
        )
        return self._send(subject, body_html)

    def _send(self, subject: str, body_html: str) -> tuple[bool, str]:
        """Thực hiện gửi email qua SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.username
            msg["To"] = self.config.recipient
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            if self.config.use_tls:
                # STARTTLS (port 587)
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(self.config.username, self.config.password)
                    server.sendmail(
                        self.config.username,
                        self.config.recipient,
                        msg.as_string()
                    )
            else:
                # SSL (port 465)
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port,
                                      context=ctx, timeout=15) as server:
                    server.login(self.config.username, self.config.password)
                    server.sendmail(
                        self.config.username,
                        self.config.recipient,
                        msg.as_string()
                    )
            return True, ""
        except smtplib.SMTPAuthenticationError:
            return False, "Sai username/password hoặc app password. Kiểm tra cấu hình."
        except smtplib.SMTPConnectError:
            return False, f"Không thể kết nối đến {self.config.smtp_host}:{self.config.smtp_port}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _build_subject(results: list) -> str:
        danger = [r for r in results if r.risk_level == "Danger"]
        warning = [r for r in results if r.risk_level == "Warning"]
        if danger:
            return f"🔴 [NGUY HIỂM] {len(danger)} IP bị dính blacklist lớn - IP Blacklist Monitor"
        return f"🟡 [CẢNH BÁO] {len(warning)} IP bị blacklist - IP Blacklist Monitor"

    @staticmethod
    def _build_html_body(results: list) -> str:
        risk_colors = {"Safe": "#3fb950", "Warning": "#d29922", "Danger": "#f85149"}
        rows = ""
        for r in results:
            color = risk_colors.get(r.risk_level, "#8b949e")
            major_names = ", ".join(e.name for e in r.major_listed) or "—"
            other_names = ", ".join(e.name for e in r.other_listed[:5]) or "—"
            if len(r.other_listed) > 5:
                other_names += f" ... (+{len(r.other_listed)-5})"
            rows += f"""
            <tr>
              <td style="padding:10px;border-bottom:1px solid #30363d;font-family:monospace">{r.ip}</td>
              <td style="padding:10px;border-bottom:1px solid #30363d;text-align:center">{r.total_listed}</td>
              <td style="padding:10px;border-bottom:1px solid #30363d;color:{color};font-weight:700">{r.risk_level}</td>
              <td style="padding:10px;border-bottom:1px solid #30363d;color:#f85149;font-size:12px">{major_names}</td>
              <td style="padding:10px;border-bottom:1px solid #30363d;font-size:12px">{other_names}</td>
            </tr>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:700px;margin:auto;background:#0d1117;padding:20px;border-radius:8px">
          <div style="border-bottom:2px solid #58a6ff;padding-bottom:12px;margin-bottom:16px">
            <h2 style="color:#58a6ff;margin:0">🛡 IP Blacklist Monitor</h2>
            <p style="color:#8b949e;margin:4px 0 0;font-size:13px">
              Cảnh báo phát hiện lúc {datetime.now().strftime("%H:%M:%S ngày %d/%m/%Y")}
            </p>
          </div>
          <table style="width:100%;border-collapse:collapse;background:#161b22;border-radius:6px;overflow:hidden">
            <thead>
              <tr style="background:#21262d">
                <th style="padding:10px;text-align:left;color:#8b949e;font-size:12px">IP</th>
                <th style="padding:10px;color:#8b949e;font-size:12px">Tổng BL</th>
                <th style="padding:10px;color:#8b949e;font-size:12px">Risk</th>
                <th style="padding:10px;text-align:left;color:#8b949e;font-size:12px">BL Lớn</th>
                <th style="padding:10px;text-align:left;color:#8b949e;font-size:12px">BL Khác</th>
              </tr>
            </thead>
            <tbody style="color:#e6edf3">
              {rows}
            </tbody>
          </table>
          <p style="color:#8b949e;font-size:11px;margin-top:16px">
            Email tự động từ IP Blacklist Monitor. Vui lòng không reply email này.
          </p>
        </div>
        """
