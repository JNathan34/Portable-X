from PySide6.QtCore import Qt, Property
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from config import *

class GlassPanel(QWidget):
    """
    A container that renders a glass-like background with a border.
    """
    def __init__(self, parent=None, radius=BORDER_RADIUS, opacity=0.05):
        super().__init__(parent)
        self.radius = radius
        self.base_opacity = opacity
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Glass Background
        bg_color = QColor(255, 255, 255, int(255 * self.base_opacity))
        painter.setBrush(bg_color)
        
        # Glass Border
        pen = QPen(COLOR_GLASS_BORDER)
        pen.setWidth(1)
        painter.setPen(pen)
        
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, self.radius, self.radius)

class AnimatableWidget(QWidget):
    """
    Base class for widgets that need background color animation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_color = QColor(0, 0, 0, 0)
        self._border_color = QColor(0, 0, 0, 0)

    def get_bg_color(self):
        return self._bg_color

    def set_bg_color(self, color):
        self._bg_color = color
        self.update()

    bg_color = Property(QColor, get_bg_color, set_bg_color)