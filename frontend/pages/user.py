"""EDETH User Profile Page
=======================
Blank user section component in EDETH workspace.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                               QVBoxLayout, QWidget)

from frontend.theme import (DISPLAY, F, LIGHT, NORMAL, QSS, T, Card, GhostButton,
                            RetroButton, badge, label, page_header, scrollable)


class UserPage(QWidget):
    """User profile page (blank workspace)."""
    logout_requested = Signal()

    def __init__(self, username: str = "pranit", parent=None):
        super().__init__(parent)
        self.username = username
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(24)

        # Right side button for header: Log Out
        btn_logout = GhostButton("LOG OUT")
        btn_logout.setFixedHeight(32)
        btn_logout.clicked.connect(self.logout_requested)

        # Page Header
        main_user = self.username.capitalize()
        header = page_header(
            "USER PROFILE", f"Hello {main_user}",
            f"Signed in as @{self.username} · Role: Platform Administrator",
            right=btn_logout
        )
        root.addWidget(header)

        # Blank workspace card
        blank_card = Card(shadow_color=T.PINK_SHADOW, bg_color="#FFFFFF")
        lay = QVBoxLayout(blank_card)
        lay.setContentsMargins(32, 40, 32, 40)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignCenter)

        user_badge = badge(f"ACTIVE USER: {self.username.upper()}", bg=T.ACCENT_LIGHT, size=9)
        lay.addWidget(user_badge, 0, Qt.AlignCenter)

        t = label("User Workspace", 18, T.TEXT, QFont.Weight.Black, 0.5)
        lay.addWidget(t, 0, Qt.AlignCenter)

        sub = label(
            "This is the blank user section. Configuration, security preferences, "
            "and account activity tools will be implemented here.",
            9.5, T.MUTED, LIGHT, 0.2
        )
        lay.addWidget(sub, 0, Qt.AlignCenter)

        root.addWidget(blank_card, 1)

    def set_user(self, username: str):
        self.username = username


# Standalone runner
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    win = QWidget()
    win.setWindowTitle("EDETH — User Page Preview")
    win.resize(1100, 720)
    win.setStyleSheet(f"background-color: {T.BG};")

    lay = QVBoxLayout(win)
    user_pg = UserPage("pranit")
    lay.addWidget(scrollable(user_pg))

    win.show()
    sys.exit(app.exec())
