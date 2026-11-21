"""EDETH — Autonomous Analytics & Decision Platform
===================================================
Main Application Entry Point (Frontend)
Built with PySide6 adhering to the retro neo-brutalist theme specifications.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Ensure project root is in sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import (QEasingCurve, QEvent, QPointF, QRectF,
                            Qt, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QKeySequence, QLinearGradient,
                           QPainter, QPainterPath, QPalette, QPen, QPolygonF, QShortcut)
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QSizeGrip, QStackedWidget, QVBoxLayout,
                               QWidget)

from frontend.pages import DataIngestionPage, LoginPage, TestingPage, UserPage, WelcomePage
from frontend.theme import (DISPLAY, F, LIGHT, NORMAL, QSS, T, Card, GhostButton,
                            badge, label, panel, qc, scrollable)


# ════════════════════════════════════════════════════════════════════════════
#  WINDOWS CAPTION BUTTONS (MINIMIZE, MAXIMIZE / RESTORE, CLOSE)
# ════════════════════════════════════════════════════════════════════════════
class WindowCaptionButton(QPushButton):
    """Windows-standard caption button placed on the top right.

    Matches Windows 10/11 behavior with red hover on close and custom vector icons.
    """

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind  # "min", "max", "close"
        self._is_maximized = False
        self.setFixedSize(48, 54)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._apply_style()

    def set_maximized(self, is_max: bool):
        self._is_maximized = is_max
        self.update()

    def _apply_style(self):
        if self.kind == "close":
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #E81123;
                }
                QPushButton:pressed {
                    background-color: #C4101E;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.22);
                }
                QPushButton:pressed {
                    background-color: rgba(255, 255, 255, 0.35);
                }
            """)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        pen = QPen(QColor("#FFFFFF"), 1.25)
        pen.setCapStyle(Qt.SquareCap)
        p.setPen(pen)

        if self.kind == "min":
            p.drawLine(cx - 5, cy, cx + 5, cy)

        elif self.kind == "max":
            if self._is_maximized:
                p.drawRect(cx - 3, cy - 5, 8, 8)
                p.drawLine(cx - 5, cy - 3, cx - 5, cy + 5)
                p.drawLine(cx - 5, cy + 5, cx + 3, cy + 5)
                p.drawLine(cx + 3, cy + 5, cx + 3, cy + 3)
            else:
                p.drawRect(cx - 5, cy - 5, 10, 10)

        elif self.kind == "close":
            p.setRenderHint(QPainter.Antialiasing, True)
            cross_pen = QPen(QColor("#FFFFFF"), 1.35)
            p.setPen(cross_pen)
            p.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            p.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)


