"""VK Dub Studio — Cyber Obsidian Pro Studio Theme v2.0.

High-end creative studio aesthetic inspired by DaVinci Resolve, Linear & Figma:
- Deep obsidian dark background (#080b12 / #0b101b / #0f172a)
- Electric cyan (#06b6d4) & neon violet (#8b5cf6) luminous accents
- Glowing gradient buttons with smooth hover feedback
- Ultra-slim modern 6px scrollbars
- Sleek glassmorphism borders and high-contrast typography
- Premium tab bars, group boxes, and enhanced interactive states
"""

DARK_THEME = """
/* =========================================================================
   1. CORE APPLICATION BASE & TYPOGRAPHY
   ========================================================================= */
QWidget {
    background-color: #0b101b;
    color: #e2e8f0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
    font-size: 13px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    outline: none;
}

QMainWindow {
    background-color: #080b12;
}

QDialog {
    background-color: #0c121e;
    color: #e2e8f0;
}

QSplitter {
    background-color: #080b12;
}

QSplitter::handle {
    background-color: #161f30;
    width: 2px;
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #06b6d4;
}

/* =========================================================================
   2. CONTAINERS, PANELS & CARDS
   ========================================================================= */
QFrame#panel {
    background-color: #080d16;
    border: 1px solid #141f32;
    border-radius: 10px;
}

QFrame#panel QLabel {
    background: transparent;
}

QFrame.card, QFrame#card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0e1626, stop:1 #0a101c);
    border: 1px solid #1c2a42;
    border-radius: 10px;
    padding: 12px;
}

QFrame.card:hover, QFrame#card:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #131e34, stop:1 #0c1424);
    border-color: #2b4266;
}

/* Drop zone container */
QFrame#dropZone, QFrame.dropZone {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a1120, stop:1 #070b14);
    border: 2px dashed #1e3150;
    border-radius: 12px;
    padding: 16px;
}

QFrame#dropZone:hover, QFrame.dropZone:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0e1930, stop:1 #09101c);
    border-color: #06b6d4;
}

/* Group box — section containers */
QGroupBox {
    background-color: #090e18;
    border: 1px solid #152033;
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 12px 10px 12px;
    font-weight: 700;
    color: #94a3b8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 10px;
    color: #38bdf8;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.8px;
    background-color: #0d1524;
    border: 1px solid #1e2f4a;
    border-radius: 5px;
}

/* =========================================================================
   3. HEADINGS, LABELS & BADGES
   ========================================================================= */
QLabel#heading {
    font-size: 18px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: 0.3px;
}

QLabel#subheading {
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
}

QLabel#muted {
    color: #64748b;
    font-size: 11px;
}

QLabel#eyebrow {
    color: #38bdf8;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

QLabel#badge {
    color: #38bdf8;
    background-color: #082f49;
    border: 1px solid #0369a1;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#badge_success {
    color: #34d399;
    background-color: #064e3b;
    border: 1px solid #059669;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#badge_warn {
    color: #fbbf24;
    background-color: #451a03;
    border: 1px solid #b45309;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#badge_error {
    color: #f87171;
    background-color: #450a0a;
    border: 1px solid #991b1b;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#badge_purple {
    color: #c084fc;
    background-color: #2e1065;
    border: 1px solid #6b21a8;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}

/* =========================================================================
   4. BUTTONS & INTERACTIVE CONTROLS
   ========================================================================= */
QPushButton {
    background-color: #0f1626;
    color: #e2e8f0;
    border: 1px solid #1c2b44;
    border-radius: 7px;
    padding: 7px 15px;
    font-weight: 600;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #17243c;
    border-color: #38bdf8;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #0b1220;
    border-color: #0284c7;
}

QPushButton:disabled {
    background-color: #0a0f1a;
    color: #475569;
    border-color: #151d2a;
}

/* Primary Cyan-Blue Gradient CTA */
QPushButton#primary, QPushButton.btnPrimary, QPushButton.primaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.6 #0369a1, stop:1 #06b6d4);
    color: #ffffff;
    border: 1px solid #38bdf8;
    border-radius: 7px;
    font-weight: 700;
    padding: 9px 18px;
    letter-spacing: 0.3px;
}

QPushButton#primary:hover, QPushButton.btnPrimary:hover, QPushButton.primaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:0.6 #0284c7, stop:1 #22d3ee);
    border-color: #7dd3fc;
    color: #ffffff;
}

QPushButton#primary:pressed, QPushButton.btnPrimary:pressed, QPushButton.primaryBtn:pressed {
    background: #0284c7;
}

QPushButton#primary:disabled, QPushButton.btnPrimary:disabled, QPushButton.primaryBtn:disabled {
    background: #0d1524;
    color: #475569;
    border-color: #162032;
}

/* Success Emerald CTA (e.g. CapCut Export) */
QPushButton#success, QPushButton.btnSuccess, QPushButton.successBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    color: #ffffff;
    border: 1px solid #34d399;
    border-radius: 6px;
    font-weight: 700;
    padding: 8px 16px;
}

QPushButton#success:hover, QPushButton.btnSuccess:hover, QPushButton.successBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
    border-color: #6ee7b7;
}

QPushButton#success:disabled, QPushButton.btnSuccess:disabled {
    background: #0c121e;
    color: #475569;
    border-color: #1e293b;
}

/* Violet Studio CTA */
QPushButton#violet, QPushButton.btnViolet {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
    color: #ffffff;
    border: 1px solid #a78bfa;
    border-radius: 6px;
    font-weight: 700;
}

QPushButton#violet:hover, QPushButton.btnViolet:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
}

/* Danger Crimson Button */
QPushButton#danger, QPushButton.btnDanger, QPushButton.dangerBtn {
    background-color: #450a0a;
    color: #fca5a5;
    border: 1px solid #991b1b;
    border-radius: 6px;
    font-weight: 600;
}

QPushButton#danger:hover, QPushButton.btnDanger:hover, QPushButton.dangerBtn:hover {
    background-color: #7f1d1d;
    border-color: #dc2626;
    color: #ffffff;
}

/* Secondary Button */
QPushButton.secondaryBtn {
    background-color: #0f1624;
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 14px;
    border: 1px solid #1e2b40;
    border-radius: 6px;
}

QPushButton.secondaryBtn:hover {
    background-color: #182337;
    color: #38bdf8;
    border-color: #0284c7;
}

/* =========================================================================
   5. INPUTS, EDITORS & COMBOBOXES
   ========================================================================= */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #070b12;
    color: #f1f5f9;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #06b6d4;
    background-color: #090e17;
}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {
    background-color: #06090e;
    color: #475569;
    border-color: #151c28;
}

QComboBox {
    background-color: #0f172a;
    color: #f1f5f9;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}

QComboBox:hover {
    border-color: #38bdf8;
}

QComboBox:on {
    border-color: #06b6d4;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #94a3b8;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #0f172a;
    color: #e2e8f0;
    border: 1px solid #1e293b;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

QSpinBox, QDoubleSpinBox {
    background-color: #070b12;
    color: #f1f5f9;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 500;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #38bdf8;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #131b2e;
    border: none;
    width: 16px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #1e293b;
}

/* =========================================================================
   6. SLIDERS & PROGRESS BARS
   ========================================================================= */
QSlider::groove:horizontal {
    height: 5px;
    background-color: #1e293b;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background-color: #f8fafc;
    border: 2px solid #06b6d4;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background-color: #ffffff;
    border-color: #38bdf8;
    width: 16px;
    height: 16px;
    margin: -6px 0;
}

QProgressBar {
    border: 1px solid #1e293b;
    background-color: #080c14;
    border-radius: 5px;
    text-align: center;
    color: #f8fafc;
    font-size: 11px;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
    border-radius: 4px;
}

/* =========================================================================
   7. LISTS, TABLES & SCROLL AREAS
   ========================================================================= */
QScrollArea {
    border: none;
    background: transparent;
}

QListWidget, QListView, QTableView {
    background-color: #080c14;
    border: 1px solid #1e293b;
    border-radius: 6px;
    color: #e2e8f0;
    gridline-color: #172033;
    outline: none;
}

QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #111827;
    border-radius: 4px;
}

QListWidget::item:hover {
    background-color: #131d31;
}

QListWidget::item:selected {
    background-color: #162b48;
    color: #38bdf8;
    border-left: 3px solid #06b6d4;
}

QHeaderView::section {
    background-color: #0d1322;
    color: #94a3b8;
    border: none;
    border-bottom: 1px solid #1e293b;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 11px;
}

/* =========================================================================
   8. MODERN ULTRA-SLIM SCROLLBARS (6px)
   ========================================================================= */
QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #1e293b;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background-color: #38bdf8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: none;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #1e293b;
    min-width: 24px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #38bdf8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: none;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* =========================================================================
   9. STATUS BAR & TOOLTIPS
   ========================================================================= */
QStatusBar {
    background-color: #080b12;
    color: #64748b;
    border-top: 1px solid #161f30;
    font-size: 11px;
}

QToolTip {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #38bdf8;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 500;
}

/* =========================================================================
   10. CHECKBOXES & RADIOS
   ========================================================================= */
QCheckBox {
    color: #cbd5e1;
    spacing: 8px;
    font-weight: 500;
}

QCheckBox:disabled {
    color: #475569;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #24324a;
    border-radius: 4px;
    background-color: #080c14;
}

QCheckBox::indicator:hover {
    border-color: #38bdf8;
    background-color: #0c121e;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

QCheckBox::indicator:disabled {
    background-color: #0a0e16;
    border-color: #1a2030;
}

QRadioButton {
    color: #cbd5e1;
    spacing: 8px;
    font-weight: 500;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #24324a;
    border-radius: 9px;
    background-color: #080c14;
}

QRadioButton::indicator:hover {
    border-color: #38bdf8;
}

QRadioButton::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* =========================================================================
   11. TAB BAR & TAB WIDGETS (Diagnostics Filters, Settings)
   ========================================================================= */
QTabWidget::pane {
    background-color: #0b101b;
    border: 1px solid #1e293b;
    border-top: none;
    border-radius: 0 0 8px 8px;
}

QTabBar::tab {
    background-color: #0c111c;
    color: #64748b;
    border: 1px solid #1a2436;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 6px 14px;
    margin-right: 2px;
    font-size: 11px;
    font-weight: 600;
}

QTabBar::tab:hover {
    background-color: #131b2c;
    color: #94a3b8;
    border-color: #24334f;
}

QTabBar::tab:selected {
    background-color: #0b101b;
    color: #38bdf8;
    border-color: #0284c7;
    border-bottom: 2px solid #06b6d4;
    font-weight: 700;
}

/* =========================================================================
   12. MENUS & CONTEXT MENUS
   ========================================================================= */
QMenu {
    background-color: #0f172a;
    color: #e2e8f0;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
    font-size: 12px;
}

QMenu::item:selected {
    background-color: #1e293b;
    color: #38bdf8;
}

QMenu::item:disabled {
    color: #475569;
}

QMenu::separator {
    height: 1px;
    background-color: #1e293b;
    margin: 4px 8px;
}

/* =========================================================================
   13. TOOL BUTTONS
   ========================================================================= */
QToolButton {
    background-color: #131b2e;
    color: #e2e8f0;
    border: 1px solid #24324a;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 600;
    font-size: 12px;
}

QToolButton:hover {
    background-color: #1c263f;
    border-color: #38bdf8;
    color: #ffffff;
}

QToolButton::menu-indicator {
    image: none;
    width: 0;
}
"""

