"""
Charts Widget - Biểu đồ thống kê sử dụng Matplotlib nhúng vào PySide6
Gồm 3 biểu đồ: cột (blacklist theo IP), tròn (risk ratio), đường (lịch sử)
"""
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("QtAgg")  # Backend PySide6

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton
)
from PySide6.QtCore import Qt

# ── Màu tối để đồng bộ với app theme ──
BG_FIG  = "#0d1117"
BG_AXES = "#161b22"
TEXT_C  = "#e6edf3"
MUTED_C = "#8b949e"
GRID_C  = "#21262d"
C_SAFE  = "#3fb950"
C_WARN  = "#d29922"
C_DANG  = "#f85149"
C_BLUE  = "#58a6ff"

RISK_COLORS = {
    "Safe":    C_SAFE,
    "Warning": C_WARN,
    "Danger":  C_DANG,
}


def _apply_dark(ax, fig):
    """Áp dụng theme tối cho matplotlib axes."""
    fig.patch.set_facecolor(BG_FIG)
    ax.set_facecolor(BG_AXES)
    ax.tick_params(colors=MUTED_C)
    ax.xaxis.label.set_color(MUTED_C)
    ax.yaxis.label.set_color(MUTED_C)
    ax.title.set_color(TEXT_C)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_C)
    ax.grid(color=GRID_C, linestyle="--", linewidth=0.5, alpha=0.7)


class BarChart(QWidget):
    """Biểu đồ cột: số blacklist bị dính của từng IP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(5, 3.2), dpi=90)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("📊 Blacklist theo IP")
        title.setStyleSheet(f"color:#e6edf3; font-size:13px; font-weight:700;")
        layout.addWidget(title)
        layout.addWidget(self.canvas)

    def update_data(self, results: dict):
        """results: {ip: ParsedResult}"""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _apply_dark(ax, self.fig)

        ips = list(results.keys())
        counts = [results[ip].total_listed for ip in ips]
        colors_bar = [RISK_COLORS.get(results[ip].risk_level, MUTED_C) for ip in ips]

        if not ips:
            ax.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center",
                    color=MUTED_C, fontsize=12, transform=ax.transAxes)
        else:
            bars = ax.bar(range(len(ips)), counts, color=colors_bar, width=0.5, zorder=3)
            ax.set_xticks(range(len(ips)))
            short_labels = [ip[-7:] if len(ip) > 7 else ip for ip in ips]
            ax.set_xticklabels(short_labels, rotation=30, ha="right", fontsize=9, color=MUTED_C)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
            ax.set_ylabel("Số BL", color=MUTED_C, fontsize=10)

            # Nhãn trên cột
            for bar, cnt in zip(bars, counts):
                if cnt > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.05,
                            str(cnt), ha="center", va="bottom",
                            color=TEXT_C, fontsize=9, fontweight="bold")

        self.fig.tight_layout(pad=0.5)
        self.canvas.draw()


class PieChart(QWidget):
    """Biểu đồ donut: tỷ lệ Safe / Warning / Danger."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(3.5, 3.2), dpi=90)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("🍩 Tỷ lệ Risk Level")
        title.setStyleSheet(f"color:#e6edf3; font-size:13px; font-weight:700;")
        layout.addWidget(title)
        layout.addWidget(self.canvas)

    def update_data(self, summary: Dict[str, int]):
        """summary: {'Safe': N, 'Warning': N, 'Danger': N}"""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor(BG_FIG)
        ax.set_facecolor(BG_FIG)

        labels = [k for k, v in summary.items() if v > 0]
        sizes  = [v for v in summary.values() if v > 0]
        colors = [RISK_COLORS[k] for k in labels]

        if not sizes:
            ax.text(0.5, 0.5, "Chưa có dữ liệu", ha="center", va="center",
                    color=MUTED_C, fontsize=12, transform=ax.transAxes)
        else:
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=None,
                colors=colors,
                autopct="%1.0f%%",
                startangle=90,
                wedgeprops=dict(width=0.55, edgecolor=BG_FIG, linewidth=2),
                pctdistance=0.75,
            )
            for at in autotexts:
                at.set_color(TEXT_C)
                at.set_fontsize(10)
                at.set_fontweight("bold")

            # Legend
            patches = [
                mpatches.Patch(color=RISK_COLORS[k], label=f"{k} ({summary[k]})")
                for k in ["Safe", "Warning", "Danger"]
                if summary.get(k, 0) > 0
            ]
            ax.legend(handles=patches, loc="lower center",
                      bbox_to_anchor=(0.5, -0.08),
                      fontsize=9, frameon=False,
                      labelcolor=TEXT_C)

        self.fig.tight_layout(pad=0.3)
        self.canvas.draw()