# ════════════════════════════════════════════════════════════════════════════
#  TITLE BAR WITH CLICKABLE EDETH BRAND AND TOP-RIGHT WINDOW CONTROLS
# ════════════════════════════════════════════════════════════════════════════
class TitleBar(QWidget):
    home_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)
        lay = QHBoxLayout(self)
        # 0 right margin so caption buttons dock flush against the right edge
        lay.setContentsMargins(18, 0, 0, 0)
        lay.setSpacing(0)

        # Left: Clickable EDETH title button (redirects to Home)
        left_box = QHBoxLayout()
        left_box.setSpacing(10)

        self.brand_title = QPushButton("EDETH ANALYTICS")
        self.brand_title.setCursor(Qt.PointingHandCursor)
        self.brand_title.setToolTip("Go to Home")
        self.brand_title.setFont(F(13, NORMAL, 3))
        self.brand_title.setStyleSheet("""
            QPushButton {
                color: #FFFFFF;
                background: transparent;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.brand_title.clicked.connect(self.home_requested)
        left_box.addWidget(self.brand_title)

        mode_badge = label("AUTONOMOUS ENGINE", 7.5, "#DAF8FA", NORMAL, 2.5)
        mode_badge.setStyleSheet(
            "background:#005E63;color:#DAF8FA;border:1px solid #3B2A30;padding:2px 8px;border-radius:3px;"
        )
        left_box.addWidget(mode_badge)

        lay.addLayout(left_box)
        lay.addStretch()

        # Center / Status chip
        right_box = QHBoxLayout()
        right_box.setSpacing(14)

        self.chip = label("SYSTEM READY · AUTONOMOUS WORKFLOW", 8, "#E8FAFB", NORMAL, 1.8)
        right_box.addWidget(self.chip)

        lay.addLayout(right_box)
        lay.addSpacing(16)

        # Standard Windows caption buttons on the far top-right
        self.btn_min = WindowCaptionButton("min", self)
        self.btn_max = WindowCaptionButton("max", self)
        self.btn_close = WindowCaptionButton("close", self)

        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

    def mousePressEvent(self, e):
        # Allow dragging the window from empty areas on the title bar
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        # Double clicking title bar maximizes / restores
        if e.button() == Qt.LeftButton:
            self.btn_max.click()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#008F95"))
        p.setPen(QPen(QColor(T.LINE2), 2))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ════════════════════════════════════════════════════════════════════════════
#  LEFT SIDEBAR (NAV RAIL) — STYLED ACCORDING TO THEME REFERENCE
# ════════════════════════════════════════════════════════════════════════════
class NavRail(QWidget):
    """Neo-brutalist left navigation rail with orbit indicator and active page marker."""
    selected = Signal(int)
    ITEMS = ["HOME", "INGESTION", "TESTING"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(96)
        self.setMouseTracking(True)
        self.index, self.hov, self.angle = 0, -1, 0.0
        self.iy = self._rect(0).center().y()

        # Orbit spinning animation
        self._orbit = QVariantAnimation(self)
        self._orbit.setDuration(7000)
        self._orbit.setStartValue(0.0)
        self._orbit.setEndValue(360.0)
        self._orbit.setLoopCount(-1)
        self._orbit.valueChanged.connect(self._on_orbit)
        self._orbit.start()

        # Smooth glide indicator animation
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(350)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._slide.valueChanged.connect(self._on_slide)

    def _rect(self, i: int) -> QRectF:
        return QRectF(8, 100 + i * 82, 80, 72)

    def _on_orbit(self, v):
        self.angle = float(v)
        self.update()

    def _on_slide(self, v):
        self.iy = float(v)
        self.update()

    def set_index(self, i: int):
        if i == self.index:
            return
        self.index = i
        self._slide.stop()
        self._slide.setStartValue(self.iy)
        self._slide.setEndValue(self._rect(i).center().y())
        self._slide.start()
        self.update()

    def _at(self, pos: QPointF) -> int:
        return next((i for i in range(len(self.ITEMS)) if self._rect(i).contains(pos)), -1)

    def mouseMoveEvent(self, e):
        self.hov = self._at(e.position())
        self.setCursor(Qt.PointingHandCursor if self.hov >= 0 else Qt.ArrowCursor)
        self.update()

    def leaveEvent(self, e):
        self.hov = -1
        self.update()

    def mousePressEvent(self, e):
        i = self._at(e.position())
        if i >= 0:
            self.set_index(i)
            self.selected.emit(i)

    @staticmethod
    def _draw_icon(p: QPainter, kind: int, cx: float, cy: float):
        p.setBrush(Qt.NoBrush)
        if kind == 0:  # Clean neo-brutalist HOME house icon
            roof = QPolygonF([QPointF(cx, cy - 9), QPointF(cx - 9, cy), QPointF(cx + 9, cy)])
            p.drawPolygon(roof)
            p.drawRect(QRectF(cx - 7, cy, 14, 9))
            p.drawLine(QPointF(cx, cy + 4), QPointF(cx, cy + 9))
        elif kind == 1:  # Clean neo-brutalist INGESTION database cylinder stack icon
            p.drawEllipse(QRectF(cx - 9, cy - 8, 18, 6.5))
            p.drawLine(QPointF(cx - 9, cy - 4.5), QPointF(cx - 9, cy + 7))
            p.drawLine(QPointF(cx + 9, cy - 4.5), QPointF(cx + 9, cy + 7))
            # Middle layer curve
            mid_rim = QPainterPath()
            mid_rim.moveTo(cx - 9, cy + 1)
            mid_rim.quadTo(cx, cy + 6.5, cx + 9, cy + 1)
            p.drawPath(mid_rim)
            # Bottom layer curve
            bot_rim = QPainterPath()
            bot_rim.moveTo(cx - 9, cy + 7)
            bot_rim.quadTo(cx, cy + 12.5, cx + 9, cy + 7)
            p.drawPath(bot_rim)
        elif kind == 2:  # Clean neo-brutalist TESTING lab beaker icon
            pts = [QPointF(cx - 3, cy - 8), QPointF(cx + 3, cy - 8),
                   QPointF(cx + 3, cy - 3), QPointF(cx + 8, cy + 8),
                   QPointF(cx - 8, cy + 8), QPointF(cx - 3, cy - 3)]
            p.drawPolygon(QPolygonF(pts))
            p.drawLine(QPointF(cx - 5, cy + 4), QPointF(cx + 5, cy + 4))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Solid surface background
        p.fillRect(self.rect(), QColor("#FFFFFF"))

        # Right border: 2px solid dark cocoa
        p.setPen(QPen(qc(T.LINE2), 2))
        p.drawLine(w - 1, 0, w - 1, h)

        # Top brand orbit icon
        cx, cy = w / 2, 48.0
        p.setPen(QPen(qc(T.LINE2), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 14, 14)

        a = math.radians(self.angle)
        dot = QPointF(cx + math.cos(a) * 14, cy + math.sin(a) * 14)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(T.ACCENT, 0.25))
        p.drawEllipse(dot, 6, 6)
        p.setBrush(qc(T.ACCENT))
        p.drawEllipse(dot, 2.4, 2.4)
        p.setBrush(qc(T.TEXT, 0.9))
        p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)

        # Active gliding indicator glow
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0, qc(T.ACCENT, 0.15))
        g.setColorAt(1, qc(T.ACCENT, 0.0))
        p.setBrush(QBrush(g))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, self.iy - 34, w - 1, 68), 6, 6)

        # Active indicator teal bar on left edge
        p.setBrush(qc(T.ACCENT))
        p.drawRoundedRect(QRectF(0, self.iy - 16, 3, 32), 1.5, 1.5)

        # Nav items
        for i, name in enumerate(self.ITEMS):
            r = self._rect(i)
            on = (i == self.index)
            col = qc(T.ACCENT if on else (T.TEXT if i == self.hov else T.MUTED))
            p.setPen(QPen(col, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            self._draw_icon(p, i, r.center().x(), r.top() + 24)
            p.setFont(F(7, NORMAL if on else LIGHT, 1.5))
            p.drawText(QRectF(r.left(), r.top() + 44, r.width(), 16), Qt.AlignCenter, name)

        # Bottom brand tag
        p.setFont(F(6.5, NORMAL, 2))
        p.setPen(qc(T.DIM))
        p.drawText(QRectF(0, h - 32, w, 16), Qt.AlignCenter, "EDETH")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW APPLICATION SHELL
# ════════════════════════════════════════════════════════════════════════════
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EDETH — End-to-End Autonomous Data Analytics Platform")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setMinimumSize(1100, 750)
        self.resize(1380, 920)
        self.logged_in = False
        self.current_dataset = None  # Global storage for ingested dataset/dataframe

        # Main Layout
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Title bar with top-right window controls & clickable EDETH brand
        self.bar = TitleBar(self)
        root_lay.addWidget(self.bar)

        # Top-level Stack: Page 0 = Login Page, Page 1 = Authenticated Workspace
        self.root_stack = QStackedWidget()
        root_lay.addWidget(self.root_stack, 1)

        # 1. Login Page View
        self.login_page = LoginPage()
        self.login_page.login_success.connect(self._on_login_success)
        self.root_stack.addWidget(self.login_page)

        # 2. Authenticated Workspace View
        self.workspace_widget = QWidget()
        body_lay = QHBoxLayout(self.workspace_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Left Sidebar (NavRail)
        self.sidebar = NavRail(self)
        body_lay.addWidget(self.sidebar)

        # Inner pages stack (Home, Ingestion, ...)
        self.page_stack = QStackedWidget()
        body_lay.addWidget(self.page_stack, 1)

        # Pages
        self.welcome_page = WelcomePage()
        self.page_stack.addWidget(scrollable(self.welcome_page))

        self.ingestion_page = DataIngestionPage()
        self.ingestion_page.ingest_requested.connect(self._on_ingest_requested)
        self.page_stack.addWidget(scrollable(self.ingestion_page))

        self.testing_page = TestingPage()
        self.page_stack.addWidget(scrollable(self.testing_page))

        self.root_stack.addWidget(self.workspace_widget)

        # Set initial screen to Login
        self.root_stack.setCurrentIndex(0)
        self.bar.chip.setText("🔒 AUTHENTICATION REQUIRED")

        # Navigation Signals: Click EDETH title or Sidebar item -> Navigate
        self.bar.home_requested.connect(self.go_home)
        self.sidebar.selected.connect(self.go_to_page)

        # Window Caption Buttons on top right
        self.bar.btn_min.clicked.connect(self.showMinimized)
        self.bar.btn_max.clicked.connect(self._toggle_maximize)
        self.bar.btn_close.clicked.connect(self.close)

        # Shortcuts
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)

        # Resizable corner grip
        self.grip = QSizeGrip(self)

    def _on_login_success(self, username: str):
        """Called upon successful credentials verification."""
        self.logged_in = True
        self.bar.chip.setText(f"LOGGED IN: {username.upper()} · ACTIVE SESSION")
        self.root_stack.setCurrentIndex(1)
        self.go_home()

    def _on_ingest_requested(self, payload: dict):
        """Feedback handler when an ingestion button is triggered."""
        src = payload.get("source_type", "DATA").upper()
        self.bar.chip.setText(f"READY: {src} INGESTION PAYLOAD DISPATCHED")

    def logout(self):
        """Logs out the user and returns to the login page."""
        self.logged_in = False
        self.bar.chip.setText("🔒 AUTHENTICATION REQUIRED")
        self.login_page.reset_fields()
        self.root_stack.setCurrentIndex(0)

    def go_home(self):
        """Redirects to Home (Welcome Page)."""
        if not self.logged_in:
            return
        self.sidebar.set_index(0)
        self.page_stack.setCurrentIndex(0)
        self.bar.chip.setText("SYSTEM READY · HOME")

    def go_to_page(self, idx: int):
        """Switches current active page in the workspace."""
        if not self.logged_in:
            return
        self.sidebar.set_index(idx)
        self.page_stack.setCurrentIndex(idx)
        page_name = self.sidebar.ITEMS[idx]
        self.bar.chip.setText(f"ACTIVE: {page_name}")
        # Auto-refresh testing page on tab switch
        if idx == 2 and hasattr(self, "testing_page"):
            self.testing_page.refresh_data()

    def changeEvent(self, e):
        """Update Maximize / Restore icon state when window geometry changes."""
        if e.type() == QEvent.WindowStateChange:
            is_max = self.isMaximized()
            self.bar.btn_max.set_maximized(is_max)
        super().changeEvent(e)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.bar.btn_max.set_maximized(False)
        else:
            self.showMaximized()
            self.bar.btn_max.set_maximized(True)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, e):
        self.grip.move(self.width() - 20, self.height() - 20)
        self.grip.raise_()
        super().resizeEvent(e)

    def paintEvent(self, _):
        """Retro graph paper background pattern."""
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(T.BG))

        # Grid lines
        p.setPen(QPen(QColor(T.GRID_LINE), 2))
        for x in range(0, w, 64):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 64):
            p.drawLine(0, y, w, y)

        # Outer border
        p.setPen(QPen(QColor(T.LINE2), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.WindowText, QColor(T.TEXT))
    pal.setColor(QPalette.Text, QColor(T.TEXT))
    pal.setColor(QPalette.ButtonText, QColor(T.TEXT))
    pal.setColor(QPalette.Base, QColor("#FFFFFF"))
    pal.setColor(QPalette.Window, QColor(T.BG))
    app.setPalette(pal)
    app.setFont(F(10))
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
