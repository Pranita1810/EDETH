"""EDETH Login Page
================
Minimalist, retro neo-brutalist authentication component with smooth animations.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QKeySequence, QLinearGradient,
                           QPainter, QPen, QShortcut)
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from frontend.theme import (DISPLAY, F, LIGHT, NORMAL, QSS, T, Card, PrimaryButton,
                            RetroButton, badge, clamp, ease, label, lerp, panel,
                            qc)


# ════════════════════════════════════════════════════════════════════════════
#  ANIMATED ORBIT BRAND LOGO
# ════════════════════════════════════════════════════════════════════════════
class OrbitLogo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self.angle = 0.0
        self._orbit = QVariantAnimation(self)
        self._orbit.setDuration(5000)
        self._orbit.setStartValue(0.0)
        self._orbit.setEndValue(360.0)
        self._orbit.setLoopCount(-1)
        self._orbit.valueChanged.connect(self._on_orbit)
        self._orbit.start()

    def _on_orbit(self, v):
        self.angle = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2

        # Outer orbit ring
        p.setPen(QPen(qc(T.LINE2), 1.8))
        p.setBrush(qc(T.BADGE_PINK, 0.4))
        p.drawEllipse(QPointF(cx, cy), 28, 28)

        # Inner dashed ring
        p.setPen(QPen(qc(T.ACCENT, 0.6), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 18, 18)

        # Center core dot
        p.setPen(QPen(qc(T.LINE2), 1.5))
        p.setBrush(qc(T.YELLOW))
        p.drawEllipse(QPointF(cx, cy), 6, 6)

        # Orbiting satellite particle
        rad = math.radians(self.angle)
        sx = cx + math.cos(rad) * 28
        sy = cy + math.sin(rad) * 28

        p.setPen(Qt.NoPen)
        p.setBrush(qc(T.ACCENT, 0.3))
        p.drawEllipse(QPointF(sx, sy), 9, 9)

        p.setPen(QPen(qc(T.LINE2), 1.2))
        p.setBrush(qc(T.ACCENT))
        p.drawEllipse(QPointF(sx, sy), 4.5, 4.5)


# ════════════════════════════════════════════════════════════════════════════
#  LOGIN PAGE COMPONENT
# ════════════════════════════════════════════════════════════════════════════
class LoginPage(QWidget):
    login_success = Signal(str)

    AUTH_USER = "pranit"
    AUTH_PASS = "edeth123"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shake_offset = 0.0
        self._init_ui()

    def _init_ui(self):
        # Outer layout to center the login card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setAlignment(Qt.AlignCenter)

        # Login card container
        self.card = Card(shadow_color=T.PINK_SHADOW, bg_color="#FFFFFF")
        self.card.setFixedWidth(430)
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(36, 32, 36, 32)
        card_lay.setSpacing(14)

        # 1. Top Logo & Badge
        top_box = QVBoxLayout()
        top_box.setSpacing(8)
        top_box.setAlignment(Qt.AlignCenter)

        self.logo = OrbitLogo(self)
        top_box.addWidget(self.logo, 0, Qt.AlignCenter)

        top_tag = badge("✦ AUTONOMOUS ANALYTICS PLATFORM ✦", bg=T.BADGE_PINK, size=7.5)
        top_box.addWidget(top_tag, 0, Qt.AlignCenter)

        title = label("EDETH ACCESS", 20, T.TEXT, QFont.Weight.Black, 1.0)
        top_box.addWidget(title, 0, Qt.AlignCenter)

        sub = label("Enter your credentials to enter the workspace.", 8.5, T.MUTED)
        top_box.addWidget(sub, 0, Qt.AlignCenter)

        card_lay.addLayout(top_box)
        card_lay.addSpacing(6)

        # Error notification banner (hidden by default)
        self.error_banner = label("", 8, "#FFFFFF", NORMAL)
        self.error_banner.setAlignment(Qt.AlignCenter)
        self.error_banner.setStyleSheet(
            f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:6px;padding:6px 10px;"
        )
        self.error_banner.hide()
        card_lay.addWidget(self.error_banner)

        # 2. Input Fields
        # Username
        card_lay.addWidget(label("USERNAME", 8, T.TEXT, NORMAL, 1.5))
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Enter username (pranit)")
        self.user_input.setFixedHeight(40)
        self.user_input.setFont(F(9.5))
        self.user_input.returnPressed.connect(self._focus_password)
        card_lay.addWidget(self.user_input)

        # Password
        card_lay.addWidget(label("PASSWORD", 8, T.TEXT, NORMAL, 1.5))
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("••••••••")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setFixedHeight(40)
        self.pass_input.setFont(F(9.5))
        self.pass_input.returnPressed.connect(self.attempt_login)
        card_lay.addWidget(self.pass_input)

        card_lay.addSpacing(8)

        # 3. Login Button
        self.btn_login = PrimaryButton("LOGIN TO EDETH →")
        self.btn_login.setFixedHeight(44)
        self.btn_login.clicked.connect(self.attempt_login)
        card_lay.addWidget(self.btn_login)

        # 4. Quick Auto-fill Hint
        self.hint_btn = QPushButton("Quick demo fill: pranit / edeth123")
        self.hint_btn.setCursor(Qt.PointingHandCursor)
        self.hint_btn.setFont(F(7.5, LIGHT, 0.5))
        self.hint_btn.setStyleSheet(f"color:{T.MUTED};background:transparent;border:none;text-decoration:underline;")
        self.hint_btn.clicked.connect(self._auto_fill)
        card_lay.addWidget(self.hint_btn, 0, Qt.AlignCenter)

        outer.addWidget(self.card)

        # Shake animation setup for wrong login
        self._shake_anim = QVariantAnimation(self)
        self._shake_anim.setDuration(400)
        self._shake_anim.setStartValue(0.0)
        self._shake_anim.setEndValue(1.0)
        self._shake_anim.valueChanged.connect(self._on_shake_tick)

    def _focus_password(self):
        self.pass_input.setFocus()

    def _auto_fill(self):
        self.user_input.setText(self.AUTH_USER)
        self.pass_input.setText(self.AUTH_PASS)
        self.user_input.setFocus()

    def attempt_login(self):
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()

        if user.lower() == self.AUTH_USER and pwd == self.AUTH_PASS:
            self.error_banner.hide()
            self.btn_login.setText("✓ ACCESS GRANTED")
            self.btn_login.setStyleSheet(
                f"QPushButton{{color:#FFFFFF;background:{T.POS};border:2px solid {T.LINE2};"
                f"border-radius:6px;font-weight:bold;}}"
            )
            QTimer.singleShot(250, lambda: self.login_success.emit(self.AUTH_USER))
        else:
            self.show_error("Invalid username or password.")

    def show_error(self, message: str):
        self.error_banner.setText(f"⚠ {message}")
        self.error_banner.show()
        self.pass_input.clear()
        self.pass_input.setFocus()
        self._shake_anim.stop()
        self._shake_anim.start()

    def _on_shake_tick(self, v):
        v = float(v)
        # Dampened horizontal shake waveform
        offset = math.sin(v * math.pi * 5) * 12.0 * (1.0 - v)
        self.card.setGraphicsEffect(None)
        # Shift contents margin horizontally
        margin = int(offset)
        self.layout().setContentsMargins(20 + margin, 20, 20 - margin, 20)

    def reset_fields(self):
        self.user_input.clear()
        self.pass_input.clear()
        self.error_banner.hide()
        self.btn_login.setText("LOGIN TO EDETH →")
        self.btn_login.apply_style()
        self.user_input.setFocus()


# Standalone preview
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    win = QWidget()
    win.setWindowTitle("EDETH — Login Preview")
    win.resize(1100, 720)
    win.setStyleSheet(f"background-color: {T.BG};")

    lay = QVBoxLayout(win)
    login = LoginPage()
    login.login_success.connect(lambda u: print(f"Login success for {u}!"))
    lay.addWidget(login)

    win.show()
    sys.exit(app.exec())
