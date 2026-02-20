from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property, QRect, QPointF, QPoint, QSize, QFileInfo, QTimer, QSequentialAnimationGroup, QThread, QObject, QEvent
from PySide6.QtGui import QFont, QKeySequence, QColor, QPainter, QImage, QPixmap, QLinearGradient, QPainterPath, QIcon, QBrush, QPalette, QCursor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QButtonGroup, QSizePolicy, QComboBox, QColorDialog, QFileDialog, QLineEdit,
    QGridLayout, QListView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QStyledItemDelegate, QStyle, QDialog, QDialogButtonBox, QCheckBox, QApplication,
    QFileIconProvider, QToolTip, QInputDialog, QMessageBox, QProgressBar
)
import hashlib
import json
import shutil
import subprocess
import ctypes
import socket
import time
import re

_ACTIVE_THREADS = set()

def _track_thread(thread):
    if not thread:
        return
    _ACTIVE_THREADS.add(thread)
    try:
        thread.finished.connect(lambda: _ACTIVE_THREADS.discard(thread))
    except Exception:
        pass
from config import *
from app_info import get_app_about_text, get_app_display_name
from ui_base import GlassPanel, AnimatableWidget
from ui_search import SearchBar
import os
from ui_sidebar import QuickAccessButton

def _no_window_kwargs():
    if os.name != "nt":
        return {}
    kwargs = {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creationflags:
        kwargs["creationflags"] = creationflags
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    return kwargs


CONTROL_WIDTH = 120
SMALL_CONTROL_WIDTH = 80
CONTROL_HEIGHT = 22
SMALL_CONTROL_HEIGHT = 26
SMALL_CONTROL_FONT_SIZE = 12

def rgba(color):
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"

def combo_palette():
    dark = COLOR_BG_START.lightness() < 128
    bg = "rgba(255, 255, 255, 0.06)" if dark else "rgba(0, 0, 0, 0.05)"
    border = "rgba(255, 255, 255, 0.22)" if dark else "rgba(0, 0, 0, 0.22)"
    hover = "rgba(255, 255, 255, 0.12)" if dark else "rgba(0, 0, 0, 0.08)"
    line = "rgba(255, 255, 255, 0.16)" if dark else "rgba(0, 0, 0, 0.16)"
    return {
        "bg": bg,
        "border": border,
        "hover": hover,
        "line": line,
        "dark": dark,
    }

def dropdown_palette():
    dark = COLOR_BG_START.lightness() < 128
    bg = QColor(30, 33, 38, 240) if dark else QColor(245, 247, 251, 245)
    border = QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 35)
    divider = QColor(255, 255, 255, 26) if dark else QColor(0, 0, 0, 26)
    return {
        "bg": bg,
        "border": border,
        "divider": divider,
        "dark": dark,
    }

def combo_style():
    palette = combo_palette()
    glass = palette["bg"]
    border = palette["border"]
    arrow = COLOR_TEXT_SUB.name().replace("#", "")
    line = palette["line"]
    hover = palette["hover"]
    return f"""
        QComboBox {{
            background-color: {glass};
            color: {COLOR_TEXT_MAIN.name()};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 4px 26px 4px 10px;
            font-family: "{FONT_FAMILY}";
            font-size: 11px;
        }}
        QComboBox:hover {{
            background-color: {hover};
            border-color: {COLOR_ACCENT.name()};
        }}
        QComboBox:focus {{
            border-color: {COLOR_ACCENT.name()};
        }}
        QComboBox:on {{
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            border-bottom: 0px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
            border-left: 1px solid {border};
        }}
        QComboBox::down-arrow {{
            width: 8px;
            height: 8px;
            image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='6' height='8' viewBox='0 0 6 8'><path d='M1 1l3 3-3 3' fill='none' stroke='%23{arrow}' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'/></svg>");
        }}
        QComboBox:on QComboBox::down-arrow {{
            image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='8' height='6' viewBox='0 0 8 6'><path d='M1 1l3 3 3-3' fill='none' stroke='%23{arrow}' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'/></svg>");
        }}
        QComboBox QAbstractItemView {{
            background-color: transparent;
            color: {COLOR_TEXT_MAIN.name()};
            selection-background-color: {COLOR_ACCENT.name()};
            outline: none;
            border: 1px solid {border};
            border-bottom-left-radius: 6px;
            border-bottom-right-radius: 6px;
            padding: 6px 0px;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 6px 10px;
            margin: 0px 8px;
            border-bottom: 1px solid {line};
            border-radius: 6px;
            background: transparent;
        }}
        QComboBox QAbstractItemView::item:last {{
            border-bottom: none;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: transparent;
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: transparent;
            color: {COLOR_TEXT_MAIN.name()};
        }}
    """


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._offset = 0
        self._hovered = False
        self.setFixedSize(44, 22)
        self.setCursor(Qt.PointingHandCursor)

        self.anim = QPropertyAnimation(self, b"thumb_offset")
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)
        self._sync_offset(animate=False)

    def sizeHint(self):
        return self.size()

    def isChecked(self):
        return self._checked

    def setChecked(self, checked, animate=True):
        if self._checked == checked:
            return
        self._checked = checked
        self._sync_offset(animate=animate)
        self.toggled.emit(self._checked)
        self.update()

    def toggle(self):
        self.setChecked(not self._checked)

    def _sync_offset(self, animate=True):
        thumb_d = self.height() - 6
        off = 3 if not self._checked else self.width() - thumb_d - 3
        if animate:
            self.anim.stop()
            self.anim.setStartValue(self._offset)
            self.anim.setEndValue(off)
            self.anim.start()
        else:
            self._offset = off
            self.update()

    def get_thumb_offset(self):
        return self._offset

    def set_thumb_offset(self, value):
        self._offset = value
        self.update()

    thumb_offset = Property(float, get_thumb_offset, set_thumb_offset)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def set_hovered(self, value):
        self._hovered = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track_rect = self.rect().adjusted(1, 1, -1, -1)
        dark = COLOR_BG_START.lightness() < 128
        if dark:
            track_color = QColor(255, 255, 255, 35)
            border_color = QColor(255, 255, 255, 60)
        else:
            track_color = QColor(0, 0, 0, 35)
            border_color = QColor(0, 0, 0, 80)
        if self._checked:
            track_color = QColor(COLOR_ACCENT)
            border_color = QColor(COLOR_ACCENT)
        elif self._hovered:
            border_color = QColor(COLOR_ACCENT)

        painter.setBrush(track_color)
        painter.setPen(border_color)
        painter.drawRoundedRect(track_rect, track_rect.height() / 2, track_rect.height() / 2)

        thumb_d = self.height() - 6
        thumb_rect = QRect(int(self._offset), 3, thumb_d, thumb_d)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(thumb_rect)


class ColorGridPicker(QWidget):
    colorSelected = Signal(str)

    def __init__(self, colors, current_value="", columns=8, parent=None):
        super().__init__(parent)
        self._buttons = []
        self._current = current_value or ""
        self._preset_values = set()
        self._columns = max(1, int(columns))

        self._name_map = {
            "#ED1C24": "Red",
            "#FF7F27": "Orange",
            "#FFF200": "Yellow",
            "#22B14C": "Green",
            "#00A2E8": "Blue",
            "#3F48CC": "Indigo",
            "#A349A4": "Purple",
            "#FFAEC9": "Pink",
            "#B5E61D": "Lime",
            "#99D9EA": "Light blue",
            "#FFFFFF": "White",
            "#E6E6E6": "Light gray",
            "#101318": "Charcoal",
            "#4D5561": "Slate",
        }

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(6)

        for idx, item in enumerate(colors):
            label = item.get("label", "")
            value = item.get("value", "")
            is_custom = item.get("custom", False)
            if value and value != "__custom__":
                self._preset_values.add(value)

            btn = QPushButton()
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("value", value)
            btn.setProperty("custom", is_custom)
            btn.setToolTip(self._tooltip_for(label, value))

            if is_custom:
                btn.setText("…")
            else:
                btn.setText("")

            self._buttons.append(btn)
            row = idx // self._columns
            col = idx % self._columns
            layout.addWidget(btn, row, col)

            btn.clicked.connect(self._on_click)

        self._apply_styles()

    def _tooltip_for(self, label, value):
        if label and not label.startswith("#"):
            return label
        if value and value in self._name_map:
            return self._name_map[value]
        if label and label in self._name_map:
            return self._name_map[label]
        return label or value or ""

    def _apply_styles(self):
        dark = COLOR_BG_START.lightness() < 128
        tip_bg = QColor("#1b1f26") if dark else QColor("#FDFDFD")
        tip_text = QColor(COLOR_TEXT_MAIN)
        palette = QPalette()
        palette.setColor(QPalette.ToolTipBase, tip_bg)
        palette.setColor(QPalette.ToolTipText, tip_text)
        QToolTip.setPalette(palette)
        QToolTip.setFont(QFont(FONT_FAMILY, 11))
        base_dir = get_base_dir()
        icon_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "settingsicons")
        custom_icon_path = os.path.join(icon_dir, "colorwheel.png")
        default_icon_path = os.path.join(icon_dir, "system.png")
        for btn in self._buttons:
            value = btn.property("value")
            is_custom = btn.property("custom")
            is_selected = (value == self._current)
            if is_custom and self._current and self._current not in self._preset_values:
                is_selected = True

            if is_custom:
                bg = "rgba(255, 255, 255, 0.08)"
                text = COLOR_TEXT_MAIN.name()
            elif value:
                bg = value
                text = "#ffffff"
            else:
                bg = "rgba(255, 255, 255, 0.12)"
                text = COLOR_TEXT_MAIN.name()

            border = COLOR_ACCENT.name() if is_selected else qcolor_to_rgba(COLOR_GLASS_BORDER)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {text};
                    border: 1px solid {border};
                    border-radius: 4px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    border-color: {COLOR_ACCENT.name()};
                }}
            """)
            if is_custom:
                if os.path.exists(custom_icon_path):
                    btn.setIcon(QIcon(custom_icon_path))
                    btn.setIconSize(QSize(14, 14))
                btn.setText("")
            elif value == "":
                if os.path.exists(default_icon_path):
                    btn.setIcon(QIcon(default_icon_path))
                    btn.setIconSize(QSize(14, 14))
                btn.setText("")
            else:
                btn.setIcon(QIcon())
                btn.setText("")

    def set_current(self, value):
        self._current = value or ""
        self._apply_styles()

    def _on_click(self):
        btn = self.sender()
        value = btn.property("value")
        is_custom = btn.property("custom")

        if is_custom:
            color = QColorDialog.getColor(QColor(self._current or "#ffffff"), self, "Custom Color")
            if color.isValid():
                self._current = color.name()
                self._apply_styles()
                self.colorSelected.emit(self._current)
            return

        self._current = value or ""
        self._apply_styles()
        self.colorSelected.emit(self._current)


class MiniMenuPreview(QWidget):
    def __init__(self, settings, base_dir, parent=None):
        super().__init__(parent)
        self._settings = settings or {}
        self._base_dir = base_dir
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        self._items_container = QWidget()
        self._items_container.setAttribute(Qt.WA_TranslucentBackground)
        self._items_layout = QVBoxLayout(self._items_container)
        self._items_layout.setContentsMargins(8, 8, 8, 8)
        self._items_layout.setSpacing(4)
        self._layout.addWidget(self._items_container)
        self._rebuild()

    def update_config(self, settings):
        self._settings = settings or {}
        self._rebuild()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            rect = self.rect().adjusted(1, 1, -1, -1)
            border = QColor(COLOR_GLASS_BORDER)
            bg_type = self._settings.get("mini_menu_background_type", "default")
            if bg_type == "solid":
                color = self._settings.get("mini_menu_background_color", "")
                if color:
                    painter.setBrush(QColor(color))
                    painter.setPen(border)
                    painter.drawRoundedRect(rect, 8, 8)
                    return
            if bg_type == "gradient":
                start = self._settings.get("mini_menu_background_gradient_start", "")
                end = self._settings.get("mini_menu_background_gradient_end", "")
                if start and end:
                    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
                    grad.setColorAt(0.0, QColor(start))
                    grad.setColorAt(1.0, QColor(end))
                    painter.setBrush(grad)
                    painter.setPen(border)
                    painter.drawRoundedRect(rect, 8, 8)
                    return
            # Default background
            painter.setBrush(QBrush(self._preview_bg_color()))
            painter.setPen(border)
            painter.drawRoundedRect(rect, 8, 8)
        finally:
            painter.end()

    def _rebuild(self):
        while self._items_layout.count():
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        icon_dir = os.path.join(self._base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons")
        use_icons = self._settings.get("mini_show_icons", True)
        text_color = self._preview_text_color()
        divider_color = self._preview_divider_color(text_color)

        def _add_item(label, icon_file):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(8)
            scale = float(self._settings.get("mini_menu_scale", "1.0") or "1.0")
            icon_size = int(14 * scale)
            if use_icons:
                icon_label = QLabel()
                icon_path = os.path.join(icon_dir, icon_file)
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                    icon_label.setPixmap(icon.pixmap(icon_size, icon_size))
                icon_label.setFixedSize(icon_size, icon_size)
                if not icon_file:
                    icon_label.setText("✕")
                    icon_label.setStyleSheet(f"color: {text_color};")
                    icon_label.setAlignment(Qt.AlignCenter)
                row_layout.addWidget(icon_label)
            text = QLabel(label)
            font = text.font()
            font.setPointSizeF(10 * scale)
            text.setFont(font)
            text.setStyleSheet(f"color: {text_color};")
            row_layout.addWidget(text, 1)
            self._items_layout.addWidget(row)

        def _add_divider():
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {divider_color};")
            self._items_layout.addWidget(line)

        entries = []
        if self._settings.get("mini_show_documents", True):
            entries.append(("Documents", "documents.png"))
        if self._settings.get("mini_show_music", True):
            entries.append(("Music", "music.png"))
        if self._settings.get("mini_show_videos", True):
            entries.append(("Videos", "videos.png"))
        if self._settings.get("mini_show_downloads", True):
            entries.append(("Downloads", "download.png"))
        if self._settings.get("mini_show_explore", True):
            entries.append(("Explore", "explore.png"))
        if self._settings.get("mini_show_settings", True):
            entries.append(("Settings", "options.png"))

        for label, icon_file in entries:
            _add_item(label, icon_file)

        pinned = self._settings.get("mini_pinned_preview", [])
        if pinned:
            _add_divider()
            for name in pinned:
                _add_item(name, "")

        if entries and (self._settings.get("mini_show_all_apps", True) or self._settings.get("mini_show_favorites", True)):
            _add_divider()

        if self._settings.get("mini_show_all_apps", True):
            _add_item("All Apps", "apps.png")
        if self._settings.get("mini_show_favorites", True):
            _add_item("Favorites", "favourites.png")

        if self._settings.get("mini_show_exit", True):
            _add_divider()
            _add_item("Exit", "")

    def _preview_bg_color(self):
        bg_type = self._settings.get("mini_menu_background_type", "default")
        if bg_type == "solid":
            color = self._settings.get("mini_menu_background_color", "")
            if color:
                return QColor(color)
        if bg_type == "gradient":
            start = self._settings.get("mini_menu_background_gradient_start", "")
            end = self._settings.get("mini_menu_background_gradient_end", "")
            if start and end:
                c1 = QColor(start)
                c2 = QColor(end)
                r = (c1.red() + c2.red()) // 2
                g = (c1.green() + c2.green()) // 2
                b = (c1.blue() + c2.blue()) // 2
                return QColor(r, g, b)
        # default
        mode = self._settings.get("theme_mode", "system")
        if mode == "dark":
            return QColor("#060606")
        if mode == "light":
            return QColor("#FDFDFD")
        # system: use app palette
        try:
            palette = QApplication.palette()
            window_color = palette.color(QPalette.Window)
            return QColor("#060606") if window_color.lightness() < 128 else QColor("#FDFDFD")
        except Exception:
            return QColor("#060606") if COLOR_BG_START.lightness() < 128 else QColor("#FDFDFD")

    def _preview_text_color(self):
        custom = self._settings.get("mini_menu_text_color", "")
        if custom == "__rainbow__":
            import time as _t
            hue = int((_t.time() * 60) % 360)
            color = QColor.fromHsv(hue, 255, 255)
            return color.name()
        if custom:
            return custom
        bg = self._preview_bg_color()
        return "#ffffff" if bg.lightness() < 128 else "#101318"

    def _preview_divider_color(self, text_hex):
        color = QColor(text_hex)
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, 60)"

class GlassItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(8, 4, -8, -4)

        if option.state & QStyle.State_Selected:
            painter.setBrush(QColor(COLOR_ACCENT.red(), COLOR_ACCENT.green(), COLOR_ACCENT.blue(), 140))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(QColor(255, 255, 255, 35))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)

        icon = index.data(Qt.DecorationRole)
        icon_size = 16
        text_left = rect.left() + 8
        if isinstance(icon, QIcon) and not icon.isNull():
            icon_rect = QRect(text_left, rect.center().y() - icon_size // 2, icon_size, icon_size)
            icon.paint(painter, icon_rect, Qt.AlignCenter, QIcon.Normal)
            text_left = icon_rect.right() + 6
        text_rect = QRect(text_left, rect.top(), rect.right() - text_left - 6, rect.height())

        if option.state & QStyle.State_Selected:
            painter.setPen(QColor("#ffffff"))
        else:
            painter.setPen(COLOR_TEXT_MAIN)

        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, index.data())
        painter.restore()

class ThemedComboView(QListView):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings or {}
        self._bg_cache = None
        self._bg_size = None
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("""
            QListView { background: transparent; }
            QListView::item { background: transparent; }
        """)

    def _build_background_pixmap(self, size):
        # solid themed popup background
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = dropdown_palette()["bg"]
        painter.fillRect(pixmap.rect(), bg)
        painter.end()
        return pixmap

    def paintEvent(self, event):
        from PySide6.QtGui import QPainterPath
        from PySide6.QtCore import QPointF

        painter = QPainter(self.viewport())
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            rect = self.viewport().rect()

            size = rect.size()
            if self._bg_cache is None or self._bg_size != size:
                self._bg_cache = self._build_background_pixmap(size)
                self._bg_size = size

            # Rounded bottom corners only (clip background)
            radius = 6.0
            x = rect.x()
            y = rect.y()
            w = rect.width()
            h = rect.height()
            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x + w, y)
            path.lineTo(x + w, y + h - radius)
            path.quadTo(x + w, y + h, x + w - radius, y + h)
            path.lineTo(x + radius, y + h)
            path.quadTo(x, y + h, x, y + h - radius)
            path.lineTo(x, y)

            if self._bg_cache:
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, self._bg_cache)

            # border
            painter.setClipping(False)
            painter.setPen(dropdown_palette()["border"])
            painter.drawPath(path)
        finally:
            painter.end()

        super().paintEvent(event)

class ThemedComboBox(QComboBox):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._popup_anim = None
        self._rainbow_override = None
        self.setView(ThemedComboView(settings, self))
        self.setItemDelegate(GlassItemDelegate())
        self.view().setSpacing(2)
        self.view().setMouseTracking(True)

    def set_rainbow_text_color(self, color_hex):
        self._rainbow_override = color_hex
        if color_hex:
            self.setStyleSheet(combo_style().replace(COLOR_TEXT_MAIN.name(), color_hex).replace(COLOR_TEXT_SUB.name(), color_hex))
        else:
            self.setStyleSheet(combo_style())

    def showPopup(self):
        super().showPopup()
        view = self.view()
        view.setMinimumWidth(self.width())
        popup = view.window()
        if popup:
            popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
            popup.setAttribute(Qt.WA_TranslucentBackground)
            shadow = QGraphicsDropShadowEffect(popup)
            shadow.setBlurRadius(36)
            shadow.setOffset(0, 12)
            shadow.setColor(QColor(0, 0, 0, 140))
            popup.setGraphicsEffect(shadow)

            palette = combo_palette()
            popup.setStyleSheet(f"""
                QListView {{
                    background-color: transparent;
                    border: none;
                    border-top: 0px;
                    border-bottom-left-radius: 8px;
                    border-bottom-right-radius: 8px;
                    padding: 8px 0px;
                    outline: none;
                }}
            """)

            popup.setFixedWidth(self.width())
            popup.setWindowOpacity(0.0)
            self._popup_anim = QPropertyAnimation(popup, b"windowOpacity", popup)
            self._popup_anim.setDuration(140)
            self._popup_anim.setEasingCurve(QEasingCurve.OutQuad)
            self._popup_anim.setStartValue(0.0)
            self._popup_anim.setEndValue(1.0)
        self._popup_anim.start()

class InfoCard(QFrame):
    clicked = Signal()

    def __init__(self, title, icon, dark, parent=None):
        super().__init__(parent)
        self._bg_base = "rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"
        self._bg_hover = "rgba(255, 255, 255, 0.09)" if dark else "rgba(0, 0, 0, 0.08)"
        self._apply_style(self._bg_base)
        self.setMouseTracking(True)
        self._clickable = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setStyleSheet("background: transparent; border: none;")
        if isinstance(icon, QIcon):
            icon_label.setPixmap(self._clean_icon(icon, 20))
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 11px; background: transparent; border: none;")
        self.value_label = QLabel("Loading...")
        self.value_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        self.value_label.setWordWrap(True)
        self.detail_label = QLabel(" ")
        self.detail_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
        self.detail_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.value_label)
        text_layout.addWidget(self.detail_label)
        layout.addLayout(text_layout, 1)

    def set_data(self, value, detail):
        self.value_label.setText(value)
        self.detail_label.setText(detail or " ")

    def set_clickable(self, enabled=True):
        self._clickable = bool(enabled)
        self.setCursor(Qt.PointingHandCursor if self._clickable else Qt.ArrowCursor)

    def enterEvent(self, event):
        self._apply_style(self._bg_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(self._bg_base)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _apply_style(self, bg):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: none;
                border-radius: 10px;
            }}
        """)

    def _clean_icon(self, icon, size):
        pix = icon.pixmap(size, size)
        if pix.isNull():
            return pix
        img = pix.toImage().convertToFormat(QImage.Format_ARGB32)
        if img.width() == 0 or img.height() == 0:
            return pix
        bg = QColor(img.pixel(0, 0))
        if bg.alpha() < 255:
            return pix
        tol = 8
        for y in range(img.height()):
            for x in range(img.width()):
                c = QColor(img.pixel(x, y))
                if (
                    abs(c.red() - bg.red()) <= tol
                    and abs(c.green() - bg.green()) <= tol
                    and abs(c.blue() - bg.blue()) <= tol
                ):
                    c.setAlpha(0)
                    img.setPixelColor(x, y, c)
        return QPixmap.fromImage(img)

class UsageGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.max_points = 60
        self._insets = (6, 6, 6, 6)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_insets(self, left, top, right, bottom):
        self._insets = (int(left), int(top), int(right), int(bottom))
        self.update()

    def add_value(self, value):
        try:
            val = float(value)
        except Exception:
            val = 0.0
        if val < 0:
            val = 0.0
        if val > 100:
            val = 100.0
        self.values.append(val)
        if len(self.values) > self.max_points:
            self.values = self.values[-self.max_points:]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left, top, right, bottom = self._insets
        rect = self.rect().adjusted(left, top, -right, -bottom)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawRoundedRect(rect, 6, 6)

        border_color = QColor(COLOR_TEXT_SUB)
        border_color.setAlpha(80)
        border_pen = QPen(border_color)
        border_pen.setWidthF(1.0)
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 6, 6)

        grid_color = QColor(COLOR_TEXT_SUB)
        grid_color.setAlpha(50)
        grid_pen = QPen(grid_color)
        grid_pen.setWidthF(1.0)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = rect.top() + (rect.height() * i / 4.0)
            painter.drawLine(rect.left(), y, rect.right(), y)
        for i in range(1, 6):
            x = rect.left() + (rect.width() * i / 6.0)
            painter.drawLine(x, rect.top(), x, rect.bottom())

        if len(self.values) < 2:
            return

        step = rect.width() / max(1, (len(self.values) - 1))
        path = QPainterPath()
        for idx, val in enumerate(self.values):
            x = rect.left() + (idx * step)
            y = rect.bottom() - (val / 100.0) * rect.height()
            if idx == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        pen = QPen(COLOR_ACCENT)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.drawPath(path)

