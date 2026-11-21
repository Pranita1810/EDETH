"""EDETH Design System & Theme
Derived from retro-futuristic neo-brutalist theme specifications.
"""
from __future__ import annotations

import sys
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPen, QPolygonF)
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)


# ════════════════════════════════════════════════════════════════════════════
#  THEME CONSTANTS
# ════════════════════════════════════════════════════════════════════════════
class T:
    BG = "#F9E6E4"          # pink grid paper
    GRID_LINE = "#F3CFCF"   # grid lines
    SURFACE = "#FFFFFF"     # pure white cards
    SURFACE2 = "#FBEFEF"    # soft tinted surface
    LINE = "#EBD3D3"        # soft dividers
    LINE2 = "#3B2A30"       # dark cocoa outline (2px borders)
    TEXT = "#3B2A30"        # dark cocoa primary text
    MUTED = "#7A646A"       # muted cocoa secondary text
    DIM = "#B3A0A4"         # inactive / placeholder text
    ACCENT = "#00909A"      # teal primary accent
    ACCENT_LIGHT = "#DAF8FA"# pastel sky / cyan accent
    ACCENT2 = "#EE9B00"     # sunny amber
    YELLOW = "#F5B800"      # bright sunny yellow
    PINK_SHADOW = "#F6C9CB" # retro offset shadow
    BADGE_PINK = "#F8D2D2"  # badge soft pink
    POS = "#2E9E6B"         # success / positive
    NEG = "#E04E3E"         # danger / negative
    PALETTE = [ACCENT, YELLOW, NEG, "#F29CA3", "#3B2A30", "#6CCBD0"]


FAMILIES = ["Lato", "Segoe UI", "Helvetica Neue", "Arial"]
DISPLAY = ["Lilita One", "Fredoka", "Baloo 2", "Arial Rounded MT Bold", "Segoe UI Black",
           "Arial Black", "Verdana"]
