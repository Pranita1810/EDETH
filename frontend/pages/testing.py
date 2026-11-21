"""EDETH Testing Page
==================
Temporary testing component to execute and print the DataFrame (df)
from `user/inputs/raw/user_csv.py`.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                               QTableView, QVBoxLayout, QWidget)

import frontend.pages.data_ingestion as di_mod
from frontend.theme import (DISPLAY, F, LIGHT, NORMAL, QSS, T, Card, GhostButton,
                            PrimaryButton, RetroButton, badge, label, page_header,
                            panel, qc, scrollable)


# ════════════════════════════════════════════════════════════════════════════
#  POLARS DATAFRAME TABLE MODEL (FOR PYQT TABLEVIEW)
# ════════════════════════════════════════════════════════════════════════════
class PolarsTableModel(QAbstractTableModel):
    def __init__(self, df=None):
        super().__init__()
        self._headers: list[str] = []
        self._rows: list[list[str]] = []
        if df is not None:
            self._load(df)

    def _load(self, df):
        try:
            self._headers = [str(c) for c in df.columns]
            preview = df.head(100)
            self._rows = [
                [str(v) if v is not None else "" for v in row]
                for row in preview.iter_rows()
            ]
        except Exception as ex:
            print("Error loading preview into table model:", ex)
            self._headers = []
            self._rows = []

    def update_df(self, df):
        self.beginResetModel()
        if df is not None:
            self._load(df)
        else:
            self._headers = []
            self._rows = []
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        if parent is not None and parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        if r >= len(self._rows) or c >= len(self._headers):
            return None

        if role == Qt.DisplayRole:
            return self._rows[r][c]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            return QBrush(qc(T.TEXT))
        if role == Qt.BackgroundRole:
            return QBrush(qc("#FFFFFF" if r % 2 == 0 else "#FAF2F2"))
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section < len(self._headers):
                    return self._headers[section].upper()
            elif orientation == Qt.Vertical:
                return str(section + 1)
        if role == Qt.ForegroundRole:
            return QBrush(qc(T.TEXT))
        return None


# ════════════════════════════════════════════════════════════════════════════
#  TESTING PAGE COMPONENT
# ════════════════════════════════════════════════════════════════════════════
class TestingPage(QWidget):
    """Testing page displaying the `df` from `user/inputs/raw/user_csv.py`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_df = None
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(20)

        # 1. Page Header
        header = page_header(
            "DEBUG & TESTING (TEMPORARY)", "Testing Lab",
            "Direct verification view executing user/inputs/raw/user_csv.py and printing the resulting DataFrame."
        )
        root.addWidget(header)

        # 2. Control & Status Bar Card
        control_card = Card(shadow_color=T.YELLOW, bg_color="#FFFFFF")
        c_lay = QHBoxLayout(control_card)
        c_lay.setContentsMargins(24, 18, 24, 18)
        c_lay.setSpacing(16)

        left_info = QVBoxLayout()
        left_info.setSpacing(4)
        left_info.addWidget(label("TARGET SCRIPT: user/inputs/raw/user_csv.py", 8, T.MUTED, NORMAL, 1.5))
        self.lbl_path = label("Active File: None selected yet", 9.5, T.TEXT, NORMAL, 0.5)
        left_info.addWidget(self.lbl_path)
        c_lay.addLayout(left_info, 1)

        self.lbl_shape = badge("DF STATUS: WAITING", bg="#FFF3D6", size=8)
        c_lay.addWidget(self.lbl_shape)

        self.btn_refresh = RetroButton("🔄 RE-RUN user_csv.py", bg=T.ACCENT, hover_bg="#00ACB8", fg="#FFFFFF", height=38)
        self.btn_refresh.clicked.connect(self.refresh_data)
        c_lay.addWidget(self.btn_refresh)

        root.addWidget(control_card)

        # 3. Printed Console Output Card
        console_card = Card(shadow_color=T.PINK_SHADOW, bg_color="#FFFFFF")
        console_lay = QVBoxLayout(console_card)
        console_lay.setContentsMargins(20, 16, 20, 16)
        console_lay.setSpacing(8)

        c_top = QHBoxLayout()
        c_top.addWidget(badge("TERMINAL STDOUT: print(df)", bg=T.BADGE_PINK, size=7.5))
        c_top.addStretch()
        console_lay.addLayout(c_top)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFixedHeight(180)
        self.console_output.setFont(QFont("Consolas", 9))
        self.console_output.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: #2D1F24;"
            f"  color: #DAF8FA;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 10px;"
            f"  font-family: Consolas, monospace;"
            f"}}"
        )
        self.console_output.setPlainText("user_csv.py has not been executed yet. Click 'RE-RUN user_csv.py' above.")
        console_lay.addWidget(self.console_output)

        root.addWidget(console_card)

        # 4. Interactive Table View Card
        table_card = Card(shadow_color="#DAF8FA", bg_color="#FFFFFF")
        tbl_lay = QVBoxLayout(table_card)
        tbl_lay.setContentsMargins(20, 16, 20, 16)
        tbl_lay.setSpacing(10)

        t_top = QHBoxLayout()
        t_top.addWidget(badge("INTERACTIVE TABLE PREVIEW (FIRST 100 ROWS)", bg=T.ACCENT_LIGHT, size=7.5))
        t_top.addStretch()
        tbl_lay.addLayout(t_top)

        self.table_view = QTableView()
        self.table_view.setMinimumHeight(300)
        self.table_model = PolarsTableModel()
        self.table_view.setModel(self.table_model)
        self.table_view.setShowGrid(True)
        self.table_view.setWordWrap(False)
        self.table_view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setStyleSheet(
            f"QTableView {{"
            f"  background: #FFFFFF;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  color: {T.TEXT};"
            f"  gridline-color: {T.LINE};"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: {T.TEXT};"
            f"}}"
            f"QTableView::item {{"
            f"  padding: 6px 12px;"
            f"  border-bottom: 1px solid {T.LINE};"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {T.SURFACE2};"
            f"  color: {T.TEXT};"
            f"  font-weight: bold;"
            f"  border: 1px solid {T.LINE2};"
            f"  padding: 8px 12px;"
            f"}}"
        )
        tbl_lay.addWidget(self.table_view)

        root.addWidget(table_card)

    def refresh_data(self):
        """Executes user/inputs/raw/user_csv.py and captures the DataFrame."""
        path = getattr(di_mod.page, "var_file_path", "")
        self.lbl_path.setText(f"Active File: {path if path else 'None (Select a CSV in Ingestion tab)'}")

        if not path:
            self.lbl_shape.setText("DF STATUS: NO FILE SELECTED")
            self.lbl_shape.setStyleSheet(
                f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;"
            )
            self.console_output.setPlainText(
                "Waiting for CSV file selection.\n"
                "1. Go to 'INGESTION' in the sidebar.\n"
                "2. Click 'BROWSE FILE' and select any CSV file.\n"
                "3. Come back to 'TESTING' and your DataFrame from user_csv.py will be printed here!"
            )
            self.table_model.update_df(None)
            return

        df = None
        try:
            import user.inputs.raw.all_data_inputs as user_csv_module
            importlib.reload(user_csv_module)

            df = getattr(user_csv_module, "df", None)
            if df is None and hasattr(user_csv_module, "user_csv_df"):
                df = getattr(user_csv_module, "user_csv_df")
            if df is None and hasattr(user_csv_module, "ExcelCsv") and hasattr(user_csv_module.ExcelCsv, "user_input_csv"):
                res = user_csv_module.ExcelCsv.user_input_csv()
                if isinstance(res, pl.DataFrame):
                    df = res
            if df is None and hasattr(user_csv_module, "get_df"):
                df = user_csv_module.get_df(path)
            if df is None:
                import polars as pl
                df = pl.read_csv(path)
        except Exception as err:
            try:
                import polars as pl
                df = pl.read_csv(path)
            except Exception:
                self.lbl_shape.setText("EXECUTION ERROR")
                self.lbl_shape.setStyleSheet(
                    f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self.console_output.setPlainText(f"Error executing user/inputs/raw/user_csv.py:\n{err}")
                self.table_model.update_df(None)
                return

        self.current_df = df

        if df is not None:
            # Update shape badge
            shape_str = f"SHAPE: {df.height:,} rows × {df.width} cols"
            self.lbl_shape.setText(shape_str)
            self.lbl_shape.setStyleSheet(
                f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )

            # Update terminal stdout box (exact print(df) text)
            df_str = str(df)
            self.console_output.setPlainText(df_str)

            # Update interactive table
            self.table_model.update_df(df)
            self.table_view.resizeColumnsToContents()


# Standalone runner
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    win = QWidget()
    win.setWindowTitle("EDETH — Testing Page Preview")
    win.resize(1180, 820)
    win.setStyleSheet(f"background-color: {T.BG};")

    lay = QVBoxLayout(win)
    tp = TestingPage()
    lay.addWidget(scrollable(tp))

    win.show()
    sys.exit(app.exec())