class MetricCard(QFrame):
    def __init__(self, title, icon, dark, parent=None, show_graph=True, show_usage=True, extra_widget=None):
        super().__init__(parent)
        self._bg_base = "rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"
        self._bg_hover = "rgba(255, 255, 255, 0.09)" if dark else "rgba(0, 0, 0, 0.08)"
        self._apply_style(self._bg_base)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._base_detail = ""
        self._usage_text = ""
        self._usage_percent = None
        self._expanded = False
        self._expand_anim = None
        self._show_graph = bool(show_graph)
        self._show_usage = bool(show_usage)
        self._has_expand = self._show_graph or extra_widget is not None
        self._extra_widget = extra_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        icon_label = QLabel()
        icon_label.setStyleSheet("background: transparent; border: none;")
        if isinstance(icon, QIcon):
            icon_label.setPixmap(self._clean_icon(icon, 20))
        icon_label.setFixedSize(20, 20)
        header.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 11px; background: transparent; border: none;")
        self.value_label = QLabel("Loading...")
        self.value_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        self.value_label.setWordWrap(True)
        self.detail_label = QLabel(" ")
        self.detail_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
        self.detail_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.value_label)
        text_layout.addWidget(self.detail_label)
        header.addLayout(text_layout, 1)
        layout.addLayout(header)

        self.graph_container = QWidget()
        graph_layout = QVBoxLayout(self.graph_container)
        graph_layout.setContentsMargins(0, 4, 0, 0)
        graph_layout.setSpacing(6)
        self.graph = UsageGraph(self.graph_container) if self._show_graph else None
        if self.graph is not None:
            graph_layout.addWidget(self.graph)
        if self._extra_widget is not None:
            graph_layout.addWidget(self._extra_widget)
        self.graph_container.setMaximumHeight(0)
        self.graph_container.hide()
        layout.addWidget(self.graph_container)

    def _clean_icon(self, icon, size):
        pix = icon.pixmap(size, size)
        if pix.isNull():
            return pix
        img = pix.toImage().convertToFormat(QImage.Format_ARGB32)
        if img.width() == 0 or img.height() == 0:
            return pix
        bg = QColor(img.pixel(0, 0))
        if bg.alpha() < 255:
            return pix
        tol = 8
        for y in range(img.height()):
            for x in range(img.width()):
                c = QColor(img.pixel(x, y))
                if (
                    abs(c.red() - bg.red()) <= tol
                    and abs(c.green() - bg.green()) <= tol
                    and abs(c.blue() - bg.blue()) <= tol
                ):
                    c.setAlpha(0)
                    img.setPixelColor(x, y, c)
        return QPixmap.fromImage(img)

    def set_data(self, value, detail):
        self.value_label.setText(value)
        self._base_detail = detail or ""
        self._update_detail()

    def set_usage(self, percent=None, usage_text=""):
        self._usage_percent = percent
        self._usage_text = usage_text or ""
        if percent is not None and self._show_graph and self.graph is not None:
            self.graph.add_value(percent)
        self._update_detail()

    def _update_detail(self):
        lines = []
        if self._base_detail:
            lines.append(self._base_detail)
        show_usage_now = self._show_usage and (not self._has_expand or self._expanded)
        if show_usage_now and self._usage_text:
            lines.append(self._usage_text)
        if show_usage_now:
            if self._usage_percent is None:
                lines.append("Usage: N/A")
            else:
                lines.append(f"Usage: {self._usage_percent:.0f}%")
        self.detail_label.setText("\n".join([line for line in lines if line]) or " ")

    def enterEvent(self, event):
        self._apply_style(self._bg_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(self._bg_base)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._has_expand:
            self.set_expanded(not self._expanded, animate=True)
        super().mousePressEvent(event)

    def _apply_style(self, bg):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: none;
                border-radius: 10px;
            }}
        """)

    def set_expanded(self, expanded, animate=False):
        if not self._has_expand:
            return
        self._expanded = bool(expanded)
        if self._expand_anim:
            self._expand_anim.stop()
            self._expand_anim = None

        if not animate:
            if self._expanded:
                self.graph_container.show()
                self.graph_container.setMaximumHeight(120)
            else:
                self.graph_container.hide()
                self.graph_container.setMaximumHeight(0)
            return

        if self._expanded:
            self.graph_container.setMaximumHeight(0)
            self.graph_container.show()
            target = 0
            try:
                if self.graph_container.layout():
                    target = self.graph_container.layout().sizeHint().height()
            except Exception:
                target = 0
            if target <= 0:
                try:
                    target = self.graph_container.sizeHint().height()
                except Exception:
                    target = 0
            if target <= 0:
                target = 80
            self._expand_anim = QPropertyAnimation(self.graph_container, b"maximumHeight")
            self._expand_anim.setDuration(180)
            self._expand_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._expand_anim.setStartValue(0)
            self._expand_anim.setEndValue(target)
            self._expand_anim.finished.connect(lambda: self.graph_container.setMaximumHeight(max(120, target)))
            self._expand_anim.start()
        else:
            start = self.graph_container.height()
            self._expand_anim = QPropertyAnimation(self.graph_container, b"maximumHeight")
            self._expand_anim.setDuration(160)
            self._expand_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._expand_anim.setStartValue(start)
            self._expand_anim.setEndValue(0)
            def _after():
                self.graph_container.hide()
                self.graph_container.setMaximumHeight(0)
            self._expand_anim.finished.connect(_after)
            self._expand_anim.start()
        self._update_detail()

class StorageDetailRow(QFrame):
    def __init__(self, title, dark, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; font-size: 11px; background: transparent; border: none;")
        self.value_label = QLabel("")
        self.value_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.value_label)

    def set_values(self, used_bytes, format_bytes):
        self.value_label.setText(f"{format_bytes(used_bytes)}")

class StorageDetailsWorker(QObject):
    finished = Signal(list)

    def __init__(self, root_path, used_total):
        super().__init__()
        self.root_path = root_path
        self.used_total = used_total
        self._abort = False

    def stop(self):
        self._abort = True

    def _dir_size(self, path):
        total = 0
        for root, dirs, files in os.walk(path, onerror=lambda e: None):
            if self._abort:
                return total
            for name in files:
                if self._abort:
                    return total
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except Exception:
                    pass
        return total

    def run(self):
        if self._abort:
            return
        folders = [
            ("Users", os.path.join(self.root_path, "Users")),
            ("Program Files", os.path.join(self.root_path, "Program Files")),
            ("Program Files (x86)", os.path.join(self.root_path, "Program Files (x86)")),
            ("Windows", os.path.join(self.root_path, "Windows")),
            ("ProgramData", os.path.join(self.root_path, "ProgramData")),
            ("PortableApps", os.path.join(self.root_path, "PortableApps")),
        ]
        results = []
        total_known = 0
        for name, path in folders:
            if self._abort:
                return
            if not os.path.exists(path):
                continue
            size = self._dir_size(path)
            if self._abort:
                return
            total_known += size
            results.append({"name": name, "size": size})
        other = max(self.used_total - total_known, 0)
        results.append({"name": "Other", "size": other})
        self.finished.emit(results)

class StorageCard(QFrame):
    def __init__(self, dark, parent=None):
        super().__init__(parent)
        self.dark = dark
        self.total_bytes = 0
        self.used_bytes = 0
        self.drive_root = "C:\\"
        self.details_loaded = False
        self.details_loading = False
        self.details_thread = None
        self.details_worker = None

        self._bg_base = "rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"
        self._bg_hover = "rgba(255, 255, 255, 0.09)" if dark else "rgba(0, 0, 0, 0.08)"
        self._apply_style(self._bg_base)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Open drive in File Explorer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.icon_label.setFixedSize(20, 20)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.icon_label)

        self.title_label = QLabel("Storage")
        self.title_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; font-size: 13px; font-weight: 600; background: transparent; border: none;")
        header.addWidget(self.title_label)
        header.addStretch()
        layout.addLayout(header)

        self.storage_bar = QProgressBar()
        self.storage_bar.setTextVisible(False)
        self.storage_bar.setFixedHeight(8)
        self.storage_bar.setRange(0, 1000)
        self.storage_bar.setValue(0)
        self.storage_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.18);
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_ACCENT.name()};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.storage_bar)

        usage_row = QHBoxLayout()
        usage_row.setContentsMargins(0, 0, 0, 0)
        self.used_label = QLabel("Loading...")
        self.used_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
        self.free_label = QLabel("")
        self.free_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
        usage_row.addWidget(self.used_label)
        usage_row.addStretch()
        usage_row.addWidget(self.free_label)
        layout.addLayout(usage_row)

        self.usage_percent_label = QLabel("Usage: --")
        self.usage_percent_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
        self.usage_percent_label.setVisible(False)
        layout.addWidget(self.usage_percent_label)

        self.details_button = QPushButton("See details")
        self.details_button.setCursor(Qt.PointingHandCursor)
        self.details_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_SUB.name()};
                font-size: 10px;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_MAIN.name()};
            }}
        """)
        self.details_button.clicked.connect(self._toggle_details)
        layout.addWidget(self.details_button, 0, Qt.AlignLeft)
        self.activity_graph = UsageGraph(self)
        self.activity_graph.setFixedWidth(120)
        self.activity_graph.setMinimumHeight(40)
        self.activity_graph.setMaximumHeight(80)
        self.activity_graph.set_insets(1, 0, 6, 6)
        self.activity_graph.setVisible(False)
        self.activity_graph.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.details_container = QWidget()
        self.details_layout = QVBoxLayout(self.details_container)
        self.details_layout.setContentsMargins(0, 2, 0, 0)
        self.details_layout.setSpacing(4)
        self.details_loading_label = None
        self.details_container.setVisible(False)
        self.io_container = QWidget()
        io_layout = QVBoxLayout(self.io_container)
        io_layout.setContentsMargins(0, 0, 0, 0)
        io_layout.setSpacing(2)
        self.read_label = QLabel("Read: --")
        self.write_label = QLabel("Write: --")
        for lbl in (self.read_label, self.write_label):
            lbl.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px; background: transparent; border: none;")
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            io_layout.addWidget(lbl)
        try:
            metrics = QFontMetrics(self.read_label.font())
            sample_text = "Write: 999.9 MB/s"
            width = metrics.horizontalAdvance(sample_text) + 8
            self.read_label.setFixedWidth(width)
            self.write_label.setFixedWidth(width)
            self.io_container.setFixedWidth(width)
            self.io_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        except Exception:
            pass
        self.details_row = QWidget()
        details_row_layout = QHBoxLayout(self.details_row)
        details_row_layout.setContentsMargins(0, 0, 0, 0)
        details_row_layout.setSpacing(6)
        details_row_layout.addWidget(self.io_container, 0, Qt.AlignLeft | Qt.AlignTop)
        details_row_layout.addStretch()
        self.details_layout.addWidget(self.details_row)
        self.details_button_bottom = QPushButton("Hide details")
        self.details_button_bottom.setCursor(Qt.PointingHandCursor)
        self.details_button_bottom.setStyleSheet(self.details_button.styleSheet())
        self.details_button_bottom.clicked.connect(self._toggle_details)
        self.details_button_bottom.setVisible(False)
        self.details_layout.addWidget(self.details_button_bottom, 0, Qt.AlignLeft)
        layout.addWidget(self.details_container)
        self.details_button.setText("See details")

    def set_icon(self, icon):
        if isinstance(icon, QIcon):
            self.icon_label.setPixmap(icon.pixmap(20, 20))

    def enterEvent(self, event):
        self._apply_style(self._bg_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(self._bg_base)
        super().leaveEvent(event)

    def resizeEvent(self, event):
        self._update_graph_overlay()
        super().resizeEvent(event)

    def _apply_style(self, bg):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: none;
                border-radius: 10px;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            try:
                pt = event.position().toPoint()
            except Exception:
                pt = event.pos()
            if self.details_button.geometry().contains(pt):
                return
            if self.details_container.isVisible() and self.details_container.geometry().contains(pt):
                return
            try:
                target = self.drive_root if self.drive_root and os.path.exists(self.drive_root) else get_base_dir()
                os.startfile(target)
            except Exception:
                pass
        super().mousePressEvent(event)

    def set_rw_speeds(self, read_bps, write_bps):
        self.read_label.setText(f"Read: {self._format_bps(read_bps)}")
        self.write_label.setText(f"Write: {self._format_bps(write_bps)}")

    def set_usage_percent(self, percent):
        if percent is None:
            return
        try:
            value = float(percent)
        except Exception:
            value = 0.0
        if value < 0:
            value = 0.0
        if value > 100:
            value = 100.0
        self.activity_graph.add_value(value)

    def set_data(self, drive_label, total_bytes, used_bytes, drive_root):
        self.drive_root = drive_root
        self.total_bytes = total_bytes or 0
        self.used_bytes = used_bytes or 0
        total_text = self._format_tb(self.total_bytes) if self.total_bytes else "Unknown"
        self.title_label.setText(f"{drive_label} - {total_text}")
        self._update_bar()

    def _format_tb(self, bytes_value):
        return f"{bytes_value / (1024 ** 4):.2f} TB"

    def _format_gb(self, bytes_value):
        return f"{bytes_value / (1024 ** 3):.0f} GB"

    def _format_bps(self, bps):
        if bps is None:
            return "--"
        value = float(bps)
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        idx = 0
        while value >= 1024 and idx < len(units) - 1:
            value /= 1024.0
            idx += 1
        return f"{value:.1f} {units[idx]}"

    def _update_bar(self):
        if self.total_bytes <= 0:
            self.storage_bar.setValue(0)
            self.used_label.setText("Loading...")
            self.free_label.setText("")
            self.usage_percent_label.setText("Usage: --")
            return
        used = self.used_bytes
        free = max(self.total_bytes - used, 0)
        self.storage_bar.setValue(int((used / self.total_bytes) * 1000))
        self.used_label.setText(f"{self._format_gb(used)} used")
        self.free_label.setText(f"{self._format_gb(free)} free")
        percent = max(0.0, min(100.0, (used / self.total_bytes) * 100.0))
        self.usage_percent_label.setText(f"Usage: {percent:.0f}%")

    def _toggle_details(self):
        new_state = not self.details_container.isVisible()
        if new_state:
            # Ensure only read/write details are shown.
            for i in reversed(range(self.details_layout.count())):
                item = self.details_layout.itemAt(i)
                if item and item.widget() in (self.details_row, self.details_button_bottom):
                    continue
                item = self.details_layout.takeAt(i)
                if item and item.widget():
                    item.widget().deleteLater()
        if hasattr(self, "details_button_bottom") and self.details_button_bottom:
            self.details_button_bottom.setVisible(new_state)
        if hasattr(self, "details_button") and self.details_button:
            self.details_button.setVisible(not new_state)
        if hasattr(self, "usage_percent_label") and self.usage_percent_label:
            self.usage_percent_label.setVisible(new_state)
        if hasattr(self, "activity_graph") and self.activity_graph:
            self.activity_graph.setVisible(new_state)
            self._update_graph_overlay()
            QTimer.singleShot(0, self._update_graph_overlay)
        self.details_container.setVisible(new_state)
        if hasattr(self, "details_button") and self.details_button:
            self.details_button.setText("See details")
        if hasattr(self, "details_button_bottom") and self.details_button_bottom:
            self.details_button_bottom.setText("Hide details")
        # Keep details to read/write speeds only.

    def collapse_details(self):
        if self.details_container.isVisible():
            self._toggle_details()

    def _update_graph_overlay(self):
        if not hasattr(self, "activity_graph") or not self.activity_graph:
            return
        if not self.activity_graph.isVisible():
            return
        try:
            usage_pos = self.usage_percent_label.mapTo(self, QPoint(0, 0))
            top = usage_pos.y()
        except Exception:
            top = 0
        try:
            write_pos = self.write_label.mapTo(self, QPoint(0, 0))
            bottom = write_pos.y() + self.write_label.height()
        except Exception:
            bottom = top + self.activity_graph.height()
        bottom_inset = 0
        try:
            bottom_inset = int(getattr(self.activity_graph, "_insets", (0, 0, 0, 0))[3])
        except Exception:
            bottom_inset = 0
        height = max(20, (bottom - top) + bottom_inset)
        try:
            self.activity_graph.setFixedHeight(height)
        except Exception:
            pass
        graph_w = self.activity_graph.width()
        try:
            bar_geo = self.storage_bar.geometry()
            bar_right = bar_geo.x() + bar_geo.width()
        except Exception:
            bar_right = self.width()
        right_inset = 0
        try:
            right_inset = int(getattr(self.activity_graph, "_insets", (0, 0, 0, 0))[2])
        except Exception:
            right_inset = 0
        x = bar_right - graph_w + right_inset
        if x < 0:
            x = 0
        if top < 0:
            top = 0
        self.activity_graph.move(x, top)

    def _load_details_async(self):
        if self.total_bytes <= 0:
            return
        if self.details_thread and self.details_thread.isRunning():
            return
        self.details_loading = True
        self.details_thread = QThread()
        _track_thread(self.details_thread)
        self.details_worker = StorageDetailsWorker(self.drive_root, self.used_bytes)
        self.details_worker.moveToThread(self.details_thread)
        self.details_thread.started.connect(self.details_worker.run)
        self.details_worker.finished.connect(self._apply_details)
        self.details_worker.finished.connect(self.details_thread.quit)
        self.details_worker.finished.connect(self.details_worker.deleteLater)
        self.details_thread.finished.connect(self.details_thread.deleteLater)
        self.details_thread.start()

    def _apply_details(self, details):
        self.details_loading = False
        self.details_loaded = True
        for i in reversed(range(self.details_layout.count())):
            item = self.details_layout.itemAt(i)
            if item and item.widget() is self.io_container:
                continue
            item = self.details_layout.takeAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        for entry in details:
            row = StorageDetailRow(entry["name"], self.dark, self)
            row.set_values(entry["size"], self._format_gb)
            self.details_layout.addWidget(row)

    def cleanup_threads(self):
        if self.details_worker:
            try:
                self.details_worker.stop()
            except Exception:
                pass
        if self.details_thread and self.details_thread.isRunning():
            self.details_thread.quit()
            if not self.details_thread.wait(1500):
                try:
                    self.details_thread.terminate()
                except Exception:
                    pass
                self.details_thread.wait(500)

class AboutInfoWorker(QObject):
    finished = Signal(dict)
    aborted = Signal()

    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self._abort = False

    def stop(self):
        self._abort = True

    def run(self):
        if self._abort:
            return
        drive = os.path.splitdrive(self.base_dir)[0] or "C:"
        root = drive + "\\"
        label = self._get_volume_label(root)
        drive_name = label if label else f"{drive}"
        try:
            usage = shutil.disk_usage(root)
            total_bytes = usage.total
            used_bytes = usage.used
        except Exception:
            total_bytes = 0
            used_bytes = 0

        if self._abort:
            return
        gpus = self._ps_query(
            "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
        )
        gpu = self._pick_gpu(gpus)
        ram = self._ps_query(
            "Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1 Speed | ConvertTo-Json -Compress"
        )
        cpu = self._ps_query(
            "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,MaxClockSpeed | ConvertTo-Json -Compress"
        )
        net = self._get_network_adapter()
        ip_addr = self._get_ip_address()

        gpu_name = gpu.get("Name") or "Unknown"
        gpu_mem = gpu.get("AdapterRAM")
        smi_name = self._nvidia_smi_name()
        if smi_name:
            gpu_name = smi_name
        if "nvidia" in gpu_name.lower():
            smi_mem = self._nvidia_smi_memory()
            if smi_mem:
                gpu_mem = smi_mem

        data = {
            "drive_root": root,
            "drive_name": drive_name,
            "total_bytes": total_bytes,
            "used_bytes": used_bytes,
            "gpu_name": gpu_name,
            "gpu_memory": gpu_mem,
            "ram_speed": ram.get("Speed"),
            "cpu_name": cpu.get("Name") or "Unknown",
            "cpu_speed": cpu.get("MaxClockSpeed"),
            "net_name": net.get("Name") or "Network",
            "net_speed": net.get("LinkSpeed") or "",
            "net_ip": ip_addr,
            "net_status": "Online" if ip_addr else "Offline",
        }
        data["ram_total"] = self._get_ram_total()
        if self._abort:
            return
        self.finished.emit(data)

    def _pick_gpu(self, data):
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return {}
        candidates = []
        for gpu in data:
            name = str(gpu.get("Name") or "")
            ram = gpu.get("AdapterRAM") or 0
            lowered = name.lower()
            if "microsoft basic" in lowered:
                continue
            if "virtual" in lowered:
                continue
            if "display adapter" in lowered and "nvidia" not in lowered and "amd" not in lowered and "intel" not in lowered:
                continue
            candidates.append({"Name": name, "AdapterRAM": ram})
        if not candidates:
            return data[0] if data else {}
        candidates.sort(key=lambda x: x.get("AdapterRAM") or 0, reverse=True)
        return candidates[0]

    def _ps_query(self, command):
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", command],
                stderr=subprocess.DEVNULL,
                text=True,
                **_no_window_kwargs(),
            ).strip()
            if not out:
                return []
            data = json.loads(out)
            return data
        except Exception:
            return []

    def _get_network_adapter(self):
        data = self._ps_query(
            "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
            "Select-Object -First 1 Name,LinkSpeed | ConvertTo-Json -Compress"
        )
        if isinstance(data, list):
            return data[0] if data else {}
        if isinstance(data, dict):
            return data
        return {}

    def _get_ip_address(self):
        ip = ""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
        if not ip:
            try:
                ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                ip = ""
        if ip.startswith("127."):
            return ""
        return ip

    def _nvidia_smi_memory(self):
        out = self._run_nvidia_smi(["--query-gpu=memory.total", "--format=csv,noheader,nounits"])
        if not out:
            return 0
        try:
            first = out.splitlines()[0].strip()
            mb = float(first)
            return int(mb * 1024 * 1024)
        except Exception:
            return 0

    def _nvidia_smi_name(self):
        out = self._run_nvidia_smi(["--query-gpu=name", "--format=csv,noheader"])
        if not out:
            return ""
        return out.splitlines()[0].strip()

    def _run_nvidia_smi(self, args):
        exe = shutil.which("nvidia-smi")
        if not exe:
            candidate = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
            if os.path.exists(candidate):
                exe = candidate
        if not exe:
            return ""
        try:
            out = subprocess.check_output(
                [exe] + args,
                stderr=subprocess.DEVNULL,
                text=True,
                **_no_window_kwargs(),
            ).strip()
            return out
        except Exception:
            return ""

    def _get_ram_total(self):
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.ullTotalPhys
        except Exception:
            return 0

    def _get_volume_label(self, root_path):
        try:
            vol_name = ctypes.create_unicode_buffer(1024)
            fs_name = ctypes.create_unicode_buffer(1024)
            serial = ctypes.c_uint()
            max_comp = ctypes.c_uint()
            flags = ctypes.c_uint()
            res = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root_path),
                vol_name,
                ctypes.sizeof(vol_name),
                ctypes.byref(serial),
                ctypes.byref(max_comp),
                ctypes.byref(flags),
                fs_name,
                ctypes.sizeof(fs_name),
            )
            if res:
                return vol_name.value
        except Exception:
            pass
        return ""

