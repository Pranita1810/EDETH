"""EDETH Welcome Page Component
==============================
First interactive component of EDETH data analytics platform.
Presents the platform overview, interactive animated data upload & analysis simulation,
multimedia playback capabilities, architecture pillars, and quick-start actions.
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer,
                            QUrl, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import (QFileDialog, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizePolicy, QStackedLayout, QVBoxLayout, QWidget)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False

from frontend.theme import (DISPLAY, F, LIGHT, NORMAL, QSS, T, Card, GhostButton,
                            PrimaryButton, RetroButton, badge, clamp, ease, label,
                            lerp, mix, page_header, panel, qc, scrollable)


# ════════════════════════════════════════════════════════════════════════════
#  DYNAMIC INTERACTIVE PIPELINE SIMULATION CANVAS
# ════════════════════════════════════════════════════════════════════════════
class PipelineSimulationCanvas(QWidget):
    """Rich animated vector canvas simulating data uploading, profiling,

    statistical chart generation, and autonomous decision scoring at 60 FPS.
    """
    stage_changed = Signal(int)

    STAGES = [
        ("UPLOAD & INGEST", "#00909A", "Streaming CSV rows and schema detection..."),
        ("CLEAN & PROFILE", "#EE9B00", "Removing outliers, imputing missing values..."),
        ("ANALYZE & MODEL", "#F5B800", "Fitting splines, computing correlation matrix..."),
        ("DECIDE & ACT", "#2E9E6B", "Synthesizing executive signals and action items..."),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self.current_stage = 0
        self.stage_progress = 0.0
        self.time_tick = 0
        self.paused = False
        self.speed = 1.0

        # Simulated data packets for ingestion animation
        self.packets = [
            {"x": -0.1 * i, "y": random.uniform(0.3, 0.7), "col": random.choice(T.PALETTE),
             "speed": random.uniform(0.007, 0.012)}
            for i in range(16)
        ]

        # Simulated chart points
        self.chart_points = [
            math.sin(i * 0.45) * 0.35 + 0.5 + random.uniform(-0.06, 0.06)
            for i in range(24)
        ]

        # 60 FPS update timer
        self.timer = QTimer(self)
        self.timer.setInterval(16)  # ~60 fps
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_stage(self, stage: int):
        self.current_stage = stage % len(self.STAGES)
        self.stage_progress = 0.0
        self.stage_changed.emit(self.current_stage)
        self.update()

    def next_stage(self):
        self.set_stage(self.current_stage + 1)

    def toggle_pause(self):
        self.paused = not self.paused
        self.update()

    def set_speed(self, multiplier: float):
        self.speed = multiplier

    def _tick(self):
        if self.paused:
            return

        self.time_tick += 1
        delta = 0.0035 * self.speed
        self.stage_progress += delta

        # Advance stages automatically in a continuous loop
        if self.stage_progress >= 1.0:
            self.stage_progress = 0.0
            self.current_stage = (self.current_stage + 1) % len(self.STAGES)
            self.stage_changed.emit(self.current_stage)

        # Update animated packets
        for p in self.packets:
            p["x"] += p["speed"] * self.speed
            if p["x"] > 1.15:
                p["x"] = -0.1
                p["y"] = random.uniform(0.28, 0.72)

        # Dynamic subtle sine wave for chart simulation
        if self.time_tick % 4 == 0:
            head = self.chart_points[-1]
            t = self.time_tick * 0.05
            next_val = clamp(0.5 + 0.32 * math.sin(t) + 0.12 * math.cos(t * 1.8) + random.uniform(-0.04, 0.04), 0.1, 0.9)
            self.chart_points.pop(0)
            self.chart_points.append(next_val)

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = float(self.width()), float(self.height())
        rect = QRectF(0, 0, w, h)

        # Base canvas fill (retro graph paper background)
        p.fillRect(rect, qc("#FFFFFF"))

        # Grid lines inside canvas
        p.setPen(QPen(qc(T.LINE, 0.7), 1, Qt.DashLine))
        gx = 0
        while gx < w:
            p.drawLine(QPointF(gx, 0), QPointF(gx, h))
            gx += 40
        gy = 0
        while gy < h:
            p.drawLine(QPointF(0, gy), QPointF(w, gy))
            gy += 40

        # Draw stage workflow breadcrumbs on top
        self._draw_stage_breadcrumbs(p, w, h)

        # Draw main animated stage visualization
        mid_y = h * 0.52
        if self.current_stage == 0:
            self._draw_ingestion_stage(p, w, h, mid_y)
        elif self.current_stage == 1:
            self._draw_profiling_stage(p, w, h, mid_y)
        elif self.current_stage == 2:
            self._draw_analytics_stage(p, w, h, mid_y)
        else:
            self._draw_decision_stage(p, w, h, mid_y)

        # Draw bottom status ticker
        self._draw_status_bar(p, w, h)

        # Canvas outline
        p.setPen(QPen(qc(T.LINE2), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 6, 6)

    def _draw_stage_breadcrumbs(self, p: QPainter, w: float, h: float):
        """Top stage milestone dots and connections."""
        num_stages = len(self.STAGES)
        margin_x = 50.0
        step_x = (w - 2 * margin_x) / (num_stages - 1) if num_stages > 1 else 0
        y = 38.0

        # Connecting track line
        p.setPen(QPen(qc(T.LINE2), 3))
        p.drawLine(QPointF(margin_x, y), QPointF(w - margin_x, y))

        # Active progress track fill
        active_track_end = margin_x + self.current_stage * step_x + self.stage_progress * step_x
        active_track_end = min(active_track_end, w - margin_x)
        p.setPen(QPen(qc(T.ACCENT), 4))
        p.drawLine(QPointF(margin_x, y), QPointF(active_track_end, y))

        for i, (name, color, _) in enumerate(self.STAGES):
            cx = margin_x + i * step_x
            is_active = i == self.current_stage
            is_done = i < self.current_stage

            # Node circle
            p.setPen(QPen(qc(T.LINE2), 2))
            if is_active:
                # Pulsing halo
                pulse = 14 + 4 * math.sin(self.time_tick * 0.12)
                p.setBrush(qc(color, 0.28))
                p.drawEllipse(QPointF(cx, y), pulse, pulse)
                p.setBrush(qc(color))
                p.drawEllipse(QPointF(cx, y), 10, 10)
                p.setBrush(qc("#FFFFFF"))
                p.drawEllipse(QPointF(cx, y), 4, 4)
            elif is_done:
                p.setBrush(qc(color))
                p.drawEllipse(QPointF(cx, y), 8, 8)
            else:
                p.setBrush(qc(T.SURFACE2))
                p.drawEllipse(QPointF(cx, y), 7, 7)

            # Node label
            p.setFont(F(7.5, NORMAL if is_active else LIGHT, 1.2))
            p.setPen(qc(T.TEXT if is_active else T.MUTED))
            text_rect = QRectF(cx - 65, y + 14, 130, 20)
            p.drawText(text_rect, Qt.AlignCenter, f"{i+1}. {name}")

    def _draw_ingestion_stage(self, p: QPainter, w: float, h: float, mid_y: float):
        """Simulates file uploading and streaming data packets."""
        # Source box (e.g. CSV / Database / Stream)
        box_w, box_h = 130.0, 110.0
        src_rect = QRectF(50, mid_y - box_h / 2, box_w, box_h)
        self._draw_retro_box(p, src_rect, T.BADGE_PINK, "INPUT DATA", [
            ("sales_q3.csv", T.TEXT),
            ("124,500 records", T.MUTED),
            ("24 features", T.MUTED),
            ("✓ Ingesting...", T.ACCENT),
        ])

        # Destination engine box
        dst_rect = QRectF(w - 180, mid_y - box_h / 2, box_w, box_h)
        self._draw_retro_box(p, dst_rect, T.ACCENT_LIGHT, "EDETH CORE", [
            ("Schema Inference", T.TEXT),
            ("Type Validation", T.MUTED),
            ("Buffer: ACTIVE", T.POS),
            ("Latency: 1.2ms", T.MUTED),
        ])

        # Pipeline conveyor path
        p.setPen(QPen(qc(T.LINE2), 3, Qt.DashLine))
        start_pt = QPointF(src_rect.right(), mid_y)
        end_pt = QPointF(dst_rect.left(), mid_y)
        p.drawLine(start_pt, end_pt)

        # Flowing packets along conveyor
        span = end_pt.x() - start_pt.x()
        for pkt in self.packets:
            if 0.0 <= pkt["x"] <= 1.0:
                px = start_pt.x() + pkt["x"] * span
                py = mid_y + math.sin(pkt["x"] * math.pi * 3 + self.time_tick * 0.05) * 22
                
                # Packet capsule
                p.setPen(QPen(qc(T.LINE2), 1.5))
                p.setBrush(qc(pkt["col"]))
                p.drawRoundedRect(QRectF(px - 14, py - 9, 28, 18), 4, 4)
                
                # Packet inner detail lines
                p.setPen(qc("#FFFFFF"))
                p.drawLine(QPointF(px - 8, py - 2), QPointF(px + 8, py - 2))
                p.drawLine(QPointF(px - 8, py + 3), QPointF(px + 4, py + 3))

    def _draw_profiling_stage(self, p: QPainter, w: float, h: float, mid_y: float):
        """Simulates real-time profiling, missing-value imputation, outlier detection."""
        # 3 column cards undergoing profiling
        col_w = min(170.0, (w - 120) / 3)
        col_h = 130.0
        margin_x = (w - (3 * col_w + 2 * 20)) / 2

        profiles = [
            ("TIMESTAMP", "DateTime64[ns]", "No missing (100%)", "Monotonic: TRUE", T.POS, T.ACCENT_LIGHT),
            ("REVENUE ($)", "Float64", "4 Outliers (|z|>3)", "Normalized & Scaled", T.NEG, T.BADGE_PINK),
            ("REGION", "Categorical (5)", "Missing imputed (1.2%)", "Cardinality: 5", T.POS, "#FFF3D6"),
        ]

        for i, (col_name, dtype, check, fix, status_col, bg_col) in enumerate(profiles):
            cx = margin_x + i * (col_w + 20)
            r = QRectF(cx, mid_y - col_h / 2, col_w, col_h)
            
            # Retro box
            self._draw_retro_box(p, r, bg_col, col_name, [
                (f"Type: {dtype}", T.TEXT),
                (f"Scan: {check}", status_col),
                (f"Action: {fix}", T.MUTED),
            ])

            # Animated scanner bar scanning through columns
            scan_y = r.top() + 32 + ((self.time_tick * 2 + i * 25) % int(col_h - 40))
            p.setPen(QPen(qc(T.ACCENT, 0.7), 2))
            p.drawLine(QPointF(r.left() + 6, scan_y), QPointF(r.right() - 6, scan_y))

    def _draw_analytics_stage(self, p: QPainter, w: float, h: float, mid_y: float):
        """Simulates dynamic live trend charting, correlation links, and statistics."""
        chart_w = min(480.0, w - 80)
        chart_h = 130.0
        rect = QRectF((w - chart_w) / 2, mid_y - chart_h / 2, chart_w, chart_h)

        # Background card for chart
        self._draw_retro_box(p, rect, "#FFFFFF", "STATISTICAL MODELLING ENGINE (CATMULL-ROM & PEARSON)", [])

        # Plot boundaries
        pad_x, pad_y = 20.0, 32.0
        plot_rect = QRectF(rect.left() + pad_x, rect.top() + pad_y, rect.width() - 2 * pad_x, rect.height() - pad_y - 12)

        # Grid lines inside plot
        p.setPen(QPen(qc(T.LINE, 0.8), 1))
        for gy in range(4):
            y = plot_rect.top() + gy * (plot_rect.height() / 3)
            p.drawLine(QPointF(plot_rect.left(), y), QPointF(plot_rect.right(), y))

        # Build smooth Catmull-Rom path
        pts = []
        n = len(self.chart_points)
        for i, val in enumerate(self.chart_points):
            x = plot_rect.left() + i * (plot_rect.width() / (n - 1))
            y = plot_rect.bottom() - val * plot_rect.height()
            pts.append(QPointF(x, y))

        if len(pts) > 1:
            # Gradient fill under curve
            path = QPainterPath()
            path.moveTo(pts[0])
            for i in range(len(pts) - 1):
                p0 = pts[max(i - 1, 0)]
                p1 = pts[i]
                p2 = pts[i + 1]
                p3 = pts[min(i + 2, len(pts) - 1)]
                c1 = QPointF(p1.x() + (p2.x() - p0.x()) / 6, p1.y() + (p2.y() - p0.y()) / 6)
                c2 = QPointF(p2.x() - (p3.x() - p1.x()) / 6, p2.y() - (p3.y() - p1.y()) / 6)
                path.cubicTo(c1, c2, p2)

            fill_path = QPainterPath(path)
            fill_path.lineTo(pts[-1].x(), plot_rect.bottom())
            fill_path.lineTo(pts[0].x(), plot_rect.bottom())
            fill_path.closeSubpath()

            grad = QLinearGradient(0, plot_rect.top(), 0, plot_rect.bottom())
            grad.setColorAt(0.0, qc(T.ACCENT, 0.35))
            grad.setColorAt(1.0, qc(T.ACCENT, 0.02))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawPath(fill_path)

            # Curve line
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(qc(T.ACCENT), 2.5))
            p.drawPath(path)

            # Glowing tip point
            tip = pts[-1]
            p.setBrush(qc(T.ACCENT, 0.4))
            p.drawEllipse(tip, 8, 8)
            p.setBrush(qc(T.YELLOW))
            p.setPen(QPen(qc(T.LINE2), 1.5))
            p.drawEllipse(tip, 4, 4)

    def _draw_decision_stage(self, p: QPainter, w: float, h: float, mid_y: float):
        """Simulates automated decision triggers and executive intelligence cards."""
        card_w = min(220.0, (w - 80) / 2)
        card_h = 130.0
        start_x = (w - (2 * card_w + 20)) / 2

        # Decision 1
        self._draw_retro_box(
            p, QRectF(start_x, mid_y - card_h / 2, card_w, card_h),
            "#E6F7EC", "INSIGHT: MOMENTUM",
            [
                ("Trend: +24.8% Growth", T.POS),
                ("Confidence: 99.2%", T.TEXT),
                ("Action: Scale Batch 4", T.ACCENT),
                ("Priority: CRITICAL", T.TEXT),
            ]
        )

        # Decision 2
        self._draw_retro_box(
            p, QRectF(start_x + card_w + 20, mid_y - card_h / 2, card_w, card_h),
            T.BADGE_PINK, "SIGNAL: VOLATILITY SHIELD",
            [
                ("Anomaly in Segment B", T.NEG),
                ("Root Cause: Region 3", T.TEXT),
                ("Auto Remediation: ENGAGED", T.POS),
                ("Downstream Trigger: SENT", T.MUTED),
            ]
        )

    def _draw_retro_box(self, p: QPainter, r: QRectF, bg: str, title: str, items: list[tuple[str, str]]):
        """Draws standard neo-brutalist card inside simulation."""
        # Hard drop shadow
        p.setPen(QPen(qc(T.LINE2), 2))
        p.setBrush(qc(T.PINK_SHADOW))
        p.drawRoundedRect(r.translated(4, 4), 5, 5)

        # Card surface
        p.setBrush(qc(bg))
        p.drawRoundedRect(r, 5, 5)

        # Header title
        p.setFont(F(7.5, NORMAL, 1.2))
        p.setPen(qc(T.TEXT))
        p.drawText(QRectF(r.left() + 10, r.top() + 8, r.width() - 20, 18), Qt.AlignLeft, title)

        p.setPen(QPen(qc(T.LINE2), 1))
        p.drawLine(QPointF(r.left() + 10, r.top() + 26), QPointF(r.right() - 10, r.top() + 26))

        # Rows
        curr_y = r.top() + 32
        p.setFont(F(7, LIGHT, 0.5))
        for text, col in items:
            p.setPen(qc(col))
            p.drawText(QRectF(r.left() + 10, curr_y, r.width() - 20, 16), Qt.AlignLeft, text)
            curr_y += 18

    def _draw_status_bar(self, p: QPainter, w: float, h: float):
        """Bottom ticker of active stage description."""
        bar_rect = QRectF(10, h - 36, w - 20, 26)
        p.setPen(QPen(qc(T.LINE2), 1.5))
        p.setBrush(qc(T.SURFACE2))
        p.drawRoundedRect(bar_rect, 4, 4)

        name, color, desc = self.STAGES[self.current_stage]

        # Stage badge
        p.setFont(F(7, NORMAL, 1.0))
        p.setPen(qc(color))
        p.drawText(QRectF(bar_rect.left() + 12, bar_rect.top() + 4, 140, 18), Qt.AlignLeft, f"STAGE {self.current_stage + 1}: {name}")

        # Description
        p.setFont(F(7.5, LIGHT, 0.5))
        p.setPen(qc(T.TEXT))
        p.drawText(QRectF(bar_rect.left() + 160, bar_rect.top() + 4, bar_rect.width() - 180, 18), Qt.AlignLeft, desc)


# ════════════════════════════════════════════════════════════════════════════
#  WORKFLOW SHOWCASE CONTAINER (SIMULATION + VIDEO SUPPORT)
# ════════════════════════════════════════════════════════════════════════════
class WorkflowShowcaseWidget(Card):
    """Container widget supporting both the interactive vector simulation

    and native video playback (when a demonstration video is provided/loaded).
    """

    def __init__(self, parent=None):
        super().__init__(shadow_color=T.PINK_SHADOW, bg_color="#FFFFFF")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Top Bar: Title & Controls
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        icon_lbl = badge("EDETH PIPELINE ENGINE", bg=T.ACCENT_LIGHT, fg=T.TEXT)
        top_bar.addWidget(icon_lbl)

        self.status_lbl = label("LIVE INTERACTIVE SIMULATION", 8, T.MUTED, NORMAL, 1.5)
        top_bar.addWidget(self.status_lbl)

        top_bar.addStretch()

        # Step jump buttons
        self.btn_s1 = GhostButton("1. UPLOAD")
        self.btn_s2 = GhostButton("2. CLEAN")
        self.btn_s3 = GhostButton("3. ANALYZE")
        self.btn_s4 = GhostButton("4. DECIDE")
        for b, idx in ((self.btn_s1, 0), (self.btn_s2, 1), (self.btn_s3, 2), (self.btn_s4, 3)):
            b.setFixedHeight(28)
            b.setFont(F(7, NORMAL, 1.0))
            b.clicked.connect(lambda checked=False, i=idx: self.canvas.set_stage(i))
            top_bar.addWidget(b)

        # Pause / Play button
        self.btn_pause = GhostButton("⏸ PAUSE")
        self.btn_pause.setFixedHeight(28)
        self.btn_pause.setFont(F(7, NORMAL, 1.0))
        self.btn_pause.clicked.connect(self._toggle_pause)
        top_bar.addWidget(self.btn_pause)

        # Video / Sim Toggle button
        self.btn_video_toggle = GhostButton("🎬 LOAD VIDEO")
        self.btn_video_toggle.setFixedHeight(28)
        self.btn_video_toggle.setFont(F(7, NORMAL, 1.0))
        self.btn_video_toggle.clicked.connect(self._load_video_file)
        top_bar.addWidget(self.btn_video_toggle)

        layout.addLayout(top_bar)

        # Main Display Area: Stacked Layout with Simulation Canvas and Video Widget
        self.display_stack = QStackedLayout()
        
        # 1. Canvas
        self.canvas = PipelineSimulationCanvas(self)
        self.canvas.stage_changed.connect(self._on_stage_changed)
        self.display_stack.addWidget(self.canvas)

        # 2. Video Widget (if QtMultimedia available)
        self.player = None
        self.video_widget = None
        if MULTIMEDIA_AVAILABLE:
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_output)
            self.video_widget = QVideoWidget()
            self.video_widget.setStyleSheet(f"border: 2px solid {T.LINE2}; border-radius: 6px; background:#000000;")
            self.player.setVideoOutput(self.video_widget)
            self.display_stack.addWidget(self.video_widget)

        layout.addLayout(self.display_stack)

    def _toggle_pause(self):
        self.canvas.toggle_pause()
        self.btn_pause.setText("▶ RESUME" if self.canvas.paused else "⏸ PAUSE")

    def _on_stage_changed(self, stage: int):
        buttons = [self.btn_s1, self.btn_s2, self.btn_s3, self.btn_s4]
        for i, b in enumerate(buttons):
            if i == stage:
                b.setStyleSheet(
                    f"QPushButton {{ color:#FFFFFF; background:{T.ACCENT}; border:2px solid {T.LINE2};"
                    f"border-radius:6px; padding:0 12px; font-weight:bold; }}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton {{ color:{T.TEXT}; background:#FFFFFF; border:2px solid {T.LINE2};"
                    f"border-radius:6px; padding:0 12px; }}"
                    f"QPushButton:hover {{ background:{T.YELLOW}; }}"
                )

    def _load_video_file(self):
        if not MULTIMEDIA_AVAILABLE:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Demo / Architecture Video", "",
            "Video files (*.mp4 *.webm *.avi *.mkv);;All files (*)"
        )
        if path:
            self.player.setSource(QUrl.fromLocalFile(path))
            self.display_stack.setCurrentWidget(self.video_widget)
            self.player.play()
            self.status_lbl.setText(f"PLAYING: {os.path.basename(path).upper()}")
            self.btn_video_toggle.setText("📊 BACK TO SIM")
            self.btn_video_toggle.clicked.disconnect()
            self.btn_video_toggle.clicked.connect(self._show_simulation)

    def _show_simulation(self):
        if self.player:
            self.player.pause()
        self.display_stack.setCurrentWidget(self.canvas)
        self.status_lbl.setText("LIVE INTERACTIVE SIMULATION")
        self.btn_video_toggle.setText("🎬 LOAD VIDEO")
        self.btn_video_toggle.clicked.disconnect()
        self.btn_video_toggle.clicked.connect(self._load_video_file)


# ════════════════════════════════════════════════════════════════════════════
#  CAPABILITY / ARCHITECTURE PILLAR CARD
# ════════════════════════════════════════════════════════════════════════════
class PillarCard(Card):
    def __init__(self, step_num: str, title: str, subtitle: str,
                 points: list[str], accent_color: str = T.ACCENT,
                 shadow_color: str = T.PINK_SHADOW):
        super().__init__(shadow_color=shadow_color, bg_color="#FFFFFF")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        # Header tag
        top = QHBoxLayout()
        b = badge(f"PHASE {step_num}", bg=accent_color if accent_color.startswith("#") else T.ACCENT_LIGHT)
        top.addWidget(b, 0, Qt.AlignLeft)
        top.addStretch()
        lay.addLayout(top)

        # Title
        t = label(title, 13, T.TEXT, QFont.Weight.Black, 0.4)
        lay.addWidget(t)

        # Subtitle
        sub = label(subtitle, 9, T.MUTED, LIGHT, 0, True)
        lay.addWidget(sub)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color:{T.LINE}; background:{T.LINE}; max-height:1px;")
        lay.addWidget(div)

        # Bullet list
        for pt in points:
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = label("✦", 8, T.ACCENT)
            txt = label(pt, 8.5, T.TEXT, LIGHT, 0, True)
            row.addWidget(dot, 0, Qt.AlignTop)
            row.addWidget(txt, 1)
            lay.addLayout(row)

        lay.addStretch()


# ════════════════════════════════════════════════════════════════════════════
#  WELCOME PAGE COMPONENT
# ════════════════════════════════════════════════════════════════════════════
class WelcomePage(QWidget):
    """The Welcome Page of EDETH.

    Introduces the platform purpose, showcases the animated data ingestion
    & analysis pipeline, details system pillars, and provides quick launch CTAs.
    """
    start_clicked = Signal()
    load_dataset_clicked = Signal()
    explore_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(24)

        # 1. Hero Header Section
        hero = self._build_hero_section()
        root.addWidget(hero)

        # 2. Interactive Video / Animation Showcase
        self.showcase = WorkflowShowcaseWidget(self)
        root.addWidget(self.showcase)

        # 3. Core Architecture Pillars (The 4 Steps of EDETH)
        pillars_header = page_header(
            "CORE WORKFLOW", "Autonomous Pipeline Architecture",
            "From raw unstructured files to validated executive decisions in seconds."
        )
        root.addWidget(pillars_header)

        pillars_layout = QHBoxLayout()
        pillars_layout.setSpacing(18)

        p1 = PillarCard(
            "01", "Data Ingestion",
            "Universal ingestion engine with automatic format resolution.",
            [
                "Drag & drop CSV, TSV, Parquet, and Excel",
                "Automatic date-time format resolution",
                "Schema sniffer with delimiter detection",
            ],
            accent_color=T.ACCENT_LIGHT, shadow_color=T.PINK_SHADOW
        )

        p2 = PillarCard(
            "02", "Automated Profiling",
            "Intelligent data sanitization and anomaly screening.",
            [
                "Statistical z-score outlier detection",
                "Categorical vs numerical auto-typing",
                "Zero-configuration missing-value repair",
            ],
            accent_color="#FFF3D6", shadow_color="#FCE198"
        )

        p3 = PillarCard(
            "03", "Statistical Engine",
            "Deep mathematical discovery and trend modeling.",
            [
                "Real-time Pearson correlation matrix",
                "Catmull-Rom spline curve extrapolation",
                "Distribution histograms with central tendency",
            ],
            accent_color=T.BADGE_PINK, shadow_color=T.PINK_SHADOW
        )

        p4 = PillarCard(
            "04", "Decision Intelligence",
            "Direct translation of analytics into actionable business decisions.",
            [
                "Natural language executive signal alerts",
                "KPI momentum and volatility ranking",
                "Automated downstream dispatch triggers",
            ],
            accent_color="#DAF8FA", shadow_color="#A4EBF0"
        )

        pillars_layout.addWidget(p1)
        pillars_layout.addWidget(p2)
        pillars_layout.addWidget(p3)
        pillars_layout.addWidget(p4)
        root.addLayout(pillars_layout)
        root.addSpacing(12)

    def _build_hero_section(self) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Top Tag
        tag = badge("✦ NEXT-GEN AUTONOMOUS ANALYTICS PLATFORM ✦", bg=T.BADGE_PINK, size=8.5)
        lay.addWidget(tag, 0, Qt.AlignLeft)

        # Main Title
        title = label("EDETH", 34, T.TEXT, QFont.Weight.Black, 1.0)
        lay.addWidget(title)

        # Pitch Subtitle
        pitch = (
            "An end-to-end autonomous data analytics platform designed to automate every step "
            "of the analytical workflow: from ingestion and automated cleaning to deep statistical reasoning "
            "and continuous executive decision-making."
        )
        pitch_lbl = label(pitch, 11, T.TEXT, LIGHT, 0.2, wrap=True)
        pitch_lbl.setStyleSheet(
            f"color:{T.TEXT}; background:{T.ACCENT_LIGHT}; border:2px solid {T.LINE2};"
            f"border-radius:6px; padding:10px 16px; line-height:140%;"
        )
        lay.addWidget(pitch_lbl)

        # Quick Highlights Bar
        hl = QHBoxLayout()
        hl.setSpacing(12)
        hl.addWidget(badge("⚡ 100% AUTOMATED WORKFLOWS", bg="#FFFFFF"))
        hl.addWidget(badge("📊 REAL-TIME MULTIVARIATE MODELLING", bg="#FFFFFF"))
        hl.addWidget(badge("🎯 AUTONOMOUS DECISION SCORING", bg="#FFFFFF"))
        hl.addWidget(badge("🛡️ STATISTICAL ANOMALY SHIELD", bg="#FFFFFF"))
        hl.addStretch()
        lay.addLayout(hl)

        return box


# Standalone runner for previewing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    window = QWidget()
    window.setWindowTitle("EDETH — Welcome Page Preview")
    window.resize(1340, 920)
    window.setStyleSheet(f"background-color: {T.BG};")

    lay = QVBoxLayout(window)
    lay.setContentsMargins(0, 0, 0, 0)

    welcome = WelcomePage()
    lay.addWidget(scrollable(welcome))

    window.show()
    sys.exit(app.exec())