KAPPAK_TOKENS = {
    "canvas": "#F5F7FB",
    "surface": "#FFFFFF",
    "surface_tint": "#EEF4FF",
    "primary": "#2457F5",
    "primary_dark": "#173FB8",
    "lime": "#B9F227",
    "lime_hover": "#A7DF18",
    "pink": "#FF5C8A",
    "success": "#20C96B",
    "ink": "#101828",
    "muted": "#667085",
    "border": "#101828",
}


NEO_BRUTALISM_THEME = """
/* =========================================================================
   KAPPAK — Neo Brutalism Creative Suite Theme
   ========================================================================= */
QWidget {
    background-color: #f5f7fb;
    color: #101828;
    font-family: 'Plus Jakarta Sans', 'Segoe UI', -apple-system, sans-serif;
    font-size: 14px;
    font-weight: 500;
    selection-background-color: #b9f227;
    selection-color: #101828;
    outline: none;
}

QMainWindow {
    background-color: #f5f7fb;
}

QDialog {
    background-color: #ffffff;
    color: #101828;
}

QSplitter {
    background-color: #f5f7fb;
}

QSplitter::handle {
    background-color: #cbd5e1;
    width: 2px;
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #2563eb;
}

QFrame#panel, QFrame.card, QFrame[settingsCard="true"] {
    background-color: #ffffff;
    border: 2px solid #101828;
    border-radius: 16px;
}

QPushButton {
    background-color: #ffffff;
    color: #101828;
    border: 2px solid #101828;
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 700;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #f1f5f9;
}

QPushButton:pressed {
    background-color: #e2e8f0;
}

QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #cbd5e1;
}

QPushButton.primaryBtn, QPushButton#primary, QPushButton[class="primary"] {
    background-color: #b9f227;
    color: #101828;
    border: 3px solid #101828;
    border-radius: 12px;
    font-weight: 900;
    font-size: 14px;
}

QPushButton.primaryBtn:hover, QPushButton#primary:hover, QPushButton[class="primary"]:hover {
    background-color: #a7df18;
}

QPushButton.actionBlue, QPushButton#btnBlue {
    background-color: #2457f5;
    color: #ffffff;
    border: 3px solid #101828;
    border-radius: 12px;
    font-weight: 800;
}

QPushButton.actionBlue:hover, QPushButton#btnBlue:hover {
    background-color: #173fb8;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #2563eb;
}

QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    selection-background-color: #fde047;
    selection-color: #0f172a;
    border-radius: 6px;
    padding: 4px;
}

QProgressBar {
    background-color: #e2e8f0;
    border: 2px solid #0f172a;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    color: #0f172a;
    min-height: 14px;
}

QProgressBar::chunk {
    background-color: #22c55e;
    border-radius: 6px;
}

QScrollBar:vertical {
    border: 1.5px solid #0f172a;
    background: #f1f5f9;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar:horizontal {
    border: 1.5px solid #0f172a;
    background: #f1f5f9;
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    min-width: 20px;
    border-radius: 4px;
}

QTabWidget::pane {
    border: 2px solid #0f172a;
    border-radius: 8px;
    background-color: #ffffff;
    padding: 12px;
}

QTabBar::tab {
    background-color: #f1f5f9;
    color: #64748b;
    border: 2px solid #0f172a;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 18px;
    font-weight: 700;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0f172a;
}

QTableWidget {
    background-color: #ffffff;
    border: 2px solid #0f172a;
    border-radius: 8px;
    gridline-color: #e2e8f0;
}

QHeaderView::section {
    background-color: #f1f5f9;
    color: #0f172a;
    border: 1px solid #0f172a;
    padding: 6px 8px;
    font-weight: 800;
}

QCheckBox {
    spacing: 8px;
    font-weight: 600;
    color: #0f172a;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #0f172a;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    image: none;
}
"""