class UsageSampler(QObject):
    updated = Signal(dict)
    aborted = Signal()

    def __init__(self, interval=1.0, net_link_bps=0):
        super().__init__()
        self.interval = max(0.5, float(interval))
        self.net_link_bps = float(net_link_bps or 0)
        self.drive_letter = ""
        self._abort = False
        self._last_cpu = None
        self._last_net = None
        self._last_time = None
        self._last_gpu_check = 0.0
        self._psutil = None
        try:
            import psutil  # type: ignore
            self._psutil = psutil
        except Exception:
            self._psutil = None

    def stop(self):
        self._abort = True

    def set_net_link_bps(self, bps):
        try:
            self.net_link_bps = float(bps or 0)
        except Exception:
            self.net_link_bps = 0.0

    def set_drive_letter(self, drive_letter):
        if not drive_letter:
            self.drive_letter = ""
        else:
            self.drive_letter = str(drive_letter).replace("\\", "").strip()

    def run(self):
        self._last_time = time.monotonic()
        if self._psutil:
            try:
                counters = self._psutil.net_io_counters()
                self._last_net = (counters.bytes_sent, counters.bytes_recv)
            except Exception:
                self._last_net = None

        while not self._abort:
            now = time.monotonic()
            cpu = self._get_cpu_usage()
            ram = self._get_ram_usage()
            gpu = self._get_gpu_usage(now)
            net = self._get_network_usage(now)
            disk = self._get_disk_io()

            payload = {
                "cpu": cpu,
                "ram": ram,
                "gpu": gpu,
                "net_total_bps": net.get("total_bps"),
                "net_up_bps": net.get("up_bps"),
                "net_down_bps": net.get("down_bps"),
                "net_percent": net.get("percent"),
                "disk_read_bps": disk.get("read_bps"),
                "disk_write_bps": disk.get("write_bps"),
                "disk_percent": disk.get("percent"),
            }
            self.updated.emit(payload)

            step = 0.1
            elapsed = 0.0
            while elapsed < self.interval and not self._abort:
                time.sleep(step)
                elapsed += step

        self.aborted.emit()

    def _get_cpu_usage(self):
        times = self._get_cpu_times()
        if not times:
            return None
        if self._last_cpu is None:
            self._last_cpu = times
            return None
        idle, kernel, user = times
        last_idle, last_kernel, last_user = self._last_cpu
        self._last_cpu = times
        idle_delta = idle - last_idle
        total_delta = (kernel + user) - (last_kernel + last_user)
        if total_delta <= 0:
            return None
        usage = (total_delta - idle_delta) / float(total_delta) * 100.0
        if usage < 0:
            usage = 0.0
        if usage > 100:
            usage = 100.0
        return usage

    def _get_cpu_times(self):
        try:
            class FILETIME(ctypes.Structure):
                _fields_ = [
                    ("dwLowDateTime", ctypes.c_uint32),
                    ("dwHighDateTime", ctypes.c_uint32),
                ]
            idle = FILETIME()
            kernel = FILETIME()
            user = FILETIME()
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                return None
            def _ft_to_int(ft):
                return (ft.dwHighDateTime << 32) + ft.dwLowDateTime
            return _ft_to_int(idle), _ft_to_int(kernel), _ft_to_int(user)
        except Exception:
            return None

    def _get_ram_usage(self):
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) == 0:
                return None
            if status.ullTotalPhys == 0:
                return None
            used = 1.0 - (status.ullAvailPhys / float(status.ullTotalPhys))
            usage = max(0.0, min(100.0, used * 100.0))
            return usage
        except Exception:
            return None

    def _get_gpu_usage(self, now):
        if now - self._last_gpu_check < 1.2:
            return None
        self._last_gpu_check = now
        usage = self._gpu_usage_taskmgr()
        if usage is None:
            usage = self._gpu_usage_nvidia()
        if usage is None:
            return None
        return max(0.0, min(100.0, usage))

    def _gpu_usage_nvidia(self):
        exe = shutil.which("nvidia-smi")
        if not exe:
            candidate = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
            if os.path.exists(candidate):
                exe = candidate
        if not exe:
            return None
        try:
            out = subprocess.check_output(
                [exe, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
                text=True,
                **_no_window_kwargs(),
            ).strip()
            if not out:
                return None
            first = out.splitlines()[0].strip()
            return float(first)
        except Exception:
            return None

    def _gpu_usage_taskmgr(self):
        data = self._ps_json(
            "(Get-Counter '\\\\GPU Engine(*)\\\\Utilization Percentage').CounterSamples "
            "| Select-Object InstanceName,CookedValue | ConvertTo-Json -Compress"
        )
        if not data:
            return None
        if isinstance(data, dict):
            data = [data]
        candidates = []
        fallback = []
        for item in data:
            try:
                name = str(item.get("InstanceName", "")).lower()
                value = float(item.get("CookedValue", 0.0))
            except Exception:
                continue
            if "engtype_3d" in name or "engtype_graphics" in name:
                candidates.append(value)
            elif "engtype_copy" in name:
                continue
            else:
                fallback.append(value)
        if candidates:
            return max(candidates)
        if fallback:
            return max(fallback)
        return None

    def _get_network_usage(self, now):
        total_bps = None
        up_bps = None
        down_bps = None
        if self._psutil:
            try:
                counters = self._psutil.net_io_counters()
                sent = counters.bytes_sent
                recv = counters.bytes_recv
                if self._last_net is not None and self._last_time is not None:
                    elapsed = max(0.5, now - self._last_time)
                    delta_sent = max(0, sent - self._last_net[0])
                    delta_recv = max(0, recv - self._last_net[1])
                    up_bps = (delta_sent / elapsed) * 8.0
                    down_bps = (delta_recv / elapsed) * 8.0
                    total_bps = up_bps + down_bps
                self._last_net = (sent, recv)
                self._last_time = now
            except Exception:
                pass
        else:
            totals = self._get_net_totals()
            if totals:
                sent, recv = totals
                if self._last_net is not None and self._last_time is not None:
                    elapsed = max(0.5, now - self._last_time)
                    delta_sent = max(0, sent - self._last_net[0])
                    delta_recv = max(0, recv - self._last_net[1])
                    up_bps = (delta_sent / elapsed) * 8.0
                    down_bps = (delta_recv / elapsed) * 8.0
                    total_bps = up_bps + down_bps
                self._last_net = (sent, recv)
                self._last_time = now
            if total_bps is None or (up_bps == 0 and down_bps == 0 and total_bps == 0):
                data = self._ps_json(
                    "(Get-Counter '\\\\Network Interface(*)\\\\Bytes Sent/sec','\\\\Network Interface(*)\\\\Bytes Received/sec').CounterSamples "
                    "| Select-Object Path,CookedValue | ConvertTo-Json -Compress"
                )
                if data:
                    if isinstance(data, dict):
                        data = [data]
                    sent = 0.0
                    recv = 0.0
                    for item in data:
                        try:
                            path = str(item.get('Path', ''))
                            value = float(item.get('CookedValue', 0.0))
                        except Exception:
                            continue
                        if "Bytes Sent/sec" in path:
                            sent += value
                        elif "Bytes Received/sec" in path:
                            recv += value
                    up_bps = sent * 8.0
                    down_bps = recv * 8.0
                    total_bps = up_bps + down_bps
                    self._last_time = now

        percent = None
        if total_bps is not None and self.net_link_bps > 0:
            percent = min(100.0, (total_bps / self.net_link_bps) * 100.0)
        return {
            "total_bps": total_bps,
            "up_bps": up_bps,
            "down_bps": down_bps,
            "percent": percent,
        }

    def _get_disk_io(self):
        drive = self.drive_letter or "_Total"
        if drive != "_Total" and not drive.endswith(":"):
            drive = drive + ":"

        def _query_cim(target_drive):
            cmd = (
                "Get-CimInstance Win32_PerfFormattedData_PerfDisk_LogicalDisk "
                f"-Filter \"Name='{target_drive}'\" "
                "| Select-Object DiskReadBytesPerSec,DiskWriteBytesPerSec,PercentDiskTime "
                "| ConvertTo-Json -Compress"
            )
            return self._ps_json(cmd)

        def _query_counter(target_drive):
            cmd = (
                "Get-Counter -Counter @("
                f"'\\\\LogicalDisk({target_drive})\\\\Disk Read Bytes/sec',"
                f"'\\\\LogicalDisk({target_drive})\\\\Disk Write Bytes/sec') "
                "| Select-Object -ExpandProperty CounterSamples "
                "| Select-Object Path,CookedValue | ConvertTo-Json -Compress"
            )
            return self._ps_json(cmd)

        data = _query_cim(drive)
        if not data and drive != "_Total":
            data = _query_cim("_Total")

        read_bps = None
        write_bps = None
        percent = None
        if data:
            if isinstance(data, list):
                data = data[0] if data else None
            if isinstance(data, dict):
                try:
                    if data.get("DiskReadBytesPerSec") is not None:
                        read_bps = float(data.get("DiskReadBytesPerSec"))
                    if data.get("DiskWriteBytesPerSec") is not None:
                        write_bps = float(data.get("DiskWriteBytesPerSec"))
                    if data.get("PercentDiskTime") is not None:
                        percent = float(data.get("PercentDiskTime"))
                except Exception:
                    pass

        if read_bps is None and write_bps is None:
            data = _query_counter(drive)
            if not data and drive != "_Total":
                data = _query_counter("_Total")
            if data:
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    try:
                        path = str(item.get("Path", ""))
                        value = float(item.get("CookedValue", 0.0))
                    except Exception:
                        continue
                    if "Disk Read Bytes/sec" in path:
                        read_bps = value
                    elif "Disk Write Bytes/sec" in path:
                        write_bps = value

        return {"read_bps": read_bps, "write_bps": write_bps, "percent": percent}

    def _ps_scalar(self, command):
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", command],
                stderr=subprocess.DEVNULL,
                text=True,
                **_no_window_kwargs(),
            ).strip()
            if not out:
                return None
            try:
                return float(out)
            except Exception:
                return None
        except Exception:
            return None

    def _ps_json(self, command):
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", command],
                stderr=subprocess.DEVNULL,
                text=True,
                **_no_window_kwargs(),
            ).strip()
            if not out:
                return []
            return json.loads(out)
        except Exception:
            return []

    def _get_net_totals(self):
        data = self._ps_json(
            "Get-NetAdapterStatistics | Select-Object SentBytes,ReceivedBytes | ConvertTo-Json -Compress"
        )
        if not data:
            return None
        if isinstance(data, dict):
            data = [data]
        sent = 0.0
        recv = 0.0
        for item in data:
            try:
                sent += float(item.get("SentBytes", 0.0))
                recv += float(item.get("ReceivedBytes", 0.0))
            except Exception:
                continue
        return sent, recv



class AboutPanel(QWidget):
    software_clicked = Signal()

    def __init__(self, base_dir, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.setStyleSheet("background: transparent;")
        dark = COLOR_BG_START.lightness() < 128

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 0, 4)
        layout.setSpacing(10)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(4)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {COLOR_ACCENT.name()};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.loading_bar)

        icon_dir = os.path.join(self.base_dir, "PortableApps", "PortableX", "Graphics", "abouticons")
        gpu_icon_path = os.path.join(icon_dir, "gpu.png")
        ram_icon_path = os.path.join(icon_dir, "ram.png")
        cpu_icon_path = os.path.join(icon_dir, "cpu.png")
        hdd_icon_path = os.path.join(icon_dir, "hdd.png")
        software_icon_path = os.path.join(icon_dir, "software.png")
        network_icon_path = os.path.join(icon_dir, "network.png")
        gpu_icon = QIcon(gpu_icon_path) if os.path.exists(gpu_icon_path) else self.style().standardIcon(QStyle.SP_DesktopIcon)
        ram_icon = QIcon(ram_icon_path) if os.path.exists(ram_icon_path) else self.style().standardIcon(QStyle.SP_DriveHDIcon)
        cpu_icon = QIcon(cpu_icon_path) if os.path.exists(cpu_icon_path) else self.style().standardIcon(QStyle.SP_ComputerIcon)
        hdd_icon = QIcon(hdd_icon_path) if os.path.exists(hdd_icon_path) else self.style().standardIcon(QStyle.SP_DriveHDIcon)
        software_icon = QIcon(software_icon_path) if os.path.exists(software_icon_path) else self.style().standardIcon(QStyle.SP_FileIcon)
        network_icon = QIcon(network_icon_path) if os.path.exists(network_icon_path) else self.style().standardIcon(QStyle.SP_DriveNetIcon)

        self.storage_card = StorageCard(dark, self)
        self.storage_card.set_icon(hdd_icon)
        self.storage_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.storage_card.setMinimumWidth(0)
        layout.addWidget(self.storage_card)

        self.gpu_card = MetricCard("Graphics Card", gpu_icon, dark, self)
        self.ram_card = MetricCard("Installed RAM", ram_icon, dark, self)
        self.cpu_card = MetricCard("Processor", cpu_icon, dark, self)

        net_extra = QWidget()
        net_layout = QVBoxLayout(net_extra)
        net_layout.setContentsMargins(0, 0, 0, 0)
        net_layout.setSpacing(4)
        self.net_send_label = QLabel("Send: --")
        self.net_recv_label = QLabel("Receive: --")
        for lbl in (self.net_send_label, self.net_recv_label):
            lbl.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; font-size: 11px; background: transparent; border: none;")
            net_layout.addWidget(lbl)
        self.network_card = MetricCard("Network", network_icon, dark, self, show_graph=True, show_usage=False, extra_widget=net_extra)
        self.software_card = InfoCard("Software", software_icon, dark, self)
        self.software_card.set_data(get_app_display_name(), get_app_about_text())
        self.software_card.set_clickable(True)
        self.software_card.clicked.connect(self.software_clicked)

        layout.addWidget(self.gpu_card)
        layout.addWidget(self.ram_card)
        layout.addWidget(self.cpu_card)
        layout.addWidget(self.network_card)
        layout.addWidget(self.software_card)
        layout.addStretch()

        self._start_loading()
        self.destroyed.connect(self._cleanup_threads)
        self.usage_thread = None
        self.usage_sampler = None
        self._usage_running = False
        self.net_link_bps = 0.0
        self.drive_letter = ""

    def _start_loading(self):
        self.worker_thread = QThread()
        _track_thread(self.worker_thread)
        self.worker = AboutInfoWorker(self.base_dir)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._apply_info)
        self.worker.aborted.connect(self._handle_worker_aborted)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.aborted.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.aborted.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _handle_worker_aborted(self):
        self.loading_bar.setVisible(False)

    def _cleanup_threads(self):
        if hasattr(self, "storage_card") and self.storage_card:
            try:
                self.storage_card.cleanup_threads()
            except Exception:
                pass
        if hasattr(self, "worker") and self.worker:
            try:
                self.worker.stop()
            except Exception:
                pass
        if hasattr(self, "worker_thread") and self.worker_thread:
            try:
                if self.worker_thread.isRunning():
                    self.worker_thread.quit()
                    if not self.worker_thread.wait(1500):
                        try:
                            self.worker_thread.terminate()
                        except Exception:
                            pass
                        self.worker_thread.wait(500)
            except Exception:
                pass
        if hasattr(self, "usage_sampler") and self.usage_sampler:
            try:
                self.usage_sampler.stop()
            except Exception:
                pass
        if hasattr(self, "usage_thread") and self.usage_thread:
            try:
                if self.usage_thread.isRunning():
                    self.usage_thread.quit()
                    if not self.usage_thread.wait(1500):
                        try:
                            self.usage_thread.terminate()
                        except Exception:
                            pass
                        self.usage_thread.wait(500)
            except Exception:
                pass

    def _format_gb(self, bytes_value):
        return f"{bytes_value / (1024 ** 3):.0f} GB" if bytes_value else "Unknown"

    def _format_speed(self, mhz_value):
        if isinstance(mhz_value, (int, float)):
            return f"{float(mhz_value) / 1000:.2f} GHz"
        return "Unknown"

    def _apply_info(self, data):
        self.loading_bar.setVisible(False)
        drive_name = data.get("drive_name", "Drive")
        total_bytes = data.get("total_bytes", 0)
        used_bytes = data.get("used_bytes", 0)
        self.storage_card.set_data(drive_name, total_bytes, used_bytes, data.get("drive_root", "C:\\"))
        drive_root = data.get("drive_root", "C:\\")
        self.drive_letter = drive_root.strip("\\") or ""

        gpu_name = data.get("gpu_name", "Unknown")
        gpu_mem = data.get("gpu_memory")
        gpu_mem_text = self._format_gb(gpu_mem) if isinstance(gpu_mem, (int, float)) else "Unknown"
        self.gpu_card.set_data(gpu_name, f"{gpu_mem_text} VRAM")

        ram_total = data.get("ram_total", 0)
        ram_speed = data.get("ram_speed")
        self.ram_card.set_data(self._format_gb(ram_total), f"Speed: {ram_speed} MT/s" if ram_speed else "Speed: Unknown")

        cpu_name = data.get("cpu_name", "Unknown")
        cpu_speed = data.get("cpu_speed")
        self.cpu_card.set_data(cpu_name, self._format_speed(cpu_speed))

        net_name = data.get("net_name", "Network")
        net_status = data.get("net_status", "")
        net_ip = data.get("net_ip", "")
        net_speed = data.get("net_speed", "")
        net_details = []
        if net_status:
            net_details.append(f"Status: {net_status}")
        if net_ip:
            net_details.append(f"IP: {net_ip}")
        if hasattr(self, "network_card") and self.network_card:
            self.network_card.set_data(net_name, "\n".join(net_details) if net_details else " ")
        self.net_link_bps = self._parse_link_speed_bps(net_speed)
        self._start_usage_sampler()

        if hasattr(self, "worker") and self.worker:
            try:
                self.worker.stop()
            except Exception:
                pass
        if hasattr(self, "worker_thread") and self.worker_thread:
            try:
                if self.worker_thread.isRunning():
                    self.worker_thread.quit()
                    if not self.worker_thread.wait(1500):
                        try:
                            self.worker_thread.terminate()
                        except Exception:
                            pass
                        self.worker_thread.wait(500)
            except Exception:
                pass

    def _parse_link_speed_bps(self, text):
        if not text:
            return 0.0
        raw = str(text).strip()
        match = re.search(r"([\d\.]+)\s*([KMG]?)bps", raw, re.IGNORECASE)
        if not match:
            return 0.0
        value = float(match.group(1))
        unit = match.group(2).upper()
        mult = 1.0
        if unit == "K":
            mult = 1e3
        elif unit == "M":
            mult = 1e6
        elif unit == "G":
            mult = 1e9
        return value * mult

    def _start_usage_sampler(self):
        if self._usage_running:
            if self.usage_sampler:
                try:
                    self.usage_sampler.set_net_link_bps(self.net_link_bps)
                    self.usage_sampler.set_drive_letter(self.drive_letter)
                except Exception:
                    pass
            return
        self._usage_running = True
        self.usage_thread = QThread()
        _track_thread(self.usage_thread)
        self.usage_sampler = UsageSampler(interval=1.0, net_link_bps=self.net_link_bps)
        self.usage_sampler.set_drive_letter(self.drive_letter)
        self.usage_sampler.moveToThread(self.usage_thread)
        self.usage_thread.started.connect(self.usage_sampler.run)
        self.usage_sampler.updated.connect(self._apply_usage)
        self.usage_sampler.aborted.connect(self.usage_thread.quit)
        self.usage_sampler.aborted.connect(self.usage_sampler.deleteLater)
        self.usage_thread.finished.connect(self.usage_thread.deleteLater)
        self.usage_thread.start()

    def _format_bps(self, bps):
        if bps is None:
            return ""
        value = float(bps)
        units = ["bps", "Kbps", "Mbps", "Gbps"]
        idx = 0
        while value >= 1000 and idx < len(units) - 1:
            value /= 1000.0
            idx += 1
        return f"{value:.1f} {units[idx]}"

    def _apply_usage(self, data):
        cpu = data.get("cpu")
        ram = data.get("ram")
        gpu = data.get("gpu")
        net_total = data.get("net_total_bps")
        net_up = data.get("net_up_bps")
        net_down = data.get("net_down_bps")
        net_percent = data.get("net_percent")
        disk_read = data.get("disk_read_bps")
        disk_write = data.get("disk_write_bps")
        disk_percent = data.get("disk_percent")

        if hasattr(self, "cpu_card") and self.cpu_card:
            self.cpu_card.set_usage(cpu)
        if hasattr(self, "ram_card") and self.ram_card:
            self.ram_card.set_usage(ram)
        if hasattr(self, "gpu_card") and self.gpu_card:
            self.gpu_card.set_usage(gpu)
        if hasattr(self, "storage_card") and self.storage_card:
            self.storage_card.set_rw_speeds(disk_read, disk_write)
            self.storage_card.set_usage_percent(disk_percent)
        if hasattr(self, "network_card") and self.network_card:
            if net_percent is not None:
                self.network_card.set_usage(net_percent)
            if net_up is None:
                net_up = 0.0
            if net_down is None:
                net_down = 0.0
            send_text = f"Send: {self._format_bps(net_up)}"
            recv_text = f"Receive: {self._format_bps(net_down)}"
            if hasattr(self, "net_send_label") and self.net_send_label:
                self.net_send_label.setText(send_text)
            if hasattr(self, "net_recv_label") and self.net_recv_label:
                self.net_recv_label.setText(recv_text)

    def collapse_expanded(self):
        for card_name in ("cpu_card", "ram_card", "gpu_card", "network_card"):
            card = getattr(self, card_name, None)
            if card is not None:
                try:
                    card.set_expanded(False, animate=False)
                except Exception:
                    pass
        if hasattr(self, "storage_card") and self.storage_card:
            try:
                self.storage_card.collapse_details()
            except Exception:
                pass

