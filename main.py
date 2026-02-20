import sys
import os
import json
import subprocess
import re
from datetime import datetime

DEBUG = True

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "start_minimized": False,
    "scan_interval": 3,
    "show_signal_bars": True,
    "auto_refresh": True,
    "animations": True,
    "close_to_tray": True,
    "show_tray_notifications": False,
    "theme": "Dark",
}


def debug(*args, **kwargs):
    if DEBUG:
        print(f"[DEBUG] [{datetime.now().strftime('%H:%M:%S')}]", *args, **kwargs)


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception as e:
            debug(f"Error loading config: {e}")
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=4)
        debug(f"Config saved to {CONFIG_PATH}")
    except Exception as e:
        debug(f"Error saving config: {e}")


from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSystemTrayIcon,
    QMenu,
    QComboBox,
    QLabel,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QFrame,
    QSplitter,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QSpinBox,
    QGridLayout,
)
from PySide6.QtCore import (
    QThread,
    Signal,
    Qt,
    QTimer,
    QPointF,
    QRectF,
)
from PySide6.QtGui import (
    QIcon,
    QAction,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QBrush,
    QCursor,
    QPixmap,
    QPainterPath,
    QDesktopServices,
)
from PySide6.QtCore import QUrl

from themes import THEME, apply_theme, get_theme_names, current_theme_name


# ── Data model ────────────────────────────────────────────────────────────────

class WifiNetwork:
    def __init__(self, ssid, bssid, signal, channel, freq, security, signal_bar=0):
        self.ssid = ssid
        self.bssid = bssid
        self.signal = signal
        self.channel = channel
        self.frequency = freq
        self.security = security
        self.signal_bar = signal_bar
        self.last_seen = datetime.now()

    @property
    def signal_dbm(self):
        try:
            return int((int(self.signal) / 2) - 100) if self.signal else -100
        except Exception as e:
            debug(f"[WifiNetwork] signal_dbm error: {e}")
            return -100

    @property
    def signal_quality(self):
        try:
            s = int(self.signal)
            if s >= 75:
                return "Excellent"
            elif s >= 50:
                return "Good"
            elif s >= 25:
                return "Fair"
            else:
                return "Weak"
        except Exception as e:
            debug(f"[WifiNetwork] signal_quality error: {e}")
            return "Unknown"

    @property
    def band(self):
        try:
            freq = int(self.frequency.replace("MHz", ""))
            return "5 GHz" if freq > 5000 else "2.4 GHz"
        except Exception as e:
            debug(f"[WifiNetwork] band error: {e}")
            return "Unknown"


# ── Scanner thread ─────────────────────────────────────────────────────────────

class WifiScannerThread(QThread):
    networks_found = Signal(list)

    def __init__(self):
        super().__init__()
        self.adapter = ""
        self.running = True
        self.scan_interval = 3000

    def set_adapter(self, adapter):
        self.adapter = adapter

    def set_interval(self, interval):
        self.scan_interval = interval

    def run(self):
        while self.running:
            if self.adapter and self.adapter not in ["No adapters", "p2p-dev-wlan0"]:
                debug(f"[WiFi Scanner] Scanning with adapter: {self.adapter}")
                try:
                    cmd = [
                        "nmcli", "-t",
                        "-f", "BSSID,SIGNAL,CHAN,FREQ,SECURITY,SSID",
                        "device", "wifi", "list",
                        "ifname", self.adapter,
                    ]
                    debug(f"[WiFi Scanner] Running: {' '.join(cmd)}")
                    output = subprocess.check_output(
                        cmd, text=True, stderr=subprocess.DEVNULL
                    )
                    lines = output.strip().split("\n")
                    debug(f"[WiFi Scanner] Raw output: {len(lines)} lines")

                    networks = []
                    for line in lines:
                        if not line:
                            continue
                        # Unescape BSSID colons before splitting on ':'
                        unescaped = line.replace("\\:", "\x00")
                        parts = unescaped.split(":")
                        if parts:
                            parts[0] = parts[0].replace("\x00", ":")

                        debug(f"[WiFi Scanner] Line: {line[:50]} -> parts: {len(parts)}")

                        if len(parts) >= 5:
                            bssid   = parts[0]
                            signal  = parts[1]
                            chan    = parts[2]
                            freq    = parts[3]
                            sec     = parts[4] if len(parts) > 4 else ""
                            ssid    = ":".join(parts[5:]) if len(parts) > 5 else ""

                            debug(f"[WiFi Scanner] Parsed: SSID={ssid[:30]!r} signal={signal} chan={chan} freq={freq} sec={sec!r}")

                            signal_bar = self._signal_bar(signal)
                            networks.append(
                                WifiNetwork(ssid, bssid, signal, chan, freq, sec, signal_bar)
                            )
                        else:
                            debug(f"[WiFi Scanner] Skipped (too few parts): {line[:50]!r}")

                    debug(f"[WiFi Scanner] Parsed {len(networks)} networks, sorting...")
                    networks.sort(
                        key=lambda x: int(x.signal) if x.signal.isdigit() else 0,
                        reverse=True,
                    )
                    debug(f"[WiFi Scanner] Emitting {len(networks)} networks")
                    self.networks_found.emit(networks)

                except subprocess.CalledProcessError as e:
                    debug(f"[WiFi Scanner] nmcli error (exit {e.returncode}): {e.stderr}")
                except FileNotFoundError:
                    debug("[WiFi Scanner] nmcli not found — install NetworkManager")
                except Exception as e:
                    debug(f"[WiFi Scanner] Unexpected error: {e}")
                    import traceback
                    traceback.print_exc()

            self.msleep(self.scan_interval)

    def _signal_bar(self, signal):
        try:
            s = int(signal)
            if s >= 80: return 4
            if s >= 60: return 3
            if s >= 40: return 2
            if s >= 20: return 1
            return 0
        except Exception as e:
            debug(f"[WiFi Scanner] _signal_bar error: {e}")
            return 0

    def stop(self):
        self.running = False
        self.wait()


