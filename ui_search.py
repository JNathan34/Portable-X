from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit
from config import *

class SearchIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._color_override = None

    def set_color(self, color):
        self._color_override = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(self._color_override or COLOR_TEXT_SUB)
        pen.setWidthF(2.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        painter.drawEllipse(4, 4, 11, 11)
        painter.drawLine(13, 13, 19, 19)

class SearchBar(QWidget):
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        
        # Input Field
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search")
        self.input.setFont(QFont(FONT_FAMILY, 12))
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_MAIN.name()};
                selection-background-color: {COLOR_ACCENT.name()};
            }}
        """)
        self.input.textChanged.connect(self.textChanged)
        
        # Icon
        self.icon_lbl = SearchIcon()
        
        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.input)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw the container shape
        painter.setBrush(COLOR_GLASS_WHITE)
        painter.setPen(QPen(COLOR_GLASS_BORDER, 1))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 6, 6)