# Semantic controls shared by the KAPPAK light theme.  The original UI has a
# number of specialised widgets, so keeping these rules central lets dialogs
# and newly-created controls inherit the same visual language automatically.
NEO_LIGHT_THEME = (
    NEO_BRUTALISM_THEME
    + """
QLabel#heading {
    color: #0f172a;
    font-size: 18px;
    font-weight: 900;
}
QLabel[role="section"] {
    color: #1d4ed8;
    font-size: 13px;
    font-weight: 900;
    padding-top: 6px;
}
QLabel[role="muted"] { color: #64748b; font-size: 12px; }
QLabel[role="success"] { color: #15803d; font-weight: 800; }
QLabel[role="warning"] { color: #a16207; font-weight: 700; }
QLabel[role="danger"] { color: #be123c; font-weight: 800; }

QGroupBox {
    background-color: #ffffff;
    border: 2px solid #0f172a;
    border-radius: 10px;
    margin-top: 12px;
    padding: 14px 10px 10px 10px;
    font-weight: 800;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #1d4ed8;
    background-color: #ffffff;
}
QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    border-radius: 7px;
    padding: 5px 8px;
    font-weight: 650;
}
QListWidget, QListView, QTreeWidget, QTableView, QTextBrowser {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    border-radius: 8px;
    alternate-background-color: #f1f5f9;
}
QListWidget::item, QListView::item { padding: 6px; border-radius: 5px; }
QListWidget::item:selected, QListView::item:selected {
    background-color: #fde047;
    color: #0f172a;
}
QToolButton {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    border-radius: 7px;
    padding: 5px 9px;
    font-weight: 800;
}
QToolButton:hover { background-color: #dbeafe; }
QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 2px solid #0f172a;
    padding: 5px;
}
QMenu::item { padding: 7px 22px 7px 10px; border-radius: 5px; }
QMenu::item:selected { background-color: #fde047; color: #0f172a; }
QRadioButton { spacing: 8px; font-weight: 650; }
QRadioButton::indicator {
    width: 17px; height: 17px; border: 2px solid #0f172a;
    border-radius: 10px; background-color: #ffffff;
}
QRadioButton::indicator:checked { background-color: #2563eb; border: 4px solid #ffffff; }
QSlider::groove:horizontal {
    height: 7px; background: #cbd5e1; border: 1px solid #0f172a; border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #2563eb; border: 2px solid #0f172a;
    width: 16px; margin: -6px 0; border-radius: 8px;
}
QStatusBar { background-color: #0f172a; color: #ffffff; border-top: 2px solid #020617; }
QToolTip {
    background-color: #0f172a; color: #ffffff; border: 1px solid #020617;
    padding: 5px;
}
"""
)