class SettingRow(AnimatableWidget):
    def __init__(self, text, control=None, parent=None, stacked=False, align_right=True):
        super().__init__(parent)
        self.text = text
        self.control = control
        self.setMinimumHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.disable_hover = False
        self._tooltip_text = ""
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.setInterval(2000)
        self._tooltip_timer.timeout.connect(self._show_tooltip)

        if stacked:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(12, 6, 12, 6)
            layout.setSpacing(6)
        else:
            layout = QHBoxLayout(self)
            layout.setContentsMargins(12, 0, 12, 0)
            layout.setSpacing(12)

        self.label = QLabel(text)
        self.label.setFont(QFont(FONT_FAMILY, 10))
        self.label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.label.setWordWrap(True)
        self.label.setMinimumHeight(20)

        layout.addWidget(self.label)
        if not stacked and align_right:
            layout.addStretch()
        if self.control is not None:
            if stacked:
                layout.addWidget(self.control, 0, Qt.AlignLeft | Qt.AlignVCenter)
            else:
                if align_right:
                    layout.addWidget(self.control, 0, Qt.AlignRight | Qt.AlignVCenter)
                else:
                    layout.addWidget(self.control, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.anim = QPropertyAnimation(self, b"bg_color")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def enterEvent(self, event):
        if self.disable_hover:
            super().enterEvent(event)
            return
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(COLOR_HOVER)
        self.anim.start()
        if isinstance(self.control, ToggleSwitch):
            self.control.set_hovered(True)
        if self._tooltip_text:
            self._tooltip_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.disable_hover:
            super().leaveEvent(event)
            return
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(QColor(0, 0, 0, 0))
        self.anim.start()
        if isinstance(self.control, ToggleSwitch):
            self.control.set_hovered(False)
        self._tooltip_timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and isinstance(self.control, ToggleSwitch):
            self.control.toggle()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._bg_color.alpha() > 0:
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 8, 8)

    def set_tooltip(self, text):
        self._tooltip_text = text or ""

    def _show_tooltip(self):
        if not self._tooltip_text:
            return
        QToolTip.showText(QCursor.pos(), self._tooltip_text, self)


