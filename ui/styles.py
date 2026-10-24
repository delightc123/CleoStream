"""
Modern Notion/Linear-inspired dark theme stylesheet and design tokens for PySide6.
"""

DARK_THEME_QSS = """
/* Global Window & Font */
QWidget {
    background-color: #121215;
    color: #e2e8f0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    font-size: 13px;
    selection-background-color: #6366f1;
    selection-color: #ffffff;
}

/* Main Window & Panes */
QMainWindow {
    background-color: #121215;
}

QFrame#HeaderFrame {
    background-color: #18181d;
    border-bottom: 1px solid #272730;
    padding: 8px 16px;
}

QFrame#FooterFrame {
    background-color: #18181d;
    border-top: 1px solid #272730;
    padding: 6px 16px;
}

/* Card Surfaces */
QFrame.Card {
    background-color: #1b1b22;
    border: 1px solid #292934;
    border-radius: 8px;
}

QFrame.Card:hover {
    border: 1px solid #4338ca;
}

/* Headings & Labels */
QLabel#AppTitle {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.3px;
}

QLabel#SectionHeader {
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding-bottom: 4px;
}

QLabel#BadgeActive {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#BadgeOffline {
    background-color: #272730;
    color: #94a3b8;
    border: 1px solid #3f3f4e;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#BadgeWarning {
    background-color: #78350f;
    color: #fbbf24;
    border: 1px solid #d97706;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

/* Push Buttons */
QPushButton {
    background-color: #262633;
    color: #f1f5f9;
    border: 1px solid #3b3b4f;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #323244;
    border-color: #6366f1;
}

QPushButton:pressed {
    background-color: #20202c;
}

QPushButton:disabled {
    background-color: #18181f;
    color: #525266;
    border-color: #262633;
}

/* Primary Action Button (Brand Accent) */
QPushButton#PrimaryBtn {
    background-color: #4f46e5;
    border: 1px solid #6366f1;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryBtn:hover {
    background-color: #4338ca;
    border-color: #818cf8;
}

QPushButton#PrimaryBtn:pressed {
    background-color: #3730a3;
}

/* Active Pause/Mute Button State */
QPushButton#PauseBtnActive {
    background-color: #b45309;
    border: 1px solid #f59e0b;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PauseBtnActive:hover {
    background-color: #d97706;
    border-color: #fbbf24;
}

/* Test Action Button inside cards */
QPushButton#TestBtn {
    background-color: #242432;
    border: 1px solid #3d3d52;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#TestBtn:hover {
    background-color: #6366f1;
    border-color: #818cf8;
    color: #ffffff;
}

/* ComboBox Dropdowns */
QComboBox {
    background-color: #1b1b24;
    border: 1px solid #313142;
    border-radius: 6px;
    padding: 5px 12px;
    color: #e2e8f0;
    min-width: 130px;
}

QComboBox:hover {
    border-color: #6366f1;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #181820;
    border: 1px solid #333345;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
    padding: 4px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #121216;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #2e2e3d;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4f46e5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Progress Bar */
QProgressBar {
    background-color: #1e1e28;
    border: 1px solid #313142;
    border-radius: 5px;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    font-size: 12px;
    height: 14px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #10b981);
    border-radius: 4px;
}

/* Tooltips */
QToolTip {
    background-color: #1f1f2a;
    border: 1px solid #4338ca;
    color: #ffffff;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}
"""
