#!/usr/bin/env python3
"""
AURA — Analytics
================
A luxury-minimalist, futuristic data analytics workspace in a single PySide6 file.

    pip install PySide6
    python aura_analytics.py

Pages            Ctrl+1 Overview · Ctrl+2 Explorer · Ctrl+3 Insights · Ctrl+4 Live
Load your data   Ctrl+O  (any CSV with numeric columns; a date column is auto-detected)
Fullscreen       F11

Zero dependencies beyond PySide6 — all statistics are implemented here.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict, deque

from PySide6.QtCore import (QAbstractTableModel, QEasingCurve, QModelIndex, QPointF, QRectF,
                            QSortFilterProxyModel, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QKeySequence, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QGraphicsOpacityEffect,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSizeGrip, QStackedWidget, QTableView, QVBoxLayout,
                               QWidget)


# ════════════════════════════════════════════════════════════════════════════
#  THEME
# ════════════════════════════════════════════════════════════════════════════
class T:   # 5th-grade "retro browser window" theme
    BG = "#F9E6E4"          # pink grid paper
    SURFACE = "#FFFFFF"
    SURFACE2 = "#FBEFEF"
    LINE = "#EBD3D3"
    LINE2 = "#3B2A30"       # dark cocoa outline
    TEXT = "#3B2A30"
    MUTED = "#7A646A"
    DIM = "#B3A0A4"
    ACCENT = "#00909A"      # teal
    ACCENT2 = "#EE9B00"     # sunny yellow-orange
    POS = "#2E9E6B"
    NEG = "#E04E3E"
    PALETTE = [ACCENT, "#F5B800", NEG, "#F29CA3", "#3B2A30", "#6CCBD0"]


FAMILIES = ["Lato", "Segoe UI", "Helvetica Neue", "Arial"]
DISPLAY = ["Lilita One", "Fredoka", "Baloo 2", "Arial Rounded MT Bold", "Segoe UI Black",
           "Arial Black", "Verdana"]
LIGHT, NORMAL = QFont.Weight.Normal, QFont.Weight.Bold

QSS = f"""
* {{ outline: 0; }}
QToolTip {{ background:{T.SURFACE2}; color:{T.TEXT}; border:1px solid {T.LINE2}; padding:6px 10px; }}
QScrollBar:vertical {{ background:transparent; width:8px; margin:4px 2px; }}
QScrollBar::handle:vertical {{ background:{T.LINE2}; border-radius:2px; min-height:40px; }}
QScrollBar::handle:vertical:hover {{ background:{T.DIM}; }}
QScrollBar:horizontal {{ background:transparent; height:8px; margin:2px 4px; }}
QScrollBar::handle:horizontal {{ background:{T.LINE2}; border-radius:2px; min-width:40px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QLineEdit {{ background:transparent; border:none; border-bottom:1px solid {T.LINE2}; color:{T.TEXT};
            padding:6px 2px; selection-background-color:{T.ACCENT}; selection-color:#000; }}
QLineEdit:focus {{ border-bottom:1px solid {T.ACCENT}; }}
QTableView {{ background:transparent; border:none; color:{T.TEXT}; gridline-color:transparent;
             selection-background-color:rgba(0,144,154,0.14); selection-color:{T.TEXT}; }}
QTableView::item {{ padding:0 12px; border-bottom:1px solid {T.LINE}; }}
QTableView::item:hover {{ background:rgba(0,0,0,0.04); }}
QHeaderView {{ background:transparent; }}
QHeaderView::section {{ background:transparent; color:{T.MUTED}; border:none;
                       border-bottom:1px solid {T.LINE2}; padding:10px 6px; font-size:7pt; }}
QTableCornerButton::section {{ background:transparent; border:none; }}
"""


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════
def F(size=10, weight=LIGHT, spacing=0.0) -> QFont:
    f = QFont()
    f.setFamilies(DISPLAY if weight == QFont.Weight.Black else FAMILIES)
    f.setPointSizeF(size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def qc(hexs, a=1.0) -> QColor:
    c = QColor(hexs)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease(t):
    return 1 - (1 - clamp(t, 0.0, 1.0)) ** 3


def mix(c1, c2, t) -> QColor:
    a, b = QColor(c1), QColor(c2)
    return QColor(int(lerp(a.red(), b.red(), t)), int(lerp(a.green(), b.green(), t)),
                  int(lerp(a.blue(), b.blue(), t)), int(lerp(a.alpha(), b.alpha(), t)))


def fmt(v, d=1):
    a = abs(v)
    for lim, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= lim:
            return f"{v / lim:.{d}f}{s}"
    return f"{v:,.0f}" if a >= 100 else f"{v:.{d}f}"


def label(text="", size=10, color=T.TEXT, weight=LIGHT, spacing=0.0, wrap=False) -> QLabel:
    lb = QLabel(text)
    lb.setFont(F(size, weight, spacing))
    lb.setStyleSheet(f"color:{color};background:transparent;")
    lb.setWordWrap(wrap)
    return lb


def smooth_path(pts) -> QPainterPath:
    """Catmull-Rom spline converted to cubic Béziers."""
    path = QPainterPath()
    if not pts:
        return path
    path.moveTo(pts[0])
    n = len(pts)
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        c1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6, p1.y() + (p2.y() - p0.y()) / 6)
        c2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6, p2.y() - (p3.y() - p1.y()) / 6)
        path.cubicTo(c1, c2, p2)
    return path


def draw_tip(p: QPainter, anchor: QPointF, lines, bounds: QRectF):
    """Minimal floating tooltip. lines = [(text, pointsize, color), ...]"""
    fonts = [F(s) for _, s, _ in lines]
    ws = [QFontMetrics(f).horizontalAdvance(t) for (t, _, _), f in zip(lines, fonts)]
    hs = [QFontMetrics(f).height() for f in fonts]
    w, h = max(ws) + 26, sum(hs) + 18
    x, y = anchor.x() + 16, anchor.y() - h / 2
    if x + w > bounds.right():
        x = anchor.x() - 16 - w
    y = clamp(y, bounds.top(), bounds.bottom() - h)
    p.setPen(QPen(qc(T.LINE2), 1))
    p.setBrush(qc("#FFFFFF", 0.98))
    p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
    yy = y + 9
    for (t, _, c), f, hh in zip(lines, fonts, hs):
        p.setFont(f)
        p.setPen(qc(c))
        p.drawText(QRectF(x + 13, yy, w - 26, hh), Qt.AlignLeft | Qt.AlignVCenter, t)
        yy += hh


# ════════════════════════════════════════════════════════════════════════════
#  STATISTICS (pure python)
# ════════════════════════════════════════════════════════════════════════════
def mean(v):
    return sum(v) / len(v) if v else 0.0


def stdev(v):
    if len(v) < 2:
        return 0.0
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))


def pearson(a, b):
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def linfit(y):
    n = len(y)
    if n < 2:
        return 0.0, (y[0] if y else 0.0)
    mx, my = (n - 1) / 2, mean(y)
    den = sum((i - mx) ** 2 for i in range(n))
    slope = sum((i - mx) * (v - my) for i, v in enumerate(y)) / den
    return slope, my - slope * mx


def moving_avg(v, w):
    out, acc = [], 0.0
    for i, x in enumerate(v):
        acc += x
        if i >= w:
            acc -= v[i - w]
        out.append(acc / min(i + 1, w))
    return out


def downsample(labels, values, n):
    if len(values) <= n:
        return list(labels), list(values)
    step = len(values) / n
    L, V = [], []
    for i in range(n):
        a, b = int(i * step), max(int((i + 1) * step), int(i * step) + 1)
        V.append(mean(values[a:b]))
        L.append(labels[a])
    return L, V


def histogram(vals, bins=20):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in vals:
        counts[min(bins - 1, int((v - lo) / step))] += 1
    return [fmt(lo + i * step) for i in range(bins)], counts, (mean(vals) - lo) / (hi - lo)


# ════════════════════════════════════════════════════════════════════════════
#  DATASET
# ════════════════════════════════════════════════════════════════════════════
DATE_FMTS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y")
RATIO_KEYS = ("rate", "conv", "pct", "percent", "ratio", "score", "nps", "satisf", "avg",
              "mean", "price", "temp")


def to_float(s):
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(",", "").replace("$", "").replace("%", "")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def date_fmt(sample):
    for f in DATE_FMTS:
        try:
            dt.datetime.strptime(str(sample).strip(), f)
            return f
        except ValueError:
            pass
    return None


def is_ratio(col):
    return any(k in col.lower() for k in RATIO_KEYS)


class Dataset:
    def __init__(self, name, columns, rows):
        self.name, self.columns, self.rows = name, columns, rows
        self.numeric: list[str] = []
        self.cat = None            # index of a low-cardinality categorical column
        self.date_col = None       # index of a parsed date column
        self._by_date: dict = {}
        self._keys: list = []
        self._cache: dict = {}
        self._prepare()

    def _prepare(self):
        for ci, c in enumerate(self.columns):
            vals = [r[ci] for r in self.rows]
            nums = [to_float(v) for v in vals]
            if all(x is not None for x in nums):
                for r, x in zip(self.rows, nums):
                    r[ci] = x
                self.numeric.append(c)
            elif self.date_col is None:
                f = date_fmt(vals[0])
                if f:
                    try:
                        parsed = [dt.datetime.strptime(str(v).strip(), f).date() for v in vals]
                    except ValueError:
                        continue
                    self.date_col = ci
                    for i, d in enumerate(parsed):
                        self._by_date.setdefault(d, []).append(i)
                    self._keys = sorted(self._by_date)
        for ci, c in enumerate(self.columns):
            if c in self.numeric or ci == self.date_col:
                continue
            if 1 < len({r[ci] for r in self.rows}) <= 12:
                self.cat = ci
                break

    # ---- aggregation -------------------------------------------------------
    @staticmethod
    def agg(col, xs):
        return mean(xs) if is_ratio(col) else sum(xs)

    def column(self, col):
        ci = self.columns.index(col)
        return [r[ci] for r in self.rows]

    def series(self, col, n=None):
        if col not in self._cache:
            ci = self.columns.index(col)
            if self.date_col is None:
                vals = [r[ci] for r in self.rows]
                labels = [str(i + 1) for i in range(len(vals))]
            else:
                labels, vals = [], []
                for k in self._keys:
                    vals.append(self.agg(col, [self.rows[i][ci] for i in self._by_date[k]]))
                    labels.append(k.strftime("%d %b"))
            self._cache[col] = (labels, vals)
        labels, vals = self._cache[col]
        return (labels[-n:], vals[-n:]) if n else (labels, vals)

    def breakdown(self, col, n=None):
        if self.cat is None:
            return []
        ci, cc = self.columns.index(col), self.cat
        idx = range(len(self.rows))
        if n and self.date_col is not None:
            idx = [i for k in self._keys[-n:] for i in self._by_date[k]]
        elif n:
            idx = range(max(0, len(self.rows) - n), len(self.rows))
        acc = defaultdict(list)
        for i in idx:
            acc[self.rows[i][cc]].append(self.rows[i][ci])
        return sorted(((k, self.agg(col, v)) for k, v in acc.items()), key=lambda t: -t[1])

    def monthly(self, col):
        labels, vals = self.series(col)
        if self.date_col is None:
            k = max(1, len(vals) // 12)
            chunks = [vals[i:i + k] for i in range(0, len(vals), k)][:12]
            return [str(i + 1) for i in range(len(chunks))], [self.agg(col, c) for c in chunks]
        acc = defaultdict(list)
        for key, v in zip(self._keys, vals):
            acc[(key.year, key.month)].append(v)
        months = sorted(acc)[-12:]
        return ([dt.date(y, m, 1).strftime("%b") for y, m in months],
                [self.agg(col, acc[m]) for m in months])

    # ---- constructors ------------------------------------------------------
    @staticmethod
    def from_csv(path):
        with open(path, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            raw = [r for r in csv.reader(f, dialect) if any(c.strip() for c in r)]
        if len(raw) < 6 or len(raw[0]) < 2:
            raise ValueError("needs at least 2 columns and 5 rows")
        cols = [c.strip() or f"col{i + 1}" for i, c in enumerate(raw[0])]
        rows = [(r + [""] * len(cols))[:len(cols)] for r in raw[1:]]
        ds = Dataset(os.path.basename(path), cols, rows)
        if not ds.numeric:
            raise ValueError("no numeric columns found")
        return ds

    @staticmethod
    def synthetic(days=420, seed=7):
        rnd = random.Random(seed)
        regions = {"North America": 1.0, "Europe": 0.78, "Asia Pacific": 0.92,
                   "Latin America": 0.34, "Middle East": 0.22}
        start = dt.date.today() - dt.timedelta(days=days)
        rows = []
        for d in range(days):
            day = start + dt.timedelta(days=d)
            season = 1 + 0.16 * math.sin(d / 365 * math.tau * 2 - 0.8) + 0.0011 * d
            weekly = 0.86 if day.weekday() >= 5 else 1.0
            for name, w in regions.items():
                users = int(2400 * w * season * weekly * rnd.gauss(1, 0.07))
                conv = clamp(3.1 + rnd.gauss(0, 0.3) + 0.4 * math.sin(d / 30), 1.2, 6)
                orders = int(users * conv / 100)
                spike = 2.7 if rnd.random() < 0.004 else 1.0
                revenue = orders * rnd.gauss(86, 5) * spike
                cost = revenue * rnd.gauss(0.41, 0.025) * (2.2 if rnd.random() < 0.003 else 1.0)
                sat = clamp(rnd.gauss(8.1, 0.4), 0, 10)
                rows.append([day.isoformat(), name, round(revenue, 2), users, orders,
                             round(cost, 2), round(conv, 2), round(sat, 2)])
        cols = ["date", "region", "revenue", "users", "orders", "cost", "conversion", "satisfaction"]
        return Dataset("Synthetic feed", cols, rows)


def generate_insights(ds: Dataset):
    """Returns [(title, detail, tone)] — tone ∈ pos | neg | neutral."""
    out, nums = [], ds.numeric
    m = nums[0]
    labels, vals = ds.series(m)
    k = max(2, min(30, len(vals) // 4))
    if len(vals) >= 2 * k:
        cur, prev = ds.agg(m, vals[-k:]), ds.agg(m, vals[-2 * k:-k])
        ch = (cur - prev) / prev * 100 if prev else 0
        out.append(("Momentum", f"{m.title()} is {'up' if ch >= 0 else 'down'} {abs(ch):.1f}% "
                    f"versus the previous {k} periods.", "pos" if ch >= 0 else "neg"))
    if len(nums) >= 2:
        best = max(((abs(pearson(ds.column(a), ds.column(b))), a, b)
                    for i, a in enumerate(nums) for b in nums[i + 1:]), key=lambda t: t[0])
        r = pearson(ds.column(best[1]), ds.column(best[2]))
        out.append(("Strongest link", f"{best[1].title()} and {best[2]} are "
                    f"{'positively' if r >= 0 else 'inversely'} coupled (r = {r:.2f}).", "neutral"))
    worst = (0, None)
    for c in nums:
        v = ds.series(c)[1]
        s, mu = stdev(v), mean(v)
        cnt = sum(1 for x in v if s and abs(x - mu) / s > 2.8)
        if cnt > worst[0]:
            worst = (cnt, c)
    if worst[1]:
        out.append(("Anomalies", f"{worst[0]} outlier periods detected in {worst[1]} (|z| > 2.8).", "neg"))
    else:
        out.append(("Anomalies", "No statistical outliers detected. Signals are stable.", "pos"))
    i = max(range(len(vals)), key=vals.__getitem__)
    out.append(("Peak", f"{m.title()} peaked at {fmt(vals[i], 2)} on {labels[i]}.", "neutral"))
    cv = max(((stdev(ds.series(c)[1]) / (abs(mean(ds.series(c)[1])) or 1), c) for c in nums))
    out.append(("Volatility", f"{cv[1].title()} is the most volatile metric (CV {cv[0]:.2f}).", "neutral"))
    bd = ds.breakdown(m)
    if bd:
        tot = sum(v for _, v in bd) or 1
        out.append(("Concentration", f"{bd[0][0]} contributes {bd[0][1] / tot * 100:.0f}% "
                    f"of total {m}.", "pos"))
    return out


# ════════════════════════════════════════════════════════════════════════════
#  BASE SURFACES
# ════════════════════════════════════════════════════════════════════════════
class Card(QWidget):
    """Glass surface with a hairline border that warms to champagne on hover."""

    def __init__(self):
        super().__init__()
        self._h = 0.0
        self._a = QVariantAnimation(self)
        self._a.setDuration(350)
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

    def leaveEvent(self, e):
        self._go(0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        o = 5 + 3 * self._h
        r = QRectF(2, 2, self.width() - 11, self.height() - 11)
        p.setPen(QPen(QColor(T.LINE2), 2))
        p.setBrush(QColor("#F6C9CB"))
        p.drawRoundedRect(r.translated(o, o), 6, 6)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(r, 6, 6)


def panel(eyebrow, widget, pad=24):
    c = Card()
    lay = QVBoxLayout(c)
    lay.setContentsMargins(pad, 20, pad, 18)
    lay.setSpacing(8)
    t = None
    if eyebrow:
        t = label(eyebrow, 8, T.MUTED, NORMAL, 2.4)
        lay.addWidget(t)
    lay.addWidget(widget, 1)
    return c, t


def page_header(eyebrow, title, sub, right=None):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    col = QVBoxLayout()
    col.setSpacing(5)
    e = label(eyebrow, 8, T.TEXT, NORMAL, 3)
    e.setStyleSheet(f"color:{T.TEXT};background:#F8D2D2;border:2px solid {T.LINE2};padding:3px 12px;")
    col.addWidget(e, 0, Qt.AlignLeft)
    col.addWidget(label(title, 26, T.TEXT, QFont.Weight.Black, 0.5))
    sb = label(sub, 10, T.TEXT)
    sb.setStyleSheet(f"color:{T.TEXT};background:#DAF8FA;border:2px solid {T.LINE2};padding:4px 12px;")
    col.addWidget(sb, 0, Qt.AlignLeft)
    lay.addLayout(col)
    lay.addStretch()
    if right is not None:
        lay.addWidget(right, 0, Qt.AlignBottom)
    return w


def scrollable(w):
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


class GhostButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(F(8, NORMAL, 1.8))
        self.setFixedHeight(32)
        self.setStyleSheet(
            f"QPushButton{{color:{T.TEXT};background:#FFFFFF;border:2px solid {T.LINE2};"
            f"border-radius:6px;padding:0 20px;}}"
            f"QPushButton:hover{{background:#F5B800;}}")


class Segmented(QWidget):
    """Pill-shaped segmented control with a gliding indicator."""
    changed = Signal(int)

    def __init__(self, options, index=0):
        super().__init__()
        self.index, self.hov = index, -1
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self._a = QVariantAnimation(self)
        self._a.setDuration(380)
        self._a.setEasingCurve(QEasingCurve.OutCubic)
        self._a.valueChanged.connect(self._tick)
        self.set_options(options, index)

    def set_options(self, options, index=0):
        self.options, self.index = list(options), index
        fm = QFontMetrics(F(8, NORMAL, 1.4))
        x, self.rects = 4, []
        for o in self.options:
            w = fm.horizontalAdvance(o) + 34
            self.rects.append(QRectF(x, 4, w, 24))
            x += w
        self.setFixedWidth(int(x + 4))
        r = self.rects[index]
        self._ix, self._iw = r.x(), r.width()
        self._from = self._to = (self._ix, self._iw)
        self.update()

    def select(self, i, emit=True):
        if i == self.index:
            return
        self._from, self.index = (self._ix, self._iw), i
        self._to = (self.rects[i].x(), self.rects[i].width())
        self._a.stop()
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.start()
        if emit:
            self.changed.emit(i)

    def _tick(self, v):
        v = float(v)
        self._ix, self._iw = lerp(self._from[0], self._to[0], v), lerp(self._from[1], self._to[1], v)
        self.update()

    def _at(self, x):
        return next((i for i, r in enumerate(self.rects) if r.x() <= x <= r.right()), -1)

    def mouseMoveEvent(self, e):
        self.hov = self._at(e.position().x())
        self.update()

    def leaveEvent(self, e):
        self.hov = -1
        self.update()

    def mousePressEvent(self, e):
        i = self._at(e.position().x())
        if i >= 0:
            self.select(i)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(qc(T.LINE2), 2))
        p.setBrush(QColor('#FFFFFF'))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 16, 16)
        p.setPen(QPen(qc(T.LINE2), 2))
        p.setBrush(qc('#F5B800'))
        p.drawRoundedRect(QRectF(self._ix, 4, self._iw, 24), 12, 12)
        p.setFont(F(8, NORMAL, 1.4))
        for i, (o, r) in enumerate(zip(self.options, self.rects)):
            on = i == self.index
            p.setPen(qc(T.TEXT if on else (T.TEXT if i == self.hov else T.MUTED), 1 if on else 0.85))
            p.drawText(r, Qt.AlignCenter, o)


# ════════════════════════════════════════════════════════════════════════════
#  CHARTS
# ════════════════════════════════════════════════════════════════════════════
class ChartBase(QWidget):
    """Shared: reveal animation (self.progress 0→1) + hover tracking."""

    def __init__(self, ms=1000):
        super().__init__()
        self.progress, self.hover = 1.0, None
        self.setMouseTracking(True)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(ms)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_prog)

    def _on_prog(self, v):
        self.progress = float(v)
        self.update()

    def replay(self):
        self._anim.stop()
        self.progress = 0.0
        self._anim.start()

    def mouseMoveEvent(self, e):
        self.hover = e.position()
        self.update()

    def leaveEvent(self, e):
        self.hover = None
        self.update()


class LineChart(ChartBase):
    L, R, TOP, B = 58, 28, 16, 30

    def __init__(self):
        super().__init__(1500)
        self.labels, self.values, self.forecast, self.color = [], [], [], T.ACCENT
        self.setMinimumHeight(260)

    def set_data(self, labels, values, forecast=(), color=T.ACCENT):
        self.labels, self.values = downsample(labels, values, 150)
        self.forecast, self.color = list(forecast), color
        self.replay()

    def paintEvent(self, _):
        n = len(self.values)
        if n < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        plot = QRectF(self.L, self.TOP, w - self.L - self.R, h - self.TOP - self.B)
        allv = self.values + self.forecast
        total = len(allv)
        lo, hi = min(allv), max(allv)
        pad = (hi - lo) * 0.12 or 1
        lo, hi = lo - pad, hi + pad

        def X(i):
            return plot.left() + i / (total - 1) * plot.width()

        def Y(v):
            return plot.bottom() - (v - lo) / (hi - lo) * plot.height()

        p.setFont(F(8))
        for k in range(5):                                   # grid + y labels
            v = lo + (hi - lo) * k / 4
            y = Y(v)
            p.setPen(QPen(qc(T.LINE, 0.9), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(qc(T.MUTED))
            p.drawText(QRectF(0, y - 9, self.L - 12, 18), Qt.AlignRight | Qt.AlignVCenter, fmt(v))
        for k in range(6):                                   # x labels
            i = int(k / 5 * (n - 1))
            p.setPen(qc(T.MUTED))
            p.drawText(QRectF(X(i) - 40, plot.bottom() + 9, 80, 16), Qt.AlignCenter, self.labels[i])

        p.save()
        p.setClipRect(QRectF(0, 0, plot.left() + plot.width() * self.progress + 1, h))
        pts = [QPointF(X(i), Y(v)) for i, v in enumerate(self.values)]
        line = smooth_path(pts)
        area = QPainterPath(line)
        area.lineTo(pts[-1].x(), plot.bottom())
        area.lineTo(pts[0].x(), plot.bottom())
        area.closeSubpath()
        g = QLinearGradient(0, plot.top(), 0, plot.bottom())
        g.setColorAt(0, qc(self.color, 0.24))
        g.setColorAt(1, qc(self.color, 0.0))
        p.fillPath(area, QBrush(g))

        ma = moving_avg(self.values, max(3, n // 10))        # trend
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(qc(T.TEXT, 0.26), 1, Qt.DashLine))
        p.drawPath(smooth_path([QPointF(X(i), Y(v)) for i, v in enumerate(ma)]))
        p.setPen(QPen(qc(self.color, 0.10), 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(line)                                      # glow
        p.setPen(QPen(qc(self.color), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(line)

        if self.forecast:                                     # projection + cone
            fp = [pts[-1]] + [QPointF(X(n + i), Y(v)) for i, v in enumerate(self.forecast)]
            m = len(fp)
            band = QPolygonF()
            for i, pt in enumerate(fp):
                band.append(QPointF(pt.x(), pt.y() - i / m * plot.height() * 0.10))
            for i in range(m - 1, -1, -1):
                band.append(QPointF(fp[i].x(), fp[i].y() + i / m * plot.height() * 0.10))
            p.setPen(Qt.NoPen)
            p.setBrush(qc(T.ACCENT2, 0.07))
            p.drawPolygon(band)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(qc(T.ACCENT2, 0.9), 1.6, Qt.DashLine))
            p.drawPolyline(QPolygonF(fp))
            p.setPen(QPen(qc(T.LINE2), 1, Qt.DotLine))
            p.drawLine(QPointF(X(n - 1), plot.top()), QPointF(X(n - 1), plot.bottom()))
            p.setFont(F(7, NORMAL, 2))
            p.setPen(qc(T.ACCENT2, 0.8))
            p.drawText(QRectF(X(n - 1) + 8, plot.top() + 2, 90, 14), Qt.AlignLeft, "FORECAST")
        p.restore()

        if self.progress > 0.98:                              # live end-point
            p.setPen(Qt.NoPen)
            p.setBrush(qc(self.color, 0.22))
            p.drawEllipse(pts[-1], 9, 9)
            p.setBrush(qc(self.color))
            p.drawEllipse(pts[-1], 3.5, 3.5)

        if self.hover and plot.adjusted(0, -12, 0, 12).contains(self.hover):
            i = int(clamp(round((self.hover.x() - plot.left()) / plot.width() * (total - 1)), 0, total - 1))
            v = allv[i]
            pt = QPointF(X(i), Y(v))
            p.setPen(QPen(qc(T.TEXT, 0.18), 1))
            p.drawLine(QPointF(pt.x(), plot.top()), QPointF(pt.x(), plot.bottom()))
            p.setPen(Qt.NoPen)
            p.setBrush(qc(T.TEXT, 0.15))
            p.drawEllipse(pt, 9, 9)
            p.setBrush(qc(T.TEXT))
            p.drawEllipse(pt, 3.5, 3.5)
            name = self.labels[i] if i < n else f"Forecast +{i - n + 1}"
            draw_tip(p, pt, [(name, 8, T.MUTED), (fmt(v, 2), 13, T.TEXT)], QRectF(self.rect()))


class DonutChart(ChartBase):
    def __init__(self):
        super().__init__(1300)
        self.items = []
        self.setMinimumHeight(250)

    def set_data(self, items):
        self.items = [(a, b) for a, b in items if b > 0]
        self.replay()

    def _geo(self):
        d = min(self.height() - 16, self.width() * 0.5, 270)
        return d, d / 2 + 6, self.height() / 2, d / 2 - 14

    def _hover_idx(self, cx, cy, R, tot):
        if not self.hover or not tot:
            return -1
        dx, dy = self.hover.x() - cx, self.hover.y() - cy
        if abs(math.hypot(dx, dy) - R) > 16:
            return -1
        ang, cum = math.degrees(math.atan2(dx, -dy)) % 360, 0.0
        for i, (_, v) in enumerate(self.items):
            cum += v / tot * 360
            if ang <= cum:
                return i
        return -1

    def paintEvent(self, _):
        if not self.items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tot = sum(v for _, v in self.items)
        d, cx, cy, R = self._geo()
        hov = self._hover_idx(cx, cy, R, tot)
        rect = QRectF(cx - R, cy - R, 2 * R, 2 * R)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(qc(T.LINE), 10))
        p.drawEllipse(QPointF(cx, cy), R, R)
        sweep, cum = 360 * ease(self.progress), 0.0
        for i, (_, v) in enumerate(self.items):
            seg = v / tot * 360
            vis = clamp(sweep - cum, 0, seg)
            start, cum = cum, cum + seg
            if vis < 0.6:
                continue
            gap = min(2.4, seg * 0.3)
            on = hov in (-1, i)
            col = qc(T.PALETTE[i % len(T.PALETTE)], 1.0 if on else 0.3)
            p.setPen(QPen(col, 16 if i == hov else 10, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(rect, int((90 - start - gap / 2) * 16), int(-max(vis - gap, 0.1) * 16))
        main = f"{self.items[hov][1] / tot * 100:.1f}%" if hov >= 0 else fmt(tot)
        sub = self.items[hov][0].upper()[:14] if hov >= 0 else "TOTAL"
        p.setFont(F(22, QFont.Weight.Black))
        p.setPen(qc(T.TEXT))
        p.drawText(QRectF(cx - R, cy - 26, 2 * R, 34), Qt.AlignCenter, main)
        p.setFont(F(7, NORMAL, 2.4))
        p.setPen(qc(T.MUTED))
        p.drawText(QRectF(cx - R, cy + 10, 2 * R, 16), Qt.AlignCenter, sub)
        x0, y0 = d + 40, cy - len(self.items) * 16
        fm = QFontMetrics(F(10))
        for i, (name, v) in enumerate(self.items):
            y = y0 + i * 32
            p.setPen(Qt.NoPen)
            p.setBrush(qc(T.PALETTE[i % len(T.PALETTE)], 1 if hov in (-1, i) else 0.35))
            p.drawEllipse(QPointF(x0, y + 12), 4, 4)
            p.setFont(F(10))
            p.setPen(qc(T.TEXT if hov in (-1, i) else T.MUTED))
            p.drawText(QRectF(x0 + 16, y, self.width() - x0 - 80, 24), Qt.AlignLeft | Qt.AlignVCenter,
                       fm.elidedText(str(name), Qt.ElideRight, int(self.width() - x0 - 80)))
            p.setPen(qc(T.MUTED))
            p.drawText(QRectF(self.width() - 64, y, 56, 24), Qt.AlignRight | Qt.AlignVCenter,
                       f"{v / tot * 100:.0f}%")


class BarChart(ChartBase):
    def __init__(self, axis=True):
        super().__init__(1100)
        self.axis, self.labels, self.values = axis, [], []
        self.marker, self.hi_max, self.prefix = None, True, ""
        self.setMinimumHeight(150)

    def set_data(self, labels, values, marker=None, hi_max=True):
        self.labels, self.values, self.marker, self.hi_max = list(labels), list(values), marker, hi_max
        self.replay()

    def paintEvent(self, _):
        n = len(self.values)
        if not n:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        left, bottom = (50, 26) if self.axis else (2, 4)
        plot = QRectF(left, 12, w - left - 8, h - 12 - bottom)
        mx = max(self.values) or 1
        slot = plot.width() / n
        bw = min(slot * 0.5, 34) if self.axis else slot * 0.7
        if self.axis:
            p.setFont(F(8))
            for k in range(4):
                v = mx * k / 3
                y = plot.bottom() - v / mx * plot.height()
                p.setPen(QPen(qc(T.LINE, 0.9), 1))
                p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
                p.setPen(qc(T.MUTED))
                p.drawText(QRectF(0, y - 9, left - 12, 18), Qt.AlignRight | Qt.AlignVCenter, fmt(v))
        hov = -1
        if self.hover:
            i = int((self.hover.x() - plot.left()) / slot)
            hov = i if 0 <= i < n else -1
        imax = self.values.index(max(self.values))
        step = max(1, math.ceil(n / 9))
        tip = None
        for i, v in enumerate(self.values):
            k = ease(clamp(self.progress * 1.6 - i / n * 0.6, 0, 1))
            bh = v / mx * plot.height() * k
            x = plot.left() + slot * i + (slot - bw) / 2
            r = QRectF(x, plot.bottom() - bh, bw, bh)
            on = i == hov or (self.hi_max and i == imax)
            top = qc(T.ACCENT) if on else qc(T.TEXT, 0.30)
            bot = QColor(top)
            bot.setAlphaF(top.alphaF() * 0.10)
            g = QLinearGradient(0, r.top(), 0, plot.bottom())
            g.setColorAt(0, top)
            g.setColorAt(1, bot)
            if bh > 1:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(g))
                p.drawRoundedRect(r, 2.5, 2.5)
            if self.axis and i % step == 0:
                p.setFont(F(8))
                p.setPen(qc(T.TEXT if i == hov else T.MUTED))
                p.drawText(QRectF(x - slot / 2 + bw / 2, plot.bottom() + 7, slot, 16), Qt.AlignCenter,
                           self.labels[i])
            if i == hov:
                tip = (QPointF(x + bw / 2, r.top()), i, v)
        if self.marker:
            mxp = plot.left() + self.marker[0] * plot.width()
            p.setPen(QPen(qc(T.ACCENT2, 0.8), 1, Qt.DashLine))
            p.drawLine(QPointF(mxp, plot.top()), QPointF(mxp, plot.bottom()))
            p.setFont(F(7, NORMAL, 2))
            p.setPen(qc(T.ACCENT2))
            p.drawText(QRectF(mxp + 5, plot.top() - 2, 70, 14), Qt.AlignLeft, self.marker[1])
        if tip:
            draw_tip(p, tip[0], [(self.prefix + self.labels[tip[1]], 8, T.MUTED),
                                 (fmt(tip[2], 2), 13, T.TEXT)], QRectF(self.rect()))


class Heatmap(ChartBase):
    def __init__(self):
        super().__init__(1400)
        self.names, self.mat = [], []
        self.setMinimumHeight(320)

    def set_data(self, names, mat):
        self.names, self.mat = names, mat
        self.replay()

    def paintEvent(self, _):
        n = len(self.names)
        if not n:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        lw, top = 100, 34
        cs = min((self.width() - lw - 8) / n, (self.height() - top - 8) / n)
        fm = QFontMetrics(F(8, NORMAL, 1))
        hov = None
        for i in range(n):
            p.setFont(F(8, NORMAL, 1))
            p.setPen(qc(T.MUTED))
            p.drawText(QRectF(0, top + i * cs, lw - 12, cs), Qt.AlignRight | Qt.AlignVCenter,
                       fm.elidedText(self.names[i].upper(), Qt.ElideRight, lw - 14))
            p.drawText(QRectF(lw + i * cs, 0, cs, top - 8), Qt.AlignHCenter | Qt.AlignBottom,
                       self.names[i][:4].upper())
            for j in range(n):
                v = self.mat[i][j]
                r = QRectF(lw + j * cs + 2, top + i * cs + 2, cs - 4, cs - 4)
                a = ease(clamp(self.progress * 2.2 - (i + j) / (2 * n) * 1.2, 0, 1))
                if i == j:
                    col = qc(T.TEXT, 0.07)
                else:
                    col = mix(T.SURFACE2, T.NEG if v < 0 else T.ACCENT, min(1, abs(v)) ** 1.2 * 0.95)
                col.setAlphaF(col.alphaF() * a)
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(r, 5, 5)
                if cs >= 46:
                    p.setFont(F(8))
                    p.setPen(qc("#FFFFFF" if abs(v) > 0.6 and i != j else T.TEXT, 0.75 * a))
                    p.drawText(r, Qt.AlignCenter, f"{v:.2f}")
                if self.hover and r.contains(self.hover):
                    hov = (i, j, r)
        if hov:
            i, j, r = hov
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(qc(T.ACCENT2), 1.2))
            p.drawRoundedRect(r, 5, 5)
            draw_tip(p, r.center(), [(f"{self.names[i]} × {self.names[j]}", 8, T.MUTED),
                                     (f"r = {self.mat[i][j]:.3f}", 13, T.TEXT)], QRectF(self.rect()))


class LiveChart(ChartBase):
    """Streaming signal with rolling z-score anomaly detection."""

    def __init__(self):
        super().__init__(1)
        self.data, self.anoms = deque(maxlen=150), deque(maxlen=150)
        self.paused, self.t, self.level, self.n_anom = False, 0, 100.0, 0
        self._lo = self._hi = None
        self.setMinimumHeight(380)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        for _ in range(150):
            self.step(silent=True)
        self.timer.start(90)

    def step(self, silent=False):
        if self.paused:
            return
        self.t += 1
        self.level += random.gauss(0, 0.9) + (100 - self.level) * 0.02
        v = self.level + 4 * math.sin(self.t / 9)
        if random.random() < 0.025:
            v += random.choice([-1, 1]) * random.uniform(9, 16)
        recent, an = list(self.data)[-40:], False
        if len(recent) >= 20:
            s = stdev(recent) or 1
            an = abs(v - mean(recent)) / s > 2.6
        self.data.append(v)
        self.anoms.append(an)
        if an and not silent:
            self.n_anom += 1
        if not silent:
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        d, n = list(self.data), len(self.data)
        plot = QRectF(28, 124, w - 56, h - 124 - 30)
        pad = (max(d) - min(d)) * 0.25 or 1
        tlo, thi = min(d) - pad, max(d) + pad
        self._lo = tlo if self._lo is None else lerp(self._lo, tlo, 0.12)
        self._hi = thi if self._hi is None else lerp(self._hi, thi, 0.12)
        lo, hi = self._lo, self._hi

        def X(i):
            return plot.left() + i / (n - 1) * plot.width()

        def Y(v):
            return plot.bottom() - (v - lo) / (hi - lo) * plot.height()

        p.setFont(F(7, NORMAL, 2.6))
        p.setPen(qc(T.MUTED))
        p.drawText(QRectF(28, 22, 300, 14), Qt.AlignLeft, "SIGNAL 01  ·  SYNTHETIC FEED")
        p.setFont(F(36, QFont.Weight.Black))
        p.setPen(qc(T.TEXT))
        p.drawText(QRectF(28, 40, 320, 56), Qt.AlignLeft | Qt.AlignVCenter, f"{d[-1]:,.2f}")
        delta = d[-1] - d[-2]
        p.setFont(F(10, NORMAL))
        p.setPen(qc(T.POS if delta >= 0 else T.NEG))
        p.drawText(QRectF(28, 94, 200, 18), Qt.AlignLeft, f"{'▲' if delta >= 0 else '▼'} {abs(delta):.2f}")

        stats = [("MEAN", f"{mean(d):.1f}"), ("σ", f"{stdev(d):.2f}"), ("ANOMALIES", str(self.n_anom))]
        for i, (k, v) in enumerate(stats):
            x = w - 28 - (3 - i) * 108
            p.setFont(F(7, NORMAL, 2.2))
            p.setPen(qc(T.MUTED))
            p.drawText(QRectF(x, 52, 100, 14), Qt.AlignLeft, k)
            p.setFont(F(15))
            p.setPen(qc(T.NEG if k == "ANOMALIES" and self.n_anom else T.TEXT))
            p.drawText(QRectF(x, 68, 100, 26), Qt.AlignLeft | Qt.AlignVCenter, v)
        pulse = 0.5 + 0.5 * math.sin(self.t / 2.5)
        state = "PAUSED" if self.paused else "LIVE"
        col = T.MUTED if self.paused else T.ACCENT2
        p.setFont(F(7, NORMAL, 2.6))
        p.setPen(qc(col))
        p.drawText(QRectF(w - 128, 20, 100, 16), Qt.AlignRight | Qt.AlignVCenter, state)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(col, 0.3 + 0.7 * (1 if self.paused else pulse)))
        p.drawEllipse(QPointF(w - 20, 28), 3.5, 3.5)

        for k in range(5):
            y = plot.top() + k / 4 * plot.height()
            p.setPen(QPen(qc(T.LINE, 0.9), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setFont(F(8))
            p.setPen(qc(T.DIM))
            p.drawText(QRectF(plot.left() + 2, y - 15, 60, 14), Qt.AlignLeft, f"{hi - (hi - lo) * k / 4:.0f}")
        my = Y(mean(d))
        p.setPen(QPen(qc(T.ACCENT, 0.35), 1, Qt.DashLine))
        p.drawLine(QPointF(plot.left(), my), QPointF(plot.right(), my))

        pts = [QPointF(X(i), Y(v)) for i, v in enumerate(d)]
        for i in range(1, n):                                # fading tail
            a = (i / n) ** 1.6
            p.setPen(QPen(qc(T.ACCENT2, 0.12 * a), 8, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(pts[i - 1], pts[i])
            p.setPen(QPen(qc(T.ACCENT2, 0.08 + 0.92 * a), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(pts[i - 1], pts[i])
        for i, flag in enumerate(self.anoms):
            if flag:
                a = (i / n) ** 0.8
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(qc(T.NEG, a), 1.4))
                p.drawEllipse(pts[i], 7 + 3 * math.sin(self.t / 3), 7 + 3 * math.sin(self.t / 3))
                p.setPen(Qt.NoPen)
                p.setBrush(qc(T.NEG, a))
                p.drawEllipse(pts[i], 2.5, 2.5)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(T.ACCENT2, 0.25))
        p.drawEllipse(pts[-1], 10, 10)
        p.setBrush(qc(T.TEXT))
        p.drawEllipse(pts[-1], 3.5, 3.5)


# ════════════════════════════════════════════════════════════════════════════
#  KPI CARD
# ════════════════════════════════════════════════════════════════════════════
class KPICard(Card):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.title, self.value, self.delta, self.series = "", 0.0, None, []
        self.ratio, self.selected, self.prog = False, False, 1.0
        self.setMinimumHeight(140)
        self.setCursor(Qt.PointingHandCursor)
        self._p = QVariantAnimation(self)
        self._p.setDuration(1200)
        self._p.setStartValue(0.0)
        self._p.setEndValue(1.0)
        self._p.setEasingCurve(QEasingCurve.OutCubic)
        self._p.valueChanged.connect(self._on_p)

    def _on_p(self, v):
        self.prog = float(v)
        self.update()

    def set_data(self, title, value, delta, series, selected, ratio):
        self.title, self.value, self.delta = title, value, delta
        self.series, self.selected, self.ratio = series, selected, ratio
        self._p.stop()
        self._p.start()

    def mousePressEvent(self, e):
        self.clicked.emit()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, k = self.width(), self.height(), ease(self.prog)
        if self.selected:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(qc(T.ACCENT), 3))
            p.drawRoundedRect(QRectF(2, 2, w - 11, h - 11), 6, 6)
            p.setPen(Qt.NoPen)
            p.setBrush(qc(T.ACCENT))
            p.drawRoundedRect(QRectF(24, 0, 26, 2), 1, 1)
        p.setFont(F(8, NORMAL, 2.4))
        p.setPen(qc(T.ACCENT if self.selected else T.MUTED))
        p.drawText(QRectF(24, 20, w - 48, 16), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setFont(F(25, QFont.Weight.Black))
        p.setPen(qc(T.TEXT))
        txt = f"{self.value * k:.2f}" if self.ratio else fmt(self.value * k)
        p.drawText(QRectF(24, 46, w * 0.55, 44), Qt.AlignLeft | Qt.AlignVCenter, txt)
        if self.delta is None:
            s, c = "—", T.MUTED
        else:
            up = self.delta >= 0
            s, c = f"{'▲' if up else '▼'} {abs(self.delta):.1f}%", (T.POS if up else T.NEG)
        p.setFont(F(9, NORMAL, 0.6))
        p.setPen(qc(c))
        p.drawText(QRectF(24, h - 46, 150, 18), Qt.AlignLeft | Qt.AlignVCenter, s)
        p.setFont(F(7, NORMAL, 1.8))
        p.setPen(qc(T.DIM))
        p.drawText(QRectF(24, h - 28, 170, 14), Qt.AlignLeft | Qt.AlignVCenter, "VS PRIOR PERIOD")
        if len(self.series) > 2:
            vs = self.series if len(self.series) <= 60 else downsample(range(len(self.series)), self.series, 60)[1]
            r = QRectF(w * 0.56, 50, w * 0.44 - 24, 44)
            lo, hi = min(vs), max(vs)
            span = (hi - lo) or 1
            pts = [QPointF(r.left() + i / (len(vs) - 1) * r.width(),
                           r.bottom() - (v - lo) / span * r.height()) for i, v in enumerate(vs)]
            p.save()
            p.setClipRect(QRectF(0, 0, r.left() + r.width() * k + 2, h))
            path = smooth_path(pts)
            p.setBrush(Qt.NoBrush)
            col = T.ACCENT if self.selected else T.TEXT
            p.setPen(QPen(qc(col, 0.12), 6, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(path)
            p.setPen(QPen(qc(col, 0.85), 1.5, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(path)
            p.restore()
            p.setPen(Qt.NoPen)
            p.setBrush(qc(col, k))
            p.drawEllipse(pts[-1], 2.5, 2.5)


# ════════════════════════════════════════════════════════════════════════════
#  CHROME — nav rail, title bar, toast
# ════════════════════════════════════════════════════════════════════════════
class NavRail(QWidget):
    selected = Signal(int)
    ITEMS = ["OVERVIEW", "EXPLORER", "INSIGHTS", "LIVE"]

    def __init__(self):
        super().__init__()
        self.setFixedWidth(96)
        self.setMouseTracking(True)
        self.index, self.hov, self.angle = 0, -1, 0.0
        self.iy = self._rect(0).center().y()
        self._orbit = QVariantAnimation(self)
        self._orbit.setDuration(7000)
        self._orbit.setStartValue(0.0)
        self._orbit.setEndValue(360.0)
        self._orbit.setLoopCount(-1)
        self._orbit.valueChanged.connect(self._on_orbit)
        self._orbit.start()
        self._slide = QVariantAnimation(self)
        self._slide.setDuration(450)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._slide.valueChanged.connect(self._on_slide)

    def _rect(self, i):
        return QRectF(8, 128 + i * 84, 80, 76)

    def _on_orbit(self, v):
        self.angle = float(v)
        self.update()

    def _on_slide(self, v):
        self.iy = float(v)
        self.update()

    def set_index(self, i):
        if i == self.index:
            return
        self.index = i
        self._slide.stop()
        self._slide.setStartValue(self.iy)
        self._slide.setEndValue(self._rect(i).center().y())
        self._slide.start()

    def _at(self, pos):
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
    def _icon(p, kind, cx, cy):
        p.setBrush(Qt.NoBrush)
        if kind == 0:
            for dx in (-8, 1):
                for dy in (-8, 1):
                    p.drawRoundedRect(QRectF(cx + dx, cy + dy, 7, 7), 1.5, 1.5)
        elif kind == 1:
            for dy, ln in ((-6, 18), (0, 12), (6, 15)):
                p.drawLine(QPointF(cx - 9, cy + dy), QPointF(cx - 9 + ln, cy + dy))
        elif kind == 2:
            p.drawEllipse(QPointF(cx - 4.5, cy), 7, 7)
            p.drawEllipse(QPointF(cx + 4.5, cy), 7, 7)
        else:
            pts = [(-10, 0), (-5, 0), (-2, -8), (2, 8), (5, 0), (10, 0)]
            p.drawPolyline(QPolygonF([QPointF(cx + x, cy + y) for x, y in pts]))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        p.fillRect(self.rect(), QColor('#FFFFFF'))
        p.setPen(QPen(qc(T.LINE2), 2))
        p.drawLine(w - 1, 0, w - 1, self.height())
        cx, cy = w / 2, 58                                     # brand orbit
        p.setPen(QPen(qc(T.LINE2), 1))
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
        g = QLinearGradient(8, 0, w, 0)                        # selection glow
        g.setColorAt(0, qc(T.ACCENT, 0.09))
        g.setColorAt(1, qc(T.ACCENT, 0))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(0, self.iy - 38, w - 1, 76), 8, 8)
        p.setBrush(qc(T.ACCENT))
        p.drawRoundedRect(QRectF(0, self.iy - 18, 2.5, 36), 1, 1)
        for i, name in enumerate(self.ITEMS):
            r = self._rect(i)
            on = i == self.index
            col = qc(T.ACCENT if on else (T.TEXT if i == self.hov else T.MUTED))
            p.setPen(QPen(col, 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            self._icon(p, i, r.center().x(), r.top() + 26)
            p.setFont(F(6.5, NORMAL, 1.8))
            p.drawText(QRectF(r.left(), r.top() + 46, r.width(), 14), Qt.AlignCenter, name)
        p.setFont(F(6.5, NORMAL, 2))
        p.setPen(qc(T.DIM))
        p.drawText(QRectF(0, self.height() - 38, w, 14), Qt.AlignCenter, "V 1.0")


class WinButton(QWidget):
    clicked = Signal()
    COL = {"close": "#E04E3E", "max": "#3B2A30", "min": "#F5B800"}

    def __init__(self, kind):
        super().__init__()
        self.kind, self.hov = kind, False
        self.setFixedSize(32, 34)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):
        self.hov = True
        self.update()

    def leaveEvent(self, e):
        self.hov = False
        self.update()

    def mousePressEvent(self, e):
        self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#3B2A30"), 2))
        p.setBrush(QColor(self.COL[self.kind]))
        r = 11.5 if self.hov else 10
        p.drawEllipse(QPointF(16, 17), r, r)


class TitleBar(QWidget):
    load_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(64)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(6)
        self.buttons = {}
        for kind in ("close", "max", "min"):
            b = WinButton(kind)
            self.buttons[kind] = b
            lay.addWidget(b)
        lay.addSpacing(20)
        lay.addWidget(label("DATA ANALYSIS", 13, "#FFFFFF", NORMAL, 3))
        lay.addSpacing(8)
        lay.addWidget(label("5TH GRADE", 8, "#DAF8FA", NORMAL, 3))
        lay.addStretch()
        self.chip = label("", 8, "#E8FAFB", NORMAL, 2)
        lay.addWidget(self.chip)
        lay.addSpacing(10)
        btn = GhostButton("LOAD DATA")
        btn.clicked.connect(self.load_clicked)
        lay.addWidget(btn)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        self.buttons["max"].clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#008F95"))
        p.setPen(QPen(QColor(T.LINE2), 2))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFont(F(9, NORMAL, 1))
        self.setStyleSheet(f"background:#DAF8FA;color:{T.TEXT};border:2px solid {T.LINE2};"
                           f"border-radius:8px;padding:10px 24px;")
        self.eff = QGraphicsOpacityEffect(self)
        self.eff.setOpacity(0)
        self.setGraphicsEffect(self.eff)
        self._a = QVariantAnimation(self)
        self._a.setDuration(350)
        self._a.valueChanged.connect(lambda v: self.eff.setOpacity(float(v)))
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.timeout.connect(lambda: self._fade(0.0))
        self.hide()

    def _fade(self, to):
        self._a.stop()
        self._a.setStartValue(self.eff.opacity())
        self._a.setEndValue(to)
        self._a.start()

    def show_msg(self, text):
        self.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        self.move((par.width() - self.width()) // 2, par.height() - 90)
        self.show()
        self.raise_()
        self._fade(1.0)
        self._t.start(2600)


# ════════════════════════════════════════════════════════════════════════════
#  PAGES
# ════════════════════════════════════════════════════════════════════════════
class InsightRow(QWidget):
    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(14)
        self.dot = label("●", 7, T.MUTED)
        lay.addWidget(self.dot, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        self.title = label("", 8, T.MUTED, NORMAL, 2.4)
        self.detail = label("", 10, T.TEXT, LIGHT, 0, True)
        col.addWidget(self.title)
        col.addWidget(self.detail)
        lay.addLayout(col, 1)

    def set_data(self, title, detail, tone):
        c = {"pos": T.POS, "neg": T.NEG}.get(tone, T.ACCENT)
        self.dot.setStyleSheet(f"color:{c};background:transparent;")
        self.title.setText(title.upper())
        self.detail.setText(detail)


class OverviewPage(QWidget):
    RANGES = [("7D", 7), ("30D", 30), ("90D", 90), ("1Y", 365), ("ALL", None)]

    def __init__(self):
        super().__init__()
        self.ds, self.active, self.metrics = None, 0, []
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(18)
        self.range = Segmented([r[0] for r in self.RANGES], 2)
        self.range.changed.connect(self.refresh)
        root.addWidget(page_header("OVERVIEW", "Performance at a glance",
                                   "Select a metric to focus the analysis.", self.range))
        row = QHBoxLayout()
        row.setSpacing(18)
        self.kpis = []
        for i in range(4):
            k = KPICard()
            k.clicked.connect(lambda i=i: self.pick(i))
            row.addWidget(k)
            self.kpis.append(k)
        root.addLayout(row)

        r2 = QHBoxLayout()
        r2.setSpacing(18)
        self.line = LineChart()
        self.line_card, self.line_t = panel(" ", self.line)
        self.donut = DonutChart()
        self.donut_card, self.donut_t = panel(" ", self.donut)
        r2.addWidget(self.line_card, 2)
        r2.addWidget(self.donut_card, 1)
        root.addLayout(r2)

        r3 = QHBoxLayout()
        r3.setSpacing(18)
        self.bars = BarChart()
        self.bars_card, self.bars_t = panel(" ", self.bars)
        hl = Card()
        hlay = QVBoxLayout(hl)
        hlay.setContentsMargins(24, 20, 24, 18)
        hlay.addWidget(label("HIGHLIGHTS", 8, T.MUTED, NORMAL, 2.4))
        self.hl_rows = [InsightRow() for _ in range(4)]
        for r in self.hl_rows:
            hlay.addWidget(r)
        hlay.addStretch()
        r3.addWidget(self.bars_card, 2)
        r3.addWidget(hl, 1)
        root.addLayout(r3)

    def load(self, ds):
        self.ds, self.active = ds, 0
        self.metrics = ds.numeric[:4]
        ins = generate_insights(ds)
        for r, i in zip(self.hl_rows, ins):
            r.set_data(*i)
        self.refresh()

    def pick(self, i):
        if i < len(self.metrics) and i != self.active:
            self.active = i
            self.refresh()

    def refresh(self, *_):
        ds = self.ds
        rname, n = self.RANGES[self.range.index]
        for i, k in enumerate(self.kpis):
            if i >= len(self.metrics):
                k.hide()
                continue
            k.show()
            col = self.metrics[i]
            v = ds.series(col)[1]
            win = v[-n:] if n else v
            prev = v[-2 * n:-n] if n and len(v) >= 2 * n else []
            cur = ds.agg(col, win)
            pv = ds.agg(col, prev) if prev else 0
            k.set_data(col.upper(), cur, (cur - pv) / pv * 100 if pv else None, win,
                       i == self.active, is_ratio(col))
        col = self.metrics[self.active]
        labels, vals = ds.series(col, n)
        fc = []
        if len(vals) >= 8:
            m = min(len(vals), 45)
            slope, _ = linfit(vals[-m:])
            fc = [vals[-1] + slope * (j + 1) for j in range(clamp(len(vals) // 6, 3, 40))]
        self.line.set_data(labels, vals, fc)
        self.line_t.setText(f"{col.upper()}   ·   {rname}   ·   PROJECTED TREND")
        bd = ds.breakdown(col, n)
        self.donut_card.setVisible(bool(bd))
        if bd:
            top = bd[:5]
            rest = sum(v for _, v in bd[5:])
            self.donut.set_data(top + ([("Other", rest)] if rest else []))
            self.donut_t.setText(f"{col.upper()} BY {ds.columns[ds.cat].upper()}")
        ml, mv = ds.monthly(col)
        self.bars.set_data(ml, mv)
        self.bars_t.setText(f"MONTHLY {col.upper()}")


class StatsPanel(Card):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(290)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(10)
        lay.addWidget(label("COLUMN PROFILE", 8, T.MUTED, NORMAL, 2.4))
        self.name = label("—", 18, T.TEXT)
        lay.addWidget(self.name)
        lay.addSpacing(8)
        self.rows = []
        for _ in range(7):
            r = QHBoxLayout()
            k, v = label("", 8, T.MUTED, NORMAL, 1.8), label("", 11, T.TEXT)
            v.setAlignment(Qt.AlignRight)
            r.addWidget(k)
            r.addStretch()
            r.addWidget(v)
            lay.addLayout(r)
            self.rows.append((k, v))
        lay.addSpacing(8)
        self.hist = BarChart(axis=False)
        self.hist.setMinimumHeight(110)
        lay.addWidget(self.hist, 1)

    def show_column(self, ds, col):
        vals = ds.column(col)
        self.name.setText(col)
        if col in ds.numeric:
            s, n = sorted(vals), len(vals)
            info = [("COUNT", f"{n:,}"), ("MEAN", fmt(mean(vals), 2)),
                    ("MEDIAN", fmt(statistics.median(vals), 2)), ("STD DEV", fmt(stdev(vals), 2)),
                    ("MIN", fmt(s[0], 2)), ("MAX", fmt(s[-1], 2)), ("P90", fmt(s[min(n - 1, int(n * 0.9))], 2))]
            lab, cnt, mf = histogram(vals, 18)
            self.hist.prefix = "From "
            self.hist.set_data(lab, cnt, marker=(mf, "MEAN"), hi_max=False)
        else:
            top = Counter(vals).most_common(8)
            info = [("COUNT", f"{len(vals):,}"), ("UNIQUE", f"{len(set(vals)):,}"),
                    ("TOP", str(top[0][0])[:18]), ("TOP SHARE", f"{top[0][1] / len(vals) * 100:.1f}%")]
            self.hist.prefix = ""
            self.hist.set_data([str(k) for k, _ in top], [v for _, v in top])
        for i, (k, v) in enumerate(self.rows):
            k.setText(info[i][0] if i < len(info) else "")
            v.setText(info[i][1] if i < len(info) else "")


class DataModel(QAbstractTableModel):
    def __init__(self, ds):
        super().__init__()
        self.ds = ds

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.ds.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.ds.columns)

    def data(self, idx, role=Qt.DisplayRole):
        v = self.ds.rows[idx.row()][idx.column()]
        num = self.ds.columns[idx.column()] in self.ds.numeric
        if role == Qt.DisplayRole:
            return f"{v:,.2f}".rstrip("0").rstrip(".") if num else str(v)
        if role == Qt.UserRole:
            return v
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignRight if num else Qt.AlignLeft) | Qt.AlignVCenter)
        if role == Qt.ForegroundRole and not num:
            return QBrush(qc(T.MUTED))
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.ds.columns[section].upper()
        return None


class ExplorerPage(QWidget):
    def __init__(self, toast):
        super().__init__()
        self.toast, self.ds = toast, None
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(18)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search records…")
        self.search.setFixedWidth(250)
        export = GhostButton("EXPORT CSV")
        export.clicked.connect(self.export_csv)
        right = QWidget()
        rl = QHBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(18)
        rl.addWidget(self.search)
        rl.addWidget(export)
        root.addWidget(page_header("EXPLORER", "Data explorer",
                                   "Search, sort and inspect every record. Click a cell to profile its column.", right))
        body = QHBoxLayout()
        body.setSpacing(18)
        self.table = QTableView()
        self.table.setMinimumHeight(460)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setFont(F(7, NORMAL, 1.0))
        self.table.setFont(F(10))
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.StrongFocus)
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 10, 10, 10)
        cl.addWidget(self.table)
        self.stats = StatsPanel()
        body.addWidget(card, 1)
        body.addWidget(self.stats)
        root.addLayout(body, 1)
        self.proxy = QSortFilterProxyModel()
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setSortRole(Qt.UserRole)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)

    def load(self, ds):
        self.ds = ds
        self.proxy.setSourceModel(DataModel(ds))
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.selectionModel().currentColumnChanged.connect(self._col)
        first = ds.columns.index(ds.numeric[0])
        self.table.setCurrentIndex(self.proxy.index(0, first))
        self.stats.show_column(ds, ds.numeric[0])

    def _col(self, cur, _prev):
        if cur.isValid() and self.ds:
            self.stats.show_column(self.ds, self.ds.columns[cur.column()])

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export", "aura_export.csv", "CSV (*.csv)")
        if not path:
            return
        pm = self.proxy
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self.ds.columns)
            for r in range(pm.rowCount()):
                w.writerow([pm.index(r, c).data(Qt.UserRole) for c in range(pm.columnCount())])
        self.toast(f"Exported {pm.rowCount():,} rows")


class InsightsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.ds = None
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(18)
        root.addWidget(page_header("INSIGHTS", "Hidden structure",
                                   "Correlations, outliers and distributions — surfaced automatically."))
        top = QHBoxLayout()
        top.setSpacing(18)
        self.heat = Heatmap()
        hc, _ = panel("CORRELATION MATRIX", self.heat)
        sig = Card()
        sl = QVBoxLayout(sig)
        sl.setContentsMargins(24, 20, 24, 18)
        sl.addWidget(label("SIGNALS", 8, T.MUTED, NORMAL, 2.4))
        self.rows = [InsightRow() for _ in range(6)]
        for r in self.rows:
            sl.addWidget(r)
        sl.addStretch()
        top.addWidget(hc, 3)
        top.addWidget(sig, 2)
        root.addLayout(top)
        self.seg = Segmented(["—"])
        self.seg.changed.connect(self.dist)
        self.hist = BarChart()
        self.hist.setMinimumHeight(220)
        self.hist.prefix = "From "
        hcard, self.hist_t = panel("DISTRIBUTION", self.hist)
        hcard.layout().insertWidget(0, self.seg, 0, Qt.AlignLeft)
        root.addWidget(hcard)

    def load(self, ds):
        self.ds = ds
        names = ds.numeric[:8]
        cols = [ds.column(c) for c in names]
        self.heat.set_data(names, [[pearson(a, b) for b in cols] for a in cols])
        for r, i in zip(self.rows, generate_insights(ds)):
            r.set_data(*i)
        for r in self.rows[len(generate_insights(ds)):]:
            r.set_data("", "", "neutral")
        self.seg.set_options([c.upper() for c in names], 0)
        self.dist(0)

    def dist(self, i):
        col = self.ds.numeric[i]
        lab, cnt, mf = histogram(self.ds.column(col), 28)
        self.hist.set_data(lab, cnt, marker=(mf, "MEAN"), hi_max=False)
        self.hist_t.setText(f"DISTRIBUTION  ·  {col.upper()}")


class LivePage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(18)
        right = QWidget()
        rl = QHBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        self.speed = Segmented(["SLOW", "NORMAL", "FAST"], 1)
        self.speed.changed.connect(lambda i: self.chart.timer.setInterval((160, 90, 45)[i]))
        self.pause = GhostButton("PAUSE")
        self.pause.clicked.connect(self.toggle)
        rl.addWidget(self.speed)
        rl.addWidget(self.pause)
        root.addWidget(page_header("LIVE", "Real-time stream",
                                   "Rolling z-score detection flags anomalies as they happen.", right))
        self.chart = LiveChart()
        card, _ = panel(None, self.chart, 6)
        root.addWidget(card, 1)

    def toggle(self):
        self.chart.paused = not self.chart.paused
        self.pause.setText("RESUME" if self.chart.paused else "PAUSE")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ════════════════════════════════════════════════════════════════════════════
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Analysis and Statistics — 5th Grade")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setMinimumSize(1100, 720)
        self.resize(1380, 880)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.rail = NavRail()
        outer.addWidget(self.rail)
        right = QVBoxLayout()
        right.setSpacing(0)
        self.bar = TitleBar()
        right.addWidget(self.bar)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        outer.addLayout(right, 1)

        self.toast = Toast(self)
        self.pages = [OverviewPage(), ExplorerPage(lambda m: self.toast.show_msg(m)),
                      InsightsPage(), LivePage()]
        for pg in self.pages:
            self.stack.addWidget(scrollable(pg))

        self.rail.selected.connect(self.go)
        self.bar.load_clicked.connect(self.load_file)
        self.bar.buttons["min"].clicked.connect(self.showMinimized)
        self.bar.buttons["close"].clicked.connect(self.close)
        self.bar.buttons["max"].clicked.connect(
            lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        for i in range(4):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self).activated.connect(lambda i=i: self.go(i))
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.load_file)
        QShortcut(QKeySequence("F11"), self).activated.connect(
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())

        self._fade = QVariantAnimation(self)
        self._fade.setDuration(450)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.valueChanged.connect(self._fade_tick)
        self._fade.finished.connect(self._fade_done)
        self._fw = self._fe = None
        self.grip = QSizeGrip(self)
        self.set_dataset(Dataset.synthetic())

    # ---- data --------------------------------------------------------------
    def set_dataset(self, ds):
        self.ds = ds
        self.bar.chip.setText(f"{ds.name.upper()}   ·   {len(ds.rows):,} ROWS   ·   {len(ds.columns)} COLUMNS")
        for pg in self.pages[:3]:
            pg.load(ds)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load dataset", "",
                                              "Data files (*.csv *.tsv *.txt);;All files (*)")
        if not path:
            return
        try:
            ds = Dataset.from_csv(path)
        except Exception as ex:
            self.toast.show_msg(f"Could not load file — {ex}")
            return
        self.set_dataset(ds)
        self.toast.show_msg(f"Loaded {ds.name} · {len(ds.rows):,} rows")

    # ---- navigation --------------------------------------------------------
    def _fade_tick(self, v):
        if self._fe is not None:
            self._fe.setOpacity(float(v))

    def _fade_done(self):
        if self._fw is not None:
            self._fw.setGraphicsEffect(None)
        self._fw = self._fe = None

    def go(self, i):
        if i == self.stack.currentIndex():
            return
        self._fade.stop()
        self._fade_done()
        self.rail.set_index(i)
        w = self.stack.widget(i)
        self._fe = QGraphicsOpacityEffect(w)
        self._fe.setOpacity(0.0)
        w.setGraphicsEffect(self._fe)
        self._fw = w
        self.stack.setCurrentIndex(i)
        self._fade.start()
        for c in w.findChildren(ChartBase):
            if not isinstance(c, LiveChart):
                c.replay()

    # ---- window ------------------------------------------------------------
    def resizeEvent(self, e):
        self.grip.move(self.width() - 18, self.height() - 18)
        self.grip.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(T.BG))
        p.setPen(QPen(QColor("#F3CFCF"), 2))
        for x in range(0, w, 64):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 64):
            p.drawLine(0, y, w, y)
        p.setPen(QPen(QColor(T.LINE2), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(F(10))
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()