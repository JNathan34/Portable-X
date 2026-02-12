import os
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QRect, Signal, QFileInfo, QTimer
from PySide6.QtGui import QColor, QPainter, QFont, QPixmap, QCursor, QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect, QMenu, QFileIconProvider
from config import *
from ui_base import AnimatableWidget

_ICON_CACHE = {}

def _load_icon_pixmap(path, size, fallback_path=None):
    if not path and not fallback_path:
        return None
    cache_key = (path or "", fallback_path or "", int(size))
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    def _try_path(p):
        if not p or not os.path.exists(p):
            return None
        icon = QIcon(p)
        if not icon.isNull():
            pix = icon.pixmap(size, size)
            if not pix.isNull():
                return pix
        provider = QFileIconProvider()
        info = QFileInfo(p)
        icon = provider.icon(info)
        if not icon.isNull():
            pix = icon.pixmap(size, size)
            if not pix.isNull():
                return pix
        if p.lower().endswith(".ico"):
            pix = QPixmap(p)
            if not pix.isNull():
                return pix
        return None

    pixmap = _try_path(path)
    if (pixmap is None or pixmap.isNull()) and fallback_path and fallback_path != path:
        pixmap = _try_path(fallback_path)

    if pixmap is not None and not pixmap.isNull():
        _ICON_CACHE[cache_key] = pixmap
        return pixmap

    return None

