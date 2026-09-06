DARK_THEME = """
QWidget { background: #10141d; color: #e5eaf4; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QSplitter { background: #0b0e15; }
QFrame#panel { background: #141a26; border: 1px solid #293245; border-radius: 10px; }
QFrame#panel QLabel { background: transparent; }
QLabel#heading { font-size: 19px; font-weight: 700; color: #f6f8ff; }
QLabel#muted { color: #929fb5; }
QLabel#eyebrow { color: #72d7c1; font-size: 11px; font-weight: 700; }
QLabel#badge { color: #f6c676; background: #332b1e; padding: 6px; border-radius: 5px; }
QPushButton { background: #232e41; border: 1px solid #39485f; border-radius: 6px;
              padding: 9px 10px; font-weight: 600; }
QPushButton:hover { background: #31415b; border-color: #62cdb6; }
QPushButton:pressed { background: #1a564b; }
QPushButton#primary { background: #237761; border-color: #409a81; color: white; }
QPushButton:disabled, QPushButton#primary:disabled { background: #1b2230;
              color: #69768b; border-color: #2b3444; }
QPlainTextEdit, QLineEdit { background: #0c111a; border: 1px solid #2c374a;
                         border-radius: 5px; padding: 6px; selection-background-color: #286854; }
QSlider::groove:horizontal { height: 5px; background: #313c50; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #57c9af; }
QSlider::handle:horizontal { width: 13px; margin: -4px 0; background: #d6fff5; border-radius: 6px; }
QScrollArea { border: none; }
QSplitter::handle { background: #0b0e15; width: 8px; }
QStatusBar { color: #97a5bb; background: #0c1018; }
QToolTip { color: #e5eaf4; background: #232e41; border: 1px solid #4a5d7a; }
QCheckBox:disabled { color: #69768b; }
QComboBox { background: #202b3e; border: 1px solid #39485f; padding: 6px; border-radius: 4px; }
QComboBox QAbstractItemView { background: #202b3e; selection-background-color: #237761; }
QListWidget { background: #0c111a; border: 1px solid #2c374a; border-radius: 6px; }
QListWidget::item { padding: 9px; border-bottom: 1px solid #293245; }
QListWidget::item:selected { background: #254f47; }
QProgressBar { border: 1px solid #2c374a; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: #237761; }
"""