# ── Widgets ────────────────────────────────────────────────────────────────────

class SignalStrengthWidget(QWidget):
    def __init__(self, bars=0, parent=None):
        super().__init__(parent)
        self.bars = bars
        self.setMinimumSize(40, 20)

    def set_bars(self, bars):
        self.bars = bars
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width() / 4
        h = self.height()
        colors = [THEME["signal_weak"], THEME["signal_weak"],
                  THEME["signal_fair"], THEME["signal_good"]]
        for i in range(4):
            x = i * (w + 2)
            bar_h = h * (i + 1) / 4
            if i < self.bars:
                painter.setBrush(QBrush(QColor(colors[i])))
            else:
                painter.setBrush(QBrush(QColor(THEME["text_muted"])))
            painter.setPen(Qt.NoPen)
            painter.drawRect(int(x), int(h - bar_h), int(w) - 2, int(bar_h))


class SignalGraphWidget(QWidget):
    def __init__(self, signal_history=None, parent=None):
        super().__init__(parent)
        self.signal_history = signal_history or []
        self.setMinimumHeight(180)
        self.setMinimumWidth(300)
        self._scroll_offset = 0.0
        self._scroll_speed = 0.02
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start()

    def _tick(self):
        if len(self.signal_history) >= 2:
            self._scroll_offset += self._scroll_speed
            if self._scroll_offset > 1.0:
                self._scroll_offset = 1.0
            self.update()

    def set_history(self, history):
        self.signal_history = history
        self._scroll_offset = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        left_pad, top_pad, bottom_pad, right_pad = 45, 10, 5, 10
        graph_w = w - left_pad - right_pad
        graph_h = h - top_pad - bottom_pad

        painter.fillRect(0, 0, w, h, QColor(THEME["bg_tertiary"]))
        painter.setClipRect(QRectF(0, 0, w, h))

        font = QPainter.font(painter) if False else None
        from PySide6.QtGui import QFont as _QFont
        painter.setFont(_QFont("Segoe UI", 9))
        for label, frac in [("0", 0), ("-30", 0.25), ("-60", 0.5), ("-90", 0.75), ("-100", 1.0)]:
            y = top_pad + graph_h * frac
            painter.setPen(QPen(QColor(THEME["border"]), 1, Qt.DashLine))
            painter.drawLine(int(left_pad), int(y), int(w - right_pad), int(y))
            painter.setPen(QColor(THEME["text_secondary"]))
            painter.drawText(2, int(y) + 4, label)

        if len(self.signal_history) < 2:
            painter.setPen(QColor(THEME["text_muted"]))
            painter.setFont(_QFont("Segoe UI", 12))
            painter.drawText(QRectF(left_pad, top_pad, graph_w, graph_h),
                             Qt.AlignCenter, "No data")
            painter.end()
            return

        max_points = 30
        history = list(self.signal_history[-max_points:])
        n = len(history)
        spacing = graph_w / (max_points - 1) if max_points > 1 else graph_w
        scroll_px = self._scroll_offset * spacing

        def dbm_to_y(dbm):
            clamped = max(-100, min(0, dbm))
            return top_pad + graph_h * (-clamped / 100.0)

        points = []
        right_edge = left_pad + graph_w
        for i, dbm in enumerate(history):
            x = right_edge - spacing * (n - 1 - i) - scroll_px
            points.append(QPointF(x, dbm_to_y(dbm)))

        painter.setClipRect(QRectF(left_pad, 0, graph_w, h))

        pen = QPen(QColor(THEME["border"]), 1, Qt.DashLine)
        painter.setPen(pen)
        for i in range(0, len(points), 5):
            if i > 0:
                px = points[i].x()
                if left_pad <= px <= right_edge:
                    painter.drawLine(int(px), int(top_pad), int(px), int(top_pad + graph_h))

        curve_path = QPainterPath()
        curve_path.moveTo(points[0])
        for i in range(1, len(points)):
            p0, p1 = points[i - 1], points[i]
            mid_x = (p0.x() + p1.x()) / 2.0
            curve_path.cubicTo(QPointF(mid_x, p0.y()), QPointF(mid_x, p1.y()), p1)

        fill_path = QPainterPath(curve_path)
        fill_path.lineTo(points[-1].x(), top_pad + graph_h)
        fill_path.lineTo(points[0].x(), top_pad + graph_h)
        fill_path.closeSubpath()

        gradient = QLinearGradient(0, top_pad, 0, top_pad + graph_h)
        color_top = QColor(THEME["accent_primary"]); color_top.setAlpha(80)
        color_bot = QColor(THEME["accent_primary"]); color_bot.setAlpha(10)
        gradient.setColorAt(0, color_top)
        gradient.setColorAt(1, color_bot)
        painter.fillPath(fill_path, QBrush(gradient))

        painter.setPen(QPen(QColor(THEME["accent_primary"]), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(curve_path)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(THEME["accent_primary"])))
        for p in points[-5:]:
            painter.drawEllipse(p, 3, 3)

        painter.end()