LIGHT, NORMAL = QFont.Weight.Normal, QFont.Weight.Bold


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS & TYPOGRAPHY
# ════════════════════════════════════════════════════════════════════════════
def F(size: float = 10, weight=LIGHT, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(DISPLAY if weight in (QFont.Weight.Black, QFont.Weight.ExtraBold) else FAMILIES)
    f.setPointSizeF(size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def qc(hexs: str, a: float = 1.0) -> QColor:
    c = QColor(hexs)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ease(t: float) -> float:
    return 1.0 - (1.0 - clamp(t, 0.0, 1.0)) ** 3


def mix(c1: str, c2: str, t: float) -> QColor:
    a, b = QColor(c1), QColor(c2)
    return QColor(int(lerp(a.red(), b.red(), t)), int(lerp(a.green(), b.green(), t)),
                  int(lerp(a.blue(), b.blue(), t)), int(lerp(a.alpha(), b.alpha(), t)))


def label(text: str = "", size: float = 10, color: str = T.TEXT, weight=LIGHT,
          spacing: float = 0.0, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setFont(F(size, weight, spacing))
    lb.setStyleSheet(f"color:{color};background:transparent;")
    lb.setWordWrap(wrap)
    return lb


def badge(text: str, bg: str = T.BADGE_PINK, fg: str = T.TEXT, size: float = 8) -> QLabel:
    lb = label(text, size, fg, NORMAL, 2.0)
    lb.setStyleSheet(
        f"color:{fg};background:{bg};border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;"
    )
    return lb


# ════════════════════════════════════════════════════════════════════════════
#  GLOBAL STYLESHEET
# ════════════════════════════════════════════════════════════════════════════
QSS = f"""
* {{ outline: 0; }}
QToolTip {{ background:{T.SURFACE2}; color:{T.TEXT}; border:2px solid {T.LINE2}; padding:6px 10px; font-weight:bold; }}
QScrollBar:vertical {{ background:transparent; width:8px; margin:4px 2px; }}
QScrollBar::handle:vertical {{ background:{T.LINE2}; border-radius:3px; min-height:40px; }}
QScrollBar::handle:vertical:hover {{ background:{T.ACCENT}; }}
QScrollBar:horizontal {{ background:transparent; height:8px; margin:2px 4px; }}
QScrollBar::handle:horizontal {{ background:{T.LINE2}; border-radius:3px; min-width:40px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QLineEdit {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:6px; color:{T.TEXT};
            padding:8px 12px; selection-background-color:{T.ACCENT}; selection-color:#FFFFFF; }}
QLineEdit:focus {{ border:2px solid {T.ACCENT}; }}
QComboBox {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:6px; color:{T.TEXT};
            padding:4px 10px; font-weight:bold; }}
QComboBox:hover {{ border-color:{T.ACCENT}; }}
QComboBox QAbstractItemView {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2};
                             selection-background-color:{T.ACCENT_LIGHT}; selection-color:{T.TEXT}; }}
QSpinBox {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:4px; color:{T.TEXT};
           font-weight:bold; padding:2px 6px; }}
QSpinBox:focus {{ border:2px solid {T.ACCENT}; }}
QPlainTextEdit, QTextEdit {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:6px; color:{T.TEXT};
                             selection-background-color:{T.ACCENT_LIGHT}; selection-color:{T.TEXT}; }}
"""


# ════════════════════════════════════════════════════════════════════════════
#  BASE SURFACES & BUTTONS
# ════════════════════════════════════════════════════════════════════════════
class Card(QWidget):
    """Neo-brutalist card with retro offset drop-shadow animation on hover."""

    def __init__(self, shadow_color: str = T.PINK_SHADOW, bg_color: str = T.SURFACE):
        super().__init__()
        self.shadow_color = shadow_color
        self.bg_color = bg_color
        self._h = 0.0
        self._a = QVariantAnimation(self)
        self._a.setDuration(280)
        self._a.setEasingCurve(QEasingCurve.OutCubic)
        self._a.valueChanged.connect(self._set_h)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def _go(self, t):
        self._a.stop()
        self._a.setStartValue(self._h)
        self._a.setEndValue(t)
        self._a.start()

    def enterEvent(self, e):
        self._go(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._go(0.0)
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        o = 5 + 3 * self._h
        r = QRectF(2, 2, self.width() - 11, self.height() - 11)
        # Drop shadow block
        p.setPen(QPen(QColor(T.LINE2), 2))
        p.setBrush(QColor(self.shadow_color))
        p.drawRoundedRect(r.translated(o, o), 6, 6)
        # Foreground card surface
        p.setBrush(QColor(self.bg_color))
        p.drawRoundedRect(r, 6, 6)


class RetroButton(QPushButton):
    """Neo-brutalist interactive button with offset shadow and click feedback."""

    def __init__(self, text: str, bg: str = "#FFFFFF", hover_bg: str = T.YELLOW,
                 fg: str = T.TEXT, height: int = 38, font_size: float = 9):
        super().__init__(text)
        self.bg = bg
        self.hover_bg = hover_bg
        self.fg = fg
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(F(font_size, NORMAL, 1.5))
        self.setFixedHeight(height)
        self.apply_style()

    def apply_style(self):
        self.setStyleSheet(
            f"QPushButton {{"
            f"  color: {self.fg};"
            f"  background: {self.bg};"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 0 22px;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {self.hover_bg};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background: {self.bg};"
            f"  padding-top: 2px;"
            f"}}"
        )


class GhostButton(RetroButton):
    def __init__(self, text: str):
        super().__init__(text, bg="#FFFFFF", hover_bg=T.YELLOW, fg=T.TEXT, height=34, font_size=8)


class PrimaryButton(RetroButton):
    def __init__(self, text: str):
        super().__init__(text, bg=T.ACCENT, hover_bg="#00ACB8", fg="#FFFFFF", height=42, font_size=10)


def panel(eyebrow: str | None, widget: QWidget, pad: int = 24,
          shadow_color: str = T.PINK_SHADOW) -> tuple[Card, QLabel | None]:
    c = Card(shadow_color=shadow_color)
    lay = QVBoxLayout(c)
    lay.setContentsMargins(pad, 20, pad, 18)
    lay.setSpacing(10)
    t = None
    if eyebrow:
        t = label(eyebrow, 8, T.MUTED, NORMAL, 2.4)
        lay.addWidget(t)
    lay.addWidget(widget, 1)
    return c, t


def page_header(eyebrow: str, title: str, sub: str, right: QWidget | None = None) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 8)
    col = QVBoxLayout()
    col.setSpacing(6)
    
    e = badge(eyebrow, bg=T.BADGE_PINK)
    col.addWidget(e, 0, Qt.AlignLeft)
    
    title_lbl = label(title, 26, T.TEXT, QFont.Weight.Black, 0.5)
    col.addWidget(title_lbl)
    
    sb = badge(sub, bg=T.ACCENT_LIGHT, size=9)
    col.addWidget(sb, 0, Qt.AlignLeft)
    
    lay.addLayout(col)
    lay.addStretch()
    if right is not None:
        lay.addWidget(right, 0, Qt.AlignBottom)
    return w


def scrollable(w: QWidget) -> QScrollArea:
    a = QScrollArea()
    a.setWidgetResizable(True)
    a.setFrameShape(QScrollArea.NoFrame)
    a.setWidget(w)
    a.viewport().setAutoFillBackground(False)
    w.setAutoFillBackground(False)
    a.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                    "QScrollArea > QWidget > QWidget{background:transparent;}")
    a.viewport().setStyleSheet("background:transparent;")
    return a
