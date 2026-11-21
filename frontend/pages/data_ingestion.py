"""EDETH Data Ingestion Page
=========================
Neo-brutalist data ingestion interface supporting:
1. File Ingestion (CSV, Excel)
2. PostgreSQL Database Connection
3. MSSQL Database Connection
4. REST API Endpoint Ingestion

NOTE FOR BACKEND DEVELOPER:
===========================
All collected user variables are exposed directly on this widget and dispatched via
the `ingest_requested` Signal(dict). You can import and connect your backend scripts
(e.g., user/inputs/xyz.py) directly to these variables or the signal.
"""
from __future__ import annotations

import importlib
import math
import os
import re
import sys
from pathlib import Path

import polars as pl

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QPointF, QRectF,
                            QSize, Qt, Signal)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton,
                               QScrollArea, QSizePolicy, QSpinBox, QStackedWidget,
                               QTableView, QVBoxLayout, QWidget)

from frontend.theme import (DISPLAY, F, LIGHT, NORMAL, QSS, T, Card, GhostButton,
                            PrimaryButton, RetroButton, badge, label, page_header,
                            panel, qc, scrollable)


# ════════════════════════════════════════════════════════════════════════════
#  PAGINATED POLARS TABLE MODEL (PREVENTS LARGE DATASET FREEZES / CRASHES)
# ════════════════════════════════════════════════════════════════════════════
class PaginatedPolarsTableModel(QAbstractTableModel):
    """Memory-efficient paginated table model for Polars DataFrames.
    
    Only loads and formats rows for the active page slice into Python strings,
    ensuring butter-smooth 60fps performance without GUI crashes on large datasets.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_df: pl.DataFrame | None = None
        self._filtered_df: pl.DataFrame | None = None
        self._page_rows: list[list[str]] = []
        self._headers: list[str] = []

        self.page_size: int = 50
        self.current_page: int = 1
        self.total_pages: int = 1
        self.filter_query: str = ""
        self.filter_column: str = "All Columns"

    def set_dataframe(self, df: pl.DataFrame | None):
        self._full_df = df
        if df is not None:
            self._headers = [str(c) for c in df.columns]
        else:
            self._headers = []
        self.current_page = 1
        self._apply_filter_and_page()

    def set_filter(self, query: str, column: str = "All Columns"):
        self.filter_query = query.strip()
        self.filter_column = column
        self.current_page = 1
        self._apply_filter_and_page()

    def set_page(self, page_num: int):
        self.current_page = max(1, min(page_num, self.total_pages))
        self._slice_current_page()

    def set_page_size(self, size: int):
        self.page_size = max(1, size)
        self.current_page = 1
        self._apply_filter_and_page()

    def _apply_filter_and_page(self):
        if self._full_df is None or self._full_df.height == 0:
            self._filtered_df = None
            self.total_pages = 1
            self.current_page = 1
            self._slice_current_page()
            return

        if self.filter_query:
            try:
                pattern = f"(?i){re.escape(self.filter_query)}"
                if self.filter_column != "All Columns" and self.filter_column in self._full_df.columns:
                    self._filtered_df = self._full_df.filter(
                        pl.col(self.filter_column).cast(pl.Utf8).fill_null("").str.contains(pattern)
                    )
                else:
                    pred = pl.any_horizontal([
                        pl.col(c).cast(pl.Utf8).fill_null("").str.contains(pattern)
                        for c in self._full_df.columns
                    ])
                    self._filtered_df = self._full_df.filter(pred)
            except Exception as e:
                print("Filter evaluation error:", e)
                self._filtered_df = self._full_df
        else:
            self._filtered_df = self._full_df

        total_rows = self._filtered_df.height if self._filtered_df is not None else 0
        self.total_pages = max(1, math.ceil(total_rows / self.page_size))
        self.current_page = max(1, min(self.current_page, self.total_pages))
        self._slice_current_page()

    def _slice_current_page(self):
        self.beginResetModel()
        if self._filtered_df is None or self._filtered_df.height == 0:
            self._page_rows = []
        else:
            offset = (self.current_page - 1) * self.page_size
            page_slice = self._filtered_df.slice(offset, self.page_size)
            self._page_rows = [
                [str(v) if v is not None else "" for v in row]
                for row in page_slice.iter_rows()
            ]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent is not None and parent.isValid():
            return 0
        return len(self._page_rows)

    def columnCount(self, parent=QModelIndex()):
        if parent is not None and parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        if r >= len(self._page_rows) or c >= len(self._headers):
            return None

        if role == Qt.DisplayRole:
            return self._page_rows[r][c]
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            return QBrush(qc("#1A0F13"))
        if role == Qt.BackgroundRole:
            return QBrush(qc("#FFFFFF"))
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if 0 <= section < len(self._headers):
                    return self._headers[section].upper()
            elif orientation == Qt.Vertical:
                offset = (self.current_page - 1) * self.page_size
                return str(offset + section + 1)
        if role == Qt.ForegroundRole:
            return QBrush(qc("#1A0F13"))
        if role == Qt.BackgroundRole:
            return QBrush(qc("#F8EDED"))
        return None


# ════════════════════════════════════════════════════════════════════════════
#  STRICT READ-ONLY QUERY VALIDATOR (DELEGATED TO all_data_inputs.py)
# ════════════════════════════════════════════════════════════════════════════
def validate_readonly_query(query: str) -> tuple[bool, str]:
    """Validates query by delegating to backend user/inputs/raw/all_data_inputs.py."""
    import user.inputs.raw.all_data_inputs as adi
    return adi.validate_readonly_query(query)


# ════════════════════════════════════════════════════════════════════════════
#  SOURCE TAB BUTTON
# ════════════════════════════════════════════════════════════════════════════
class SourceTabButton(QPushButton):
    """Neo-brutalist tab selector button."""

    def __init__(self, text: str, is_active: bool = False, parent=None):
        super().__init__(text, parent)
        self.is_active = is_active
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setFont(F(8.5, NORMAL, 1.2))
        self.update_style()

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  color: #FFFFFF;"
                f"  background-color: {T.ACCENT};"
                f"  border: 2px solid {T.LINE2};"
                f"  border-radius: 6px;"
                f"  padding: 0 16px;"
                f"  font-weight: bold;"
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  color: {T.TEXT};"
                f"  background-color: #FFFFFF;"
                f"  border: 2px solid {T.LINE2};"
                f"  border-radius: 6px;"
                f"  padding: 0 16px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {T.YELLOW};"
                f"}}"
            )


class DynamicStackedWidget(QStackedWidget):
    """QStackedWidget that resizes dynamically to fit the currently active page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda idx: self.updateGeometry())

    def sizeHint(self) -> QSize:
        curr = self.currentWidget()
        if curr:
            return curr.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        curr = self.currentWidget()
        if curr:
            return curr.minimumSizeHint()
        return super().minimumSizeHint()


# Module-level variable reference for user scripts:
class IngestionState:
    def __init__(self):
        self.var_file_path: str = ""
        self.var_file_type: str = "csv"     # 'csv' | 'excel'
        self.var_csv_delimiter: str = ","
        self.var_excel_sheet: str = ""
        self.var_postgres_host: str = ""
        self.var_postgres_port: str = "5432"
        self.var_postgres_database: str = ""
        self.var_postgres_username: str = ""
        self.var_postgres_password: str = ""
        self.var_postgres_query: str = ""
        self.var_mssql_server: str = ""
        self.var_mssql_port: str = "1433"
        self.var_mssql_database: str = ""
        self.var_mssql_username: str = ""
        self.var_mssql_password: str = ""
        self.var_mssql_query: str = ""
        self.var_api_url: str = ""
        self.var_api_method: str = "GET"
        self.var_api_headers: str = ""
        self.var_api_payload: str = ""
        self.raw_data = None

page = IngestionState()