# ── Dialogs ────────────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        from PySide6.QtWidgets import QTabWidget
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._scanning_tab(), "Scanning")
        tabs.addTab(self._appearance_tab(), "Appearance")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_settings)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _group_style(self):
        return f"""
            QGroupBox {{
                color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """

    def _general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("Application")
        gl = QVBoxLayout()

        self.start_minimized = QCheckBox("Start minimized to tray")
        self.auto_refresh = QCheckBox("Auto-refresh on startup")
        self.auto_refresh.setChecked(True)
        self.close_to_tray = QCheckBox("Minimize to system tray on close")
        self.close_to_tray.setChecked(True)
        self.show_tray_notifications = QCheckBox("Show system tray notifications")
        self.show_tray_notifications.setChecked(False)

        gl.addWidget(self.start_minimized)
        gl.addWidget(self.auto_refresh)
        gl.addWidget(self.close_to_tray)
        gl.addWidget(self.show_tray_notifications)
        group.setLayout(gl)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _scanning_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("WiFi Scanning")
        gl = QVBoxLayout()

        row = QHBoxLayout()
        row.addWidget(QLabel("Scan interval (seconds):"))
        self.scan_interval = QSpinBox()
        self.scan_interval.setRange(1, 60)
        self.scan_interval.setValue(3)
        row.addWidget(self.scan_interval)
        row.addStretch()
        gl.addLayout(row)
        group.setLayout(gl)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _appearance_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Theme selector
        theme_group = QGroupBox("Colour Theme")
        tgl = QVBoxLayout()

        theme_row = QHBoxLayout()
        theme_lbl = QLabel("Theme:")
        theme_row.addWidget(theme_lbl)

        self.theme_combo = QComboBox()
        for name in get_theme_names():
            self.theme_combo.addItem(name)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        tgl.addLayout(theme_row)
        theme_group.setLayout(tgl)
        layout.addWidget(theme_group)

        # Display options
        disp_group = QGroupBox("Display")
        dgl = QVBoxLayout()

        self.show_signal_bars = QCheckBox("Show signal strength bars")
        self.show_signal_bars.setChecked(True)
        self.animations = QCheckBox("Enable animations")
        self.animations.setChecked(True)

        dgl.addWidget(self.show_signal_bars)
        dgl.addWidget(self.animations)
        disp_group.setLayout(dgl)
        layout.addWidget(disp_group)

        layout.addStretch()
        return widget

    def load_settings(self):
        cfg = load_config()
        self.start_minimized.setChecked(cfg.get("start_minimized", False))
        self.scan_interval.setValue(cfg.get("scan_interval", 3))
        self.show_signal_bars.setChecked(cfg.get("show_signal_bars", True))
        self.auto_refresh.setChecked(cfg.get("auto_refresh", True))
        self.animations.setChecked(cfg.get("animations", True))
        self.close_to_tray.setChecked(cfg.get("close_to_tray", True))
        self.show_tray_notifications.setChecked(cfg.get("show_tray_notifications", False))
        saved_theme = cfg.get("theme", "Dark")
        idx = self.theme_combo.findText(saved_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

    def save_settings(self):
        cfg = load_config()
        cfg["start_minimized"] = self.start_minimized.isChecked()
        cfg["scan_interval"] = self.scan_interval.value()
        cfg["show_signal_bars"] = self.show_signal_bars.isChecked()
        cfg["auto_refresh"] = self.auto_refresh.isChecked()
        cfg["animations"] = self.animations.isChecked()
        cfg["close_to_tray"] = self.close_to_tray.isChecked()
        cfg["show_tray_notifications"] = self.show_tray_notifications.isChecked()
        cfg["theme"] = self.theme_combo.currentText()
        save_config(cfg)


class NetworkDetailsDialog(QDialog):
    def __init__(self, network: WifiNetwork, signal_history=None, scan_interval=3, parent=None):
        super().__init__(parent)
        self.network = network
        self.signal_history = signal_history or []
        self._scan_interval = scan_interval
        self.setWindowTitle(f"Network Details - {network.ssid}")
        self.setMinimumSize(800, 400)
        self._build_ui(network)

    def _build_ui(self, network):
        layout = QVBoxLayout(self)

        header = QLabel(f"📶 {network.ssid}")
        header.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {THEME['accent_primary']}; padding: 10px;"
        )
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)

        # Left: info panel
        info_frame = QFrame()
        info_frame.setMinimumWidth(250)
        info_frame.setStyleSheet(
            f"QFrame {{ background: {THEME['bg_tertiary']}; border-radius: 8px; padding: 15px; }}"
        )
        info_layout = QGridLayout()
        info_layout.setAlignment(Qt.AlignTop)

        sig_val = int(network.signal) if network.signal.isdigit() else 0
        if sig_val >= 75:   sig_color = THEME["signal_excellent"]
        elif sig_val >= 50: sig_color = THEME["signal_good"]
        elif sig_val >= 25: sig_color = THEME["signal_fair"]
        else:               sig_color = THEME["signal_weak"]

        info_items = [
            ("SSID",      network.ssid if network.ssid else "<Hidden>",  None),
            ("BSSID",     network.bssid,                                 None),
            ("Signal",    f"{network.signal}%",                          sig_color),
            ("dBm",       f"{network.signal_dbm} dBm",                   sig_color),
            ("Quality",   network.signal_quality,                        sig_color),
            ("Channel",   network.channel,                               None),
            ("Frequency", network.frequency,                             None),
            ("Band",      network.band,                                  None),
            ("Security",  network.security if network.security else "Open", None),
        ]
        for r, (label, value, color) in enumerate(info_items):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-weight: 600;")
            val = QLabel(str(value))
            val.setStyleSheet(
                f"color: {color if color else THEME['text_primary']}; font-weight: 600;"
            )
            info_layout.addWidget(lbl, r, 0)
            info_layout.addWidget(val, r, 1)

        row = len(info_items)
        interval_lbl = QLabel("Scan interval:")
        interval_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-weight: 600;")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(self._scan_interval)
        self.interval_spin.setSuffix(" s")
        info_layout.addWidget(interval_lbl, row, 0)
        info_layout.addWidget(self.interval_spin, row, 1)
        info_layout.setRowStretch(row + 1, 1)
        info_frame.setLayout(info_layout)

        # Right: signal graph
        graph_frame = QFrame()
        graph_frame.setStyleSheet(
            f"QFrame {{ background: {THEME['bg_tertiary']}; border-radius: 8px;"
            f" border: 1px solid {THEME['border']}; }}"
        )
        graph_layout = QVBoxLayout(graph_frame)
        graph_lbl = QLabel("Signal Strength (dBm)")
        graph_lbl.setStyleSheet(f"color: {THEME['text_secondary']}; font-weight: 600;")
        graph_layout.addWidget(graph_lbl)
        self.graph = SignalGraphWidget(self.signal_history)
        graph_layout.addWidget(self.graph, 1)

        splitter.addWidget(info_frame)
        splitter.addWidget(graph_frame)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# ── Main window ────────────────────────────────────────────────────────────────

class NZscanMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        debug("Initializing NZscan (WiFi-only)...")
        self.config = load_config()
        self.setWindowTitle("NZscan - WiFi Scanner")
        self.setWindowIcon(self._make_icon(32))
        self.setMinimumSize(1000, 650)
        self.resize(1100, 700)

        self._quitting = False
        self.wifi_networks = []       # full unfiltered list
        self.signal_history = {}      # bssid -> [dBm, ...]
        self.connected_bssid = ""

        apply_theme(self.config.get("theme", "Dark"))
        self._setup_stylesheet()
        self._setup_ui()
        self._setup_tray()
        self._load_adapters()
        self._setup_scanner()

        if self.config.get("start_minimized", False):
            self.hide()
        else:
            self.show()

    # ── Stylesheet ──────────────────────────────────────────────────────────────

    def _setup_stylesheet(self):
        css = f"""
            QMainWindow {{
                background-color: {THEME["bg_primary"]};
            }}
            QDialog {{
                background-color: {THEME["bg_secondary"]};
            }}
            QWidget {{
                color: {THEME["text_primary"]}; font-family: 'Segoe UI', sans-serif;
            }}
            QTabWidget > QWidget {{
                background-color: {THEME["bg_secondary"]};
            }}
            QLabel {{ color: {THEME["text_primary"]}; }}

            /* ── Inputs ── */
            QLineEdit {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 6px; padding: 6px 12px;
            }}
            QLineEdit:focus {{ border-color: {THEME["accent_primary"]}; }}

            QSpinBox {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 6px; padding: 5px 8px;
            }}
            QSpinBox:focus {{ border-color: {THEME["accent_primary"]}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {THEME["bg_card"]}; border: none; width: 18px;
            }}
            QSpinBox::up-arrow {{
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-bottom: 5px solid {THEME["text_secondary"]};
            }}
            QSpinBox::down-arrow {{
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid {THEME["text_secondary"]};
            }}

            QComboBox {{
                background-color: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 6px;
                padding: 8px 12px; min-width: 120px;
            }}
            QComboBox:hover {{ border-color: {THEME["accent_primary"]}; }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent; border-right: 5px solid transparent;
                border-top: 5px solid {THEME["text_secondary"]}; margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {THEME["bg_secondary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 6px;
                selection-background-color: {THEME["accent_primary"]};
                selection-color: {THEME["bg_primary"]};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 12px; min-height: 24px;
                background-color: {THEME["bg_secondary"]};
                color: {THEME["text_primary"]};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {THEME["bg_tertiary"]};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {THEME["accent_primary"]};
                color: {THEME["bg_primary"]};
            }}

            /* ── Table ── */
            QTableWidget {{
                background-color: {THEME["bg_secondary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 8px;
                gridline-color: {THEME["border"]};
                selection-background-color: {THEME["accent_primary"]};
                selection-color: {THEME["bg_primary"]};
            }}
            QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {THEME["border"]}; }}
            QTableWidget::item:selected {{ background-color: {THEME["accent_primary"]}; }}
            QHeaderView::section {{
                background-color: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: none; border-bottom: 2px solid {THEME["accent_primary"]};
                padding: 10px; font-weight: 600; font-size: 11px; letter-spacing: 1px;
            }}

            /* ── Buttons ── */
            QPushButton {{
                background: {THEME["accent_primary"]}; color: {THEME["bg_primary"]};
                border: none; border-radius: 6px; padding: 10px 20px;
                font-weight: 600; font-size: 12px;
            }}
            QPushButton:hover {{ background: {THEME["btn_hover"]}; }}
            QPushButton:pressed {{ background: {THEME["btn_pressed"]}; }}
            QPushButton#secondary {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]};
            }}
            QPushButton#secondary:hover {{
                border-color: {THEME["accent_primary"]}; background: {THEME["bg_card"]};
            }}

            /* ── Checkboxes ── */
            QCheckBox {{ color: {THEME["text_secondary"]}; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px; border-radius: 4px;
                border: 2px solid {THEME["border"]}; background: {THEME["bg_tertiary"]};
            }}
            QCheckBox::indicator:checked {{
                background: {THEME["accent_primary"]}; border-color: {THEME["accent_primary"]};
            }}

            /* ── Tabs ── */
            QTabWidget::pane {{
                background: {THEME["bg_secondary"]};
                border: 1px solid {THEME["border"]}; border-radius: 8px;
            }}
            QTabWidget > QWidget {{
                background-color: {THEME["bg_secondary"]};
            }}
            QTabBar::tab {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_secondary"]};
                padding: 10px 20px; border: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px;
            }}
            QTabBar::tab:selected {{
                background: {THEME["bg_secondary"]}; color: {THEME["accent_primary"]};
            }}
            QTabBar::tab:hover:!selected {{ background: {THEME["bg_card"]}; }}

            /* ── GroupBox ── */
            QGroupBox {{
                color: {THEME["text_secondary"]}; border: 1px solid {THEME["border"]};
                border-radius: 8px; margin-top: 15px; padding-top: 10px;
                font-size: 11px; letter-spacing: 1px;
                background: transparent;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 15px; padding: 0 8px; }}

            /* ── Menu ── */
            QMenu {{
                background-color: {THEME["bg_secondary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 8px; padding: 5px;
            }}
            QMenu::item {{ padding: 8px 30px; border-radius: 4px; }}
            QMenu::item:selected {{
                background-color: {THEME["accent_primary"]}30; color: {THEME["accent_primary"]};
            }}
            QMenu::separator {{ height: 1px; background: {THEME["border"]}; margin: 5px 0; }}

            /* ── Scrollbar ── */
            QScrollBar:vertical {{
                background: {THEME["bg_tertiary"]}; width: 10px; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME["accent_primary"]}; border-radius: 5px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {THEME["btn_hover"]}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            /* ── Splitter ── */
            QSplitter::handle {{ background: {THEME["border"]}; }}

            /* ── DialogButtonBox ── */
            QDialogButtonBox QPushButton {{
                min-width: 80px; padding: 8px 20px;
            }}
        """
        # Apply to QApplication so all dialogs and top-level widgets are covered
        QApplication.instance().setStyleSheet(css)

    def _apply_inline_styles(self):
        """Re-apply per-widget inline stylesheets after a theme change."""
        self.header_title.setStyleSheet(f"""
            font-size: 24px; font-weight: bold;
            color: {THEME["accent_primary"]}; font-family: 'Segoe UI', sans-serif;
        """)
        self.adapter_label.setStyleSheet(f"color: {THEME['text_secondary']};")
        self.wifi_count.setStyleSheet(f"color: {THEME['accent_primary']}; font-weight: 600;")

        _sec = f"""
            QPushButton {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {THEME["bg_card"]}; }}
        """
        self.settings_btn.setStyleSheet(_sec)
        self.about_btn.setStyleSheet(_sec)

        self.wifi_filter.setStyleSheet(f"""
            QLineEdit {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 6px; padding: 6px 12px;
            }}
            QLineEdit:focus {{ border-color: {THEME["accent_primary"]}; }}
        """)
        self.status_label.setStyleSheet(f"color: {THEME['text_secondary']};")
        self.last_scan.setStyleSheet(f"color: {THEME['text_secondary']};")
        self.wifi_table.viewport().update()

    # ── UI layout ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._build_wifi_panel(), 1)
        main_layout.addWidget(self._build_status_bar())

    def _build_header(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._make_icon(28).pixmap(28, 28))
        icon_lbl.setFixedSize(28, 28)
        layout.addWidget(icon_lbl)

        self.header_title = QLabel("NZscan")
        self.header_title.setStyleSheet(f"""
            font-size: 24px; font-weight: bold;
            color: {THEME["accent_primary"]}; font-family: 'Segoe UI', sans-serif;
        """)
        layout.addWidget(self.header_title)
        layout.addSpacing(20)

        self.adapter_label = QLabel("Adapter:")
        self.adapter_label.setStyleSheet(f"color: {THEME['text_secondary']};")
        layout.addWidget(self.adapter_label)

        self.wifi_adapter = QComboBox()
        self.wifi_adapter.setMinimumWidth(120)
        self.wifi_adapter.currentTextChanged.connect(self._on_adapter_changed)
        layout.addWidget(self.wifi_adapter)

        self.scan_btn = QPushButton("🔄 Scan")
        self.scan_btn.clicked.connect(self._manual_scan)
        layout.addWidget(self.scan_btn)

        self.auto_scan = QCheckBox("Auto")
        self.auto_scan.setChecked(True)
        self.auto_scan.stateChanged.connect(self._toggle_auto_scan)
        layout.addWidget(self.auto_scan)

        self.wifi_count = QLabel("0")
        self.wifi_count.setStyleSheet(f"color: {THEME['accent_primary']}; font-weight: 600;")
        layout.addWidget(self.wifi_count)

        layout.addStretch()

        _sec_style = f"""
            QPushButton {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {THEME["bg_card"]}; }}
        """
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setStyleSheet(_sec_style)
        self.settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_btn)

        self.about_btn = QPushButton("About")
        self.about_btn.setStyleSheet(_sec_style)
        self.about_btn.clicked.connect(self._open_about)
        layout.addWidget(self.about_btn)

        return widget

    def _build_wifi_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter bar
        filter_layout = QHBoxLayout()
        self.wifi_filter = QLineEdit()
        self.wifi_filter.setPlaceholderText("Search networks...")
        self.wifi_filter.setClearButtonEnabled(True)
        self.wifi_filter.setStyleSheet(f"""
            QLineEdit {{
                background: {THEME["bg_tertiary"]}; color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]}; border-radius: 6px; padding: 6px 12px;
            }}
            QLineEdit:focus {{ border-color: {THEME["accent_primary"]}; }}
        """)
        self.wifi_filter.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.wifi_filter)
        filter_layout.addSpacing(10)

        self.band_24 = QCheckBox("2.4 GHz")
        self.band_24.setChecked(True)
        self.band_24.stateChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.band_24)

        self.band_5 = QCheckBox("5 GHz")
        self.band_5.setChecked(True)
        self.band_5.stateChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.band_5)

        layout.addLayout(filter_layout)

        # Table
        self.wifi_table = QTableWidget()
        self.wifi_table.setColumnCount(9)
        self.wifi_table.setHorizontalHeaderLabels(
            ["", "SSID", "BSSID", "Signal", "dBm", "Channel", "Frequency", "Band", "Security"]
        )
        self.wifi_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.wifi_table.setColumnWidth(0, 50)
        self.wifi_table.setColumnWidth(2, 140)
        self.wifi_table.setColumnWidth(3, 80)
        self.wifi_table.setColumnWidth(4, 70)
        self.wifi_table.setColumnWidth(5, 60)
        self.wifi_table.setColumnWidth(6, 90)
        self.wifi_table.setColumnWidth(7, 70)
        self.wifi_table.setColumnWidth(8, 100)
        self.wifi_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.wifi_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.wifi_table.verticalHeader().setVisible(False)
        self.wifi_table.doubleClicked.connect(self._show_details)
        self.wifi_table.horizontalHeader().sectionClicked.connect(self._sort_by_column)
        self._sort_col = -1
        self._sort_asc = True

        layout.addWidget(self.wifi_table)
        return widget

    def _build_status_bar(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {THEME['text_secondary']};")
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.last_scan = QLabel("Last scan: Never")
        self.last_scan.setStyleSheet(f"color: {THEME['text_secondary']};")
        layout.addWidget(self.last_scan)
        return widget

    # ── Icon ────────────────────────────────────────────────────────────────────

    def _make_icon(self, size=64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#1a1a2e")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)
        cx, cy = size / 2.0, size * 0.65
        pw = max(2, size // 14)
        painter.setPen(QPen(QColor("#00d4ff"), pw, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        for r in [size * 0.15, size * 0.27, size * 0.39]:
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            painter.drawArc(rect, 45 * 16, 90 * 16)
        dot_r = max(2, size // 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#00d4ff")))
        painter.drawEllipse(QPointF(cx, cy), dot_r, dot_r)
        painter.end()
        return QIcon(pixmap)

    # ── Tray ────────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._make_icon(64))
        menu = QMenu()

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)
        menu.addSeparator()

        scan_action = QAction("Scan Now", self)
        scan_action.triggered.connect(self._manual_scan)
        menu.addAction(scan_action)
        menu.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self._quit)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    # ── Adapters & scanner ──────────────────────────────────────────────────────

    def _load_adapters(self):
        debug("Loading WiFi adapters...")
        self.wifi_adapter.clear()
        try:
            result = subprocess.check_output(
                ["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], text=True
            )
            debug(f"nmcli device list:\n{result.strip()}")
            for line in result.splitlines():
                if "wifi" in line.lower() and "p2p" not in line.lower():
                    adapter = line.split(":")[0]
                    debug(f"Found WiFi adapter: {adapter}")
                    self.wifi_adapter.addItem(adapter)
        except Exception as e:
            debug(f"Error loading adapters: {e}")

        if self.wifi_adapter.count() == 0:
            debug("No WiFi adapters found")
            self.wifi_adapter.addItem("No adapters")
        else:
            debug(f"Using adapter: {self.wifi_adapter.currentText()}")

    def _setup_scanner(self):
        debug("Setting up WiFi scanner...")
        self.wifi_scanner = WifiScannerThread()
        self.wifi_scanner.networks_found.connect(self._on_networks_found)

        interval_ms = self.config.get("scan_interval", 3) * 1000
        debug(f"Scan interval: {interval_ms}ms")
        self.wifi_scanner.set_interval(interval_ms)

        adapter = self.wifi_adapter.currentText()
        if adapter and adapter != "No adapters":
            debug(f"Setting adapter: {adapter}")
            self.wifi_scanner.set_adapter(adapter)

        if self.auto_scan.isChecked():
            debug("Auto-scan enabled, starting...")
            self._start_scan()

    def _on_adapter_changed(self, adapter):
        debug(f"Adapter changed to: {adapter!r}")
        if adapter and adapter != "No adapters" and hasattr(self, "wifi_scanner"):
            self.wifi_scanner.set_adapter(adapter)
            if self.auto_scan.isChecked():
                self._start_scan()

    def _toggle_auto_scan(self, state):
        if state:
            self._start_scan()
        else:
            self._stop_scan()

    def _start_scan(self):
        if not self.wifi_scanner.isRunning():
            debug("Starting WiFi scanner thread")
            self.wifi_scanner.start()
        self.status_label.setText("Scanning...")
        self.scan_btn.setEnabled(False)

    def _stop_scan(self):
        debug("Stopping WiFi scanner thread")
        self.wifi_scanner.stop()
        self.wifi_scanner.wait()
        self.status_label.setText("Scan stopped")
        self.scan_btn.setEnabled(True)

    def _manual_scan(self):
        debug("Manual scan triggered")
        adapter = self.wifi_adapter.currentText()
        debug(f"Adapter: {adapter!r}")
        if adapter and adapter != "No adapters":
            self.wifi_scanner.set_adapter(adapter)
            if not self.wifi_scanner.isRunning():
                self.wifi_scanner.start()
            self.status_label.setText("Manual scan initiated...")
        else:
            debug("No valid adapter selected")

    # ── Data update ─────────────────────────────────────────────────────────────

    def _get_connected_bssid(self):
        try:
            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "BSSID,ACTIVE", "device", "wifi", "list"],
                text=True, stderr=subprocess.DEVNULL,
            )
            for line in output.strip().split("\n"):
                unescaped = line.replace("\\:", "\x00")
                parts = unescaped.split(":")
                if len(parts) >= 2 and parts[-1].strip() == "yes":
                    bssid = parts[0].replace("\x00", ":")
                    debug(f"Connected BSSID: {bssid}")
                    return bssid
        except Exception as e:
            debug(f"[Connected] Error: {e}")
        return ""

    def _on_networks_found(self, networks):
        debug(f"Networks received: {len(networks)}")
        self.wifi_networks = networks

        for net in networks:
            if net.bssid not in self.signal_history:
                self.signal_history[net.bssid] = []
            self.signal_history[net.bssid].append(net.signal_dbm)
            if len(self.signal_history[net.bssid]) > 30:
                self.signal_history[net.bssid] = self.signal_history[net.bssid][-30:]

        self.connected_bssid = self._get_connected_bssid()
        self.last_scan.setText(f"Last scan: {datetime.now().strftime('%H:%M:%S')}")
        self._apply_filter()

    # ── Sorting ─────────────────────────────────────────────────────────────────

    def _sort_by_column(self, col):
        if col == 0:
            return
        if col == self._sort_col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        sort_keys = {
            1: lambda n: (n.ssid or "").lower(),
            2: lambda n: n.bssid,
            3: lambda n: int(n.signal) if n.signal.isdigit() else 0,
            4: lambda n: n.signal_dbm,
            5: lambda n: int(n.channel) if n.channel.isdigit() else 0,
            6: lambda n: n.frequency,
            7: lambda n: n.band,
            8: lambda n: n.security or "",
        }
        key_fn = sort_keys.get(col)
        if key_fn:
            self.wifi_networks.sort(key=key_fn, reverse=not self._sort_asc)
        self._apply_filter()

    # ── Filter & render ─────────────────────────────────────────────────────────

    def _apply_filter(self, *_):
        search = self.wifi_filter.text().strip().lower()
        show_24 = self.band_24.isChecked()
        show_5  = self.band_5.isChecked()

        filtered = []
        for net in self.wifi_networks:
            if net.band == "2.4 GHz" and not show_24:
                continue
            if net.band == "5 GHz" and not show_5:
                continue
            if search:
                haystack = f"{net.ssid} {net.bssid} {net.security}".lower()
                if search not in haystack:
                    continue
            filtered.append(net)

        debug(f"Filter: showing {len(filtered)}/{len(self.wifi_networks)} networks")

        self.wifi_table.setRowCount(0)
        connected_bg = QColor(THEME["accent_primary"])
        connected_bg.setAlpha(25)

        for row, net in enumerate(filtered):
            self.wifi_table.insertRow(row)
            is_connected = (net.bssid == self.connected_bssid)

            sig_widget = SignalStrengthWidget(net.signal_bar)
            self.wifi_table.setCellWidget(row, 0, sig_widget)

            items = [
                ("📡 " if is_connected else "") + (net.ssid if net.ssid else "<Hidden Network>"),
                net.bssid,
                f"{net.signal}%",
                f"{net.signal_dbm} dBm",
                net.channel,
                net.frequency,
                net.band,
                net.security if net.security else "Open",
            ]
            for col, val in enumerate(items, 1):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if is_connected:
                    item.setBackground(connected_bg)
                    if col == 1:
                        f = QFont(); f.setBold(True); item.setFont(f)
                if col == 3:
                    sig = int(net.signal) if net.signal.isdigit() else 0
                    if sig >= 75:   c = THEME["signal_excellent"]
                    elif sig >= 50: c = THEME["signal_good"]
                    elif sig >= 25: c = THEME["signal_fair"]
                    else:           c = THEME["signal_weak"]
                    item.setForeground(QColor(c))
                    f = QFont(); f.setBold(True); item.setFont(f)
                if col == 4:
                    dbm = net.signal_dbm
                    if dbm >= -50:   c = THEME["signal_excellent"]
                    elif dbm >= -70: c = THEME["signal_good"]
                    elif dbm >= -80: c = THEME["signal_fair"]
                    else:            c = THEME["signal_weak"]
                    item.setForeground(QColor(c))
                    f = QFont(); f.setBold(True); item.setFont(f)
                self.wifi_table.setItem(row, col, item)

        self.wifi_count.setText(f"{len(filtered)}/{len(self.wifi_networks)}")
        self.status_label.setText(
            f"Showing {len(filtered)} of {len(self.wifi_networks)} networks"
        )

    # ── Details dialog ──────────────────────────────────────────────────────────

    def _show_details(self):
        row = self.wifi_table.currentRow()
        # Map table row back to filtered list to get correct network
        search   = self.wifi_filter.text().strip().lower()
        show_24  = self.band_24.isChecked()
        show_5   = self.band_5.isChecked()
        filtered = []
        for net in self.wifi_networks:
            if net.band == "2.4 GHz" and not show_24: continue
            if net.band == "5 GHz"   and not show_5:  continue
            if search:
                if search not in f"{net.ssid} {net.bssid} {net.security}".lower(): continue
            filtered.append(net)

        if 0 <= row < len(filtered):
            network = filtered[row]
            debug(f"Opening details for: {network.ssid!r} ({network.bssid})")
            history  = self.signal_history.get(network.bssid, [])
            interval = self.config.get("scan_interval", 3)
            dialog   = NetworkDetailsDialog(network, history, interval, self)
            if dialog.exec():
                new_interval = dialog.interval_spin.value()
                if new_interval != interval:
                    self.config["scan_interval"] = new_interval
                    save_config(self.config)
                    self.wifi_scanner.set_interval(new_interval * 1000)
                    debug(f"Scan interval updated to {new_interval}s")

    # ── Settings & About ────────────────────────────────────────────────────────

    def _apply_theme_change(self):
        """Apply the theme stored in config to all UI elements."""
        theme_name = self.config.get("theme", "Dark")
        apply_theme(theme_name)
        debug(f"Applying theme: {theme_name}")
        self._setup_stylesheet()
        self._apply_inline_styles()
        self._apply_filter()   # re-render table rows with new signal colours

    def _open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.config = load_config()
            interval_ms = self.config.get("scan_interval", 3) * 1000
            self.wifi_scanner.set_interval(interval_ms)
            debug(f"Settings saved, interval={interval_ms}ms")
            self._apply_theme_change()

    def _open_about(self):
        about_text = """
<h2>NZscan - WiFi Scanner</h2>
<p><b>Version:</b> 0.2 alpha</p>
<p><b>Description:</b></p>
<p>Advanced WiFi scanner for detecting and monitoring networks with real-time signal tracking.</p>
<p><b>Features:</b></p>
<ul>
    <li>WiFi network scanning with detailed information</li>
    <li>Signal strength monitoring (dBm)</li>
    <li>Real-time signal graph</li>
    <li>Auto-refresh with configurable interval</li>
    <li>System tray support</li>
    <li>Multiple colour themes (Dark, Light, Nord, Dracula)</li>
</ul>
<p><b>License:</b> MIT License</p>
<p><a href="https://github.com/NeleBiH/NZscan">github.com/NeleBiH/NZscan</a></p>
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("About NZscan")
        dialog.setMinimumSize(400, 350)
        layout = QVBoxLayout(dialog)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._make_icon(64).pixmap(64, 64))
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        text = QLabel(about_text)
        text.setWordWrap(True)
        text.setStyleSheet("padding: 10px;")
        text.setAlignment(Qt.AlignCenter)
        text.setOpenExternalLinks(True)
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()

    # ── Close / quit ────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        if self.config.get("close_to_tray", True):
            event.ignore()
            self.hide()
            if self.config.get("show_tray_notifications", False):
                self.tray.showMessage(
                    "NZscan",
                    "Application minimized to system tray",
                    QSystemTrayIcon.Information,
                    2000,
                )
        else:
            self._quit()
            event.accept()

    def _quit(self):
        self._quitting = True
        debug("Quitting — stopping scanner...")
        self.wifi_scanner.stop()
        QApplication.quit()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = NZscanMainWindow()
    sys.exit(app.exec())