NEO_DARK_THEME = """
QWidget {
    background-color: #0b1020;
    color: #e5e7eb;
    font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif;
    font-size: 13px;
    font-weight: 500;
    selection-background-color: #a3e635;
    selection-color: #07111f;
    outline: none;
}
QMainWindow, QDialog, QSplitter { background-color: #0b1020; color: #e5e7eb; }
QSplitter::handle { background-color: #334155; width: 2px; height: 2px; }
QFrame#panel, QFrame.card {
    background-color: #111827; border: 2px solid #020617; border-radius: 12px;
}
QLabel#heading { color: #f8fafc; font-size: 18px; font-weight: 900; }
QLabel[role="section"] { color: #818cf8; font-size: 13px; font-weight: 900; padding-top: 6px; }
QLabel[role="muted"] { color: #94a3b8; font-size: 12px; }
QLabel[role="success"] { color: #86efac; font-weight: 800; }
QLabel[role="warning"] { color: #fde047; font-weight: 700; }
QLabel[role="danger"] { color: #fda4af; font-weight: 800; }
QPushButton, QToolButton {
    background-color: #1e293b; color: #f8fafc; border: 2px solid #020617;
    border-radius: 8px; padding: 6px 14px; font-weight: 750;
}
QPushButton:hover, QToolButton:hover { background-color: #312e81; border-color: #818cf8; }
QPushButton:pressed, QToolButton:pressed { background-color: #3730a3; }
QPushButton:disabled { background-color: #111827; color: #64748b; border-color: #334155; }
QPushButton#primary, QPushButton[class="primary"], QPushButton.primaryBtn {
    background-color: #a3e635; color: #07111f; border: 2px solid #020617;
    border-radius: 9px; font-weight: 900;
}
QPushButton#primary:hover, QPushButton[class="primary"]:hover, QPushButton.primaryBtn:hover {
    background-color: #bef264;
}
QPushButton.actionBlue, QPushButton#btnBlue {
    background-color: #4f46e5; color: #ffffff; border: 2px solid #020617; font-weight: 900;
}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox,
QSpinBox, QDoubleSpinBox, QListWidget, QListView, QTreeWidget, QTableWidget, QTableView {
    background-color: #111827; color: #f8fafc; border: 2px solid #020617;
    border-radius: 8px; padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #818cf8; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #111827; color: #f8fafc; border: 2px solid #020617;
    selection-background-color: #a3e635; selection-color: #07111f;
}
QListWidget::item, QListView::item { padding: 6px; border-radius: 5px; }
QListWidget::item:selected, QListView::item:selected { background-color: #4f46e5; color: #ffffff; }
QGroupBox {
    background-color: #111827; border: 2px solid #020617; border-radius: 10px;
    margin-top: 12px; padding: 14px 10px 10px 10px; font-weight: 800;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #a5b4fc; background-color: #111827;
}
QTabWidget::pane {
    border: 2px solid #020617; border-radius: 8px;
    background-color: #111827; padding: 12px;
}
QTabBar::tab {
    background-color: #1e293b; color: #94a3b8; border: 2px solid #020617;
    border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px;
    padding: 8px 18px; font-weight: 750; margin-right: 4px;
}
QTabBar::tab:selected { background-color: #4f46e5; color: #ffffff; }
QHeaderView::section {
    background-color: #1e293b; color: #f8fafc; border: 1px solid #020617;
    padding: 6px 8px; font-weight: 850;
}
QProgressBar {
    background-color: #1e293b; border: 2px solid #020617; border-radius: 8px;
    text-align: center; font-weight: 800; color: #f8fafc; min-height: 14px;
}
QProgressBar::chunk { background-color: #a3e635; border-radius: 6px; }
QCheckBox, QRadioButton { spacing: 8px; color: #e5e7eb; font-weight: 650; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px; height: 18px; border: 2px solid #020617; background-color: #111827;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 10px; }
QCheckBox::indicator:checked { background-color: #a3e635; }
QRadioButton::indicator:checked { background-color: #818cf8; border: 4px solid #111827; }
QSlider::groove:horizontal {
    height: 7px; background: #334155; border: 1px solid #020617; border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #a3e635; border: 2px solid #020617;
    width: 16px; margin: -6px 0; border-radius: 8px;
}
QMenu { background-color: #111827; color: #f8fafc; border: 2px solid #020617; padding: 5px; }
QMenu::item { padding: 7px 22px 7px 10px; border-radius: 5px; }
QMenu::item:selected { background-color: #4f46e5; color: #ffffff; }
QScrollBar:vertical { border: 1px solid #020617; background: #111827; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #475569; min-height: 22px; border-radius: 4px; }
QScrollBar:horizontal { border: 1px solid #020617; background: #111827; height: 10px; margin: 0; }
QScrollBar::handle:horizontal { background: #475569; min-width: 22px; border-radius: 4px; }
QStatusBar { background-color: #020617; color: #e5e7eb; border-top: 2px solid #020617; }
QToolTip { background-color: #020617; color: #f8fafc; border: 1px solid #818cf8; padding: 5px; }
"""


