"""Apple-inspired glass theme and design tokens for KAPPAK Studio V2."""

from __future__ import annotations

# Design Tokens
COLOR_APP_BG = "#F5F8FD"
COLOR_SURFACE = "rgba(255, 255, 255, 0.78)"
COLOR_SURFACE_STRONG = "rgba(255, 255, 255, 0.92)"
COLOR_TEXT_PRIMARY = "#0A1738"
COLOR_TEXT_SECONDARY = "#66779C"
COLOR_PRIMARY = "#2777FF"
COLOR_PRIMARY_HOVER = "#1B63E0"
COLOR_PRIMARY_SOFT = "#E7F1FF"
COLOR_BORDER = "rgba(76, 104, 153, 0.12)"
COLOR_BORDER_STRONG = "rgba(76, 104, 153, 0.20)"

# Module Pastel Tints
TINT_BLUE = "#DFEEFF"      # Downloader
TINT_MINT = "#DBFAF0"      # Data Studio
TINT_VIOLET = "#EDE1FF"    # Auto Video
TINT_CYAN = "#DDF6FA"      # Auto Dub
TINT_PINK = "#FFE4F1"      # Social
TINT_AMBER = "#FFEFD6"     # Today

APPLE_GLASS_STYLESHEET = """
QMainWindow, QWidget#centralRoot, QWidget#middleContainer, QStackedWidget {
    background-color: #F5F8FD;
}

/* Left Icon Rail */
QFrame#iconRail {
    background-color: #FFFFFF;
    border-right: 1px solid rgba(76, 104, 153, 0.10);
}

QPushButton.railTab {
    background-color: transparent;
    border: none;
    border-radius: 16px;
    padding: 10px;
}

QPushButton.railTab:hover {
    background-color: rgba(231, 241, 255, 0.6);
}

QPushButton.railTab:checked {
    background-color: #E7F1FF;
}

/* Top Bar */
QFrame#topBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid rgba(76, 104, 153, 0.10);
}

QLineEdit#searchPill {
    background-color: #F8FAFD;
    border: 1px solid rgba(76, 104, 153, 0.15);
    border-radius: 21px;
    padding: 0 18px 0 42px;
    font-size: 13px;
    color: #0A1738;
}

QLineEdit#searchPill:focus {
    border: 1.5px solid #2777FF;
    background-color: #FFFFFF;
}

/* Status Pill */
QFrame#statusPill {
    background-color: #EDF9F0;
    border: 1px solid rgba(34, 197, 94, 0.25);
    border-radius: 16px;
    padding: 4px 12px;
}

/* User Profile Chip */
QFrame#userProfileChip {
    background-color: #FFFFFF;
    border: 1px solid rgba(76, 104, 153, 0.12);
    border-radius: 18px;
    padding: 3px 12px 3px 4px;
}

/* Hero Section */
QFrame#heroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFFFFF, stop:0.45 #F2F7FF, stop:1 #E9F2FF);
    border: 1px solid rgba(76, 104, 153, 0.12);
    border-radius: 30px;
}

/* Module Cards */
QFrame.moduleCard {
    background-color: #FFFFFF;
    border: 1px solid rgba(76, 104, 153, 0.10);
    border-radius: 24px;
}

QFrame.moduleCard:hover {
    background-color: #FFFFFF;
    border-color: rgba(39, 119, 255, 0.35);
}

/* Bottom Cards */
QFrame.bottomCard {
    background-color: #FFFFFF;
    border: 1px solid rgba(76, 104, 153, 0.10);
    border-radius: 22px;
}

/* Pill Buttons */
QPushButton.primaryPill {
    background-color: #2777FF;
    color: #FFFFFF;
    border: none;
    border-radius: 18px;
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton.primaryPill:hover {
    background-color: #1B63E0;
}

QPushButton.glassPill {
    background-color: #FFFFFF;
    color: #0A1738;
    border: 1px solid rgba(76, 104, 153, 0.18);
    border-radius: 18px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.glassPill:hover {
    background-color: #FFFFFF;
    border-color: #2777FF;
    color: #2777FF;
}

QPushButton.heroCtaPill {
    background-color: #FFFFFF;
    color: #0A1738;
    border: 1px solid rgba(76, 104, 153, 0.15);
    border-radius: 18px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.heroCtaPill:hover {
    border-color: #2777FF;
    color: #2777FF;
}

QPushButton.askKappakTrigger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2777FF, stop:1 #8B5CF6);
    color: #FFFFFF;
    border: none;
    border-radius: 16px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 700;
}

QPushButton.askKappakTrigger:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1B63E0, stop:1 #7C3AED);
}

QPushButton.arrowCircle {
    background-color: #F1F6FD;
    border: none;
    border-radius: 16px;
}

QPushButton.arrowCircle:hover {
    background-color: #2777FF;
}

/* Scroll Area */
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background-color: #F5F8FD;
    border: none;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: rgba(100, 116, 139, 0.25);
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(100, 116, 139, 0.45);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Drawer */
QFrame#askKappakDrawer {
    background-color: #FFFFFF;
    border-left: 1px solid rgba(76, 104, 153, 0.15);
}

/* Footer */
QFrame#footerBar {
    background-color: #F5F8FD;
    border-top: 1px solid rgba(76, 104, 153, 0.10);
}
"""
