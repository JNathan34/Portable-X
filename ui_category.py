import os
from PySide6.QtCore import Qt, QSize, QEasingCurve, QPropertyAnimation, Signal, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog, QComboBox, QDialogButtonBox
from config import *
from ui_base import AnimatableWidget
from ui_app_item import AppListItem

class CategorySelectionDialog(QDialog):
    def __init__(self, categories, current_category, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Category")
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.resize(300, 120)
        
        # Style
        self.setStyleSheet("""
            QDialog { background-color: #1b1f26; color: white; }
            QLabel { color: white; font-size: 14px; font-family: "Segoe UI"; }
            QComboBox { 
                background-color: #2d323b; 
                color: white; 
                border: 1px solid #3e4451; 
                padding: 5px; 
                border-radius: 4px;
                font-family: "Segoe UI";
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #2d323b;
                color: white;
                selection-background-color: #0078d4;
                outline: none;
            }
            QPushButton {
                background-color: #2d323b;
                color: white;
                border: 1px solid #3e4451; 
                padding: 5px 15px;
                border-radius: 4px;
                font-family: "Segoe UI";
            }
            QPushButton:hover { background-color: #3e4451; }
        """)

        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select Category:"))
        
        self.combo = QComboBox()
        self.combo.setIconSize(QSize(24, 24))
        
        for cat in categories:
            icon_path = get_category_icon_path(cat)
            icon = QIcon(icon_path) if icon_path and os.path.exists(icon_path) else QIcon()
            self.combo.addItem(icon, cat)
            
        index = self.combo.findText(current_category)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        self.combo.activated.connect(self.accept)
            
        layout.addWidget(self.combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_category(self):
        return self.combo.currentText()

class CategoryHeader(AnimatableWidget):
    clicked = Signal()
    
    def __init__(self, name, icon_path, parent=None):
        super().__init__(parent)
        self.name = name
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setStyleSheet("background-color: transparent;")
        
        self.icon_pixmap = None
        if icon_path and os.path.exists(icon_path):
            self.icon_pixmap = QPixmap(icon_path)
            self.icon_pixmap = self.icon_pixmap.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
        self.text_label = QLabel(name)
        self.text_label.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.text_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")
        
        self.arrow_label = QLabel("▶")
        self.arrow_label.setFont(QFont(FONT_FAMILY, 8))
        self.arrow_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        layout.addWidget(self.arrow_label)
        
        self.anim = QPropertyAnimation(self, b"bg_color")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def set_expanded(self, expanded):
        self.arrow_label.setText("▼" if expanded else "▶")

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(COLOR_HOVER)
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(QColor(0, 0, 0, 0))
        self.anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._bg_color = COLOR_PRESSED
            self.update()
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._bg_color = COLOR_HOVER
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self._bg_color.alpha() > 0:
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 8, 8)

        if self.icon_pixmap and not self.icon_pixmap.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            x = 10 + (18 - self.icon_pixmap.width()) // 2
            y = 7 + (18 - self.icon_pixmap.height()) // 2
            painter.drawPixmap(x, y, self.icon_pixmap)
        else:
            # Dummy Icon
            icon_rect = QRect(10, 7, 18, 18)
            hue = abs(hash(self.name)) % 360
            icon_color = QColor.fromHsl(hue, 200, 150)
            painter.setBrush(icon_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(icon_rect)

class CategoryItem(QWidget):
    app_clicked = Signal(str)
    toggled = Signal(bool, QWidget)

    def __init__(self, name, icon_path, apps, parent=None, lazy=True):
        super().__init__(parent)
        self.name = name
        self.apps_data = apps
        self.expanded = False
        self._items_built = False
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.header = CategoryHeader(name, icon_path, self)
        self.header.clicked.connect(self.toggle_expand)
        self.layout.addWidget(self.header)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 0, 0, 0)
        self.content_layout.setSpacing(1)
        self._content_anim = None
        
        self.app_items = []
        if not lazy:
            self._ensure_items()
            
        self.layout.addWidget(self.content_widget)
        self.content_widget.setMaximumHeight(0)
        self.content_widget.hide()
        self.header.set_expanded(False)

    def _ensure_items(self):
        if self._items_built:
            return
        self._items_built = True
        for app in self.apps_data:
            item = AppListItem(app["name"], app["icon"], app["exe"], app["is_favorite"], app["is_hidden"], app["category"], app["version"], app["description"])
            item.clicked.connect(self.app_clicked.emit)
            self.content_layout.addWidget(item)
            self.app_items.append(item)

    def _set_content_visible(self, visible, animate=False):
        if self._content_anim:
            self._content_anim.stop()
            self._content_anim = None

        if visible:
            self._ensure_items()
        if not animate:
            if visible:
                self.content_widget.show()
                self.content_widget.setMaximumHeight(16777215)
            else:
                self.content_widget.hide()
                self.content_widget.setMaximumHeight(0)
            return

        if visible:
            self.content_widget.setMaximumHeight(0)
            self.content_widget.show()
            target = self.content_widget.sizeHint().height()
            if target <= 0:
                target = self.content_layout.sizeHint().height()
            self._content_anim = QPropertyAnimation(self.content_widget, b"maximumHeight")
            self._content_anim.setDuration(180)
            self._content_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._content_anim.setStartValue(0)
            self._content_anim.setEndValue(target)
            self._content_anim.finished.connect(lambda: self.content_widget.setMaximumHeight(16777215))
            self._content_anim.start()
        else:
            start = self.content_widget.height()
            self._content_anim = QPropertyAnimation(self.content_widget, b"maximumHeight")
            self._content_anim.setDuration(160)
            self._content_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._content_anim.setStartValue(start)
            self._content_anim.setEndValue(0)
            def _after():
                self.content_widget.hide()
                self.content_widget.setMaximumHeight(0)
            self._content_anim.finished.connect(_after)
            self._content_anim.start()

    def toggle_expand(self):
        self.expanded = not self.expanded
        self.header.set_expanded(self.expanded)
        if self.expanded:
            self._ensure_items()
        self._set_content_visible(self.expanded, animate=True)
        self.toggled.emit(self.expanded, self)
            
    def set_expanded(self, expanded, animate=False):
        self.expanded = expanded
        self.header.set_expanded(expanded)
        if expanded:
            self._ensure_items()
        self._set_content_visible(self.expanded, animate=animate)

    def filter(self, text, search_descriptions=False):
        if text:
            self._ensure_items()
        match_cat = text in self.name.lower()
        has_visible_app = False
        
        for item in self.app_items:
            name_match = text in item.name.lower()
            desc_match = search_descriptions and text in (item.description or "").lower()
            if name_match or desc_match:
                item.show()
                has_visible_app = True
            else:
                if match_cat:
                    item.show()
                else:
                    item.hide()
        
        if match_cat or has_visible_app:
            self.show()
            if has_visible_app and text:
                self._set_content_visible(True, animate=False)
                self.header.set_expanded(True)
            elif not text:
                self._set_content_visible(self.expanded, animate=False)
                self.header.set_expanded(self.expanded) # Restore state
        else:
            self.hide()
