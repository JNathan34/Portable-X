import os
import shutil
import configparser
from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QStorageInfo, Signal, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QPixmap, QLinearGradient, QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFileDialog
from config import *
from ui_base import AnimatableWidget

class QuickAccessButton(AnimatableWidget):
    """
    Right panel buttons.
    """
    clicked = Signal(str)

    def __init__(self, name, icon_path, parent=None):
        super().__init__(parent)
        self.name = name
        self._selected = False
        self.pixmap = None
        if isinstance(icon_path, QPixmap):
            self.pixmap = icon_path
        elif isinstance(icon_path, QIcon):
            self.pixmap = icon_path.pixmap(22, 22)
        elif icon_path and os.path.exists(icon_path):
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
        if not self._selected:
            self.anim.setEndValue(COLOR_HOVER)
            self.anim.start()
            self.label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        if not self._selected:
            self.anim.setEndValue(QColor(0, 0, 0, 0))
            self.anim.start()
            self.label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        super().leaveEvent(event)

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self._bg_color = COLOR_HOVER
            self.label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()}; background: transparent;")
        else:
            self._bg_color = QColor(0, 0, 0, 0)
            self.label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; background: transparent;")
        self.update()

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
        text = f"{self.drive_name}: {self.free // (1024**3)}GB free of {self.total // (1024**3)}GB"
        painter.setPen(QColor("#ffffff"))
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
                self.pixmap = QPixmap(path)
                self.save_profile_pic(path)
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
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Clip to circle
            path = QPainterPath()
            path.addEllipse(0, 0, self.width(), self.height())
            painter.setClipPath(path)

            if self.pixmap and not self.pixmap.isNull():
                inset = 1
                safe = int(min(self.width(), self.height()) * 0.96)
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
        finally:
            painter.end()