class AppTooltip(QWidget):
    def __init__(self, name, version, description, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #2b2f38;
                border: 1px solid #454545;
                border-radius: 4px;
            }
            QLabel {
                color: #e0e0e0;
                border: none;
                background: transparent;
            }
        """)
        
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 8, 10, 8)
        frame_layout.setSpacing(2)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        header_layout.addWidget(name_lbl)
        
        if version:
            ver_lbl = QLabel(f"v{version}")
            ver_lbl.setFont(QFont(FONT_FAMILY, 8))
            ver_lbl.setStyleSheet("color: #888888;")
            header_layout.addWidget(ver_lbl)
            
        header_layout.addStretch()
        frame_layout.addLayout(header_layout)
        
        if description:
            desc_lbl = QLabel(description)
            desc_lbl.setFont(QFont(FONT_FAMILY, 9))
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #cccccc;")
            desc_lbl.setMaximumWidth(300)
            frame_layout.addWidget(desc_lbl)
            
        layout.addWidget(frame)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        frame.setGraphicsEffect(shadow)

class AppListItem(AnimatableWidget):
    """
    Represents a single app in the left list.
    """
    clicked = Signal(str)

    def __init__(self, name, icon_path, exe_path, is_favorite=False, is_hidden=False, category="Other", version="", description="", parent=None):
        super().__init__(parent)
        self.name = name
        self.exe_path = exe_path
        self.is_favorite = is_favorite
        self.is_hidden = is_hidden
        self.category = category
        self.version = version
        self.description = description
        self.icon_pixmap = None
        
        self.tooltip_win = None
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(1500)
        self.hover_timer.timeout.connect(self.show_tooltip)

        # Load Icon
        self.icon_pixmap = _load_icon_pixmap(icon_path, 32, fallback_path=self.exe_path)
        
        if self.icon_pixmap and not self.icon_pixmap.isNull():
            self.icon_pixmap = self.icon_pixmap.scaled(
                18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        
        # Icon Placeholder (Draw a circle)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(18, 18)
        self.icon_label.setStyleSheet("background-color: transparent;")
        # We will draw the icon in paintEvent or use a pixmap. 
        # For simplicity/no-assets, we draw in paintEvent of this widget.
        
        self.text_label = QLabel(name)
        self.text_label.setFont(QFont(FONT_FAMILY, 9))
        if self.is_hidden:
            self.text_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        else:
            self.text_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()

        # Animation setup
        self.anim = QPropertyAnimation(self, b"bg_color")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        effective = getattr(self.window(), "effective_theme", "dark")
        dark = effective == "dark"
        bg = "#1b1f26" if dark else "#FDFDFD"
        fg = COLOR_TEXT_MAIN.name()
        border = "rgba(255, 255, 255, 0.2)" if dark else "rgba(0, 0, 0, 0.2)"
        def _apply_style():
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {bg};
                    color: {COLOR_TEXT_MAIN.name()};
                    border: 1px solid {border};
                }}
                QMenu::item {{
                    padding: 5px 20px;
                    color: {COLOR_TEXT_MAIN.name()};
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)
        _apply_style()
        if getattr(self.window(), "text_color", "") == "__rainbow__":
            timer = QTimer(menu)
            timer.timeout.connect(_apply_style)
            timer.start(120)
            menu.aboutToHide.connect(timer.stop)

        # Actions
        fav_action = menu.addAction("Favourite")
        fav_action.setCheckable(True)
        fav_action.setChecked(self.is_favorite)
        fav_action.triggered.connect(lambda: self.window().toggle_favorite(self.exe_path))

        menu.addSeparator()

        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self.window().request_rename(self.exe_path, self.name))

        cat_action = menu.addAction("Change Category")
        cat_action.triggered.connect(lambda: self.window().request_category(self.exe_path))

        menu.addSeparator()

        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(lambda: self.window().refresh_apps())

        explore_action = menu.addAction("Explore Here")
        explore_action.triggered.connect(lambda: self.window().explore_app_dir(self.exe_path))

        menu.addSeparator()

        hide_action = menu.addAction("Unhide" if self.is_hidden else "Hide")
        hide_action.triggered.connect(lambda: self.window().toggle_hide(self.exe_path))

        show_hidden_action = menu.addAction("Show Hidden Icons")
        show_hidden_action.setCheckable(True)
        show_hidden_action.setChecked(self.window().show_hidden)
        show_hidden_action.triggered.connect(lambda: self.window().toggle_show_hidden())

        menu.exec(event.globalPos())

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(COLOR_HOVER)
        self.anim.start()
        self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(QColor(0, 0, 0, 0))
        self.anim.start()
        self.hover_timer.stop()
        if self.tooltip_win:
            self.tooltip_win.close()
            self.tooltip_win = None
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.tooltip_win:
            self.tooltip_win.close()
            self.tooltip_win = None
        if event.button() == Qt.LeftButton:
            self._bg_color = COLOR_PRESSED
            self.update()
            self.clicked.emit(self.exe_path)
        super().mousePressEvent(event)

    def show_tooltip(self):
        if not self.tooltip_win:
            desc = self.description
            if (not desc or not desc.strip()) and self.exe_path:
                desc = QFileInfo(self.exe_path).fileName()
            self.tooltip_win = AppTooltip(self.name, self.version, desc)
            cursor_pos = QCursor.pos()
            self.tooltip_win.move(cursor_pos + QPoint(10, 10))
            self.tooltip_win.show()

    def mouseReleaseEvent(self, event):
        # Return to hover state
        self._bg_color = COLOR_HOVER
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw Background (Animated)
        if self._bg_color.alpha() > 0:
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 8, 8)

        # Draw Icon
        if self.icon_pixmap and not self.icon_pixmap.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            x = 10 + (18 - self.icon_pixmap.width()) // 2
            y = 7 + (18 - self.icon_pixmap.height()) // 2
            painter.drawPixmap(x, y, self.icon_pixmap)
        else:
            # Draw Dummy Icon (Circle with letter)
            icon_rect = QRect(10, 7, 18, 18)
            
            # Generate a consistent color based on name hash
            hue = abs(hash(self.name)) % 360
            icon_color = QColor.fromHsl(hue, 200, 150)
            
            painter.setBrush(icon_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(icon_rect)
            
            # Draw first letter
            painter.setPen(QColor("#101010"))
            painter.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
            painter.drawText(icon_rect, Qt.AlignCenter, self.name[0])


class AppGridItem(AnimatableWidget):
    """
    Represents a single app in grid view.
    """
    clicked = Signal(str)

    def __init__(self, name, icon_path, exe_path, is_favorite=False, is_hidden=False, category="Other", version="", description="", parent=None, tile_width=110, tile_height=90, font_size=None):
        super().__init__(parent)
        self.name = name
        self.display_name = (name.split()[0] if name else "")
        self.exe_path = exe_path
        self.is_favorite = is_favorite
        self.is_hidden = is_hidden
        self.category = category
        self.version = version
        self.description = description
        self.icon_pixmap = None

        self.tooltip_win = None
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(1500)
        self.hover_timer.timeout.connect(self.show_tooltip)

        # Load Icon
        self.icon_pixmap = _load_icon_pixmap(icon_path, 48, fallback_path=self.exe_path)

        icon_size = max(24, min(40, int(tile_width * 0.35)))
        if self.icon_pixmap and not self.icon_pixmap.isNull():
            self.icon_pixmap = self.icon_pixmap.scaled(
                icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            self.icon_pixmap = self._make_fallback_icon(icon_size)

        self.setFixedSize(tile_width, tile_height)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(icon_size, icon_size)
        self.icon_label.setPixmap(self.icon_pixmap)
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.text_label = QLabel(self.display_name)
        if font_size is None:
            if tile_width <= 60:
                font_size = 6
            elif tile_width <= 80:
                font_size = 7
            elif tile_width <= 110:
                font_size = 8
            else:
                font_size = 9
        self.text_label.setFont(QFont(FONT_FAMILY, int(font_size)))
        self.text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.text_label.setWordWrap(True)
        if self.is_hidden:
            self.text_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        else:
            self.text_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")

        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)
        layout.addWidget(self.text_label, 0, Qt.AlignHCenter)
        layout.addStretch()

        self.anim = QPropertyAnimation(self, b"bg_color")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def _make_fallback_icon(self, size):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        hue = abs(hash(self.name)) % 360
        icon_color = QColor.fromHsl(hue, 200, 150)
        painter.setBrush(icon_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.setPen(QColor("#101010"))
        painter.setFont(QFont(FONT_FAMILY, max(9, int(size * 0.3)), QFont.Bold))
        painter.drawText(pix.rect(), Qt.AlignCenter, self.name[0])
        painter.end()
        return pix

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        effective = getattr(self.window(), "effective_theme", "dark")
        dark = effective == "dark"
        bg = "#1b1f26" if dark else "#FDFDFD"
        border = "rgba(255, 255, 255, 0.2)" if dark else "rgba(0, 0, 0, 0.2)"

        def _apply_style():
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {bg};
                    color: {COLOR_TEXT_MAIN.name()};
                    border: 1px solid {border};
                }}
                QMenu::item {{
                    padding: 5px 20px;
                    color: {COLOR_TEXT_MAIN.name()};
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)

        _apply_style()
        if getattr(self.window(), "text_color", "") == "__rainbow__":
            timer = QTimer(menu)
            timer.timeout.connect(_apply_style)
            timer.start(120)
            menu.aboutToHide.connect(timer.stop)

        fav_action = menu.addAction("Favourite")
        fav_action.setCheckable(True)
        fav_action.setChecked(self.is_favorite)
        fav_action.triggered.connect(lambda: self.window().toggle_favorite(self.exe_path))

        menu.addSeparator()

        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self.window().request_rename(self.exe_path, self.name))

        cat_action = menu.addAction("Change Category")
        cat_action.triggered.connect(lambda: self.window().request_category(self.exe_path))

        menu.addSeparator()

        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(lambda: self.window().refresh_apps())

        explore_action = menu.addAction("Explore Here")
        explore_action.triggered.connect(lambda: self.window().explore_app_dir(self.exe_path))

        menu.addSeparator()

        hide_action = menu.addAction("Unhide" if self.is_hidden else "Hide")
        hide_action.triggered.connect(lambda: self.window().toggle_hide(self.exe_path))

        show_hidden_action = menu.addAction("Show Hidden Icons")
        show_hidden_action.setCheckable(True)
        show_hidden_action.setChecked(self.window().show_hidden)
        show_hidden_action.triggered.connect(lambda: self.window().toggle_show_hidden())

        menu.exec(event.globalPos())

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(COLOR_HOVER)
        self.anim.start()
        self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(QColor(0, 0, 0, 0))
        self.anim.start()
        self.hover_timer.stop()
        if self.tooltip_win:
            self.tooltip_win.close()
            self.tooltip_win = None
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.tooltip_win:
            self.tooltip_win.close()
            self.tooltip_win = None
        if event.button() == Qt.LeftButton:
            self._bg_color = COLOR_PRESSED
            self.update()
            self.clicked.emit(self.exe_path)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._bg_color = COLOR_HOVER
        self.update()
        super().mouseReleaseEvent(event)

    def show_tooltip(self):
        if not self.tooltip_win:
            desc = self.description
            if (not desc or not desc.strip()) and self.exe_path:
                desc = QFileInfo(self.exe_path).fileName()
            self.tooltip_win = AppTooltip(self.name, self.version, desc)
            cursor_pos = QCursor.pos()
            self.tooltip_win.move(cursor_pos + QPoint(10, 10))
            self.tooltip_win.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._bg_color.alpha() > 0:
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 10, 10)