class OptionsPanel(QWidget):
    refresh_clicked = Signal()
    add_cat_clicked = Signal()
    settings_clicked = Signal()
    import_settings_clicked = Signal()
    export_settings_clicked = Signal()
    restart_clicked = Signal()
    exit_clicked = Signal()
    close_clicked = Signal()
    startup_apps_clicked = Signal()
    fix_settings_clicked = Signal()
    browser_changed = Signal(dict)
    browser_install_clicked = Signal(str)
    browser_open_folder_clicked = Signal(str)
    software_notice_clicked = Signal()
    check_updates_clicked = Signal()
    updates_auto_check_toggled = Signal(bool)

    hidden_toggled = Signal(bool)
    expand_default_toggled = Signal(bool)
    accordion_toggled = Signal(bool)
    fade_toggled = Signal(bool)
    keybind_changed = Signal(str)

    collapse_on_minimize_toggled = Signal(bool)
    search_desc_toggled = Signal(bool)
    keep_visible_toggled = Signal(bool)
    start_minimized_toggled = Signal(bool)
    show_search_toggled = Signal(bool)
    show_in_taskbar_toggled = Signal(bool)
    confirm_launch_toggled = Signal(bool)
    confirm_web_toggled = Signal(bool)
    confirm_exit_toggled = Signal(bool)
    app_session_unlock_toggled = Signal(bool)
    set_password_clicked = Signal()
    clear_password_clicked = Signal()
    protected_apps_clicked = Signal()
    trusted_devices_clear_clicked = Signal()
    require_app_password_toggled = Signal(bool)
    require_settings_password_toggled = Signal(bool)
    theme_mode_changed = Signal(str)
    accent_color_changed = Signal(str)
    text_color_changed = Signal(str)
    background_changed = Signal(dict)
    view_mode_changed = Signal(str)
    grid_columns_changed = Signal(str)
    mini_menu_background_changed = Signal(dict)
    always_on_top_toggled = Signal(bool)
    remember_last_screen_toggled = Signal(bool)
    mini_keybind_changed = Signal(str)
    mini_menu_setting_changed = Signal(str, bool)
    manage_pinned_clicked = Signal()
    mini_menu_items_changed = Signal(dict)
    home_shortcuts_changed = Signal(dict)
    gui_scale_changed = Signal(str)
    mini_menu_scale_changed = Signal(str)
    mini_menu_text_color_changed = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._security_unlocked = False
        self._security_password_set = bool(self.settings.get("password_hash") and self.settings.get("password_salt"))
        self._app_session_unlock = bool(self.settings.get("app_session_unlock", False))
        if "effective_theme" not in self.settings:
            self.settings["effective_theme"] = "dark" if COLOR_BG_START.lightness() < 128 else "light"
        self.current_category = "Behavior"
        self.rows = []
        self._built_categories = set()
        self._all_rows_built = False
        self._has_rows_stretch = False
        self._build_queue = []
        self._build_timer_active = False
        self.base_dir = get_base_dir()
        self.background_type = self.settings.get("background_type", "theme")
        self.initial_category = self.settings.get("current_category", "Behavior")
        self.initial_search = self.settings.get("settings_search", "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        main_panel = GlassPanel(radius=6, opacity=0.05)
        panel_layout = QVBoxLayout(main_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(10)

        # Search row
        search_container = QWidget()
        search_container.setFixedHeight(48)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_layout.setSpacing(16)
        search_layout.setAlignment(Qt.AlignVCenter)

        self.search_bar = SearchBar()
        self.search_bar.setFixedHeight(32)
        self.search_bar.input.setPlaceholderText("Search settings")
        self.search_bar.textChanged.connect(self.filter_rows)

        self.back_btn = QPushButton("Back")
        self.back_btn.setFixedSize(64, 32)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.close_clicked.emit)
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background: {qcolor_to_rgba(COLOR_GLASS_WHITE)};
                color: {COLOR_TEXT_SUB.name()};
                border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {qcolor_to_rgba(COLOR_HOVER)};
                border-color: {COLOR_ACCENT.name()};
                color: {COLOR_TEXT_MAIN.name()};
            }}
        """)
        self._back_btn_hovered = False
        self._back_btn_opacity = QGraphicsOpacityEffect(self.back_btn)
        self._back_btn_opacity.setOpacity(1.0)
        self.back_btn.setGraphicsEffect(self._back_btn_opacity)
        self._back_btn_anim = QPropertyAnimation(self._back_btn_opacity, b"opacity")
        self._back_btn_anim.setDuration(140)
        self._back_btn_anim.setEasingCurve(QEasingCurve.OutQuad)
        self.back_btn.installEventFilter(self)

        search_layout.addWidget(self.search_bar, 1)
        search_layout.addWidget(self.back_btn, 0)

        panel_layout.addWidget(search_container)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {qcolor_to_rgba(COLOR_GLASS_BORDER)};")
        panel_layout.addWidget(line)

        # Content
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        self.settings_list_container = QWidget()
        self.settings_list_container.setStyleSheet("background: transparent;")
        self.settings_layout = QVBoxLayout(self.settings_list_container)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout.setSpacing(4)

        # Scroll
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.settings_list_container)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content_layout.addWidget(self.scroll, 17)

        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet(f"background-color: {qcolor_to_rgba(COLOR_GLASS_BORDER)}; margin: 5px 0px;")
        content_layout.addWidget(separator)

        # Sidebar categories
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(2)

        self.category_buttons = {}
        self._all_categories = ["Behavior", "Search", "Appearance", "Shortcuts", "Mini menu", "Management", "Security", "System", "About"]
        icon_dir = os.path.join(self.base_dir, "PortableApps", "PortableX", "Graphics", "settingsicons")
        icon_map = {
            "Behavior": "behavior.png",
            "Search": "search.png",
            "Appearance": "appearance.png",
            "Shortcuts": "shortcuts.png",
            "Mini menu": "minimenu.png",
            "Management": "management.png",
            "Security": "security.ico",
            "System": "system.png",
            "About": "about.png",
        }
        for name in self._all_categories:
            icon_path = os.path.join(icon_dir, icon_map.get(name, "options.png"))
            btn = QuickAccessButton(name, icon_path if os.path.exists(icon_path) else "")
            btn.setObjectName(name)
            btn.clicked.connect(lambda n=name: self.set_category(n))
            sidebar_layout.addWidget(btn)
            self.category_buttons[name] = btn

        sidebar_layout.addStretch()

        # Close button (bottom-right)
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_TEXT_SUB.name()};
                border: none;
                font-weight: bold;
                font-size: 18px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_MAIN.name()};
            }}
            QPushButton:pressed {{
                color: {COLOR_ACCENT.name()};
            }}
        """)
        sidebar_layout.addWidget(self.close_btn, 0, Qt.AlignRight)

        content_layout.addWidget(sidebar, 3)
        panel_layout.addWidget(content_container, 1)

        layout.addWidget(main_panel)

        # Build rows (lazy per-category)
        self.current_category = self.initial_category
        if self.initial_search:
            # Avoid prompting for Security on search restore.
            if self.current_category == "Security":
                self._security_unlocked = False
                self.current_category = "Behavior"
        else:
            if self.current_category == "Security":
                # Always lock on open; prompt for password before showing Security rows.
                self._security_unlocked = False
                if not self._ensure_security_unlocked():
                    self.current_category = "Behavior"
        self.build_rows([self.current_category])
        self.apply_category_filter()
        if self.current_category == "About":
            self._ensure_about_panel_loaded()
        if self.initial_search:
            try:
                self.search_bar.input.blockSignals(True)
                self.search_bar.input.setText(self.initial_search)
            finally:
                self.search_bar.input.blockSignals(False)
            self.filter_rows(self.initial_search)
        self.update_category_highlight()
        if self.current_category in ("Mini menu", "About"):
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.verticalScrollBar().valueChanged.connect(self._update_preview_scroll)

    def _update_preview_scroll(self):
        if self.current_category == "About":
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            return
        if self.current_category != "Mini menu":
            return
        if not hasattr(self, "mini_preview") or not self.mini_preview:
            return
        row = self.mini_preview.parent()
        if not row:
            return
        rect = row.geometry()
        view = self.scroll.viewport().rect()
        visible = rect.top() >= view.top() and rect.bottom() <= view.bottom()
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff if visible else Qt.ScrollBarAsNeeded)

    def build_rows(self, categories=None):
        if categories is None:
            categories = self._all_categories
        if not hasattr(self, "_tooltip_map"):
            self._tooltip_map = {
            "Show hidden apps": "Show apps marked as hidden in the main list.",
            "Expand categories by default": "Start with all categories expanded.",
            "Accordion mode": "Expanding one category collapses the others.",
            "Collapse categories on minimize": "Collapse all categories when the app is minimized or hidden.",
            "Remember last screen": "Keep the current screen instead of returning home when hidden.",
            "Keep menu visible after launch": "Do not hide the launcher after starting an app.",
            "Start minimized to tray": "Launch directly to the system tray.",
            "Show in taskbar": "Show the launcher in the Windows taskbar.",
            "Always on top": "Keep the launcher above other windows.",
            "Show search bar": "Show the search bar on the home screen.",
            "Search in app descriptions": "Include app descriptions in search results.",
            "Create password": "Create a new security password.",
            "Change password": "Update the security password.",
            "Delete password": "Remove the current security password.",
            "Require password to open launcher": "Ask for the password when opening the launcher.",
            "Protected apps": "Choose apps that require a password to launch.",
            "Confirm before launching apps": "Ask before opening any app.",
            "Confirm before exiting app": "Ask before closing the launcher.",
            "Keep app unlocked for session": "Keep the main app unlocked until it is fully closed.",
            "Trusted devices": "Clear the saved PCs that auto-unlock the launcher.",
            "Fade menu in and out": "Use a fade animation when showing or hiding the menu.",
            "Theme": "Choose light, dark, or system theme.",
            "GUI Scale": "Scale the main window UI. Restart required.",
            "List Grid": "Choose list or grid view for apps. Restart required.",
            "Grid columns": "Set how many columns appear in grid view.",
            "Home shortcuts": "Choose which quick buttons appear on the home screen.",
            "Accent color": "Color used for highlights and accents.",
            "Text color": "Main text color used in the app.",
            "Background": "Choose background style or image.",
            "Toggle menu key": "Global hotkey to show or hide the main menu.",
            "Mini mode key": "Global hotkey to open the mini menu.",
            "Preview": "Live preview of the mini menu.",
            "Menu items": "Choose which items appear in the mini menu.",
            "Pinned apps": "Choose apps to pin in the mini menu.",
            "Mini menu background": "Set the mini menu background style.",
            "Mini menu text color": "Set the mini menu text color.",
            "Mini menu scale": "Scale the mini menu size.",
            "Show icons": "Show icons in the mini menu.",
            "Also apply to system tray": "Apply mini menu layout to the system tray menu.",
            "Refresh app list": "Rescan the PortableApps folder.",
            "New category": "Add a new custom category.",
            "Edit settings (.ini)": "Open Data\\settings.ini for manual edits.",
            "Import settings": "Import a settings.ini file and overwrite current settings.",
            "Export settings": "Save your current settings.ini to a file.",
            "Startup apps": "Apps that launch when the launcher starts.",
            "Fix settings": "Run the settings repair tool.",
            "Default browser": "Browser used for web searches.",
            "Restart app": "Restart the launcher.",
            "Exit application": "Close the launcher.",
            }

        for category in categories:
            if category in self._built_categories:
                continue

            if category == "Behavior":
                self.add_row("Behavior", self.make_toggle_row("Show hidden apps", self.settings.get("show_hidden", False), self.hidden_toggled))
                self.add_row("Behavior", self.make_toggle_row("Expand categories by default", self.settings.get("expand_default", False), self.expand_default_toggled))
                self.add_row("Behavior", self.make_toggle_row("Accordion mode", self.settings.get("accordion", False), self.accordion_toggled))
                self.add_row("Behavior", self.make_toggle_row("Collapse categories on minimize", self.settings.get("collapse_on_minimize", True), self.collapse_on_minimize_toggled))
                self.add_row("Behavior", self.make_toggle_row("Remember last screen", self.settings.get("remember_last_screen", False), self.remember_last_screen_toggled))
                self.add_row("Behavior", self.make_toggle_row("Keep menu visible after launch", self.settings.get("keep_visible_after_launch", True), self.keep_visible_toggled))
                self.start_minimized_row = self.make_toggle_row("Start minimized to tray", self.settings.get("start_minimized", True), self.start_minimized_toggled)
                self.add_row("Behavior", self.start_minimized_row)
                self.show_in_taskbar_row = self.make_toggle_row("Show in taskbar", self.settings.get("show_in_taskbar", False), self.show_in_taskbar_toggled)
                self.add_row("Behavior", self.show_in_taskbar_row)
                show_taskbar_init = self.settings.get("show_in_taskbar", False)
                self.start_minimized_row._force_hidden = not show_taskbar_init
                self.start_minimized_row.setVisible(show_taskbar_init)
                self.start_minimized_row.setDisabled(not show_taskbar_init)
                if isinstance(self.show_in_taskbar_row.control, ToggleSwitch):
                    def _toggle_start_minimized():
                        enabled = self.show_in_taskbar_row.control.isChecked()
                        self.start_minimized_row._force_hidden = not enabled
                        self.start_minimized_row.setVisible(enabled)
                        self.start_minimized_row.setDisabled(not enabled)
                        self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
                    self.show_in_taskbar_row.control.toggled.connect(lambda _: _toggle_start_minimized())
                    _toggle_start_minimized()
                self.add_row("Behavior", self.make_toggle_row("Always on top", self.settings.get("always_on_top", False), self.always_on_top_toggled))

            elif category == "Search":
                self.add_row("Search", self.make_toggle_row("Show search bar", self.settings.get("show_search_bar", False), self.show_search_toggled))
                self.add_row("Search", self.make_toggle_row("Search in app descriptions", self.settings.get("search_descriptions", True), self.search_desc_toggled))

            elif category == "Security":
                warning_desc = QLabel(
                    "Passwords only protect the launcher. Anyone can browse files on the drive unless it is encrypted "
                    "(BitLocker To Go or VeraCrypt)."
                )
                warning_desc.setWordWrap(True)
                warning_desc.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
                warning_desc.setFont(QFont(FONT_FAMILY, 9))
                warning_row = SettingRow("Drive security warning", warning_desc, stacked=True, align_right=False)
                warning_row.disable_hover = True
                warning_row.setCursor(Qt.ArrowCursor)
                if hasattr(warning_row, "label") and warning_row.label:
                    warning_row.label.setStyleSheet(f"color: {COLOR_ACCENT.name()}; background: transparent;")
                self.add_row("Security", warning_row)
                self.create_password_row = self.make_button_row(
                    "Create password",
                    self.set_password_clicked,
                    button_text="Create",
                    width=SMALL_CONTROL_WIDTH,
                    height=SMALL_CONTROL_HEIGHT,
                    font_size=SMALL_CONTROL_FONT_SIZE,
                )
                self.change_password_row = self.make_button_row(
                    "Change password",
                    self.set_password_clicked,
                    button_text="Change",
                    width=SMALL_CONTROL_WIDTH,
                    height=SMALL_CONTROL_HEIGHT,
                    font_size=SMALL_CONTROL_FONT_SIZE,
                )
                self.add_row("Security", self.create_password_row)
                self.add_row("Security", self.change_password_row)
                if hasattr(self.create_password_row, "setMinimumHeight"):
                    self.create_password_row.setMinimumHeight(60)
                if hasattr(self.change_password_row, "setMinimumHeight"):
                    self.change_password_row.setMinimumHeight(60)
                for row in (self.create_password_row, self.change_password_row):
                    if hasattr(row, "label") and row.label:
                        row.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                        row.label.setMinimumHeight(0)
                        row.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.add_row("Security", self.make_toggle_row("Require password to open launcher", self.settings.get("require_app_password", False), self.require_app_password_toggled))
                self.add_row("Security", self.make_button_row("Protected apps", self.protected_apps_clicked, button_text="Manage", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("Security", self.make_toggle_row("Confirm before launching apps", self.settings.get("confirm_launch", False), self.confirm_launch_toggled))
                self.add_row("Security", self.make_toggle_row("Confirm before exiting app", self.settings.get("confirm_exit", True), self.confirm_exit_toggled))
                self.add_row("Security", self.make_toggle_row("Keep app unlocked for session", self.settings.get("app_session_unlock", False), self.app_session_unlock_toggled))
                self.trusted_devices_row = self.make_button_row(
                    "Trusted devices",
                    self.trusted_devices_clear_clicked,
                    button_text="Clear",
                    width=SMALL_CONTROL_WIDTH,
                    height=SMALL_CONTROL_HEIGHT,
                    font_size=SMALL_CONTROL_FONT_SIZE,
                )
                self.add_row("Security", self.trusted_devices_row)
                if not self.settings.get("trusted_devices"):
                    self.trusted_devices_row.setDisabled(True)
                self.delete_password_row = self.make_button_row(
                    "Delete password",
                    self.clear_password_clicked,
                    is_destructive=True,
                    button_text="Delete",
                    width=SMALL_CONTROL_WIDTH,
                    height=SMALL_CONTROL_HEIGHT,
                    font_size=SMALL_CONTROL_FONT_SIZE,
                )
                if not self._security_password_set:
                    self.delete_password_row.setDisabled(True)
                    self.delete_password_row._force_hidden = True
                self.add_row(
                    "Security",
                    self.delete_password_row,
                )
                if self._security_password_set:
                    self.create_password_row._force_hidden = True
                    self.change_password_row._force_hidden = False
                    self.delete_password_row._force_hidden = False
                    self.delete_password_row.setDisabled(False)
                else:
                    self.create_password_row._force_hidden = False
                    self.change_password_row._force_hidden = True
                    self.delete_password_row._force_hidden = True
                    self.delete_password_row.setDisabled(True)

            elif category == "Appearance":
                self.add_row("Appearance", self.make_toggle_row("Fade menu in and out", self.settings.get("fade", True), self.fade_toggled, align_right=False))
                self.add_row("Appearance", self.make_theme_row(self.settings.get("theme_mode", "system")))
                self.add_row("Appearance", self.make_gui_scale_row(self.settings.get("gui_scale", "1.0")))
                self.view_mode_row = self.make_view_mode_row(self.settings.get("view_mode", "list"))
                self.add_row("Appearance", self.view_mode_row)
                self.grid_columns_row = self.make_grid_columns_row(self.settings.get("grid_columns", "auto"))
                self.add_row("Appearance", self.grid_columns_row)
                is_grid_init = self.settings.get("view_mode", "list") == "grid"
                self.grid_columns_row._force_hidden = not is_grid_init
                self.grid_columns_row.setVisible(is_grid_init)
                self.grid_columns_row.setDisabled(not is_grid_init)
                if isinstance(self.view_mode_row.control, QComboBox):
                    def _toggle_grid_columns():
                        is_grid = self.view_mode_row.control.currentData() == "grid"
                        self.grid_columns_row._force_hidden = not is_grid
                        self.grid_columns_row.setVisible(is_grid)
                        self.grid_columns_row.setDisabled(not is_grid)
                        self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
                    self.view_mode_row.control.currentIndexChanged.connect(lambda _: _toggle_grid_columns())
                    _toggle_grid_columns()
                self.add_row("Appearance", self.make_accent_row(self.settings.get("accent_color", "")))
                self.add_row("Appearance", self.make_text_color_row(self.settings.get("text_color", "")))
                self.add_row("Appearance", self.make_background_row(
                    self.settings.get("background_type", "theme"),
                    self.settings.get("background_color", ""),
                    self.settings.get("background_gradient_start", ""),
                    self.settings.get("background_gradient_end", ""),
                    self.settings.get("background_image", "")
                ))

            elif category == "Shortcuts":
                self.add_row("Shortcuts", self.make_keybind_row("Toggle menu key", self.settings.get("menu_key", "Ctrl+R"), "menu_key", self.keybind_changed))
                self.add_row("Shortcuts", self.make_keybind_row("Mini mode key", self.settings.get("mini_key", "Ctrl+E"), "mini_key", self.mini_keybind_changed))

            elif category == "Mini menu":
                self.mini_preview = MiniMenuPreview(self.settings, self.base_dir)
                self.add_row("Mini menu", SettingRow("Preview", self.mini_preview, stacked=True, align_right=False))
                self.add_row("Mini menu", self.make_button_row("Menu items", self.open_mini_items_dialog, button_text="Edit", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("Mini menu", self.make_button_row("Pinned apps", self.manage_pinned_clicked, button_text="Manage", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("Mini menu", self.make_mini_menu_background_row(
                    self.settings.get("mini_menu_background_type", "default"),
                    self.settings.get("mini_menu_background_color", ""),
                    self.settings.get("mini_menu_background_gradient_start", ""),
                    self.settings.get("mini_menu_background_gradient_end", "")
                ))
                self.add_row("Mini menu", self.make_mini_menu_text_color_row(self.settings.get("mini_menu_text_color", "")))
                self.add_row("Mini menu", self.make_mini_menu_scale_row(self.settings.get("mini_menu_scale", "1.0")))
                self.add_row("Mini menu", self.make_toggle_row_with_key("Show icons", self.settings.get("mini_show_icons", True), "mini_show_icons"))
                self.add_row("Mini menu", self.make_toggle_row_with_key("Also apply to system tray", self.settings.get("mini_apply_to_tray", False), "mini_apply_to_tray"))

            elif category == "Management":
                self.add_row("Management", self.make_button_row("Refresh app list", self.refresh_clicked, button_text="Refresh", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("Management", self.make_button_row("Home shortcuts", self.open_home_shortcuts_dialog, button_text="Edit", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("Management", self.make_button_row("New category", self.add_cat_clicked, button_text="Add", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("Management", self.make_button_row("Edit settings (.ini)", self.settings_clicked, button_text="Edit", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))

            elif category == "System":
                self.add_row("System", self.make_button_row("Startup apps", self.startup_apps_clicked, button_text="Manage", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("System", self.make_toggle_row("Auto-check for updates", self.settings.get("updates_auto_check", True), self.updates_auto_check_toggled, align_right=False))
                self.add_row("System", self.make_button_row("Check for updates", self.check_updates_clicked, button_text="Check", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.fix_settings_row = self.make_button_row("Fix settings", self.fix_settings_clicked, button_text="Fix", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE)
                self.fix_settings_button = self.fix_settings_row.control if hasattr(self.fix_settings_row, "control") else None
                self.add_row("System", self.fix_settings_row)
                self.add_row("System", self.make_button_row("Import settings", self.import_settings_clicked, button_text="Import", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("System", self.make_button_row("Export settings", self.export_settings_clicked, button_text="Export", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("System", self.make_browser_row(
                    self.settings.get("browser_choice", "system"),
                    self.settings.get("browser_path", "")
                ))
                self.add_row("System", self.make_button_row("Restart app", self.restart_clicked, button_text="Restart", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))
                self.add_row("System", self.make_button_row("Exit application", self.exit_clicked, is_destructive=False, button_text="Exit", width=SMALL_CONTROL_WIDTH, height=SMALL_CONTROL_HEIGHT, font_size=SMALL_CONTROL_FONT_SIZE))

            elif category == "About":
                self.about_panel = None
                self.about_placeholder = QLabel("Open About to load system info.")
                self.about_placeholder.setWordWrap(True)
                self.about_placeholder.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 11px; background: transparent;")
                about_row = SettingRow("About", self.about_placeholder, stacked=True, align_right=False)
                about_row.setMinimumHeight(120)
                if hasattr(about_row, "label") and about_row.label:
                    about_row.label.setVisible(False)
                try:
                    layout = about_row.layout()
                    layout.setContentsMargins(4, 4, -8, 4)
                    layout.removeWidget(self.about_placeholder)
                    layout.addWidget(self.about_placeholder)
                except Exception:
                    pass
                about_row.disable_hover = True
                self.about_row = about_row
                self.add_row("About", about_row)

            self._built_categories.add(category)

        if not self._has_rows_stretch:
            self.settings_layout.addStretch()
            self._has_rows_stretch = True

        if set(self._built_categories) == set(self._all_categories):
            self._all_rows_built = True

    def _queue_build_categories(self, categories):
        if not categories:
            return
        for category in categories:
            if category in self._built_categories:
                continue
            if category not in self._build_queue:
                self._build_queue.append(category)
        if self._build_timer_active:
            return
        self._build_timer_active = True
        QTimer.singleShot(0, self._process_build_queue)

    def _process_build_queue(self):
        if not self._build_queue:
            self._build_timer_active = False
            return
        category = self._build_queue.pop(0)
        self.build_rows([category])
        self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
        QTimer.singleShot(0, self._process_build_queue)

    def _ensure_all_rows_built_async(self):
        if self._all_rows_built:
            return
        self._queue_build_categories(self._all_categories)

    def _ensure_about_panel_loaded(self):
        if self.about_panel is not None:
            return
        self.about_panel = AboutPanel(self.base_dir, self)
        self.about_panel.software_clicked.connect(self.software_notice_clicked)
        try:
            if hasattr(self, "about_row") and self.about_row:
                layout = self.about_row.layout()
                if self.about_placeholder:
                    layout.removeWidget(self.about_placeholder)
                    self.about_placeholder.deleteLater()
                    self.about_placeholder = None
                layout.addWidget(self.about_panel)
                self.about_row.setMinimumHeight(380)
                self.about_row.disable_hover = True
        except Exception:
            pass
        try:
            self.about_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        except Exception:
            pass

    def add_row(self, category, row):
        row.category = category
        if hasattr(self, "_tooltip_map") and row.text in self._tooltip_map:
            row.set_tooltip(self._tooltip_map.get(row.text, ""))
        self.rows.append(row)
        if self._has_rows_stretch and self.settings_layout.count() > 0:
            self.settings_layout.insertWidget(self.settings_layout.count() - 1, row)
        else:
            self.settings_layout.addWidget(row)

    def make_toggle_row(self, text, checked, signal, align_right=True):
        toggle = ToggleSwitch(checked=checked)
        toggle.toggled.connect(signal.emit)
        return SettingRow(text, toggle, align_right=align_right)

    def make_button_row(self, text, signal, is_destructive=False, button_text=None, width=CONTROL_WIDTH, height=CONTROL_HEIGHT, font_size=10):
        btn = QPushButton(button_text or "Open")
        btn.setCursor(Qt.PointingHandCursor)
        if hasattr(signal, "emit"):
            btn.clicked.connect(signal.emit)
        else:
            btn.clicked.connect(signal)
        btn.setFixedWidth(width)
        btn.setFixedHeight(height)
        btn.setStyleSheet(self.get_button_style(is_destructive=is_destructive, font_size=font_size))
        if not hasattr(self, "_rainbow_buttons"):
            self._rainbow_buttons = []
        self._rainbow_buttons.append((btn, font_size))
        return SettingRow(text, btn)

    def set_fix_settings_busy(self, busy):
        if not hasattr(self, "fix_settings_row") or not self.fix_settings_row:
            return
        btn = getattr(self, "fix_settings_button", None)
        if btn is None:
            try:
                btn = self.fix_settings_row.control
            except Exception:
                btn = None
        if btn is None:
            return
        if busy:
            btn.setEnabled(False)
            btn.setText("Working...")
        else:
            btn.setEnabled(True)
            btn.setText("Fix")

    def make_theme_row(self, current_mode):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)
        combo.addItem("System", "system")
        combo.addItem("Light", "light")
        combo.addItem("Dark", "dark")
        idx = combo.findData(current_mode)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(lambda _: self.theme_mode_changed.emit(combo.currentData()))
        combo.setStyleSheet(combo_style())
        return SettingRow("Theme", combo, stacked=True)

    def make_accent_row(self, current_color):
        items = [
            {"label": "#ED1C24", "value": "#ED1C24"},
            {"label": "#FF7F27", "value": "#FF7F27"},
            {"label": "#FFF200", "value": "#FFF200"},
            {"label": "#22B14C", "value": "#22B14C"},
            {"label": "#00A2E8", "value": "#00A2E8"},
            {"label": "#3F48CC", "value": "#3F48CC"},
            {"label": "#A349A4", "value": "#A349A4"},
            {"label": "#FFAEC9", "value": "#FFAEC9"},
            {"label": "#B5E61D", "value": "#B5E61D"},
            {"label": "#99D9EA", "value": "#99D9EA"},
            {"label": "Default", "value": ""},
            {"label": "Custom", "value": "__custom__", "custom": True},
        ]
        picker = ColorGridPicker(items, current_value=current_color or "", columns=6)
        picker.colorSelected.connect(self.accent_color_changed.emit)
        return SettingRow("Accent color", picker, stacked=True)

    def make_text_color_row(self, current_color):
        items = [
            {"label": "#ED1C24", "value": "#ED1C24"},
            {"label": "#FF7F27", "value": "#FF7F27"},
            {"label": "#FFF200", "value": "#FFF200"},
            {"label": "#22B14C", "value": "#22B14C"},
            {"label": "#00A2E8", "value": "#00A2E8"},
            {"label": "#3F48CC", "value": "#3F48CC"},
            {"label": "#A349A4", "value": "#A349A4"},
            {"label": "#FFAEC9", "value": "#FFAEC9"},
            {"label": "#B5E61D", "value": "#B5E61D"},
            {"label": "#99D9EA", "value": "#99D9EA"},
            {"label": "Default", "value": ""},
            {"label": "Custom", "value": "__custom__", "custom": True},
        ]
        picker = ColorGridPicker(items, current_value=current_color or "", columns=6)
        picker.colorSelected.connect(self.text_color_changed.emit)
        return SettingRow("Text color", picker, stacked=True)

    def make_background_row(self, current_type, current_color, grad_start, grad_end, image_path):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)

        options = [
            ("Theme default", "theme"),
            ("Solid color...", "solid"),
            ("Gradient...", "gradient"),
            ("Image...", "image"),
        ]
        for label, value in options:
            combo.addItem(label, value)

        idx = combo.findData(current_type)
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)

        def _apply_background(bg_type, color="", g_start="", g_end="", image=""):
            nonlocal current_type, current_color, grad_start, grad_end, image_path
            self.background_type = bg_type
            current_type = bg_type
            if color:
                current_color = color
            if g_start:
                grad_start = g_start
            if g_end:
                grad_end = g_end
            if image:
                image_path = image
            self.background_changed.emit({
                "type": bg_type,
                "color": color,
                "gradient_start": g_start,
                "gradient_end": g_end,
                "image": image,
            })

        def _on_change():
            value = combo.currentData()
            if value == "theme":
                _apply_background("theme")
                return
            if value == "solid":
                color = QColorDialog.getColor(QColor(current_color or "#1b1f26"), self, "Select Background Color")
                if color.isValid():
                    _apply_background("solid", color.name())
                else:
                    combo.setCurrentIndex(combo.findData(self.background_type))
                return
            if value == "gradient":
                start = QColorDialog.getColor(QColor(grad_start or "#0e1014"), self, "Gradient Start Color")
                if not start.isValid():
                    combo.setCurrentIndex(combo.findData(self.background_type))
                    return
                end = QColorDialog.getColor(QColor(grad_end or "#1b1f26"), self, "Gradient End Color")
                if not end.isValid():
                    combo.setCurrentIndex(combo.findData(self.background_type))
                    return
                _apply_background("gradient", g_start=start.name(), g_end=end.name())
                return
            if value == "image":
                path, _ = QFileDialog.getOpenFileName(
                    self, "Select Background Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
                )
                if path:
                    _apply_background("image", image=path)
                else:
                    combo.setCurrentIndex(combo.findData(self.background_type))

        combo.activated.connect(_on_change)

        combo.setStyleSheet(combo_style())
        return SettingRow("Background", combo, stacked=True)

    def make_keybind_row(self, label, current_key, setting_key, signal):
        btn = QPushButton(current_key)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedWidth(80)
        btn.setFixedHeight(26)
        btn.setStyleSheet(self.get_button_style(font_size=12))
        btn.clicked.connect(lambda checked, b=btn, k=setting_key, s=signal: self.wait_for_key(checked, b, k, s))
        if not hasattr(self, "_rainbow_buttons"):
            self._rainbow_buttons = []
        self._rainbow_buttons.append((btn, 12))
        return SettingRow(label, btn)

    def make_gui_scale_row(self, current_value):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)

        options = [
            ("80%", "0.8"),
            ("90%", "0.9"),
            ("100%", "1.0"),
            ("110%", "1.1"),
            ("125%", "1.25"),
            ("150%", "1.5"),
        ]
        for label, value in options:
            combo.addItem(label, value)

        idx = combo.findData(current_value)
        if idx < 0:
            idx = combo.findData("1.0")
        combo.setCurrentIndex(idx)

        combo.currentIndexChanged.connect(lambda _: self.gui_scale_changed.emit(combo.currentData()))
        combo.setStyleSheet(combo_style())
        return SettingRow("GUI Scale", combo, stacked=True)

    def make_view_mode_row(self, current_value):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)

        options = [
            ("List view", "list"),
            ("Grid view", "grid"),
        ]
        for label, value in options:
            combo.addItem(label, value)

        idx = combo.findData(current_value)
        if idx < 0:
            idx = combo.findData("list")
        combo.setCurrentIndex(idx)

        combo.currentIndexChanged.connect(lambda _: self.view_mode_changed.emit(combo.currentData()))
        combo.setStyleSheet(combo_style())
        return SettingRow("List Grid", combo, stacked=True)

    def make_grid_columns_row(self, current_value):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)

        options = [
            ("Auto", "auto"),
            ("1 x", "1"),
            ("2 x", "2"),
            ("3 x", "3"),
            ("4 x", "4"),
            ("5 x", "5"),
        ]
        for label, value in options:
            combo.addItem(label, value)

        idx = combo.findData(current_value)
        if idx < 0:
            idx = combo.findData("auto")
        combo.setCurrentIndex(idx)

        combo.currentIndexChanged.connect(lambda _: self.grid_columns_changed.emit(combo.currentData()))
        combo.setStyleSheet(combo_style())
        return SettingRow("Grid columns", combo, stacked=True)

    def make_mini_menu_scale_row(self, current_value):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)

        options = [
            ("80%", "0.8"),
            ("90%", "0.9"),
            ("100%", "1.0"),
            ("110%", "1.1"),
            ("125%", "1.25"),
            ("150%", "1.5"),
        ]
        for label, value in options:
            combo.addItem(label, value)

        idx = combo.findData(current_value)
        if idx < 0:
            idx = combo.findData("1.0")
        combo.setCurrentIndex(idx)

        combo.currentIndexChanged.connect(lambda _: self._on_mini_menu_scale_changed(combo.currentData()))
        combo.setStyleSheet(combo_style())
        return SettingRow("Mini menu scale", combo, stacked=True)

    def make_mini_menu_text_color_row(self, current_color):
        items = [
            {"label": "#FFFFFF", "value": "#FFFFFF"},
            {"label": "#E6E6E6", "value": "#E6E6E6"},
            {"label": "#101318", "value": "#101318"},
            {"label": "#4D5561", "value": "#4D5561"},
            {"label": "Default", "value": ""},
            {"label": "Custom", "value": "__custom__", "custom": True},
        ]
        picker = ColorGridPicker(items, current_value=current_color or "", columns=6)
        picker.colorSelected.connect(self._on_mini_menu_text_color_changed)
        return SettingRow("Mini menu text color", picker, stacked=True)

    def make_browser_row(self, current_choice, current_path):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(140)
        combo.setMaximumWidth(200)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)
        combo.setIconSize(QSize(16, 16))
        if combo.view():
            combo.view().setIconSize(QSize(16, 16))
            combo.view().setUniformItemSizes(True)
            combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        base_dir = get_base_dir()
        provider = QFileIconProvider()

        def _icon_for(path, fallback=None):
            if path and os.path.exists(path):
                return provider.icon(QFileInfo(path))
            return fallback if fallback else QIcon()

        browser_icons_dir = os.path.join(
            base_dir, "PortableApps", "PortableX", "Graphics", "browsericons"
        )

        def _browser_icon(name, fallback=None):
            icon_path = os.path.join(browser_icons_dir, f"{name}.ico")
            if os.path.exists(icon_path):
                return QIcon(icon_path)
            return fallback if fallback else QIcon()

        defaults = {
            "chrome": os.path.join(base_dir, "PortableApps", "GoogleChromePortable", "GoogleChromePortable.exe"),
            "firefox": os.path.join(base_dir, "PortableApps", "FirefoxPortable", "FirefoxPortable.exe"),
            "opera": os.path.join(base_dir, "PortableApps", "OperaPortable", "OperaPortable.exe"),
            "operagx": os.path.join(base_dir, "PortableApps", "OperaGXPortable", "OperaGXPortable.exe"),
            "brave": os.path.join(base_dir, "PortableApps", "BravePortable", "brave-portable.exe"),
        }

        custom_icon_path = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons", "app.png")
        custom_icon = QIcon(custom_icon_path) if os.path.exists(custom_icon_path) else self.style().standardIcon(QStyle.SP_FileIcon)
        options = [
            ("Computer default", "system", self.style().standardIcon(QStyle.SP_ComputerIcon)),
            ("Microsoft Edge", "edge", _browser_icon("edge", self.style().standardIcon(QStyle.SP_DesktopIcon))),
            ("Chrome Portable", "chrome", _browser_icon("chrome", _icon_for(defaults["chrome"]))),
            ("Firefox Portable", "firefox", _browser_icon("firefox", _icon_for(defaults["firefox"]))),
            ("Opera Portable", "opera", _browser_icon("opera", _icon_for(defaults["opera"]))),
            ("Opera GX Portable", "operagx", _browser_icon("operagx", _icon_for(defaults["operagx"]))),
            ("Brave Portable", "brave", _browser_icon("brave", _icon_for(defaults["brave"]))),
            ("Custom...", "custom", custom_icon),
        ]
        for label, value, icon in options:
            combo.addItem(icon, label, value)

        idx = combo.findData(current_choice)
        if idx < 0:
            idx = combo.findData("system")
        combo.setCurrentIndex(idx)

        install_btn = QPushButton("Install")
        install_btn.setCursor(Qt.PointingHandCursor)
        install_btn.setFixedHeight(CONTROL_HEIGHT + 4)
        install_btn.setFixedWidth(90)
        install_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        install_btn.setStyleSheet(self.get_button_style(font_size=SMALL_CONTROL_FONT_SIZE))
        if not hasattr(self, "_rainbow_buttons"):
            self._rainbow_buttons = []
        self._rainbow_buttons.append((install_btn, SMALL_CONTROL_FONT_SIZE))

        open_btn = QPushButton("Open Folder")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setFixedHeight(CONTROL_HEIGHT + 4)
        open_btn.setFixedWidth(110)
        open_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        open_btn.setStyleSheet(self.get_button_style(font_size=SMALL_CONTROL_FONT_SIZE))
        self._rainbow_buttons.append((open_btn, SMALL_CONTROL_FONT_SIZE))

        def _update_install_state():
            choice = combo.currentData()
            install_btn.setEnabled(choice in {"chrome", "firefox", "opera", "operagx", "brave"})
            open_btn.setEnabled(choice in {"chrome", "firefox", "opera", "operagx", "brave", "custom"})

        _update_install_state()
        combo.currentIndexChanged.connect(_update_install_state)

        def _on_change():
            value = combo.currentData()
            path = current_path
            if value == "custom":
                picked, _ = QFileDialog.getOpenFileName(
                    self, "Select Browser Executable", "", "Executable (*.exe)"
                )
                if picked:
                    path = picked
                    custom_idx = combo.findData("custom")
                    if custom_idx >= 0:
                        combo.setItemIcon(custom_idx, _icon_for(picked))
                else:
                    combo.setCurrentIndex(combo.findData(current_choice))
                    return
            self.browser_changed.emit({"choice": value, "path": path or ""})

        def _on_install():
            self.browser_install_clicked.emit(combo.currentData())

        def _on_open_folder():
            self.browser_open_folder_clicked.emit(combo.currentData())

        install_btn.clicked.connect(_on_install)
        open_btn.clicked.connect(_on_open_folder)
        combo.activated.connect(_on_change)
        combo.setStyleSheet(combo_style())

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row_layout = QVBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(combo, 0, Qt.AlignLeft)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)
        btn_row.addWidget(install_btn, 0, Qt.AlignLeft)
        btn_row.addWidget(open_btn, 0, Qt.AlignLeft)
        btn_row.addStretch()
        row_layout.addLayout(btn_row)
        return SettingRow("Default browser", container, stacked=True)

    def make_mini_menu_background_row(self, current_type, current_color, grad_start, grad_end):
        combo = ThemedComboBox(self.settings)
        combo.setMinimumWidth(160)
        combo.setMaximumWidth(220)
        combo.setFixedHeight(CONTROL_HEIGHT + 4)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setCursor(Qt.PointingHandCursor)

        options = [
            ("Default", "default"),
            ("Solid color...", "solid"),
            ("Gradient...", "gradient"),
        ]
        for label, value in options:
            combo.addItem(label, value)

        idx = combo.findData(current_type)
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)

        def _apply_background(bg_type, color="", g_start="", g_end=""):
            self._on_mini_menu_background_changed({
                "type": bg_type,
                "color": color,
                "gradient_start": g_start,
                "gradient_end": g_end,
            })

        def _on_change():
            value = combo.currentData()
            if value == "default":
                _apply_background("default")
                return
            if value == "solid":
                color = QColorDialog.getColor(QColor(current_color or "#1b1f26"), self, "Select Mini Menu Color")
                if color.isValid():
                    _apply_background("solid", color.name())
                else:
                    combo.setCurrentIndex(combo.findData(current_type))
                return
            if value == "gradient":
                start = QColorDialog.getColor(QColor(grad_start or "#0e1014"), self, "Mini Menu Gradient Start")
                if not start.isValid():
                    combo.setCurrentIndex(combo.findData(current_type))
                    return
                end = QColorDialog.getColor(QColor(grad_end or "#1b1f26"), self, "Mini Menu Gradient End")
                if not end.isValid():
                    combo.setCurrentIndex(combo.findData(current_type))
                    return
                _apply_background("gradient", g_start=start.name(), g_end=end.name())
                return

        combo.activated.connect(_on_change)
        combo.setStyleSheet(combo_style())
        return SettingRow("Mini menu background", combo, stacked=True)

    def make_toggle_row_with_key(self, text, checked, key):
        toggle = ToggleSwitch(checked=checked)
        toggle.toggled.connect(lambda v, k=key: self._on_mini_setting_changed(k, v))
        return SettingRow(text, toggle)

    def _on_mini_setting_changed(self, key, value):
        self.settings[key] = value
        if hasattr(self, "mini_preview") and self.mini_preview:
            self.mini_preview.update_config(self.settings)
        self.mini_menu_setting_changed.emit(key, value)

    def _on_mini_menu_background_changed(self, payload):
        payload = payload or {}
        self.settings["mini_menu_background_type"] = payload.get("type", "default")
        self.settings["mini_menu_background_color"] = payload.get("color", "")
        self.settings["mini_menu_background_gradient_start"] = payload.get("gradient_start", "")
        self.settings["mini_menu_background_gradient_end"] = payload.get("gradient_end", "")
        if hasattr(self, "mini_preview") and self.mini_preview:
            self.mini_preview.update_config(self.settings)
        self.mini_menu_background_changed.emit(payload)

    def _on_mini_menu_scale_changed(self, value):
        if not value:
            return
        self.settings["mini_menu_scale"] = value
        if hasattr(self, "mini_preview") and self.mini_preview:
            self.mini_preview.update_config(self.settings)
        self.mini_menu_scale_changed.emit(value)

    def _on_mini_menu_text_color_changed(self, value):
        self.settings["mini_menu_text_color"] = value or ""
        if hasattr(self, "mini_preview") and self.mini_preview:
            self.mini_preview.update_config(self.settings)
        self.mini_menu_text_color_changed.emit(value or "")

    def open_home_shortcuts_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Home Shortcuts")
        layout = QVBoxLayout(dlg)

        items = [
            ("Documents", "home_show_documents", "documents.png"),
            ("Music", "home_show_music", "music.png"),
            ("Pictures", "home_show_pictures", "pictures.png"),
            ("Videos", "home_show_videos", "videos.png"),
            ("Downloads", "home_show_downloads", "download.png"),
            ("Explore", "home_show_explore", "explore.png"),
        ]

        icon_dir = os.path.join(self.base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons")
        checkboxes = []
        for label, key, icon_file in items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            if icon_file:
                icon_label = QLabel()
                icon_path = os.path.join(icon_dir, icon_file)
                if os.path.exists(icon_path):
                    icon_label.setPixmap(QIcon(icon_path).pixmap(14, 14))
                icon_label.setFixedSize(14, 14)
                row_layout.addWidget(icon_label)
            cb = QCheckBox(label)
            cb.setChecked(self.settings.get(key, True))
            row_layout.addWidget(cb)
            checkboxes.append((cb, key))
            layout.addWidget(row)

        custom_folders = list(self.settings.get("home_custom_folders", []))
        if not custom_folders:
            legacy_path = self.settings.get("home_custom_folder", "")
            legacy_label = self.settings.get("home_custom_label", "")
            if legacy_path:
                custom_folders = [{"path": legacy_path, "label": legacy_label, "enabled": True}]
        for entry in custom_folders:
            if isinstance(entry, dict) and "enabled" not in entry:
                entry["enabled"] = True

        custom_section = QWidget()
        custom_section_layout = QVBoxLayout(custom_section)
        custom_section_layout.setContentsMargins(0, 8, 0, 0)
        custom_section_layout.setSpacing(6)

        custom_header = QWidget()
        custom_header_layout = QHBoxLayout(custom_header)
        custom_header_layout.setContentsMargins(0, 0, 0, 0)
        custom_header_layout.setSpacing(8)
        custom_title = QLabel("Custom folders")
        custom_title.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; font-size: 15px;")
        custom_header_layout.addWidget(custom_title)
        custom_header_layout.addStretch()
        add_btn = QPushButton("Add")
        add_btn.setFixedHeight(24)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(self.get_button_style(font_size=10))
        custom_header_layout.addWidget(add_btn)
        custom_section_layout.addWidget(custom_header)

        custom_list = QWidget()
        custom_list_layout = QVBoxLayout(custom_list)
        custom_list_layout.setContentsMargins(0, 0, 0, 0)
        custom_list_layout.setSpacing(6)

        def _normalize_folder_entry(path, label="", enabled=True):
            return {
                "path": path,
                "label": label or os.path.basename(path) or "Custom Folder",
                "enabled": bool(enabled),
            }

        def _update_empty_state():
            custom_list.setVisible(len(custom_folders) > 0)

        def _add_custom_row(entry):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            icon_label = QLabel()
            icon_label.setFixedSize(14, 14)
            try:
                icon = QFileIconProvider().icon(QFileInfo(entry.get("path", "")))
                if not icon.isNull():
                    icon_label.setPixmap(icon.pixmap(14, 14))
            except Exception:
                pass

            text_col = QWidget()
            text_layout = QVBoxLayout(text_col)
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)

            title = QCheckBox(entry.get("label") or os.path.basename(entry.get("path", "")) or "Custom Folder")
            title.setChecked(entry.get("enabled", True))
            def _toggle_entry(state):
                entry["enabled"] = bool(state)
            title.toggled.connect(_toggle_entry)
            text_layout.addWidget(title)

            remove_btn = QPushButton("Remove")
            remove_btn.setFixedHeight(24)
            remove_btn.setCursor(Qt.PointingHandCursor)
            remove_btn.setStyleSheet(self.get_button_style(font_size=10))

            def _remove_entry():
                try:
                    custom_folders.remove(entry)
                except ValueError:
                    pass
                row.setParent(None)
                row.deleteLater()
                _update_empty_state()

            remove_btn.clicked.connect(_remove_entry)

            row_layout.setAlignment(icon_label, Qt.AlignTop)
            row_layout.setAlignment(text_col, Qt.AlignTop)
            row_layout.addWidget(icon_label)
            row_layout.addWidget(text_col, 1)
            row_layout.addWidget(remove_btn)
            custom_list_layout.addWidget(row)

        def _add_custom_folder():
            start_dir = self.base_dir
            if custom_folders:
                last_path = custom_folders[-1].get("path", "")
                if last_path and os.path.exists(last_path):
                    start_dir = last_path
            folder = QFileDialog.getExistingDirectory(self, "Select Custom Folder", start_dir)
            if folder:
                try:
                    norm = os.path.normpath(folder).lower()
                except Exception:
                    norm = folder.lower()
                for entry in custom_folders:
                    try:
                        existing = os.path.normpath(entry.get("path", "")).lower()
                    except Exception:
                        existing = entry.get("path", "").lower()
                    if existing == norm:
                        return
                entry = _normalize_folder_entry(folder)
                custom_folders.append(entry)
                _add_custom_row(entry)
                _update_empty_state()

        add_btn.clicked.connect(_add_custom_folder)

        for entry in list(custom_folders):
            _add_custom_row(entry)
        _update_empty_state()

        custom_section_layout.addWidget(custom_list)
        layout.addWidget(custom_section)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        dlg.setSizeGripEnabled(False)
        dlg.adjustSize()
        dlg.setFixedSize(dlg.sizeHint())

        if dlg.exec() == QDialog.Accepted:
            updates = {}
            for cb, key in checkboxes:
                updates[key] = cb.isChecked()
                self.settings[key] = updates[key]
            updates["home_show_custom_folder"] = any(entry.get("enabled", True) for entry in custom_folders)
            updates["home_custom_folders"] = custom_folders
            if custom_folders:
                updates["home_custom_folder"] = custom_folders[0].get("path", "")
                updates["home_custom_label"] = custom_folders[0].get("label", "")
            else:
                updates["home_custom_folder"] = ""
                updates["home_custom_label"] = ""
            self.settings["home_show_custom_folder"] = updates["home_show_custom_folder"]
            self.settings["home_custom_folders"] = custom_folders
            self.settings["home_custom_folder"] = updates["home_custom_folder"]
            self.settings["home_custom_label"] = updates["home_custom_label"]
            if updates:
                self.home_shortcuts_changed.emit(updates)

    def open_mini_items_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Mini Menu Items")
        layout = QVBoxLayout(dlg)

        items = [
            ("Documents", "mini_show_documents", "documents.png"),
            ("Music", "mini_show_music", "music.png"),
            ("Videos", "mini_show_videos", "videos.png"),
            ("Downloads", "mini_show_downloads", "download.png"),
            ("Explore", "mini_show_explore", "explore.png"),
            ("Settings", "mini_show_settings", "options.png"),
            ("All Apps", "mini_show_all_apps", "apps.png"),
            ("Favorites", "mini_show_favorites", "favourites.png"),
            ("Exit", "mini_show_exit", ""),
        ]

        icon_dir = os.path.join(self.base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons")
        checkboxes = []
        for label, key, icon_file in items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            if icon_file:
                icon_label = QLabel()
                icon_path = os.path.join(icon_dir, icon_file)
                if os.path.exists(icon_path):
                    icon_label.setPixmap(QIcon(icon_path).pixmap(14, 14))
                icon_label.setFixedSize(14, 14)
                row_layout.addWidget(icon_label)
            cb = QCheckBox(label)
            cb.setChecked(self.settings.get(key, True))
            row_layout.addWidget(cb)
            checkboxes.append((cb, key))
            layout.addWidget(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        dlg.setSizeGripEnabled(False)
        dlg.adjustSize()
        dlg.setFixedSize(dlg.sizeHint())

        if dlg.exec() == QDialog.Accepted:
            updates = {}
            for cb, key in checkboxes:
                updates[key] = cb.isChecked()
                self.settings[key] = updates[key]
                self.mini_menu_setting_changed.emit(key, updates[key])
            if hasattr(self, "mini_preview") and self.mini_preview:
                self.mini_preview.update_config(self.settings)

    def get_button_style(self, is_destructive=False, is_toggle=False, font_size=10):
        base_color = "rgba(255, 255, 255, 0.05)"
        hover_color = "rgba(255, 255, 255, 0.12)"
        text_color = COLOR_TEXT_MAIN.name()
        border_color = qcolor_to_rgba(COLOR_GLASS_BORDER)

        if is_destructive:
            hover_color = "rgba(255, 50, 50, 0.3)"
            border_color = "rgba(255, 50, 50, 0.5)"

        if is_toggle:
            return f"""
                QPushButton {{
                    background-color: {base_color};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 3px 8px;
                    font-family: "{FONT_FAMILY}";
                    font-size: {font_size}px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:checked {{
                    background-color: {COLOR_ACCENT.name()};
                    border-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """

        return f"""
            QPushButton {{
                background-color: {base_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 3px 8px;
                font-family: "{FONT_FAMILY}";
                font-size: {font_size}px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border-color: {COLOR_ACCENT.name()};
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.18);
            }}
        """

    def set_category(self, name):
        if name == self.current_category:
            return
        self.collapse_expanded_sections()
        if name != "Security" and self._security_password_set:
            # Lock security when switching away.
            self._security_unlocked = False
        if name == "Security":
            # Always prompt when entering Security. Hide rows first.
            self._security_unlocked = False
            self.current_category = "Security"
            self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
            self.update_category_highlight()
            if not self._ensure_security_unlocked():
                self.current_category = "Behavior"
                self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
                self.update_category_highlight()
                return
            self.build_rows(["Security"])
            self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
            self.update_category_highlight()
            return
        if hasattr(self, "_category_anim") and self._category_anim:
            self._category_anim.stop()
        target = self.settings_list_container
        effect = QGraphicsOpacityEffect(target)
        target.setGraphicsEffect(effect)
        effect.setOpacity(1.0)

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(120)
        fade_out.setEasingCurve(QEasingCurve.OutCubic)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        def _apply():
            self.current_category = name
            self.build_rows([self.current_category])
            if self.current_category == "About":
                self._ensure_about_panel_loaded()
            self.apply_category_filter()
            self.update_category_highlight()
            if self.current_category in ("Mini menu", "About"):
                self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            else:
                self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        fade_out.finished.connect(_apply)

        fade_in = QPropertyAnimation(effect, b"opacity", self)
        fade_in.setDuration(160)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.finished.connect(lambda: target.setGraphicsEffect(None))

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)
        self._category_anim = group
        group.start()

    def collapse_expanded_sections(self):
        if hasattr(self, "about_panel") and self.about_panel:
            try:
                self.about_panel.collapse_expanded()
            except Exception:
                pass

    def lock_security(self):
        if self._security_password_set:
            self._security_unlocked = False
            if self.current_category == "Security":
                self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")

    def _ensure_security_unlocked(self):
        if self._security_unlocked:
            return True
        pwd_hash = self.settings.get("password_hash", "")
        pwd_salt = self.settings.get("password_salt", "")
        if not pwd_hash or not pwd_salt:
            self._security_unlocked = True
            return True
        while True:
            pwd, ok = QInputDialog.getText(self, "Security", "Enter password:", QLineEdit.Password)
            if not ok:
                return False
            if self._verify_password(pwd, pwd_salt, pwd_hash):
                self._security_unlocked = True
                return True
            QMessageBox.warning(self, "Incorrect Password", "The password you entered is incorrect.")

    def on_password_state_changed(self, has_password, relock=False):
        self._security_password_set = bool(has_password)
        if self._security_password_set:
            if hasattr(self, "create_password_row") and self.create_password_row:
                self.create_password_row._force_hidden = True
            if hasattr(self, "change_password_row") and self.change_password_row:
                self.change_password_row._force_hidden = False
            if hasattr(self, "delete_password_row") and self.delete_password_row:
                self.delete_password_row._force_hidden = False
                self.delete_password_row.setDisabled(False)
        else:
            if hasattr(self, "create_password_row") and self.create_password_row:
                self.create_password_row._force_hidden = False
            if hasattr(self, "change_password_row") and self.change_password_row:
                self.change_password_row._force_hidden = True
            if hasattr(self, "delete_password_row") and self.delete_password_row:
                self.delete_password_row._force_hidden = True
                self.delete_password_row.setDisabled(True)
        if relock:
            self._security_unlocked = False
            if self.current_category == "Security":
                self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
                if not self._ensure_security_unlocked():
                    self.current_category = "Behavior"
                self.apply_category_filter(self.search_bar.input.text() if hasattr(self, "search_bar") else "")
                self.update_category_highlight()

    def set_app_session_unlock(self, enabled):
        self._app_session_unlock = bool(enabled)

    def _verify_password(self, password, salt_hex, expected_hash):
        try:
            salt = bytes.fromhex(salt_hex)
        except Exception:
            salt = salt_hex.encode("utf-8")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return digest.hex() == expected_hash

    def filter_rows(self, text):
        if not hasattr(self, "_rainbow_search_active"):
            self._rainbow_search_active = False
        if "rainbow" in text.lower():
            if not self._rainbow_search_active:
                self._rainbow_search_active = True
                self.text_color_changed.emit("__rainbow__")
        else:
            self._rainbow_search_active = False
        if text.strip() and not self._all_rows_built:
            self._ensure_all_rows_built_async()
        self.apply_category_filter(text)

    def apply_rainbow_text(self, color_hex):
        for row in self.rows:
            if hasattr(row, "label") and row.label:
                row.label.setStyleSheet(f"color: {color_hex}; background: transparent;")
        for btn in self.category_buttons.values():
            if hasattr(btn, "label"):
                btn.label.setStyleSheet(f"color: {color_hex}; background: transparent;")
        if hasattr(self, "back_btn"):
            self.back_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {qcolor_to_rgba(COLOR_GLASS_WHITE)};
                    color: {color_hex};
                    border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                    border-radius: 6px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {qcolor_to_rgba(COLOR_HOVER)};
                    border-color: {COLOR_ACCENT.name()};
                    color: {color_hex};
                }}
            """)
        if hasattr(self, "close_btn"):
            self.close_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {color_hex};
                    border: none;
                    font-weight: bold;
                    font-size: 18px;
                }}
                QPushButton:hover {{
                    color: {color_hex};
                }}
                QPushButton:pressed {{
                    color: {COLOR_ACCENT.name()};
                }}
            """)
        for btn, font_size in getattr(self, "_rainbow_buttons", []):
            try:
                style = self.get_button_style(font_size=font_size).replace(COLOR_TEXT_MAIN.name(), color_hex)
                btn.setStyleSheet(style)
            except Exception:
                pass

    def _animate_back_btn_opacity(self, value):
        if not hasattr(self, "_back_btn_opacity") or not self._back_btn_opacity:
            return
        try:
            self._back_btn_anim.stop()
            self._back_btn_anim.setStartValue(self._back_btn_opacity.opacity())
            self._back_btn_anim.setEndValue(value)
            self._back_btn_anim.start()
        except Exception:
            pass

    def eventFilter(self, obj, event):
        if hasattr(self, "back_btn") and obj is self.back_btn:
            if event.type() == QEvent.Enter:
                self._back_btn_hovered = True
                self._animate_back_btn_opacity(0.9)
            elif event.type() == QEvent.Leave:
                self._back_btn_hovered = False
                self._animate_back_btn_opacity(1.0)
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self._animate_back_btn_opacity(0.8)
            elif event.type() == QEvent.MouseButtonRelease:
                self._animate_back_btn_opacity(0.9 if self._back_btn_hovered else 1.0)
        return super().eventFilter(obj, event)

    def apply_category_filter(self, text=""):
        query = text.strip().lower()
        for row in self.rows:
            if getattr(row, "_force_hidden", False):
                row.setVisible(False)
                continue
            if row.category == "Security" and self._security_password_set and not self._security_unlocked:
                row.setVisible(False)
                continue
            if query:
                text_match = query in row.text.lower()
                desc_match = False
                tooltip_text = getattr(row, "_tooltip_text", "")
                if tooltip_text:
                    desc_match = query in tooltip_text.lower()
                row.setVisible(text_match or desc_match)
            else:
                row.setVisible(row.category == self.current_category)

    def update_category_highlight(self):
        for name, btn in self.category_buttons.items():
            btn.set_selected(name == self.current_category)

    def wait_for_key(self, checked, button, setting_key, signal):
        if checked:
            button.setText("Press key...")
            self._keybind_target = (button, setting_key, signal)
            self.grabKeyboard()
        else:
            self.releaseKeyboard()

    def keyPressEvent(self, event):
        if hasattr(self, "_keybind_target") and self._keybind_target:
            button, setting_key, signal = self._keybind_target
            key = event.key()
            modifiers = event.modifiers()

            if key == Qt.Key_Escape:
                button.setChecked(False)
                button.setText(self.settings.get(setting_key, "Ctrl+R" if setting_key == "menu_key" else "Ctrl+E"))
                self._keybind_target = None
                self.releaseKeyboard()
                return

            if key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
                return

            key_seq = QKeySequence(Qt.Key(key) | modifiers)
            key_str = key_seq.toString()

            button.setText(key_str)
            button.setChecked(False)
            self._keybind_target = None
            self.releaseKeyboard()
            signal.emit(key_str)
        else:
            super().keyPressEvent(event)
