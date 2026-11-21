
import sys
import math
import random
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QRadialGradient,
    QLinearGradient, QFont
)


# ---------------- PARTICLE BACKGROUND ----------------

class ParticleBackground(QWidget):

    def __init__(self):
        super().__init__()

        self.particles = [
            [
                random.randint(0, 1400),
                random.randint(0, 900),
                random.uniform(0.5, 2.5),
                random.uniform(0.3, 1.5)
            ]
            for _ in range(100)
        ]

        self.angle = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

    def animate(self):
        self.angle += 0.02

        for p in self.particles:
            p[1] -= p[3]
            p[0] += math.sin(self.angle + p[1] / 80) * 0.7

            if p[1] < 0:
                p[1] = self.height()
                p[0] = random.randint(0, max(1, self.width()))

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor("#080B18"))

        for x, y, size, speed in self.particles:
            glow = QColor("#7061FF")
            glow.setAlpha(random.randint(100, 220))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(
                QPointF(x, y), size, size
            )


# ---------------- ANIMATED ORB ----------------

class EnergyOrb(QWidget):

    def __init__(self):
        super().__init__()

        self.angle = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

    def animate(self):
        self.angle += 1.2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        radius = min(self.width(), self.height()) * 0.25

        # Orbital rings
        for i in range(4):
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(self.angle + i * 45)

            pen = QPen(
                QColor("#715BFF"),
                2 - i * 0.2
            )
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawEllipse(
                QPointF(0, 0),
                radius + 30 + i * 15,
                radius * 0.35 + i * 8
            )

            painter.restore()

        # Outer glow
        gradient = QRadialGradient(
            cx, cy, radius * 1.5
        )
        gradient.setColorAt(0, QColor("#236CFF"))
        gradient.setColorAt(0.5, QColor("#172B88"))
        gradient.setColorAt(1, QColor("#080B18"))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(
            QPointF(cx, cy), radius, radius
        )

        # Rotating light points
        for i in range(12):
            a = math.radians(self.angle * 2 + i * 30)
            x = cx + math.cos(a) * radius * 1.2
            y = cy + math.sin(a) * radius * 1.2

            painter.setBrush(QColor("#00D9FF"))
            painter.drawEllipse(
                QPointF(x, y), 3, 3
            )

        # Center text
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "EDETH\nAI CORE"
        )


# ---------------- METRIC CARDS ----------------