def apply_brutalist_shadow(widget, *, offset: int = 4, color: str = "#101828") -> None:
    """Attach the crisp offset shadow used by the KAPPAK mockups."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(0)
    effect.setOffset(offset, offset)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


def normalize_theme(theme: str | None) -> str:
    """Return one of the two supported persisted theme names."""
    return "dark" if str(theme).lower() == "dark" else "light"


def _darken_inline_qss(style: str) -> str:
    """Translate legacy light-only component QSS into the dark KAPPAK palette.

    Component-specific inline QSS is retained for backwards compatibility with
    the mature PySide UI.  The translation is deliberately conservative and
    starts from the saved light source each time, so switching themes never
    accumulates colour substitutions.
    """
    import re

    replacements = {
        "#f8fafc": "#0b1020",
        "#ffffff": "#111827",
        "#fff": "#111827",
        "#f1f5f9": "#1e293b",
        "#e2e8f0": "#334155",
        "#cbd5e1": "#475569",
        "#94a3b8": "#94a3b8",
        "#64748b": "#94a3b8",
        "#475569": "#cbd5e1",
        "#334155": "#e2e8f0",
        "#1e293b": "#f1f5f9",
        "#0f172a": "#f8fafc",
        "#dbeafe": "#312e81",
        "#eff6ff": "#172554",
        "#fff1f2": "#3f1726",
        "#fef2f2": "#450a0a",
        "#dcfce7": "#052e16",
        "#f0fdf4": "#052e16",
        "#fef9c3": "#422006",
        "#fef3c7": "#451a03",
    }
    pattern = re.compile(
        "|".join(re.escape(source) for source in sorted(replacements, key=len, reverse=True)),
        flags=re.IGNORECASE,
    )
    result = pattern.sub(lambda match: replacements[match.group(0).lower()], style)

    # Borders remain near-black in both modes; the generic colour replacement
    # above intentionally brightens text, then this pass restores dark outlines.
    result = re.sub(
        r"(border(?:-\w+)?\s*:\s*[^;{}]*?)(#f8fafc)",
        r"\1#020617",
        result,
        flags=re.IGNORECASE,
    )
    return result


def apply_widget_theme(root, theme: str | None = None) -> None:
    """Apply the active theme to specialised widgets with legacy inline QSS."""
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance()
    active = normalize_theme(theme or (app.property("kappakTheme") if app else "light"))
    widgets = [root]
    if isinstance(root, QWidget):
        widgets.extend(root.findChildren(QWidget))
    for widget in widgets:
        current = widget.styleSheet()
        last_applied = widget.property("_kappakLastAppliedQss")
        base = widget.property("_kappakLightQss")
        if current and current != last_applied:
            base = current
            widget.setProperty("_kappakLightQss", base)
        if not base:
            continue
        themed = _darken_inline_qss(str(base)) if active == "dark" else str(base)
        if current != themed:
            widget.setStyleSheet(themed)
        widget.setProperty("_kappakLastAppliedQss", themed)


def set_application_theme(app, theme: str | None) -> str:
    """Set the application theme and refresh all currently visible windows."""
    active = normalize_theme(theme)
    app.setProperty("kappakTheme", active)
    app.setStyleSheet(NEO_DARK_THEME if active == "dark" else NEO_LIGHT_THEME)
    for window in app.topLevelWidgets():
        apply_widget_theme(window, active)
    return active