# ════════════════════════════════════════════════════════════════════════════
#  DATA INGESTION PAGE COMPONENT
# ════════════════════════════════════════════════════════════════════════════
class DataIngestionPage(QWidget):
    """Data Ingestion component.

    Emits `ingest_requested(dict)` with all variables ready for your backend scripts.
    """
    ingest_requested = Signal(dict)

    @property
    def var_file_path(self) -> str:
        return page.var_file_path

    @var_file_path.setter
    def var_file_path(self, val: str):
        page.var_file_path = val

    @property
    def raw_data(self):
        return page.raw_data

    @raw_data.setter
    def raw_data(self, val):
        page.raw_data = val

    def __init__(self, parent=None):
        super().__init__(parent)

        # ═════════════════════════════════════════════════════════════════════
        #  BACKEND VARIABLE REGISTRY (ACCESS THESE IN YOUR BACKEND SCRIPTS):
        # ═════════════════════════════════════════════════════════════════════
        # 1. File Upload Variables:
        self.var_file_type: str = "csv"     # 'csv' | 'excel'
        self.var_csv_delimiter: str = ","   # Separator: ',', ';', '\t', '|'
        self.var_excel_sheet: str = ""      # Optional specific sheet name

        # 2. PostgreSQL Variables:
        self.var_postgres_host: str = ""
        self.var_postgres_port: str = "5432"
        self.var_postgres_database: str = ""
        self.var_postgres_username: str = ""
        self.var_postgres_password: str = ""
        self.var_postgres_query: str = ""

        # 3. MSSQL Variables:
        self.var_mssql_server: str = ""
        self.var_mssql_port: str = "1433"
        self.var_mssql_database: str = ""
        self.var_mssql_username: str = ""
        self.var_mssql_password: str = ""
        self.var_mssql_query: str = ""

        # 4. REST API Variables:
        self.var_api_url: str = ""
        self.var_api_method: str = "GET"    # 'GET' | 'POST'
        self.var_api_headers: str = ""      # JSON or raw string of headers
        self.var_api_payload: str = ""      # Request body or query parameters

        # 5. Resulting Loaded Data Storage (Put your backend returned DataFrame/Dataset here):
        self.raw_data = None                # <-- STORE PROCESSED DATA HERE (DataFrame / Dataset)
        # ═════════════════════════════════════════════════════════════════════

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 36)
        root.setSpacing(20)

        # Small top-right notification pill (strictly small message for success/fail)
        self.top_toast = QLabel("")
        self.top_toast.setFont(F(8.5, NORMAL))
        self.top_toast.setFixedHeight(32)
        self.top_toast.setAlignment(Qt.AlignCenter)
        self.top_toast.setVisible(False)
        self.top_toast.setStyleSheet(
            f"color:#FFFFFF; background:{T.POS}; border:2px solid {T.LINE2}; "
            f"border-radius:6px; padding:2px 14px; font-weight:bold;"
        )

        # 1. Page Header (with top-right notification)
        header = page_header(
            "INGESTION ENGINE", "Data Ingestion",
            "Choose a source to ingest raw data into EDETH: File upload, Relational Database, or REST API.",
            right=self.top_toast
        )
        root.addWidget(header)

        # 2. Source Selector Tabs
        tabs_box = QHBoxLayout()
        tabs_box.setSpacing(12)

        self.tab_file = SourceTabButton("📁 CSV / EXCEL", is_active=True)
        self.tab_postgres = SourceTabButton("🐘 POSTGRESQL")
        self.tab_mssql = SourceTabButton("🗄️ MSSQL SERVER")
        self.tab_api = SourceTabButton("🌐 REST API")

        self.tab_buttons = [self.tab_file, self.tab_postgres, self.tab_mssql, self.tab_api]

        for idx, btn in enumerate(self.tab_buttons):
            btn.clicked.connect(lambda checked=False, i=idx: self._switch_tab(i))
            tabs_box.addWidget(btn)

        tabs_box.addStretch()
        root.addLayout(tabs_box)

        # 3. Panels Stack
        self.panels_stack = DynamicStackedWidget()

        self.panel_file = self._build_file_panel()
        self.panel_postgres = self._build_postgres_panel()
        self.panel_mssql = self._build_mssql_panel()
        self.panel_api = self._build_api_panel()

        self.panels_stack.addWidget(self.panel_file)
        self.panels_stack.addWidget(self.panel_postgres)
        self.panels_stack.addWidget(self.panel_mssql)
        self.panels_stack.addWidget(self.panel_api)

        root.addWidget(self.panels_stack)

        # 4. Developer Reference Box (Shows variables ready for backend xyz.py)
        dev_note_card = self._build_dev_notes_card()
        root.addWidget(dev_note_card)

        root.addStretch()

    def _switch_tab(self, index: int):
        for i, btn in enumerate(self.tab_buttons):
            btn.set_active(i == index)
        self.panels_stack.setCurrentIndex(index)
        self.panels_stack.updateGeometry()

    # ═════════════════════════════════════════════════════════════════════════
    #  PANEL 1: FILE INGESTION (CSV, EXCEL)
    # ═════════════════════════════════════════════════════════════════════════
    def _build_file_panel(self) -> Card:
        card = Card(shadow_color=T.PINK_SHADOW, bg_color="#FFFFFF")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # File selection row
        row = QHBoxLayout()
        row.setSpacing(12)

        self.input_file_path = QLineEdit()
        self.input_file_path.setPlaceholderText("Select or browse a CSV or Excel (.xlsx, .xls) file...")
        self.input_file_path.setReadOnly(True)
        self.input_file_path.setFixedHeight(40)
        self.input_file_path.setStyleSheet(
            f"QLineEdit {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2}; border-radius:6px; padding:4px 12px; font-size:13px; font-weight:bold; }}"
        )
        row.addWidget(self.input_file_path, 1)

        btn_browse = RetroButton("📂 BROWSE FILE", bg=T.YELLOW, hover_bg="#E5AC00", height=40)
        btn_browse.clicked.connect(self._browse_file)
        row.addWidget(btn_browse)

        lay.addLayout(row)

        # Options row: Data type format & conditional Excel sheet name
        opt_row = QHBoxLayout()
        opt_row.setSpacing(18)
        opt_row.setAlignment(Qt.AlignTop)

        # Format selector (CSV / Excel)
        fmt_box = QVBoxLayout()
        fmt_box.setSpacing(6)
        fmt_box.setAlignment(Qt.AlignTop)
        lbl_fmt = QLabel("DATA TYPE / FORMAT")
        lbl_fmt.setFont(F(8.5, NORMAL, 1.2))
        lbl_fmt.setStyleSheet(f"color:{T.TEXT}; background:transparent; font-weight:bold;")
        lbl_fmt.setFixedHeight(18)
        fmt_box.addWidget(lbl_fmt)

        self.combo_format = QComboBox()
        self.combo_format.addItems(["CSV (*.csv)", "Excel (*.xlsx, *.xls)"])
        self.combo_format.setFixedHeight(38)
        self.combo_format.setMinimumWidth(220)
        self.combo_format.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: {T.TEXT};"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 4px 12px;"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"}}"
            f"QComboBox:hover {{"
            f"  border-color: {T.ACCENT};"
            f"}}"
            f"QComboBox::drop-down {{"
            f"  subcontrol-origin: padding;"
            f"  subcontrol-position: top right;"
            f"  width: 28px;"
            f"  border-left: 2px solid {T.LINE2};"
            f"  background: {T.SURFACE2};"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: {T.TEXT};"
            f"  border: 2px solid {T.LINE2};"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: {T.TEXT};"
            f"  padding: 4px;"
            f"}}"
        )
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)
        fmt_box.addWidget(self.combo_format)
        opt_row.addLayout(fmt_box)

        # Excel Sheet Name container (ONLY visible if user uploads or selects an Excel file!)
        self.box_excel_sheet = QWidget()
        sheet_lay = QVBoxLayout(self.box_excel_sheet)
        sheet_lay.setContentsMargins(0, 0, 0, 0)
        sheet_lay.setSpacing(6)
        sheet_lay.setAlignment(Qt.AlignTop)
        lbl_sheet = QLabel("EXCEL SHEET NAME (OPTIONAL)")
        lbl_sheet.setFont(F(8.5, NORMAL, 1.2))
        lbl_sheet.setStyleSheet(f"color:{T.TEXT}; background:transparent; font-weight:bold;")
        lbl_sheet.setFixedHeight(18)
        sheet_lay.addWidget(lbl_sheet)

        self.input_excel_sheet = QLineEdit()
        self.input_excel_sheet.setPlaceholderText("e.g. Sheet1 (default: first sheet)")
        self.input_excel_sheet.setFixedHeight(38)
        self.input_excel_sheet.setStyleSheet(
            f"QLineEdit {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2}; border-radius:6px; padding:4px 10px; font-size:13px; font-weight:bold; }}"
        )
        sheet_lay.addWidget(self.input_excel_sheet)
        self.box_excel_sheet.setVisible(False)  # Hidden for CSV by default
        opt_row.addWidget(self.box_excel_sheet, 1)

        opt_row.addStretch()
        lay.addLayout(opt_row)

        # Action Buttons: 1. SHOW DATA  2. PROCESS DATA
        lay.addSpacing(6)
        act_row = QHBoxLayout()
        act_row.setSpacing(14)

        # Option 1: SHOW DATA
        self.btn_show_data = PrimaryButton("👁️ SHOW DATA")
        self.btn_show_data.setFixedHeight(44)
        self.btn_show_data.clicked.connect(self._on_show_data_clicked)
        act_row.addWidget(self.btn_show_data, 1)

        # Option 2: PROCESS DATA (user writes processing logic in all_data_inputs.py)
        self.btn_process_data = RetroButton("⚙️ PROCESS DATA", bg=T.YELLOW, hover_bg="#E5AC00", fg=T.TEXT, height=44)
        self.btn_process_data.clicked.connect(self._on_process_data_clicked)
        act_row.addWidget(self.btn_process_data, 1)

        lay.addLayout(act_row)

        # ─────────────────────────────────────────────────────────────────────
        #  INTERACTIVE PAGINATED DATA PREVIEW CONTAINER (BELOW ACTION BUTTONS)
        # ─────────────────────────────────────────────────────────────────────
        lay.addSpacing(10)
        self.preview_container = Card(shadow_color="#DAF8FA", bg_color="#FFFFFF")
        self.preview_container.setVisible(False)  # Hidden initially until user clicks SHOW DATA
        p_lay = QVBoxLayout(self.preview_container)
        p_lay.setContentsMargins(18, 16, 18, 16)
        p_lay.setSpacing(12)

        # 1. Real-time Filter Bar
        filter_box = QHBoxLayout()
        filter_box.setSpacing(10)

        lbl_filter_tag = QLabel("FILTER BY:")
        lbl_filter_tag.setFont(F(8, NORMAL, 1.0))
        lbl_filter_tag.setStyleSheet(f"color:{T.TEXT}; background:transparent; font-weight:bold;")
        filter_box.addWidget(lbl_filter_tag)

        self.combo_filter_col = QComboBox()
        self.combo_filter_col.addItem("All Columns")
        self.combo_filter_col.setFixedHeight(34)
        self.combo_filter_col.setMinimumWidth(130)
        self.combo_filter_col.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 2px 8px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_filter_col.currentIndexChanged.connect(self._on_filter_changed)
        filter_box.addWidget(self.combo_filter_col)

        self.input_filter = QLineEdit()
        self.input_filter.setPlaceholderText("🔍 Search / filter rows in real-time (case-insensitive keyword)...")
        self.input_filter.setFixedHeight(34)
        self.input_filter.setStyleSheet(
            f"QLineEdit {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.input_filter.textChanged.connect(self._on_filter_changed)
        filter_box.addWidget(self.input_filter, 1)

        self.btn_clear_filter = RetroButton("✖ CLEAR", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=34)
        self.btn_clear_filter.setToolTip("Clear search filter text, or click to clear dataset view")
        self.btn_clear_filter.clicked.connect(self._on_clear_filter)
        filter_box.addWidget(self.btn_clear_filter)

        self.lbl_filter_match = badge("ALL ROWS", bg=T.BADGE_PINK, size=7)
        filter_box.addWidget(self.lbl_filter_match)

        p_lay.addLayout(filter_box)

        # 2. Interactive Table View (Clean, borderless table, all rows solid white)
        self.preview_table = QTableView()
        self.preview_table.setMinimumHeight(480)
        self.preview_model = PaginatedPolarsTableModel()
        self.preview_table.setModel(self.preview_model)
        self.preview_table.setShowGrid(True)
        self.preview_table.setWordWrap(False)
        self.preview_table.setAlternatingRowColors(False)
        self.preview_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.verticalHeader().setDefaultSectionSize(30)
        self.preview_table.setStyleSheet(
            f"QTableView {{"
            f"  background-color: #FFFFFF;"
            f"  border: none;"
            f"  color: #1A0F13;"
            f"  gridline-color: #EBD3D3;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"  font-size: 13px;"
            f"}}"
            f"QTableView::item {{"
            f"  color: #1A0F13;"
            f"  padding: 6px 12px;"
            f"  border-bottom: 1px solid #F0D5D5;"
            f"}}"
            f"QTableView::item:selected {{"
            f"  background-color: {T.ACCENT_LIGHT};"
            f"  color: #1A0F13;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {T.SURFACE2};"
            f"  color: {T.TEXT};"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  border: none;"
            f"  border-bottom: 2px solid {T.LINE2};"
            f"  border-right: 1px solid {T.LINE};"
            f"  padding: 8px 12px;"
            f"}}"
        )
        p_lay.addWidget(self.preview_table)

        # 3. Pagination Controls Bar (Crisp, fully visible numbers and controls)
        p_nav = QHBoxLayout()
        p_nav.setSpacing(8)

        self.btn_first = RetroButton("⏮ FIRST", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_first.clicked.connect(lambda: self._go_to_page(1))
        p_nav.addWidget(self.btn_first)

        self.btn_prev = RetroButton("◀ PREV", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_prev.clicked.connect(lambda: self._go_to_page(self.preview_model.current_page - 1))
        p_nav.addWidget(self.btn_prev)

        lbl_p_tag = QLabel("PAGE:")
        lbl_p_tag.setFont(F(8, NORMAL))
        lbl_p_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_p_tag)

        self.spin_page = QSpinBox()
        self.spin_page.setRange(1, 1)
        self.spin_page.setValue(1)
        self.spin_page.setFixedHeight(32)
        self.spin_page.setFixedWidth(64)
        self.spin_page.setStyleSheet(
            f"QSpinBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"  padding: 2px 4px;"
            f"}}"
        )
        self.spin_page.valueChanged.connect(self._go_to_page)
        p_nav.addWidget(self.spin_page)

        self.lbl_total_pages = QLabel("of 1")
        self.lbl_total_pages.setFont(F(8.5, NORMAL))
        self.lbl_total_pages.setStyleSheet(f"color: #1A0F13; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_total_pages)

        self.btn_next = RetroButton("NEXT ▶", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_next.clicked.connect(lambda: self._go_to_page(self.preview_model.current_page + 1))
        p_nav.addWidget(self.btn_next)

        self.btn_last = RetroButton("LAST ⏭", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_last.clicked.connect(lambda: self._go_to_page(self.preview_model.total_pages))
        p_nav.addWidget(self.btn_last)

        p_nav.addSpacing(16)
        lbl_sz_tag = QLabel("PAGE SIZE:")
        lbl_sz_tag.setFont(F(8, NORMAL))
        lbl_sz_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_sz_tag)

        self.combo_page_size = QComboBox()
        self.combo_page_size.addItems(["25 rows / page", "50 rows / page", "100 rows / page", "250 rows / page"])
        self.combo_page_size.setCurrentIndex(1)  # Default 50
        self.combo_page_size.setFixedHeight(32)
        self.combo_page_size.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  padding: 2px 6px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_page_size.currentIndexChanged.connect(self._on_page_size_changed)
        p_nav.addWidget(self.combo_page_size)

        p_nav.addStretch()
        self.lbl_page_records = QLabel("No dataset loaded yet")
        self.lbl_page_records.setFont(F(8, NORMAL))
        self.lbl_page_records.setStyleSheet(f"color: {T.MUTED}; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_page_records)

        p_lay.addLayout(p_nav)

        lay.addWidget(self.preview_container)
        lay.addStretch(1)
        return card

    def _on_format_changed(self, idx: int):
        is_excel = (idx == 1)
        self.box_excel_sheet.setVisible(is_excel)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Data File", "",
            "Data Files (*.csv *.tsv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if path:
            self.input_file_path.setText(path)
            self.var_file_path = path
            ext = os.path.splitext(path)[1].lower()
            if ext == ".csv":
                self.combo_format.setCurrentIndex(0)
                self.box_excel_sheet.setVisible(False)
            elif ext in (".xlsx", ".xls"):
                self.combo_format.setCurrentIndex(1)
                self.box_excel_sheet.setVisible(True)

    def _sync_input_variables(self):
        """Synchronizes UI values into page state and variables."""
        self.var_file_path = self.input_file_path.text().strip()
        idx = self.combo_format.currentIndex()
        self.var_file_type = "csv" if idx == 0 else "excel"
        self.var_csv_delimiter = ","
        self.var_excel_sheet = self.input_excel_sheet.text().strip() if self.var_file_type == "excel" else ""

        page.var_file_path = self.var_file_path
        page.var_file_type = self.var_file_type
        page.var_csv_delimiter = self.var_csv_delimiter
        page.var_excel_sheet = self.var_excel_sheet

    def _on_show_data_clicked(self):
        """Option 1: SHOW DATA
        Takes data from user/inputs/raw/all_data_inputs.py and displays it in paginated view.
        """
        self._sync_input_variables()
        path = self.var_file_path

        if not path:
            self._notify_action("⚠️ Please browse and select a CSV or Excel file first.")
            return
        if not os.path.exists(path):
            self._notify_action(f"⚠️ Selected file does not exist: {path}")
            return

        df = None
        err_msg = ""

        # 1. Take variable from user/inputs/raw/all_data_inputs.py
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)

            # Check if user defined top-level df / dataset / user_csv_df / user_xl_df
            df = getattr(adi, "df", None)
            if df is None:
                if self.var_file_type == "csv":
                    df = getattr(adi, "user_csv_df", None)
                    if df is None and hasattr(adi, "ExcelCsv") and hasattr(adi.ExcelCsv, "user_input_csv"):
                        res = adi.ExcelCsv.user_input_csv()
                        if isinstance(res, pl.DataFrame):
                            df = res
                        elif isinstance(res, Exception):
                            err_msg = str(res)
                else:
                    df = getattr(adi, "user_xl_df", None)
                    if df is None and hasattr(adi, "ExcelCsv") and hasattr(adi.ExcelCsv, "user_input_xl"):
                        res = adi.ExcelCsv.user_input_xl()
                        if isinstance(res, pl.DataFrame):
                            df = res
                        elif isinstance(res, Exception):
                            err_msg = str(res)
        except Exception as e:
            err_msg = str(e)

        # 2. Fallback to direct Polars read if all_data_inputs didn't return a DataFrame
        if df is None or not isinstance(df, pl.DataFrame):
            try:
                if self.var_file_type == "csv":
                    df = pl.read_csv(path, separator=self.var_csv_delimiter)
                else:
                    df = pl.read_excel(path, sheet_name=self.var_excel_sheet or None)
            except Exception as e:
                err_msg = f"Direct file read error: {e}"

        if df is not None and isinstance(df, pl.DataFrame):
            self.raw_data = df
            page.raw_data = df
            self._display_preview_data(df)
            self._notify_action(f"Showing {df.height:,} rows × {df.width} cols from all_data_inputs.py")
        else:
            self._notify_action(f"⚠️ Could not load data: {err_msg or 'Empty DataFrame'}")

    def _on_process_data_clicked(self):
        """Option 2: PROCESS DATA
        Collects input parameters and dispatches payload.
        Processing logic itself is handled by user backend in all_data_inputs.py.
        """
        self._sync_input_variables()
        self._notify_action("✓ Process Data triggered — Variables ready for your backend logic in all_data_inputs.py")
        payload = {
            "action": "process_data",
            "source_type": self.var_file_type,
            "file_path": self.var_file_path,
            "delimiter": self.var_csv_delimiter,
            "sheet_name": self.var_excel_sheet,
        }
        self.ingest_requested.emit(payload)

    def _display_preview_data(self, df: pl.DataFrame):
        self.preview_container.setVisible(True)
        self.panels_stack.updateGeometry()
        self.preview_model.set_dataframe(df)
        self._update_filter_columns()
        self._update_pagination_ui()
        self.preview_table.resizeColumnsToContents()

    def _update_filter_columns(self):
        current_selection = self.combo_filter_col.currentText()
        self.combo_filter_col.blockSignals(True)
        self.combo_filter_col.clear()
        self.combo_filter_col.addItem("All Columns")
        if self.preview_model._full_df is not None:
            for c in self.preview_model._full_df.columns:
                self.combo_filter_col.addItem(str(c))
        idx = self.combo_filter_col.findText(current_selection)
        if idx >= 0:
            self.combo_filter_col.setCurrentIndex(idx)
        else:
            self.combo_filter_col.setCurrentIndex(0)
        self.combo_filter_col.blockSignals(False)

    def _on_filter_changed(self):
        query = self.input_filter.text()
        col = self.combo_filter_col.currentText()
        self.preview_model.set_filter(query, col)
        self._update_pagination_ui()

    def _on_clear_filter(self):
        has_filter = bool(self.input_filter.text().strip())
        self.input_filter.blockSignals(True)
        self.input_filter.clear()
        self.input_filter.blockSignals(False)
        self.combo_filter_col.blockSignals(True)
        self.combo_filter_col.setCurrentIndex(0)
        self.combo_filter_col.blockSignals(False)
        self.preview_model.set_filter("", "All Columns")

        if not has_filter:
            # When filter is already empty, CLEAR clears the loaded preview dataset
            self.preview_model.set_dataframe(None)
            self.raw_data = None
            page.raw_data = None
            self.preview_container.setVisible(False)
            self.panels_stack.updateGeometry()
            self._notify_action("✓ Data preview cleared.")

        self._update_pagination_ui()
        self.preview_table.viewport().update()

    def _go_to_page(self, page_num: int):
        self.preview_model.set_page(page_num)
        self._update_pagination_ui()

    def _on_page_size_changed(self, idx: int):
        sizes = [25, 50, 100, 250]
        size = sizes[idx] if idx < len(sizes) else 50
        self.preview_model.set_page_size(size)
        self._update_pagination_ui()

    def _update_pagination_ui(self):
        m = self.preview_model
        total_p = m.total_pages
        curr_p = m.current_page

        self.spin_page.blockSignals(True)
        self.spin_page.setRange(1, total_p)
        self.spin_page.setValue(curr_p)
        self.spin_page.blockSignals(False)

        self.lbl_total_pages.setText(f"of {total_p:,}")
        self.btn_first.setEnabled(curr_p > 1)
        self.btn_prev.setEnabled(curr_p > 1)
        self.btn_next.setEnabled(curr_p < total_p)
        self.btn_last.setEnabled(curr_p < total_p)

        total_rows = m._filtered_df.height if m._filtered_df is not None else 0
        full_rows = m._full_df.height if m._full_df is not None else 0

        if full_rows == 0:
            self.lbl_page_records.setText("No dataset loaded yet")
            self.lbl_filter_match.setText("NO DATA")
        elif total_rows == 0:
            self.lbl_page_records.setText("0 matching rows found")
            self.lbl_filter_match.setText("0 MATCHES")
            self.lbl_filter_match.setStyleSheet(
                f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
            )
        else:
            start_row = (curr_p - 1) * m.page_size + 1
            end_row = min(curr_p * m.page_size, total_rows)
            filter_suffix = f" (filtered from {full_rows:,})" if total_rows != full_rows else ""
            self.lbl_page_records.setText(f"Showing {start_row:,}–{end_row:,} of {total_rows:,} rows{filter_suffix}")
            if total_rows != full_rows:
                self.lbl_filter_match.setText(f"{total_rows:,} MATCHES")
                self.lbl_filter_match.setStyleSheet(
                    f"background:{T.YELLOW};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;font-weight:bold;"
                )
            else:
                self.lbl_filter_match.setText(f"ALL {full_rows:,} ROWS")
                self.lbl_filter_match.setStyleSheet(
                    f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
                )

    # ═════════════════════════════════════════════════════════════════════════
    #  PANEL 2: POSTGRESQL INGESTION
    # ═════════════════════════════════════════════════════════════════════════
    def _build_postgres_panel(self) -> Card:
        card = Card(shadow_color="#DAF8FA", bg_color="#FFFFFF")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        # Connection grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        # Host
        grid.addWidget(label("HOST / SERVER", 8, T.TEXT, NORMAL, 1.2), 0, 0)
        self.input_pg_host = QLineEdit("localhost")
        self.input_pg_host.setFixedHeight(36)
        grid.addWidget(self.input_pg_host, 1, 0)

        # Port
        grid.addWidget(label("PORT", 8, T.TEXT, NORMAL, 1.2), 0, 1)
        self.input_pg_port = QLineEdit("5432")
        self.input_pg_port.setFixedHeight(36)
        grid.addWidget(self.input_pg_port, 1, 1)

        # Database
        grid.addWidget(label("DATABASE NAME", 8, T.TEXT, NORMAL, 1.2), 0, 2)
        self.input_pg_db = QLineEdit()
        self.input_pg_db.setPlaceholderText("analytics_db")
        self.input_pg_db.setFixedHeight(36)
        grid.addWidget(self.input_pg_db, 1, 2)

        # Username
        grid.addWidget(label("USERNAME", 8, T.TEXT, NORMAL, 1.2), 2, 0)
        self.input_pg_user = QLineEdit("postgres")
        self.input_pg_user.setFixedHeight(36)
        grid.addWidget(self.input_pg_user, 3, 0)

        # Password
        grid.addWidget(label("PASSWORD", 8, T.TEXT, NORMAL, 1.2), 2, 1)
        self.input_pg_pass = QLineEdit()
        self.input_pg_pass.setEchoMode(QLineEdit.Password)
        self.input_pg_pass.setPlaceholderText("••••••••")
        self.input_pg_pass.setFixedHeight(36)
        grid.addWidget(self.input_pg_pass, 3, 1)

        lay.addLayout(grid)

        # Action Buttons Row: 1. TEST CONNECTION  2. FETCH TABLES FROM DATABASE
        act_row = QHBoxLayout()
        act_row.setSpacing(12)

        self.btn_pg_test_conn = RetroButton("🔌 1. TEST CONNECTION", bg=T.YELLOW, hover_bg="#E5AC00", fg=T.TEXT, height=40)
        self.btn_pg_test_conn.clicked.connect(self._on_pg_test_connection)
        act_row.addWidget(self.btn_pg_test_conn)

        self.btn_pg_fetch_tables = PrimaryButton("📋 2. FETCH TABLES FROM DATABASE")
        self.btn_pg_fetch_tables.setFixedHeight(40)
        self.btn_pg_fetch_tables.clicked.connect(self._on_pg_fetch_tables)
        act_row.addWidget(self.btn_pg_fetch_tables)

        self.lbl_pg_conn_status = badge("STATUS: NOT TESTED", bg="#FFF3D6", size=7.5)
        act_row.addWidget(self.lbl_pg_conn_status)
        act_row.addStretch()

        lay.addLayout(act_row)

        # Subtle divider
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet(f"background-color:{T.LINE}; min-height:1px; max-height:1px; border:none; margin:4px 0;")
        lay.addWidget(sep1)

        # ─────────────────────────────────────────────────────────────────────
        #  TABLE EXPLORER ROW (CLEAN, BORDERLESS SECTION)
        # ─────────────────────────────────────────────────────────────────────
        tbl_top = QHBoxLayout()
        tbl_top.addWidget(label("SELECT DATABASE TABLE:", 8, T.TEXT, NORMAL, 1.2))
        tbl_top.addStretch()
        self.lbl_pg_table_count = label("No tables fetched yet", 8, T.MUTED, NORMAL)
        tbl_top.addWidget(self.lbl_pg_table_count)
        lay.addLayout(tbl_top)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        self.combo_pg_tables = QComboBox()
        self.combo_pg_tables.addItem("Select a table (click 'FETCH TABLES' above)...")
        self.combo_pg_tables.setFixedHeight(38)
        self.combo_pg_tables.setStyleSheet(
            f"QComboBox {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2}; border-radius:6px; font-weight:bold; font-size:13px; padding:4px 10px; }}"
            f"QComboBox QAbstractItemView {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2}; selection-background-color:{T.ACCENT_LIGHT}; selection-color:{T.TEXT}; }}"
        )
        sel_row.addWidget(self.combo_pg_tables, 1)

        self.btn_pg_show_table = PrimaryButton("👁️ SHOW TABLE")
        self.btn_pg_show_table.setFixedHeight(38)
        self.btn_pg_show_table.clicked.connect(self._on_pg_show_table)
        sel_row.addWidget(self.btn_pg_show_table)

        self.btn_pg_process_table = RetroButton("⚙️ PROCESS TABLE", bg=T.YELLOW, hover_bg="#E5AC00", fg=T.TEXT, height=38)
        self.btn_pg_process_table.clicked.connect(self._on_pg_process_table)
        sel_row.addWidget(self.btn_pg_process_table)

        lay.addLayout(sel_row)

        # Subtle divider
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color:{T.LINE}; min-height:1px; max-height:1px; border:none; margin:4px 0;")
        lay.addWidget(sep2)

        # ─────────────────────────────────────────────────────────────────────
        #  CUSTOM SQL VIEW QUERY (CLEAN, BORDERLESS SECTION)
        # ─────────────────────────────────────────────────────────────────────
        q_top = QHBoxLayout()
        q_top.addWidget(label("CUSTOM SQL VIEW QUERY (READ-ONLY):", 8, T.TEXT, NORMAL, 1.2))
        q_top.addWidget(badge("🔒 STRICT READ-ONLY", bg="#FFF3D6", size=7.0))
        q_top.addStretch()
        lay.addLayout(q_top)

        self.input_pg_query = QPlainTextEdit()
        self.input_pg_query.setPlaceholderText("SELECT * FROM public.sales_records LIMIT 1000;")
        self.input_pg_query.setFixedHeight(72)
        self.input_pg_query.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 8px;"
            f"  font-family: Consolas, monospace;"
            f"  font-size: 13px;"
            f"  font-weight: bold;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        lay.addWidget(self.input_pg_query)

        q_btn_row = QHBoxLayout()
        self.btn_pg_exec_query = PrimaryButton("👁️ EXECUTE VIEW QUERY")
        self.btn_pg_exec_query.setFixedHeight(38)
        self.btn_pg_exec_query.clicked.connect(self._on_pg_execute_query)
        q_btn_row.addWidget(self.btn_pg_exec_query)

        self.lbl_pg_security_alert = badge("READ-ONLY VERIFIED", bg=T.ACCENT_LIGHT, size=7.5)
        q_btn_row.addStretch()
        q_btn_row.addWidget(self.lbl_pg_security_alert)
        lay.addLayout(q_btn_row)

        # ─────────────────────────────────────────────────────────────────────
        #  PAGINATED POSTGRESQL DATA PREVIEW (FILTERING + PAGINATION)
        # ─────────────────────────────────────────────────────────────────────
        lay.addSpacing(6)
        self.pg_preview_container = Card(shadow_color="#DAF8FA", bg_color="#FFFFFF")
        self.pg_preview_container.setVisible(False)  # Hidden initially until user clicks SHOW TABLE or EXECUTE QUERY
        p_lay = QVBoxLayout(self.pg_preview_container)
        p_lay.setContentsMargins(18, 16, 18, 16)
        p_lay.setSpacing(12)

        # 1. Filter bar
        filter_box = QHBoxLayout()
        filter_box.setSpacing(10)

        lbl_pg_f_tag = QLabel("FILTER BY:")
        lbl_pg_f_tag.setFont(F(8, NORMAL, 1.0))
        lbl_pg_f_tag.setStyleSheet(f"color:{T.TEXT}; background:transparent; font-weight:bold;")
        filter_box.addWidget(lbl_pg_f_tag)

        self.combo_pg_filter_col = QComboBox()
        self.combo_pg_filter_col.addItem("All Columns")
        self.combo_pg_filter_col.setFixedHeight(34)
        self.combo_pg_filter_col.setMinimumWidth(130)
        self.combo_pg_filter_col.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 2px 8px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_pg_filter_col.currentIndexChanged.connect(self._on_pg_filter_changed)
        filter_box.addWidget(self.combo_pg_filter_col)

        self.input_pg_filter = QLineEdit()
        self.input_pg_filter.setPlaceholderText("🔍 Search / filter rows in real-time (case-insensitive keyword)...")
        self.input_pg_filter.setFixedHeight(34)
        self.input_pg_filter.setStyleSheet(
            f"QLineEdit {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.input_pg_filter.textChanged.connect(self._on_pg_filter_changed)
        filter_box.addWidget(self.input_pg_filter, 1)

        self.btn_pg_clear_filter = RetroButton("✖ CLEAR", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=34)
        self.btn_pg_clear_filter.setToolTip("Clear search filter text, or click to clear dataset view")
        self.btn_pg_clear_filter.clicked.connect(self._on_pg_clear_filter)
        filter_box.addWidget(self.btn_pg_clear_filter)

        self.lbl_pg_filter_match = badge("ALL ROWS", bg=T.BADGE_PINK, size=7)
        filter_box.addWidget(self.lbl_pg_filter_match)

        p_lay.addLayout(filter_box)

        # 2. Table View (Clean, borderless table, all rows solid white)
        self.pg_preview_table = QTableView()
        self.pg_preview_table.setMinimumHeight(480)
        self.pg_preview_model = PaginatedPolarsTableModel()
        self.pg_preview_table.setModel(self.pg_preview_model)
        self.pg_preview_table.setShowGrid(True)
        self.pg_preview_table.setWordWrap(False)
        self.pg_preview_table.setAlternatingRowColors(False)
        self.pg_preview_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.pg_preview_table.horizontalHeader().setStretchLastSection(True)
        self.pg_preview_table.verticalHeader().setDefaultSectionSize(30)
        self.pg_preview_table.setStyleSheet(
            f"QTableView {{"
            f"  background-color: #FFFFFF;"
            f"  border: none;"
            f"  color: #1A0F13;"
            f"  gridline-color: #EBD3D3;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"  font-size: 13px;"
            f"}}"
            f"QTableView::item {{"
            f"  color: #1A0F13;"
            f"  padding: 6px 12px;"
            f"  border-bottom: 1px solid #F0D5D5;"
            f"}}"
            f"QTableView::item:selected {{"
            f"  background-color: {T.ACCENT_LIGHT};"
            f"  color: #1A0F13;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {T.SURFACE2};"
            f"  color: {T.TEXT};"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  border: none;"
            f"  border-bottom: 2px solid {T.LINE2};"
            f"  border-right: 1px solid {T.LINE};"
            f"  padding: 8px 12px;"
            f"}}"
        )
        p_lay.addWidget(self.pg_preview_table)

        # 3. Pagination Bar (Crisp, fully visible numbers and controls)
        p_nav = QHBoxLayout()
        p_nav.setSpacing(8)

        self.btn_pg_first = RetroButton("⏮ FIRST", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_pg_first.clicked.connect(lambda: self._go_to_pg_page(1))
        p_nav.addWidget(self.btn_pg_first)

        self.btn_pg_prev = RetroButton("◀ PREV", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_pg_prev.clicked.connect(lambda: self._go_to_pg_page(self.pg_preview_model.current_page - 1))
        p_nav.addWidget(self.btn_pg_prev)

        lbl_pg_p_tag = QLabel("PAGE:")
        lbl_pg_p_tag.setFont(F(8, NORMAL))
        lbl_pg_p_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_pg_p_tag)

        self.spin_pg_page = QSpinBox()
        self.spin_pg_page.setRange(1, 1)
        self.spin_pg_page.setValue(1)
        self.spin_pg_page.setFixedHeight(32)
        self.spin_pg_page.setFixedWidth(64)
        self.spin_pg_page.setStyleSheet(
            f"QSpinBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"  padding: 2px 4px;"
            f"}}"
        )
        self.spin_pg_page.valueChanged.connect(self._go_to_pg_page)
        p_nav.addWidget(self.spin_pg_page)

        self.lbl_pg_total_pages = QLabel("of 1")
        self.lbl_pg_total_pages.setFont(F(8.5, NORMAL))
        self.lbl_pg_total_pages.setStyleSheet(f"color: #1A0F13; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_pg_total_pages)

        self.btn_pg_next = RetroButton("NEXT ▶", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_pg_next.clicked.connect(lambda: self._go_to_pg_page(self.pg_preview_model.current_page + 1))
        p_nav.addWidget(self.btn_pg_next)

        self.btn_pg_last = RetroButton("LAST ⏭", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_pg_last.clicked.connect(lambda: self._go_to_pg_page(self.pg_preview_model.total_pages))
        p_nav.addWidget(self.btn_pg_last)

        p_nav.addSpacing(16)
        lbl_pg_sz_tag = QLabel("PAGE SIZE:")
        lbl_pg_sz_tag.setFont(F(8, NORMAL))
        lbl_pg_sz_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_pg_sz_tag)

        self.combo_pg_page_size = QComboBox()
        self.combo_pg_page_size.addItems(["25 rows / page", "50 rows / page", "100 rows / page", "250 rows / page"])
        self.combo_pg_page_size.setCurrentIndex(1)
        self.combo_pg_page_size.setFixedHeight(32)
        self.combo_pg_page_size.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  padding: 2px 6px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_pg_page_size.currentIndexChanged.connect(self._on_pg_page_size_changed)
        p_nav.addWidget(self.combo_pg_page_size)

        p_nav.addStretch()
        self.lbl_pg_page_records = QLabel("No dataset loaded yet")
        self.lbl_pg_page_records.setFont(F(8, NORMAL))
        self.lbl_pg_page_records.setStyleSheet(f"color: {T.MUTED}; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_pg_page_records)

        p_lay.addLayout(p_nav)

        lay.addWidget(self.pg_preview_container)
        lay.addStretch(1)
        return card

    def _sync_postgres_variables(self):
        self.var_postgres_host = self.input_pg_host.text().strip() or "localhost"
        self.var_postgres_port = self.input_pg_port.text().strip() or "5432"
        self.var_postgres_database = self.input_pg_db.text().strip()
        self.var_postgres_username = self.input_pg_user.text().strip()
        self.var_postgres_password = self.input_pg_pass.text()
        self.var_postgres_query = self.input_pg_query.toPlainText().strip()

        page.var_postgres_host = self.var_postgres_host
        page.var_postgres_port = self.var_postgres_port
        page.var_postgres_database = self.var_postgres_database
        page.var_postgres_username = self.var_postgres_username
        page.var_postgres_password = self.var_postgres_password
        page.var_postgres_query = self.var_postgres_query

    def _on_pg_test_connection(self):
        self._sync_postgres_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            ok, msg = adi.PostgreSQL.test_connection()
            if ok:
                self.lbl_pg_conn_status.setText("🟢 CONNECTED SUCCESSFULLY")
                self.lbl_pg_conn_status.setStyleSheet(
                    f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self._notify_action(f"PostgreSQL connection to '{self.var_postgres_database}' succeeded!")
            else:
                self.lbl_pg_conn_status.setText("🔴 CONNECTION FAILED")
                self.lbl_pg_conn_status.setStyleSheet(
                    f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self._notify_action(f"PostgreSQL error: {msg}")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Connection failed"
            self.lbl_pg_conn_status.setText("🔴 CONNECTION FAILED")
            self.lbl_pg_conn_status.setStyleSheet(
                f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._notify_action(f"PostgreSQL error: {err_msg}")

    def _on_pg_fetch_tables(self):
        self._sync_postgres_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            tables = adi.PostgreSQL.fetch_tables()

            self.combo_pg_tables.blockSignals(True)
            self.combo_pg_tables.clear()
            if tables:
                for t in tables:
                    self.combo_pg_tables.addItem(t)
                self.lbl_pg_table_count.setText(f"Found {len(tables)} tables")
                self.lbl_pg_conn_status.setText("🟢 TABLES FETCHED")
                self.lbl_pg_conn_status.setStyleSheet(
                    f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self._notify_action(f"Fetched {len(tables)} tables via all_data_inputs.py")
            else:
                self.combo_pg_tables.addItem("No user tables found in database.")
                self.lbl_pg_table_count.setText("0 tables found")
                self._notify_action("Connected, but 0 base tables found.")
            self.combo_pg_tables.blockSignals(False)
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Failed to fetch tables"
            self.lbl_pg_conn_status.setText("🔴 FETCH FAILED")
            self.lbl_pg_conn_status.setStyleSheet(
                f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._notify_action(f"Failed to fetch tables: {err_msg}")

    def _on_pg_show_table(self):
        tbl = self.combo_pg_tables.currentText().strip()
        if not tbl or tbl.startswith("Select") or tbl.startswith("No user") or tbl.startswith("Error"):
            self._notify_action("⚠️ Please fetch and select a valid table first.")
            return

        self._sync_postgres_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            df = adi.PostgreSQL.fetch_table_data(tbl)
            self.raw_data = df
            page.raw_data = df
            self.input_pg_query.setPlainText(f"SELECT * FROM {tbl} LIMIT 1000;")
            self._display_pg_preview_data(df)
            self._notify_action(f"Loaded {df.height:,} rows × {df.width} cols from {tbl} (via all_data_inputs.py)")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Failed to load table"
            self._notify_action(f"PostgreSQL Query Error: {err_msg}")

    def _on_pg_process_table(self):
        tbl = self.combo_pg_tables.currentText().strip()
        if not tbl or tbl.startswith("Select") or tbl.startswith("No user") or tbl.startswith("Error"):
            self._notify_action("⚠️ Please fetch and select a valid table first.")
            return

        self._sync_postgres_variables()
        self.var_postgres_query = f"SELECT * FROM {tbl};"
        page.var_postgres_query = self.var_postgres_query

        self._notify_action(f"✓ Process Table option triggered for '{tbl}' — Ready for backend logic")
        payload = {
            "action": "process_table",
            "source_type": "postgres",
            "table_name": tbl,
            "host": self.var_postgres_host,
            "port": self.var_postgres_port,
            "database": self.var_postgres_database,
            "username": self.var_postgres_username,
            "query": self.var_postgres_query,
        }
        self.ingest_requested.emit(payload)

    def _on_pg_execute_query(self):
        query = self.input_pg_query.toPlainText().strip()
        if not query:
            self._notify_action("⚠️ Please enter a SQL query.")
            return

        self._sync_postgres_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            df = adi.PostgreSQL.execute_view_query(query)
            self.raw_data = df
            page.raw_data = df
            self.lbl_pg_security_alert.setText("🔒 READ-ONLY: VALIDATED")
            self.lbl_pg_security_alert.setStyleSheet(
                f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._display_pg_preview_data(df)
            self._notify_action(f"Loaded {df.height:,} rows × {df.width} cols (via all_data_inputs.py)")
        except PermissionError as pe:
            self.lbl_pg_security_alert.setText(f"🚫 {pe}")
            self.lbl_pg_security_alert.setStyleSheet(
                f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._notify_action(f"Blocked by security rule: {pe}")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Query execution failed"
            self._notify_action(f"PostgreSQL Query Error: {err_msg}")

    def _display_pg_preview_data(self, df: pl.DataFrame):
        self.pg_preview_container.setVisible(True)
        self.panels_stack.updateGeometry()
        self.pg_preview_model.set_dataframe(df)
        self._update_pg_filter_columns()
        self._update_pg_pagination_ui()
        self.pg_preview_table.resizeColumnsToContents()

    def _update_pg_filter_columns(self):
        current_selection = self.combo_pg_filter_col.currentText()
        self.combo_pg_filter_col.blockSignals(True)
        self.combo_pg_filter_col.clear()
        self.combo_pg_filter_col.addItem("All Columns")
        if self.pg_preview_model._full_df is not None:
            for c in self.pg_preview_model._full_df.columns:
                self.combo_pg_filter_col.addItem(str(c))
        idx = self.combo_pg_filter_col.findText(current_selection)
        if idx >= 0:
            self.combo_pg_filter_col.setCurrentIndex(idx)
        else:
            self.combo_pg_filter_col.setCurrentIndex(0)
        self.combo_pg_filter_col.blockSignals(False)

    def _on_pg_filter_changed(self):
        query = self.input_pg_filter.text()
        col = self.combo_pg_filter_col.currentText()
        self.pg_preview_model.set_filter(query, col)
        self._update_pg_pagination_ui()

    def _on_pg_clear_filter(self):
        has_filter = bool(self.input_pg_filter.text().strip())
        self.input_pg_filter.blockSignals(True)
        self.input_pg_filter.clear()
        self.input_pg_filter.blockSignals(False)
        self.combo_pg_filter_col.blockSignals(True)
        self.combo_pg_filter_col.setCurrentIndex(0)
        self.combo_pg_filter_col.blockSignals(False)
        self.pg_preview_model.set_filter("", "All Columns")

        if not has_filter:
            # When filter is already empty, CLEAR clears the loaded preview dataset
            self.pg_preview_model.set_dataframe(None)
            self.raw_data = None
            page.raw_data = None
            self.pg_preview_container.setVisible(False)
            self.panels_stack.updateGeometry()
            self._notify_action("✓ PostgreSQL data preview cleared.")

        self._update_pg_pagination_ui()
        self.pg_preview_table.viewport().update()

    def _go_to_pg_page(self, page_num: int):
        self.pg_preview_model.set_page(page_num)
        self._update_pg_pagination_ui()

    def _on_pg_page_size_changed(self, idx: int):
        sizes = [25, 50, 100, 250]
        size = sizes[idx] if idx < len(sizes) else 50
        self.pg_preview_model.set_page_size(size)
        self._update_pg_pagination_ui()

    def _update_pg_pagination_ui(self):
        m = self.pg_preview_model
        total_p = m.total_pages
        curr_p = m.current_page

        self.spin_pg_page.blockSignals(True)
        self.spin_pg_page.setRange(1, total_p)
        self.spin_pg_page.setValue(curr_p)
        self.spin_pg_page.blockSignals(False)

        self.lbl_pg_total_pages.setText(f"of {total_p:,}")
        self.btn_pg_first.setEnabled(curr_p > 1)
        self.btn_pg_prev.setEnabled(curr_p > 1)
        self.btn_pg_next.setEnabled(curr_p < total_p)
        self.btn_pg_last.setEnabled(curr_p < total_p)

        total_rows = m._filtered_df.height if m._filtered_df is not None else 0
        full_rows = m._full_df.height if m._full_df is not None else 0

        if full_rows == 0:
            self.lbl_pg_page_records.setText("No dataset loaded yet")
            self.lbl_pg_filter_match.setText("NO DATA")
        elif total_rows == 0:
            self.lbl_pg_page_records.setText("0 matching rows found")
            self.lbl_pg_filter_match.setText("0 MATCHES")
            self.lbl_pg_filter_match.setStyleSheet(
                f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
            )
        else:
            start_row = (curr_p - 1) * m.page_size + 1
            end_row = min(curr_p * m.page_size, total_rows)
            filter_suffix = f" (filtered from {full_rows:,})" if total_rows != full_rows else ""
            self.lbl_pg_page_records.setText(f"Showing {start_row:,}–{end_row:,} of {total_rows:,} rows{filter_suffix}")
            if total_rows != full_rows:
                self.lbl_pg_filter_match.setText(f"{total_rows:,} MATCHES")
                self.lbl_pg_filter_match.setStyleSheet(
                    f"background:{T.YELLOW};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;font-weight:bold;"
                )
            else:
                self.lbl_pg_filter_match.setText(f"ALL {full_rows:,} ROWS")
                self.lbl_pg_filter_match.setStyleSheet(
                    f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
                )

    # ═════════════════════════════════════════════════════════════════════════
    #  PANEL 3: MSSQL SERVER INGESTION
    # ═════════════════════════════════════════════════════════════════════════
    def _build_mssql_panel(self) -> Card:
        card = Card(shadow_color="#FFF3D6", bg_color="#FFFFFF")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        # Connection grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        # Server
        grid.addWidget(label("MSSQL SERVER / HOST", 8, T.TEXT, NORMAL, 1.2), 0, 0)
        self.input_ms_server = QLineEdit("localhost")
        self.input_ms_server.setFixedHeight(36)
        grid.addWidget(self.input_ms_server, 1, 0)

        # Port
        grid.addWidget(label("PORT", 8, T.TEXT, NORMAL, 1.2), 0, 1)
        self.input_ms_port = QLineEdit("1433")
        self.input_ms_port.setFixedHeight(36)
        grid.addWidget(self.input_ms_port, 1, 1)

        # Database
        grid.addWidget(label("DATABASE NAME", 8, T.TEXT, NORMAL, 1.2), 0, 2)
        self.input_ms_db = QLineEdit()
        self.input_ms_db.setPlaceholderText("EnterpriseDB")
        self.input_ms_db.setFixedHeight(36)
        grid.addWidget(self.input_ms_db, 1, 2)

        # Username
        grid.addWidget(label("USERNAME (SA / SQL AUTH)", 8, T.TEXT, NORMAL, 1.2), 2, 0)
        self.input_ms_user = QLineEdit("sa")
        self.input_ms_user.setFixedHeight(36)
        grid.addWidget(self.input_ms_user, 3, 0)

        # Password
        grid.addWidget(label("PASSWORD", 8, T.TEXT, NORMAL, 1.2), 2, 1)
        self.input_ms_pass = QLineEdit()
        self.input_ms_pass.setEchoMode(QLineEdit.Password)
        self.input_ms_pass.setPlaceholderText("••••••••")
        self.input_ms_pass.setFixedHeight(36)
        grid.addWidget(self.input_ms_pass, 3, 1)

        lay.addLayout(grid)

        # Action Buttons Row: 1. TEST CONNECTION  2. FETCH TABLES FROM DATABASE
        act_row = QHBoxLayout()
        act_row.setSpacing(12)

        self.btn_ms_test_conn = RetroButton("🔌 1. TEST CONNECTION", bg=T.YELLOW, hover_bg="#E5AC00", fg=T.TEXT, height=40)
        self.btn_ms_test_conn.clicked.connect(self._on_ms_test_connection)
        act_row.addWidget(self.btn_ms_test_conn)

        self.btn_ms_fetch_tables = PrimaryButton("📋 2. FETCH TABLES FROM DATABASE")
        self.btn_ms_fetch_tables.setFixedHeight(40)
        self.btn_ms_fetch_tables.clicked.connect(self._on_ms_fetch_tables)
        act_row.addWidget(self.btn_ms_fetch_tables)

        self.lbl_ms_conn_status = badge("STATUS: NOT TESTED", bg="#FFF3D6", size=7.5)
        act_row.addWidget(self.lbl_ms_conn_status)
        act_row.addStretch()

        lay.addLayout(act_row)

        # Subtle divider
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet(f"background-color:{T.LINE}; min-height:1px; max-height:1px; border:none; margin:4px 0;")
        lay.addWidget(sep1)

        # ─────────────────────────────────────────────────────────────────────
        #  TABLE EXPLORER ROW (CLEAN, BORDERLESS SECTION)
        # ─────────────────────────────────────────────────────────────────────
        tbl_top = QHBoxLayout()
        tbl_top.addWidget(label("SELECT MSSQL TABLE:", 8, T.TEXT, NORMAL, 1.2))
        tbl_top.addStretch()
        self.lbl_ms_table_count = label("No tables fetched yet", 8, T.MUTED, NORMAL)
        tbl_top.addWidget(self.lbl_ms_table_count)
        lay.addLayout(tbl_top)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        self.combo_ms_tables = QComboBox()
        self.combo_ms_tables.addItem("Select a table (click 'FETCH TABLES' above)...")
        self.combo_ms_tables.setFixedHeight(38)
        self.combo_ms_tables.setStyleSheet(
            f"QComboBox {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2}; border-radius:6px; font-weight:bold; font-size:13px; padding:4px 10px; }}"
            f"QComboBox QAbstractItemView {{ background:#FFFFFF; color:{T.TEXT}; border:2px solid {T.LINE2}; selection-background-color:{T.ACCENT_LIGHT}; selection-color:{T.TEXT}; }}"
        )
        sel_row.addWidget(self.combo_ms_tables, 1)

        self.btn_ms_show_table = PrimaryButton("👁️ SHOW TABLE")
        self.btn_ms_show_table.setFixedHeight(38)
        self.btn_ms_show_table.clicked.connect(self._on_ms_show_table)
        sel_row.addWidget(self.btn_ms_show_table)

        self.btn_ms_process_table = RetroButton("⚙️ PROCESS TABLE", bg=T.YELLOW, hover_bg="#E5AC00", fg=T.TEXT, height=38)
        self.btn_ms_process_table.clicked.connect(self._on_ms_process_table)
        sel_row.addWidget(self.btn_ms_process_table)

        lay.addLayout(sel_row)

        # Subtle divider
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background-color:{T.LINE}; min-height:1px; max-height:1px; border:none; margin:4px 0;")
        lay.addWidget(sep2)

        # ─────────────────────────────────────────────────────────────────────
        #  CUSTOM SQL VIEW QUERY (CLEAN, BORDERLESS SECTION)
        # ─────────────────────────────────────────────────────────────────────
        q_top = QHBoxLayout()
        q_top.addWidget(label("CUSTOM T-SQL VIEW QUERY (READ-ONLY):", 8, T.TEXT, NORMAL, 1.2))
        q_top.addWidget(badge("🔒 STRICT READ-ONLY", bg="#FFF3D6", size=7.0))
        q_top.addStretch()
        lay.addLayout(q_top)

        self.input_ms_query = QPlainTextEdit()
        self.input_ms_query.setPlaceholderText("SELECT TOP 1000 * FROM dbo.Orders;")
        self.input_ms_query.setFixedHeight(72)
        self.input_ms_query.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 8px;"
            f"  font-family: Consolas, monospace;"
            f"  font-size: 13px;"
            f"  font-weight: bold;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        lay.addWidget(self.input_ms_query)

        q_btn_row = QHBoxLayout()
        self.btn_ms_exec_query = PrimaryButton("👁️ EXECUTE VIEW QUERY")
        self.btn_ms_exec_query.setFixedHeight(38)
        self.btn_ms_exec_query.clicked.connect(self._on_ms_execute_query)
        q_btn_row.addWidget(self.btn_ms_exec_query)

        self.lbl_ms_security_alert = badge("READ-ONLY VERIFIED", bg=T.ACCENT_LIGHT, size=7.5)
        q_btn_row.addStretch()
        q_btn_row.addWidget(self.lbl_ms_security_alert)
        lay.addLayout(q_btn_row)

        # ─────────────────────────────────────────────────────────────────────
        #  PAGINATED MSSQL DATA PREVIEW (FILTERING + PAGINATION)
        # ─────────────────────────────────────────────────────────────────────
        lay.addSpacing(6)
        self.ms_preview_container = Card(shadow_color="#FFF3D6", bg_color="#FFFFFF")
        self.ms_preview_container.setVisible(False)  # Hidden initially until user clicks SHOW TABLE or EXECUTE QUERY
        p_lay = QVBoxLayout(self.ms_preview_container)
        p_lay.setContentsMargins(18, 16, 18, 16)
        p_lay.setSpacing(12)

        # 1. Filter bar
        filter_box = QHBoxLayout()
        filter_box.setSpacing(10)

        lbl_ms_f_tag = QLabel("FILTER BY:")
        lbl_ms_f_tag.setFont(F(8, NORMAL, 1.0))
        lbl_ms_f_tag.setStyleSheet(f"color:{T.TEXT}; background:transparent; font-weight:bold;")
        filter_box.addWidget(lbl_ms_f_tag)

        self.combo_ms_filter_col = QComboBox()
        self.combo_ms_filter_col.addItem("All Columns")
        self.combo_ms_filter_col.setFixedHeight(34)
        self.combo_ms_filter_col.setMinimumWidth(130)
        self.combo_ms_filter_col.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 2px 8px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_ms_filter_col.currentIndexChanged.connect(self._on_ms_filter_changed)
        filter_box.addWidget(self.combo_ms_filter_col)

        self.input_ms_filter = QLineEdit()
        self.input_ms_filter.setPlaceholderText("🔍 Search / filter rows in real-time (case-insensitive keyword)...")
        self.input_ms_filter.setFixedHeight(34)
        self.input_ms_filter.setStyleSheet(
            f"QLineEdit {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.input_ms_filter.textChanged.connect(self._on_ms_filter_changed)
        filter_box.addWidget(self.input_ms_filter, 1)

        self.btn_ms_clear_filter = RetroButton("✖ CLEAR", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=34)
        self.btn_ms_clear_filter.setToolTip("Clear search filter text, or click to clear dataset view")
        self.btn_ms_clear_filter.clicked.connect(self._on_ms_clear_filter)
        filter_box.addWidget(self.btn_ms_clear_filter)

        self.lbl_ms_filter_match = badge("ALL ROWS", bg=T.BADGE_PINK, size=7)
        filter_box.addWidget(self.lbl_ms_filter_match)

        p_lay.addLayout(filter_box)

        # 2. Table View (Clean, borderless table, all rows solid white)
        self.ms_preview_table = QTableView()
        self.ms_preview_table.setMinimumHeight(480)
        self.ms_preview_model = PaginatedPolarsTableModel()
        self.ms_preview_table.setModel(self.ms_preview_model)
        self.ms_preview_table.setShowGrid(True)
        self.ms_preview_table.setWordWrap(False)
        self.ms_preview_table.setAlternatingRowColors(False)
        self.ms_preview_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.ms_preview_table.horizontalHeader().setStretchLastSection(True)
        self.ms_preview_table.verticalHeader().setDefaultSectionSize(30)
        self.ms_preview_table.setStyleSheet(
            f"QTableView {{"
            f"  background-color: #FFFFFF;"
            f"  border: none;"
            f"  color: #1A0F13;"
            f"  gridline-color: #EBD3D3;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"  font-size: 13px;"
            f"}}"
            f"QTableView::item {{"
            f"  color: #1A0F13;"
            f"  padding: 6px 12px;"
            f"  border-bottom: 1px solid #F0D5D5;"
            f"}}"
            f"QTableView::item:selected {{"
            f"  background-color: {T.ACCENT_LIGHT};"
            f"  color: #1A0F13;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {T.SURFACE2};"
            f"  color: {T.TEXT};"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  border: none;"
            f"  border-bottom: 2px solid {T.LINE2};"
            f"  border-right: 1px solid {T.LINE};"
            f"  padding: 8px 12px;"
            f"}}"
        )
        p_lay.addWidget(self.ms_preview_table)

        # 3. Pagination Bar (Crisp, fully visible numbers and controls)
        p_nav = QHBoxLayout()
        p_nav.setSpacing(8)

        self.btn_ms_first = RetroButton("⏮ FIRST", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_ms_first.clicked.connect(lambda: self._go_to_ms_page(1))
        p_nav.addWidget(self.btn_ms_first)

        self.btn_ms_prev = RetroButton("◀ PREV", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_ms_prev.clicked.connect(lambda: self._go_to_ms_page(self.ms_preview_model.current_page - 1))
        p_nav.addWidget(self.btn_ms_prev)

        lbl_ms_p_tag = QLabel("PAGE:")
        lbl_ms_p_tag.setFont(F(8, NORMAL))
        lbl_ms_p_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_ms_p_tag)

        self.spin_ms_page = QSpinBox()
        self.spin_ms_page.setRange(1, 1)
        self.spin_ms_page.setValue(1)
        self.spin_ms_page.setFixedHeight(32)
        self.spin_ms_page.setFixedWidth(64)
        self.spin_ms_page.setStyleSheet(
            f"QSpinBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"  padding: 2px 4px;"
            f"}}"
        )
        self.spin_ms_page.valueChanged.connect(self._go_to_ms_page)
        p_nav.addWidget(self.spin_ms_page)

        self.lbl_ms_total_pages = QLabel("of 1")
        self.lbl_ms_total_pages.setFont(F(8.5, NORMAL))
        self.lbl_ms_total_pages.setStyleSheet(f"color: #1A0F13; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_ms_total_pages)

        self.btn_ms_next = RetroButton("NEXT ▶", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_ms_next.clicked.connect(lambda: self._go_to_ms_page(self.ms_preview_model.current_page + 1))
        p_nav.addWidget(self.btn_ms_next)

        self.btn_ms_last = RetroButton("LAST ⏭", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_ms_last.clicked.connect(lambda: self._go_to_ms_page(self.ms_preview_model.total_pages))
        p_nav.addWidget(self.btn_ms_last)

        p_nav.addSpacing(16)
        lbl_ms_sz_tag = QLabel("PAGE SIZE:")
        lbl_ms_sz_tag.setFont(F(8, NORMAL))
        lbl_ms_sz_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_ms_sz_tag)

        self.combo_ms_page_size = QComboBox()
        self.combo_ms_page_size.addItems(["25 rows / page", "50 rows / page", "100 rows / page", "250 rows / page"])
        self.combo_ms_page_size.setCurrentIndex(1)
        self.combo_ms_page_size.setFixedHeight(32)
        self.combo_ms_page_size.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  padding: 2px 6px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_ms_page_size.currentIndexChanged.connect(self._on_ms_page_size_changed)
        p_nav.addWidget(self.combo_ms_page_size)

        p_nav.addStretch()
        self.lbl_ms_page_records = QLabel("No dataset loaded yet")
        self.lbl_ms_page_records.setFont(F(8, NORMAL))
        self.lbl_ms_page_records.setStyleSheet(f"color: {T.MUTED}; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_ms_page_records)

        p_lay.addLayout(p_nav)

        lay.addWidget(self.ms_preview_container)
        lay.addStretch(1)
        return card

    def _sync_mssql_variables(self):
        self.var_mssql_server = self.input_ms_server.text().strip() or "localhost"
        self.var_mssql_port = self.input_ms_port.text().strip() or "1433"
        self.var_mssql_database = self.input_ms_db.text().strip()
        self.var_mssql_username = self.input_ms_user.text().strip()
        self.var_mssql_password = self.input_ms_pass.text()
        self.var_mssql_query = self.input_ms_query.toPlainText().strip()

        page.var_mssql_server = self.var_mssql_server
        page.var_mssql_port = self.var_mssql_port
        page.var_mssql_database = self.var_mssql_database
        page.var_mssql_username = self.var_mssql_username
        page.var_mssql_password = self.var_mssql_password
        page.var_mssql_query = self.var_mssql_query

    def _on_ms_test_connection(self):
        self._sync_mssql_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            ok, msg = adi.MsSQL.test_connections()
            if ok:
                self.lbl_ms_conn_status.setText("🟢 CONNECTED SUCCESSFULLY")
                self.lbl_ms_conn_status.setStyleSheet(
                    f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self._notify_action(f"MSSQL connection to '{self.var_mssql_database}' succeeded!")
            else:
                self.lbl_ms_conn_status.setText("🔴 CONNECTION FAILED")
                self.lbl_ms_conn_status.setStyleSheet(
                    f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self._notify_action(f"MSSQL error: {msg}")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Connection failed"
            self.lbl_ms_conn_status.setText("🔴 CONNECTION FAILED")
            self.lbl_ms_conn_status.setStyleSheet(
                f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._notify_action(f"MSSQL error: {err_msg}")

    def _on_ms_fetch_tables(self):
        self._sync_mssql_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            tables = adi.MsSQL.fetch_tables()

            self.combo_ms_tables.blockSignals(True)
            self.combo_ms_tables.clear()
            if tables:
                for t in tables:
                    self.combo_ms_tables.addItem(t)
                self.lbl_ms_table_count.setText(f"Found {len(tables)} tables")
                self.lbl_ms_conn_status.setText("🟢 TABLES FETCHED")
                self.lbl_ms_conn_status.setStyleSheet(
                    f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
                )
                self._notify_action(f"Fetched {len(tables)} tables via all_data_inputs.py")
            else:
                self.combo_ms_tables.addItem("No user tables found in database.")
                self.lbl_ms_table_count.setText("0 tables found")
                self._notify_action("Connected, but 0 base tables found.")
            self.combo_ms_tables.blockSignals(False)
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Failed to fetch tables"
            self.lbl_ms_conn_status.setText("🔴 FETCH FAILED")
            self.lbl_ms_conn_status.setStyleSheet(
                f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._notify_action(f"Failed to fetch tables: {err_msg}")

    def _on_ms_show_table(self):
        tbl = self.combo_ms_tables.currentText().strip()
        if not tbl or tbl.startswith("Select") or tbl.startswith("No user") or tbl.startswith("Error"):
            self._notify_action("⚠️ Please fetch and select a valid table first.")
            return

        self._sync_mssql_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            df = adi.MsSQL.fetch_table_data(tbl)
            self.raw_data = df
            page.raw_data = df
            self.input_ms_query.setPlainText(f"SELECT TOP 1000 * FROM {tbl};")
            self._display_ms_preview_data(df)
            self._notify_action(f"Loaded {df.height:,} rows × {df.width} cols from {tbl} (via all_data_inputs.py)")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Failed to load table"
            self._notify_action(f"MSSQL Query Error: {err_msg}")

    def _on_ms_process_table(self):
        tbl = self.combo_ms_tables.currentText().strip()
        if not tbl or tbl.startswith("Select") or tbl.startswith("No user") or tbl.startswith("Error"):
            self._notify_action("⚠️ Please fetch and select a valid table first.")
            return

        self._sync_mssql_variables()
        self.var_mssql_query = f"SELECT TOP 1000 * FROM {tbl};"
        page.var_mssql_query = self.var_mssql_query

        self._notify_action(f"✓ Process Table option triggered for '{tbl}' — Ready for backend logic")
        payload = {
            "action": "process_table",
            "source_type": "mssql",
            "table_name": tbl,
            "server": self.var_mssql_server,
            "port": self.var_mssql_port,
            "database": self.var_mssql_database,
            "username": self.var_mssql_username,
            "query": self.var_mssql_query,
        }
        self.ingest_requested.emit(payload)

    def _on_ms_execute_query(self):
        query = self.input_ms_query.toPlainText().strip()
        if not query:
            self._notify_action("⚠️ Please enter a SQL query.")
            return

        self._sync_mssql_variables()
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            df = adi.MsSQL.execute_view_query(query)
            self.raw_data = df
            page.raw_data = df
            self.lbl_ms_security_alert.setText("🔒 READ-ONLY: VALIDATED")
            self.lbl_ms_security_alert.setStyleSheet(
                f"background:{T.POS};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._display_ms_preview_data(df)
            self._notify_action(f"Loaded {df.height:,} rows × {df.width} cols (via all_data_inputs.py)")
        except PermissionError as pe:
            self.lbl_ms_security_alert.setText(f"🚫 {pe}")
            self.lbl_ms_security_alert.setStyleSheet(
                f"background:{T.NEG};color:#FFFFFF;border:2px solid {T.LINE2};border-radius:4px;padding:3px 10px;font-weight:bold;"
            )
            self._notify_action(f"Blocked by security rule: {pe}")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Query execution failed"
            self._notify_action(f"MSSQL Query Error: {err_msg}")

    def _display_ms_preview_data(self, df: pl.DataFrame):
        self.ms_preview_container.setVisible(True)
        self.panels_stack.updateGeometry()
        self.ms_preview_model.set_dataframe(df)
        self._update_ms_filter_columns()
        self._update_ms_pagination_ui()
        self.ms_preview_table.resizeColumnsToContents()

    def _update_ms_filter_columns(self):
        current_selection = self.combo_ms_filter_col.currentText()
        self.combo_ms_filter_col.blockSignals(True)
        self.combo_ms_filter_col.clear()
        self.combo_ms_filter_col.addItem("All Columns")
        if self.ms_preview_model._full_df is not None:
            for c in self.ms_preview_model._full_df.columns:
                self.combo_ms_filter_col.addItem(str(c))
        idx = self.combo_ms_filter_col.findText(current_selection)
        if idx >= 0:
            self.combo_ms_filter_col.setCurrentIndex(idx)
        else:
            self.combo_ms_filter_col.setCurrentIndex(0)
        self.combo_ms_filter_col.blockSignals(False)

    def _on_ms_filter_changed(self):
        query = self.input_ms_filter.text()
        col = self.combo_ms_filter_col.currentText()
        self.ms_preview_model.set_filter(query, col)
        self._update_ms_pagination_ui()

    def _on_ms_clear_filter(self):
        has_filter = bool(self.input_ms_filter.text().strip())
        self.input_ms_filter.blockSignals(True)
        self.input_ms_filter.clear()
        self.input_ms_filter.blockSignals(False)
        self.combo_ms_filter_col.blockSignals(True)
        self.combo_ms_filter_col.setCurrentIndex(0)
        self.combo_ms_filter_col.blockSignals(False)
        self.ms_preview_model.set_filter("", "All Columns")

        if not has_filter:
            # When filter is already empty, CLEAR clears the loaded preview dataset
            self.ms_preview_model.set_dataframe(None)
            self.raw_data = None
            page.raw_data = None
            self.ms_preview_container.setVisible(False)
            self.panels_stack.updateGeometry()
            self._notify_action("✓ MSSQL data preview cleared.")

        self._update_ms_pagination_ui()
        self.ms_preview_table.viewport().update()

    def _go_to_ms_page(self, page_num: int):
        self.ms_preview_model.set_page(page_num)
        self._update_ms_pagination_ui()

    def _on_ms_page_size_changed(self, idx: int):
        sizes = [25, 50, 100, 250]
        size = sizes[idx] if idx < len(sizes) else 50
        self.ms_preview_model.set_page_size(size)
        self._update_ms_pagination_ui()

    def _update_ms_pagination_ui(self):
        m = self.ms_preview_model
        total_p = m.total_pages
        curr_p = m.current_page

        self.spin_ms_page.blockSignals(True)
        self.spin_ms_page.setRange(1, total_p)
        self.spin_ms_page.setValue(curr_p)
        self.spin_ms_page.blockSignals(False)

        self.lbl_ms_total_pages.setText(f"of {total_p:,}")
        self.btn_ms_first.setEnabled(curr_p > 1)
        self.btn_ms_prev.setEnabled(curr_p > 1)
        self.btn_ms_next.setEnabled(curr_p < total_p)
        self.btn_last.setEnabled(curr_p < total_p)

        total_rows = m._filtered_df.height if m._filtered_df is not None else 0
        full_rows = m._full_df.height if m._full_df is not None else 0

        if full_rows == 0:
            self.lbl_ms_page_records.setText("No dataset loaded yet")
            self.lbl_ms_filter_match.setText("NO DATA")
        elif total_rows == 0:
            self.lbl_ms_page_records.setText("0 matching rows found")
            self.lbl_ms_filter_match.setText("0 MATCHES")
            self.lbl_ms_filter_match.setStyleSheet(
                f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
            )
        else:
            start_row = (curr_p - 1) * m.page_size + 1
            end_row = min(curr_p * m.page_size, total_rows)
            filter_suffix = f" (filtered from {full_rows:,})" if total_rows != full_rows else ""
            self.lbl_ms_page_records.setText(f"Showing {start_row:,}–{end_row:,} of {total_rows:,} rows{filter_suffix}")
            if total_rows != full_rows:
                self.lbl_ms_filter_match.setText(f"{total_rows:,} MATCHES")
                self.lbl_ms_filter_match.setStyleSheet(
                    f"background:{T.YELLOW};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;font-weight:bold;"
                )
            else:
                self.lbl_ms_filter_match.setText(f"ALL {full_rows:,} ROWS")
                self.lbl_ms_filter_match.setStyleSheet(
                    f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
                )

    # ═════════════════════════════════════════════════════════════════════════
    #  PANEL 4: REST API INGESTION
    # ═════════════════════════════════════════════════════════════════════════
    def _build_api_panel(self) -> Card:
        card = Card(shadow_color="#F8D2D2", bg_color="#FFFFFF")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        tag = badge("SOURCE TYPE: REST API ENDPOINT", bg=T.BADGE_PINK, size=8)
        lay.addWidget(tag, 0, Qt.AlignLeft)

        # URL + Method row
        url_row = QHBoxLayout()
        url_row.setSpacing(12)

        self.combo_api_method = QComboBox()
        self.combo_api_method.addItems(["GET", "POST"])
        self.combo_api_method.setFixedSize(90, 40)
        self.combo_api_method.setStyleSheet(
            f"QComboBox {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:6px; font-weight:bold; padding-left:12px; }}"
        )
        url_row.addWidget(self.combo_api_method)

        self.input_api_url = QLineEdit()
        self.input_api_url.setPlaceholderText("https://api.example.com/v1/analytics/records?format=json")
        self.input_api_url.setFixedHeight(40)
        url_row.addWidget(self.input_api_url, 1)

        lay.addLayout(url_row)

        # Headers & Body
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        lbl_headers = label("REQUEST HEADERS (JSON OR KEY: VALUE)", 8, T.TEXT, NORMAL, 1.2)
        lbl_headers.setFixedHeight(18)
        grid.addWidget(lbl_headers, 0, 0)
        self.input_api_headers = QPlainTextEdit()
        self.input_api_headers.setPlaceholderText('{\n  "Authorization": "Bearer YOUR_TOKEN",\n  "Accept": "application/json"\n}')
        self.input_api_headers.setFixedHeight(80)
        self.input_api_headers.setStyleSheet(
            f"QPlainTextEdit {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:6px; padding:8px; font-family:Consolas, monospace; }}"
        )
        grid.addWidget(self.input_api_headers, 1, 0)

        lbl_payload = label("BODY PAYLOAD / QUERY PARAMS (FOR POST)", 8, T.TEXT, NORMAL, 1.2)
        lbl_payload.setFixedHeight(18)
        grid.addWidget(lbl_payload, 0, 1)
        self.input_api_payload = QPlainTextEdit()
        self.input_api_payload.setPlaceholderText('{\n  "limit": 1000,\n  "filter": "active"\n}')
        self.input_api_payload.setFixedHeight(80)
        self.input_api_payload.setStyleSheet(
            f"QPlainTextEdit {{ background:#FFFFFF; border:2px solid {T.LINE2}; border-radius:6px; padding:8px; font-family:Consolas, monospace; }}"
        )
        grid.addWidget(self.input_api_payload, 1, 1)

        lay.addLayout(grid)

        # Action Buttons: 1. SHOW DATA  2. PROCESS DATA
        lay.addSpacing(6)
        act_row = QHBoxLayout()
        act_row.setSpacing(14)

        # Option 1: SHOW DATA (Fetches and renders tabular preview)
        self.btn_api_show_data = PrimaryButton("👁️ SHOW DATA")
        self.btn_api_show_data.setFixedHeight(44)
        self.btn_api_show_data.clicked.connect(self._on_api_show_data_clicked)
        act_row.addWidget(self.btn_api_show_data, 1)

        # Option 2: PROCESS DATA (Dispatches parameters for backend processing)
        self.btn_api_process_data = RetroButton("⚙️ PROCESS DATA", bg=T.YELLOW, hover_bg="#E5AC00", fg=T.TEXT, height=44)
        self.btn_api_process_data.clicked.connect(self._on_api_process_data_clicked)
        act_row.addWidget(self.btn_api_process_data, 1)

        # Backward compatibility alias
        self.btn_ingest_api = self.btn_api_show_data

        lay.addLayout(act_row)

        # ─────────────────────────────────────────────────────────────────────
        #  INTERACTIVE PAGINATED DATA PREVIEW CONTAINER (REST API TABULAR VIEW)
        # ─────────────────────────────────────────────────────────────────────
        lay.addSpacing(10)
        self.api_preview_container = Card(shadow_color="#F8D2D2", bg_color="#FFFFFF")
        self.api_preview_container.setVisible(False)  # Hidden initially until user clicks SHOW DATA
        p_lay = QVBoxLayout(self.api_preview_container)
        p_lay.setContentsMargins(18, 16, 18, 16)
        p_lay.setSpacing(12)

        # 1. Real-time Filter Bar
        filter_box = QHBoxLayout()
        filter_box.setSpacing(10)

        lbl_api_f_tag = QLabel("FILTER BY:")
        lbl_api_f_tag.setFont(F(8, NORMAL, 1.0))
        lbl_api_f_tag.setStyleSheet(f"color:{T.TEXT}; background:transparent; font-weight:bold;")
        filter_box.addWidget(lbl_api_f_tag)

        self.combo_api_filter_col = QComboBox()
        self.combo_api_filter_col.addItem("All Columns")
        self.combo_api_filter_col.setFixedHeight(34)
        self.combo_api_filter_col.setMinimumWidth(130)
        self.combo_api_filter_col.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 2px 8px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_api_filter_col.currentIndexChanged.connect(self._on_api_filter_changed)
        filter_box.addWidget(self.combo_api_filter_col)

        self.input_api_filter = QLineEdit()
        self.input_api_filter.setPlaceholderText("🔍 Search / filter rows in real-time (case-insensitive keyword)...")
        self.input_api_filter.setFixedHeight(34)
        self.input_api_filter.setStyleSheet(
            f"QLineEdit {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 6px;"
            f"  padding: 4px 10px;"
            f"  font-size: 12px;"
            f"}}"
        )
        self.input_api_filter.textChanged.connect(self._on_api_filter_changed)
        filter_box.addWidget(self.input_api_filter, 1)

        self.btn_api_clear_filter = RetroButton("✖ CLEAR", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=34)
        self.btn_api_clear_filter.setToolTip("Clear search filter text, or click to clear dataset view")
        self.btn_api_clear_filter.clicked.connect(self._on_api_clear_filter)
        filter_box.addWidget(self.btn_api_clear_filter)

        self.lbl_api_filter_match = badge("ALL ROWS", bg=T.BADGE_PINK, size=7)
        filter_box.addWidget(self.lbl_api_filter_match)

        p_lay.addLayout(filter_box)

        # 2. Interactive Table View (Clean, borderless, uniform white rows)
        self.api_preview_table = QTableView()
        self.api_preview_table.setMinimumHeight(480)
        self.api_preview_model = PaginatedPolarsTableModel()
        self.api_preview_table.setModel(self.api_preview_model)
        self.api_preview_table.setShowGrid(True)
        self.api_preview_table.setWordWrap(False)
        self.api_preview_table.setAlternatingRowColors(False)
        self.api_preview_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.api_preview_table.horizontalHeader().setStretchLastSection(True)
        self.api_preview_table.verticalHeader().setDefaultSectionSize(30)
        self.api_preview_table.setStyleSheet(
            f"QTableView {{"
            f"  background-color: #FFFFFF;"
            f"  border: none;"
            f"  color: #1A0F13;"
            f"  gridline-color: #EBD3D3;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"  font-size: 13px;"
            f"}}"
            f"QTableView::item {{"
            f"  color: #1A0F13;"
            f"  padding: 6px 12px;"
            f"  border-bottom: 1px solid #F0D5D5;"
            f"}}"
            f"QTableView::item:selected {{"
            f"  background-color: {T.ACCENT_LIGHT};"
            f"  color: #1A0F13;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: {T.SURFACE2};"
            f"  color: {T.TEXT};"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  border: none;"
            f"  border-bottom: 2px solid {T.LINE2};"
            f"  border-right: 1px solid {T.LINE};"
            f"  padding: 8px 12px;"
            f"}}"
        )
        p_lay.addWidget(self.api_preview_table)

        # 3. Pagination Controls Bar
        p_nav = QHBoxLayout()
        p_nav.setSpacing(8)

        self.btn_api_first = RetroButton("⏮ FIRST", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_api_first.clicked.connect(lambda: self._go_to_api_page(1))
        p_nav.addWidget(self.btn_api_first)

        self.btn_api_prev = RetroButton("◀ PREV", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_api_prev.clicked.connect(lambda: self._go_to_api_page(self.api_preview_model.current_page - 1))
        p_nav.addWidget(self.btn_api_prev)

        lbl_p_tag = QLabel("PAGE:")
        lbl_p_tag.setFont(F(8, NORMAL))
        lbl_p_tag.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_p_tag)

        self.spin_api_page = QSpinBox()
        self.spin_api_page.setRange(1, 1)
        self.spin_api_page.setValue(1)
        self.spin_api_page.setFixedHeight(32)
        self.spin_api_page.setFixedWidth(64)
        self.spin_api_page.setStyleSheet(
            f"QSpinBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"  padding: 2px 4px;"
            f"}}"
        )
        self.spin_api_page.valueChanged.connect(self._go_to_api_page)
        p_nav.addWidget(self.spin_api_page)

        self.lbl_api_total_pages = QLabel("/ 1")
        self.lbl_api_total_pages.setFont(F(8.5, NORMAL))
        self.lbl_api_total_pages.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_api_total_pages)

        self.btn_api_next = RetroButton("NEXT ▶", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_api_next.clicked.connect(lambda: self._go_to_api_page(self.api_preview_model.current_page + 1))
        p_nav.addWidget(self.btn_api_next)

        self.btn_api_last = RetroButton("LAST ⏭", bg=T.SURFACE2, hover_bg="#F3D5D5", fg=T.TEXT, height=32)
        self.btn_api_last.clicked.connect(lambda: self._go_to_api_page(self.api_preview_model.total_pages))
        p_nav.addWidget(self.btn_api_last)

        p_nav.addSpacing(16)
        lbl_sz = QLabel("PAGE SIZE:")
        lbl_sz.setFont(F(8, NORMAL))
        lbl_sz.setStyleSheet(f"color: {T.TEXT}; background: transparent; font-weight: bold;")
        p_nav.addWidget(lbl_sz)

        self.combo_api_page_size = QComboBox()
        self.combo_api_page_size.addItems(["25 rows", "50 rows", "100 rows", "250 rows"])
        self.combo_api_page_size.setCurrentIndex(1)
        self.combo_api_page_size.setFixedHeight(32)
        self.combo_api_page_size.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  border: 2px solid {T.LINE2};"
            f"  border-radius: 4px;"
            f"  font-weight: bold;"
            f"  font-size: 12px;"
            f"  padding: 2px 6px;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #1A0F13;"
            f"  selection-background-color: {T.ACCENT_LIGHT};"
            f"  selection-color: #1A0F13;"
            f"}}"
        )
        self.combo_api_page_size.currentIndexChanged.connect(self._on_api_page_size_changed)
        p_nav.addWidget(self.combo_api_page_size)

        p_nav.addStretch()
        self.lbl_api_page_records = QLabel("No dataset loaded yet")
        self.lbl_api_page_records.setFont(F(8, NORMAL))
        self.lbl_api_page_records.setStyleSheet(f"color: {T.MUTED}; background: transparent; font-weight: bold;")
        p_nav.addWidget(self.lbl_api_page_records)

        p_lay.addLayout(p_nav)

        lay.addWidget(self.api_preview_container)
        lay.addStretch(1)

        return card

    def _sync_api_variables(self):
        self.var_api_url = self.input_api_url.text().strip()
        self.var_api_method = self.combo_api_method.currentText()
        self.var_api_headers = self.input_api_headers.toPlainText().strip()
        self.var_api_payload = self.input_api_payload.toPlainText().strip()

        page.var_api_url = self.var_api_url
        page.var_api_method = self.var_api_method
        page.var_api_headers = self.var_api_headers
        page.var_api_payload = self.var_api_payload

    def _on_api_show_data_clicked(self):
        """Option 1: SHOW DATA (Fetches REST API response and renders in tabular view)"""
        self._sync_api_variables()
        if not self.var_api_url:
            self._notify_action("⚠️ Please enter a REST API URL before fetching.")
            return

        self._notify_action(f"Fetching REST API data from: {self.var_api_url}...")
        try:
            import user.inputs.raw.all_data_inputs as adi
            importlib.reload(adi)
            df = adi.RestAPI.fetch_data()
            if df is not None and isinstance(df, pl.DataFrame):
                self.raw_data = df
                page.raw_data = df
                self._display_api_preview_data(df)
                self._notify_action(f"Showing {df.height:,} rows × {df.width} cols from REST API")
            else:
                self._notify_action("⚠️ REST API returned empty or unrecognized dataset.")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "REST API fetch failed"
            self._notify_action(f"REST API Error: {err_msg}")

    def _on_api_process_data_clicked(self):
        """Option 2: PROCESS DATA (Dispatches parameters for backend processing)"""
        self._sync_api_variables()
        self._notify_action("✓ Process Data triggered — Variables ready for your backend logic in all_data_inputs.py")
        payload = {
            "action": "process_data",
            "source_type": "api",
            "url": self.var_api_url,
            "method": self.var_api_method,
            "headers": self.var_api_headers,
            "payload": self.var_api_payload,
        }
        self.ingest_requested.emit(payload)

    def _on_trigger_api_ingest(self):
        """Legacy trigger method alias pointing to _on_api_show_data_clicked."""
        self._on_api_show_data_clicked()

    def _display_api_preview_data(self, df: pl.DataFrame):
        self.api_preview_container.setVisible(True)
        self.panels_stack.updateGeometry()
        self.api_preview_model.set_dataframe(df)
        self._update_api_filter_columns()
        self._update_api_pagination_ui()
        self.api_preview_table.resizeColumnsToContents()

    def _update_api_filter_columns(self):
        current_selection = self.combo_api_filter_col.currentText()
        self.combo_api_filter_col.blockSignals(True)
        self.combo_api_filter_col.clear()
        self.combo_api_filter_col.addItem("All Columns")
        if self.api_preview_model._full_df is not None:
            for c in self.api_preview_model._full_df.columns:
                self.combo_api_filter_col.addItem(str(c))
        idx = self.combo_api_filter_col.findText(current_selection)
        if idx >= 0:
            self.combo_api_filter_col.setCurrentIndex(idx)
        else:
            self.combo_api_filter_col.setCurrentIndex(0)
        self.combo_api_filter_col.blockSignals(False)

    def _on_api_filter_changed(self):
        query = self.input_api_filter.text()
        col = self.combo_api_filter_col.currentText()
        self.api_preview_model.set_filter(query, col)
        self._update_api_pagination_ui()

    def _on_api_clear_filter(self):
        has_filter = bool(self.input_api_filter.text().strip())
        self.input_api_filter.blockSignals(True)
        self.input_api_filter.clear()
        self.input_api_filter.blockSignals(False)
        self.combo_api_filter_col.blockSignals(True)
        self.combo_api_filter_col.setCurrentIndex(0)
        self.combo_api_filter_col.blockSignals(False)
        self.api_preview_model.set_filter("", "All Columns")

        if not has_filter:
            # When filter is already empty, CLEAR clears the loaded preview dataset
            self.api_preview_model.set_dataframe(None)
            self.raw_data = None
            page.raw_data = None
            self.api_preview_container.setVisible(False)
            self.panels_stack.updateGeometry()
            self._notify_action("✓ REST API data preview cleared.")

        self._update_api_pagination_ui()
        self.api_preview_table.viewport().update()

    def _go_to_api_page(self, page_num: int):
        self.api_preview_model.set_page(page_num)
        self._update_api_pagination_ui()

    def _on_api_page_size_changed(self, idx: int):
        sizes = [25, 50, 100, 250]
        size = sizes[idx] if idx < len(sizes) else 50
        self.api_preview_model.set_page_size(size)
        self._update_api_pagination_ui()

    def _update_api_pagination_ui(self):
        m = self.api_preview_model
        total_p = m.total_pages
        curr_p = m.current_page
        total_rows = m._filtered_df.height if m._filtered_df is not None else 0
        unfiltered_rows = m._full_df.height if m._full_df is not None else 0

        self.spin_api_page.blockSignals(True)
        self.spin_api_page.setRange(1, total_p)
        self.spin_api_page.setValue(curr_p)
        self.spin_api_page.blockSignals(False)

        self.lbl_api_total_pages.setText(f"/ {total_p}")
        self.btn_api_first.setEnabled(curr_p > 1)
        self.btn_api_prev.setEnabled(curr_p > 1)
        self.btn_api_next.setEnabled(curr_p < total_p)
        self.btn_api_last.setEnabled(curr_p < total_p)

        if m._full_df is None:
            self.lbl_api_page_records.setText("No dataset loaded yet")
            self.lbl_api_filter_match.setText("ALL ROWS")
            self.lbl_api_filter_match.setStyleSheet(
                f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
            )
        else:
            start = (curr_p - 1) * m.page_size + 1 if total_rows > 0 else 0
            end = min(curr_p * m.page_size, total_rows)
            self.lbl_api_page_records.setText(f"Showing rows {start:,}–{end:,} of {total_rows:,} (Total: {unfiltered_rows:,})")
            if total_rows < unfiltered_rows:
                self.lbl_api_filter_match.setText(f"FILTERED: {total_rows:,} / {unfiltered_rows:,}")
                self.lbl_api_filter_match.setStyleSheet(
                    f"background:{T.YELLOW};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;font-weight:bold;"
                )
            else:
                self.lbl_api_filter_match.setText(f"ALL {total_rows:,} ROWS")
                self.lbl_api_filter_match.setStyleSheet(
                    f"background:{T.BADGE_PINK};color:{T.TEXT};border:2px solid {T.LINE2};border-radius:4px;padding:2px 8px;"
                )

    # ═════════════════════════════════════════════════════════════════════════
    #  DEVELOPER REFERENCE CARD (EXPOSES BACKEND VARIABLE NAMES CLEARLY)
    # ═════════════════════════════════════════════════════════════════════════
    def _build_dev_notes_card(self) -> Card:
        card = Card(shadow_color="#FCE198", bg_color="#FFFFFF")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)

        top = QHBoxLayout()
        b = badge("DEVELOPER HOOK REFERENCE", bg="#FFF3D6", fg=T.TEXT, size=7.5)
        top.addWidget(b, 0, Qt.AlignLeft)
        top.addStretch()
        tag = badge("STATE SYNC", bg=T.SURFACE2, fg=T.TEXT, size=7.0)
        top.addWidget(tag, 0, Qt.AlignRight)
        lay.addLayout(top)

        # Status Banner (Wraps cleanly onto new lines without stretching the window)
        self.lbl_status = QLabel("Status: Ready to Ingest")
        self.lbl_status.setFont(F(8, NORMAL, 0.4))
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_status.setMinimumWidth(0)
        self.lbl_status.setStyleSheet(
            f"color: {T.ACCENT}; background: {T.ACCENT_LIGHT}; border: 1px solid {T.LINE2}; "
            f"border-radius: 4px; padding: 6px 12px; font-weight: bold;"
        )
        lay.addWidget(self.lbl_status)

        desc = (
            "📌 BACKEND HOOK NOTE:\n"
            "When the user clicks any Ingestion button, the frontend emits ingest_requested(payload: dict).\n"
            "Use these exact variable names inside your backend user/inputs/xyz.py scripts:\n"
            "• File: page.var_file_path, page.var_file_type ('csv'|'excel'), page.var_csv_delimiter, page.var_excel_sheet\n"
            "• PostgreSQL: page.var_postgres_host, page.var_postgres_port, page.var_postgres_database, page.var_postgres_username, page.var_postgres_password, page.var_postgres_query\n"
            "• MSSQL: page.var_mssql_server, page.var_mssql_port, page.var_mssql_database, page.var_mssql_username, page.var_mssql_password, page.var_mssql_query\n"
            "• API: page.var_api_url, page.var_api_method ('GET'|'POST'), page.var_api_headers, page.var_api_payload"
        )
        lbl_desc = QLabel(desc)
        lbl_desc.setFont(F(8, LIGHT, 0.4))
        lbl_desc.setWordWrap(True)
        lbl_desc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        lbl_desc.setMinimumWidth(0)
        lbl_desc.setStyleSheet(f"color: {T.MUTED}; background: transparent; line-height: 140%;")
        lay.addWidget(lbl_desc)

        return card

    def _notify_action(self, msg: str):
        self.lbl_status.setText(f"Status: {msg}")
        is_error = any(w in msg.lower() for w in ["error", "failed", "blocked", "forbidden", "violation", "⚠️", "🚫", "fail"])

        # Top-right strictly small notification message
        clean = msg
        for prefix in ["✓ ", "⚠️ ", "🔴 ", "🟢 ", "🚫 "]:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
        if len(clean) > 52:
            clean = clean[:49] + "..."

        if is_error:
            self.lbl_status.setStyleSheet(
                f"color: {T.NEG}; background: {T.BADGE_PINK}; border: 1px solid {T.LINE2}; "
                f"border-radius: 4px; padding: 6px 12px; font-weight: bold;"
            )
            self.top_toast.setText(f"🔴 {clean}")
            self.top_toast.setStyleSheet(
                f"color: #FFFFFF; background: {T.NEG}; border: 2px solid {T.LINE2}; "
                f"border-radius: 6px; padding: 4px 12px; font-weight: bold; font-size: 11px;"
            )
        else:
            self.lbl_status.setStyleSheet(
                f"color: {T.ACCENT}; background: {T.ACCENT_LIGHT}; border: 1px solid {T.LINE2}; "
                f"border-radius: 4px; padding: 6px 12px; font-weight: bold;"
            )
            self.top_toast.setText(f"🟢 {clean}")
            self.top_toast.setStyleSheet(
                f"color: #FFFFFF; background: {T.POS}; border: 2px solid {T.LINE2}; "
                f"border-radius: 6px; padding: 4px 12px; font-weight: bold; font-size: 11px;"
            )
        self.top_toast.setVisible(True)

        from PySide6.QtCore import QTimer
        QTimer.singleShot(6000, lambda: self.top_toast.setVisible(False) if self.top_toast.text().endswith(clean) else None)


# Standalone runner
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    win = QWidget()
    win.setWindowTitle("EDETH — Data Ingestion Preview")
    win.resize(1200, 840)
    win.setStyleSheet(f"background-color: {T.BG};")

    lay = QVBoxLayout(win)
    page = DataIngestionPage()
    page.ingest_requested.connect(lambda d: print("Ingest Requested Payload:", d))
    lay.addWidget(scrollable(page))

    win.show()
    sys.exit(app.exec())
