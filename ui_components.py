import os
import shutil
import configparser
from PySide6.QtCore import (
    Qt, QSize, QPoint, QPropertyAnimation, QEasingCurve, 
    QParallelAnimationGroup, QRect, Property, Signal, QObject, QStorageInfo, QFileInfo, QTimer
)
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush, QFont, 
    QLinearGradient, QRadialGradient, QIcon, QPalette, QPixmap, QCursor
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QLabel, QScrollArea, QFrame, QGraphicsDropShadowEffect,
    QGraphicsBlurEffect, QSizePolicy, QStackedLayout, QPushButton, QFileIconProvider,
    QFileDialog, QMenu, QInputDialog, QDialog, QComboBox, QDialogButtonBox
)
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
        if icon_path:
            if icon_path.lower().endswith(".ico") and os.path.exists(icon_path):
                self.icon_pixmap = QPixmap(icon_path)
            else:
                # Try provider (works for exe, or fallback)
                provider = QFileIconProvider()
                info = QFileInfo(icon_path)
                icon = provider.icon(info)
                if not icon.isNull():
                    self.icon_pixmap = icon.pixmap(32, 32)
        
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
        menu.setStyleSheet("""
            QMenu {
                background-color: #1b1f26;
                color: white;
                border: 1px solid #333;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)

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

class QuickAccessButton(AnimatableWidget):
    """
    Right panel buttons.
    """
    clicked = Signal(str)

    def __init__(self, name, icon_path, parent=None):
        super().__init__(parent)
        self.name = name
        self.pixmap = None
        if icon_path and os.path.exists(icon_path):
            self.pixmap = QPixmap(icon_path)
            
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(48, 0, 10, 0)
        layout.setSpacing(10)
        
        # Icon Badge
        self.badge_color = QColor(255, 255, 255, 30)
        
        self.label = QLabel(name)
        self.label.setFont(QFont(FONT_FAMILY, 10))
        self.label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        
        layout.addWidget(self.label)
        layout.addStretch()

        self.anim = QPropertyAnimation(self, b"bg_color")
        self.anim.setDuration(150)

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setEndValue(COLOR_HOVER)
        self.anim.start()
        self.label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setEndValue(QColor(0, 0, 0, 0))
        self.anim.start()
        self.label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._bg_color = COLOR_PRESSED
            self.update()
            self.clicked.emit(self.name)

    def mouseReleaseEvent(self, event):
        self._bg_color = COLOR_HOVER
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        if self._bg_color.alpha() > 0:
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 8, 8)
        
        # Draw Icon
        if self.pixmap:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            target_rect = QRect(12, 7, 22, 22)
            painter.drawPixmap(target_rect, self.pixmap)
        else:
            # Fallback Badge
            badge_rect = QRect(12, 9, 18, 18)
            painter.setBrush(self.badge_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(badge_rect)

class SearchIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(QColor("#cccccc"))
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
        self.input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: white;
            }
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
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 6, 6)

class DriveUsageBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setCursor(Qt.PointingHandCursor)
        
        try:
            path = os.path.abspath(".")
            storage = QStorageInfo(path)
            self.drive_name = storage.name() or "Local Disk"
            self.drive_letter = os.path.splitdrive(path)[0]
            self.total, self.used, self.free = shutil.disk_usage(path)
            self.percent = self.used / self.total if self.total > 0 else 0
        except:
            self.drive_name = "Unknown"
            self.drive_letter = "?"
            self.total = 1
            self.used = 0
            self.free = 0
            self.percent = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        # Track
        painter.setBrush(QColor(255, 255, 255, 30))
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawRoundedRect(rect, 3, 3)
        
        # Progress
        if self.percent > 0:
            painter.setPen(Qt.NoPen)
            path = QPainterPath()
            path.addRoundedRect(rect, 3, 3)
            painter.setClipPath(path)
            
            fill_width = int(rect.width() * self.percent)
            fill_rect = QRect(rect.x(), rect.y(), fill_width, rect.height())
            
            grad = QLinearGradient(rect.x(), rect.y(), rect.x() + fill_width, rect.y())
            grad.setColorAt(0, QColor(0, 120, 212, 30))
            grad.setColorAt(1, QColor(0, 188, 242, 30))
            
            painter.setBrush(grad)
            painter.drawRect(fill_rect)
            painter.setClipping(False)

        # Text
        text = f"{self.drive_name} {self.free // (1024**3)}GB free of {self.total // (1024**3)}GB"
        text = f"{self.drive_name}: {self.free // (1024**3)}GB free of {self.total // (1024**3)}GB"
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        painter.setFont(QFont(FONT_FAMILY, 8))
        painter.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, text)

class ProfilePicture(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.pixmap = None
        self.load_profile_pic()

    def load_profile_pic(self):
        try:
            base_dir = get_base_dir()
            settings_path = get_settings_path()
            fallback_path = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "profilepic", "profile.png")
            loaded_pixmap = None
            if os.path.exists(settings_path):
                config = configparser.ConfigParser()
                config.optionxform = str
                config.read(settings_path)
                if "User" in config and "ProfilePic" in config["User"]:
                    path = config["User"]["ProfilePic"]
                    if not os.path.isabs(path):
                        path = os.path.join(base_dir, path)
                    if os.path.exists(path):
                        candidate = QPixmap(path)
                        if not candidate.isNull():
                            loaded_pixmap = candidate
                elif "User" in config and "profilepic" in config["User"]:
                    path = config["User"]["profilepic"]
                    if not os.path.isabs(path):
                        path = os.path.join(base_dir, path)
                    if os.path.exists(path):
                        candidate = QPixmap(path)
                        if not candidate.isNull():
                            loaded_pixmap = candidate

            if loaded_pixmap is None and os.path.exists(fallback_path):
                candidate = QPixmap(fallback_path)
                if not candidate.isNull():
                    loaded_pixmap = candidate

            if loaded_pixmap is not None:
                self.pixmap = loaded_pixmap
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Profile Picture", "", "Images (*.png *.jpg *.jpeg *.bmp)"
            )
            if path:
                saved_path = self.save_profile_pic(path)
                self.pixmap = QPixmap(saved_path if saved_path else path)
                self.update()

    def save_profile_pic(self, path):
        base_dir = get_base_dir()
        settings_path = get_settings_path()
        profile_dir = os.path.join(get_data_dir(), "profilepic")
        os.makedirs(profile_dir, exist_ok=True)

        saved_path = path
        try:
            target_path = os.path.join(profile_dir, "profile.png")
            pix = QPixmap(path)
            if not pix.isNull():
                pix.save(target_path, "PNG")
                saved_path = target_path
            else:
                filename = os.path.basename(path)
                target_path = os.path.join(profile_dir, filename)
                if os.path.abspath(path) != os.path.abspath(target_path):
                    shutil.copy2(path, target_path)
                saved_path = target_path
        except Exception:
            saved_path = path

        config = configparser.ConfigParser()
        config.optionxform = str
        config.read(settings_path)
        if "User" not in config:
            config["User"] = {}
        rel_path = os.path.relpath(saved_path, base_dir).replace("\\", "/")
        config["User"]["ProfilePic"] = rel_path
        if config.has_option("User", "profilepic"):
            config.remove_option("User", "profilepic")
        with open(settings_path, 'w') as f:
            config.write(f)
        return saved_path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Clip to circle
        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        painter.setClipPath(path)

        if self.pixmap and not self.pixmap.isNull():
            # Draw background to avoid empty corners when fitting
            painter.setBrush(QColor(255, 255, 255, 30))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, self.width(), self.height())

            # Fit inside a safe square so the circular clip doesn't crop the image
            inset = 3
            safe = int(min(self.width(), self.height()) * 0.68)
            target = QSize(max(1, safe - inset * 2), max(1, safe - inset * 2))
            scaled = self.pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            # Draw Circle Background
            painter.setBrush(QColor(255, 255, 255, 30))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, self.width(), self.height())
            
            # Draw generic user silhouette
            painter.setBrush(QColor(255, 255, 255, 180))
            painter.drawEllipse(11, 7, 14, 14) # Head
            painter.drawEllipse(5, 24, 26, 20) # Shoulders

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
        
        base_dir = get_base_dir()
        icon_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "categories")
        
        for cat in categories:
            icon_path = os.path.join(icon_dir, f"{cat}.png")
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
            else:
                icon = QIcon()
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
        self.text_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
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

    def __init__(self, name, icon_path, apps, parent=None):
        super().__init__(parent)
        self.name = name
        self.apps_data = apps
        self.expanded = False
        
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
        
        self.app_items = []
        for app in apps:
            item = AppListItem(app["name"], app["icon"], app["exe"], app["is_favorite"], app["is_hidden"], app["category"], app["version"], app["description"])
            item.clicked.connect(self.app_clicked.emit)
            self.content_layout.addWidget(item)
            self.app_items.append(item)
            
        self.layout.addWidget(self.content_widget)
        self.content_widget.hide()
        self.header.set_expanded(False)

    def toggle_expand(self):
        self.expanded = not self.expanded
        self.header.set_expanded(self.expanded)
        if self.expanded:
            self.content_widget.show()
        else:
            self.content_widget.hide()
            
    def set_expanded(self, expanded):
        self.expanded = expanded
        self.header.set_expanded(expanded)
        if self.expanded:
            self.content_widget.show()
        else:
            self.content_widget.hide()

    def filter(self, text):
        match_cat = text in self.name.lower()
        has_visible_app = False
        
        for item in self.app_items:
            if text in item.name.lower():
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
                self.content_widget.show()
                self.header.set_expanded(True)
            elif not text:
                self.content_widget.hide()
                self.header.set_expanded(self.expanded) # Restore state
        else:
            self.hide()