class MetricCard(QFrame):

    def __init__(self, title, value, color):
        super().__init__()

        self.setFixedHeight(115)
        self.setStyleSheet("""
            QFrame {
                background: #141A30;
                border: 1px solid #292F50;
                border-radius: 14px;
            }
        """)

        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: #929CBF; font-size: 13px;"
        )

        self.value_label = QLabel("0")

        self.value_label.setStyleSheet(f"""
            color: {color};
            font-size: 28px;
            font-weight: bold;
            border: none;
        """)

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

        self.target = int(value)
        self.current = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.count_up)
        self.timer.start(15)

    def count_up(self):
        if self.current < self.target:
            self.current += max(1, self.target // 60)
            self.current = min(self.current, self.target)
            self.value_label.setText(
                f"{self.current:,}"
            )
        else:
            self.timer.stop()


# ---------------- MAIN APPLICATION ----------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("EDETH | AI Analytics Platform")
        self.resize(1400, 900)

        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame {
                background: #0D1123;
                border-right: 1px solid #252B48;
            }
        """)

        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 30, 20, 20)

        logo = QLabel("✦ EDETH")
        logo.setStyleSheet("""
            color: #927AFF;
            font-size: 28px;
            font-weight: bold;
            border: none;
        """)

        side_layout.addWidget(logo)
        side_layout.addSpacing(35)

        for name in [
            "⌂  Dashboard",
            "▥  Analytics",
            "◈  Data Pipeline",
            "✧  AI Assistant",
            "⚙  Settings",
            "ⓘ  About"
        ]:
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    color: #B9C1E0;
                    background: transparent;
                    border: none;
                    border-radius: 9px;
                    padding: 14px;
                    text-align: left;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #25234B;
                    color: #A895FF;
                }
            """)
            side_layout.addWidget(btn)

        side_layout.addStretch()

        status = QLabel("● SYSTEM ONLINE")
        status.setStyleSheet(
            "color: #00E5A0; font-size: 12px;"
        )
        side_layout.addWidget(status)

        # Main content
        content = QWidget()
        content.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 25, 30, 25)

        # Header
        header = QHBoxLayout()

        heading = QLabel("Welcome to EDETH")
        heading.setStyleSheet("""
            color: white;
            font-size: 29px;
            font-weight: bold;
        """)

        subtitle = QLabel("Your data. Our intelligence.")
        subtitle.setStyleSheet(
            "color: #929CBF; font-size: 13px;"
        )

        heading_layout = QVBoxLayout()
        heading_layout.addWidget(heading)
        heading_layout.addWidget(subtitle)

        header.addLayout(heading_layout)
        header.addStretch()

        online = QLabel("●  ALL SYSTEMS OPERATIONAL")
        online.setStyleSheet(
            "color: #00E5A0; font-size: 12px;"
        )
        header.addWidget(online)

        content_layout.addLayout(header)
        content_layout.addSpacing(25)

        # Metrics
        metrics = QHBoxLayout()
        metrics.setSpacing(15)

        metrics.addWidget(
            MetricCard("TOTAL RECORDS", 1250000, "#927AFF")
        )
        metrics.addWidget(
            MetricCard("PROCESSES TODAY", 247, "#00E5A0")
        )
        metrics.addWidget(
            MetricCard("ACTIVE MODELS", 18, "#00CFFF")
        )

        content_layout.addLayout(metrics)
        content_layout.addSpacing(20)

        # Orb and information
        center = QHBoxLayout()

        orb = EnergyOrb()
        orb.setMinimumSize(500, 400)

        center.addWidget(orb, 2)

        info = QVBoxLayout()
        info.setSpacing(15)

        activity_title = QLabel("LIVE ACTIVITY")
        activity_title.setStyleSheet("""
            color: white;
            font-size: 19px;
            font-weight: bold;
        """)

        info.addWidget(activity_title)

        activities = [
            "✓  Data pipeline completed",
            "◈  AI model initialized",
            "↗  Analytics updated",
            "●  Database connected",
            "✦  EDETH engine running"
        ]

        for activity in activities:
            label = QLabel(activity)
            label.setStyleSheet("""
                color: #B9C1E0;
                background: #141A30;
                border: 1px solid #292F50;
                border-radius: 9px;
                padding: 17px;
                font-size: 13px;
            """)
            info.addWidget(label)

        info.addStretch()
        center.addLayout(info, 1)

        content_layout.addLayout(center)

        # Bottom panel
        bottom = QFrame()
        bottom.setStyleSheet("""
            QFrame {
                background: #141A30;
                border: 1px solid #34315D;
                border-radius: 14px;
            }
        """)

        bottom_layout = QHBoxLayout(bottom)

        message = QLabel(
            "✦  EDETH AI ENGINE\n"
            "Intelligence is not just about data. "
            "It's about what you do with it."
        )

        message.setStyleSheet("""
            color: white;
            font-size: 16px;
            padding: 15px;
            border: none;
        """)

        explore = QPushButton("EXPLORE EDETH →")
        explore.setCursor(Qt.CursorShape.PointingHandCursor)
        explore.setStyleSheet("""
            QPushButton {
                color: white;
                background: #7052FF;
                border: none;
                border-radius: 9px;
                padding: 15px 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #927AFF;
            }
        """)

        bottom_layout.addWidget(message)
        bottom_layout.addStretch()
        bottom_layout.addWidget(explore)

        content_layout.addWidget(bottom)

        main_layout.addWidget(sidebar)

        # Animated background behind content
        self.background = ParticleBackground()
        self.background.lower()

        main_layout.addWidget(content)

        self.setStyleSheet("""
            QMainWindow {
                background: #080B18;
            }
        """)

        self.background.setGeometry(root.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.background.setGeometry(
            self.centralWidget().rect()
        )


# ---------------- RUN ----------------

app = QApplication(sys.argv)

app.setFont(QFont("Segoe UI", 10))

window = MainWindow()
window.show()

sys.exit(app.exec())