class LineChart(QWidget):
    """Biểu đồ đường: số blacklist theo thời gian của 1 IP (từ history)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(figsize=(5, 3.2), dpi=90)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # IP selector row
        ctrl_row = QHBoxLayout()
        self.lbl_title = QLabel("📈 Lịch sử theo thời gian")
        self.lbl_title.setStyleSheet(f"color:#e6edf3; font-size:13px; font-weight:700;")
        self.combo_ip = QComboBox()
        self.combo_ip.setStyleSheet(
            f"background:#21262d; color:#e6edf3; border:1px solid #30363d;"
            f"border-radius:4px; padding:2px 8px; font-size:12px;"
        )
        self.combo_ip.setMinimumWidth(140)
        ctrl_row.addWidget(self.lbl_title)
        ctrl_row.addStretch()
        ctrl_row.addWidget(QLabel("IP: "))
        ctrl_row.addWidget(self.combo_ip)

        layout.addLayout(ctrl_row)
        layout.addWidget(self.canvas)

        self._ip_data: Dict[str, List] = {}
        self.combo_ip.currentTextChanged.connect(self._redraw)

    def update_ips(self, ip_data: Dict[str, List]):
        """
        ip_data: {ip: [{'checked_at': str, 'total_listed': int}, ...]}
        """
        self._ip_data = ip_data
        current = self.combo_ip.currentText()
        self.combo_ip.blockSignals(True)
        self.combo_ip.clear()
        self.combo_ip.addItems(list(ip_data.keys()))
        # Giữ IP đã chọn nếu còn
        if current in ip_data:
            self.combo_ip.setCurrentText(current)
        self.combo_ip.blockSignals(False)
        self._redraw()

    def _redraw(self):
        ip = self.combo_ip.currentText()
        records = self._ip_data.get(ip, [])
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        _apply_dark(ax, self.fig)

        if not records or len(records) < 2:
            ax.text(0.5, 0.5,
                    "Cần ≥2 lần check để hiện biểu đồ" if records else "Chưa có dữ liệu",
                    ha="center", va="center", color=MUTED_C, fontsize=11,
                    transform=ax.transAxes)
        else:
            from datetime import datetime as dt
            times = []
            counts = []
            for r in records:
                try:
                    t = dt.fromisoformat(r["checked_at"])
                    times.append(t)
                    counts.append(r["total_listed"])
                except Exception:
                    continue

            ax.plot(times, counts, color=C_BLUE, linewidth=2, marker="o",
                    markersize=5, markerfacecolor=C_BLUE, zorder=3)
            ax.fill_between(times, counts, alpha=0.15, color=C_BLUE)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
            ax.set_ylabel("Số BL", color=MUTED_C, fontsize=10)

            # Format trục thời gian
            self.fig.autofmt_xdate(rotation=30)
            for label in ax.get_xticklabels():
                label.set_fontsize(8)
                label.set_color(MUTED_C)

        ax.set_title(f"Lịch sử: {ip}" if ip else "Chưa chọn IP", color=TEXT_C, fontsize=11)
        self.fig.tight_layout(pad=0.5)
        self.canvas.draw()


class ChartsWidget(QWidget):
    """Widget tổng hợp 3 biểu đồ."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # Hàng trên: bar + pie
        top = QHBoxLayout()
        self.bar_chart = BarChart()
        self.pie_chart = PieChart()
        top.addWidget(self.bar_chart, stretch=3)
        top.addWidget(self.pie_chart, stretch=2)
        layout.addLayout(top, stretch=1)

        # Hàng dưới: line chart
        self.line_chart = LineChart()
        layout.addWidget(self.line_chart, stretch=1)

    def refresh(self, results: dict, risk_summary: dict, ip_histories: dict):
        """
        results: {ip: ParsedResult}
        risk_summary: {'Safe': N, 'Warning': N, 'Danger': N}
        ip_histories: {ip: [{'checked_at':..., 'total_listed':...}]}
        """
        self.bar_chart.update_data(results)
        self.pie_chart.update_data(risk_summary)
        self.line_chart.update_ips(ip_histories)
