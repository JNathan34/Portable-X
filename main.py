import sys
import os
import shutil
import configparser
import subprocess
import webbrowser
import ctypes
import time
import signal
import urllib.parse
import urllib.request
import hashlib
import secrets
import getpass
import platform
import stat
import json
import update_checker
import fix_settings
from app_info import (
    DEFAULT_GITHUB_REPO,
    DEFAULT_UPDATE_CHECK_INTERVAL_HOURS,
    get_app_display_name,
    get_app_version,
)
from ctypes import wintypes
from PySide6.QtCore import (
    Qt, QSize, QPoint, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QRect, Property, Signal, QObject, QStorageInfo, QFileInfo, QTimer, QEvent,
    QAbstractNativeEventFilter, QThread
)
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush, QFont, QKeySequence, QShortcut,
    QLinearGradient, QRadialGradient, QIcon, QPalette, QPixmap, QCursor, QAction
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QLabel, QScrollArea, QStackedWidget, QFrame, QGraphicsDropShadowEffect,
    QGraphicsBlurEffect, QGraphicsOpacityEffect, QSizePolicy, QStackedLayout, QPushButton, QFileIconProvider,
    QFileDialog, QMenu, QInputDialog, QDialog, QComboBox, QDialogButtonBox, QProgressBar, QProgressDialog, QCheckBox,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QToolButton, QHeaderView,
    QSystemTrayIcon, QStyle, QMessageBox
)
from config import *
from ui_base import GlassPanel
from ui_search import SearchBar
from ui_sidebar import QuickAccessButton, ProfilePicture
from ui_app_item import AppListItem, AppGridItem
from ui_category import CategoryItem, CategorySelectionDialog
from ui_options import OptionsPanel

NOTICE_TITLE = f"{get_app_display_name()} - Notice"
NOTICE_BODY = (
    "Created by Jacob Nathan.\n\n"
    "Portable X is a portable application launcher and organizer for your PortableApps setup. "
    "It helps you scan, manage, and launch apps from your drive, and provides system-style "
    "folders and settings for your portable environment.\n\n"
    "Recommended USB setup:\n"
    "- Use USB 3.0/3.1/3.2 or USB-C drives for the best speed.\n"
    "- Aim for at least 100 MB/s read and 50 MB/s write for smooth app launching.\n"
    "- Avoid very slow USB 2.0 drives, as they can cause long load times.\n\n"
    "Hotkey: Press Ctrl + R to open/close the menu.\n\n"
    "This software is for your personal use only.\n"
    "You may not share, copy, redistribute, or claim any part of this program as your own.\n"
    "Do not remove this notice.\n\n"
    "All rights are reserved by the creator."
)

BASE_CATEGORIES = [
    "Accessibility", "Benchmark", "Development", "Education", "Games",
    "Graphics and Pictures", "Internet", "Messaging", "Microsoft",
    "Music and Video", "Office", "Other", "Portable Apps", "Security",
    "Steam Games", "Utilities", "No Category"
]

def _parse_global_categories(settings_config):
    categories = []
    if settings_config and settings_config.has_section("GlobalCategories"):
        for name, value in settings_config.items("GlobalCategories"):
            if not name:
                continue
            raw = str(value).strip().lower()
            if raw in {"0", "false", "no", "off"}:
                continue
            cleaned = normalize_category_name(name)
            if cleaned:
                categories.append(cleaned)
    return categories

def _build_allowed_categories(settings_config, base_categories):
    seen = set()
    allowed = []
    no_category_label = "No Category"
    for cat in base_categories or []:
        norm = normalize_category_name(cat)
        if not norm:
            continue
        if norm.lower() == "no category":
            no_category_label = cat
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        allowed.append(cat)

    for cat in _parse_global_categories(settings_config):
        norm = normalize_category_name(cat)
        if not norm:
            continue
        key = norm.lower()
        if key in seen or key == "no category":
            continue
        seen.add(key)
        allowed.append(cat)

    if "no category" not in seen:
        allowed.append(no_category_label)
    return allowed


def _scan_portable_apps_on_disk(base_dir, show_hidden):
    apps = []
    apps_dir = os.path.join(base_dir, "PortableApps")

    if not os.path.exists(apps_dir):
        return []

    settings_config = configparser.ConfigParser()
    settings_config.optionxform = str
    settings_config.read(get_settings_path())
    allowed_categories = _build_allowed_categories(settings_config, BASE_CATEGORIES)

    def _get_app_key(exe_path):
        try:
            return os.path.relpath(exe_path, base_dir).replace("\\", "/")
        except ValueError:
            return exe_path.replace("\\", "/")

    for entry in os.scandir(apps_dir):
        if not entry.is_dir():
            continue
        potential_apps = []
        ini_path = os.path.join(entry.path, "App", "AppInfo", "appinfo.ini")

        if os.path.exists(ini_path):
            try:
                app_config = configparser.ConfigParser()
                app_config.read(ini_path)

                name = app_config.get("Details", "Name", fallback=entry.name)
                name = name.replace("Portable", "").replace("  ", " ").strip()
                category = app_config.get("Details", "Category", fallback="No Category")
                start_exe = app_config.get("Control", "Start", fallback=None)
                version = app_config.get("Version", "DisplayVersion", fallback="")
                description = app_config.get("Details", "Description", fallback="")

                if start_exe:
                    exe_path = os.path.join(entry.path, start_exe)

                    # Icon Logic
                    icon_path = None
                    ico_file = os.path.join(entry.path, "App", "AppInfo", "appicon.ico")
                    if os.path.exists(ico_file):
                        icon_path = ico_file
                    else:
                        icon_path = exe_path

                    potential_apps.append((name, exe_path, icon_path, version, description, category))
            except Exception:
                pass
        else:
            try:
                for file in os.scandir(entry.path):
                    if file.is_file() and file.name.lower().endswith(".exe"):
                        name = os.path.splitext(file.name)[0]
                        name = name.replace("Portable", "").replace("  ", " ").strip()
                        potential_apps.append((name, file.path, file.path, "", "", "No Category"))
            except Exception:
                pass

        for name, exe_path, icon_path, version, description, default_cat in potential_apps:
            is_fav = False
            is_hidden = False
            category = default_cat

            key = _get_app_key(exe_path)

            if settings_config.has_option("Renames", key):
                name = settings_config.get("Renames", key)
            if settings_config.has_option("Categories", key):
                category = settings_config.get("Categories", key)
            if settings_config.has_option("Favorites", key):
                is_fav = settings_config.getboolean("Favorites", key, fallback=False)
            if settings_config.has_option("Hidden", key):
                is_hidden = settings_config.getboolean("Hidden", key, fallback=False)

            category = resolve_category_name(category, allowed_categories)

            if is_hidden and not show_hidden:
                continue

            apps.append({
                "name": name,
                "exe": exe_path,
                "icon": icon_path,
                "is_favorite": is_fav,
                "is_hidden": is_hidden,
                "category": category,
                "version": version,
                "description": description
            })

    return sorted(apps, key=lambda x: (not x["is_favorite"], x["name"].lower()))


class AppScanWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, base_dir, show_hidden):
        super().__init__()
        self.base_dir = base_dir
        self.show_hidden = bool(show_hidden)

    def run(self):
        try:
            apps = _scan_portable_apps_on_disk(self.base_dir, self.show_hidden)
            self.finished.emit(apps)
        except Exception as e:
            self.error.emit(str(e))


class FixSettingsWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def run(self):
        try:
            result = fix_settings.fix_settings()
            if result is None:
                result = {"fixed": 0, "message": "Fix settings completed.", "changed": False}
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class UpdateCheckWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, repo):
        super().__init__()
        self.repo = repo

    def run(self):
        try:
            result = update_checker.get_latest_github_release(self.repo)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

# -----------------------------------------------------------------------------
# GUI Scale (read before QApplication)
# -----------------------------------------------------------------------------

def read_gui_scale_setting():
    try:
        config = configparser.ConfigParser()
        config.optionxform = str
        path = get_settings_path()
        config.read(path)
        return config.get("Settings", "GuiScale", fallback="1.0")
    except Exception:
        return "1.0"

# -----------------------------------------------------------------------------
# Hotkey Filter (for WM_HOTKEY when registered on thread queue)
# -----------------------------------------------------------------------------

class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312:
                if msg.wParam == self.window.hotkey_id:
                    self.window.toggle_app_visibility()
                    # Re-register after each trigger to avoid Windows dropping the hotkey
                    QTimer.singleShot(200, self.window.register_global_hotkey)
                    return True, 0
                if msg.wParam == self.window.mini_hotkey_id:
                    self.window.show_tray_menu_from_hotkey()
                    QTimer.singleShot(200, self.window.register_global_hotkey)
                    return True, 0
        return False, 0

# -----------------------------------------------------------------------------
# Main Window
# -----------------------------------------------------------------------------

class LauncherWindow(QMainWindow):
    CATEGORIES = list(BASE_CATEGORIES)

    def __init__(self):
        super().__init__()
        
        # Settings
        self.settings = self.load_settings_dict()
        self._refresh_category_list()

        # Window Setup
        self.show_in_taskbar = self.settings.get("show_in_taskbar", False)
        self.confirm_launch = self.settings.get("confirm_launch", False)
        self.confirm_web = self.settings.get("confirm_web", False)
        self.confirm_exit = self.settings.get("confirm_exit", True)
        self.require_app_password = self.settings.get("require_app_password", False)
        self.require_settings_password = self.settings.get("require_settings_password", False)
        self.protected_apps = self.settings.get("protected_apps", [])
        self.password_salt = self.settings.get("password_salt", "")
        self.password_hash = self.settings.get("password_hash", "")
        self.trusted_devices = self.settings.get("trusted_devices", [])
        self.app_session_unlock = self.settings.get("app_session_unlock", False)
        self.app_session_unlock = self.settings.get("app_session_unlock", False)
        self._app_unlocked_session = False
        base_flags = Qt.FramelessWindowHint | Qt.WindowSystemMenuHint
        if not self.show_in_taskbar:
            base_flags |= Qt.Tool  # keep the window out of the taskbar (tray-only)
        self.setWindowFlags(base_flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.show_hidden = self.settings.get("show_hidden", False)
        self.expand_default = self.settings.get("expand_default", False)
        self.accordion_mode = self.settings.get("accordion", False)
        self.fade_enabled = self.settings.get("fade", True)
        self.menu_key = self.settings.get("menu_key", "Ctrl+R")
        self.mini_key = self.settings.get("mini_key", "Ctrl+E")
        self.gui_scale = self.settings.get("gui_scale", "1.0")
        self.collapse_on_minimize = self.settings.get("collapse_on_minimize", True)
        self.remember_last_screen = self.settings.get("remember_last_screen", False)
        self._favorites_only = False
        self.home_show_documents = self.settings.get("home_show_documents", True)
        self.home_show_music = self.settings.get("home_show_music", True)
        self.home_show_pictures = self.settings.get("home_show_pictures", True)
        self.home_show_videos = self.settings.get("home_show_videos", True)
        self.home_show_downloads = self.settings.get("home_show_downloads", True)
        self.home_show_explore = self.settings.get("home_show_explore", True)
        self.home_show_custom_folder = self.settings.get("home_show_custom_folder", False)
        self.home_custom_folder = self.settings.get("home_custom_folder", "")
        self.home_custom_label = self.settings.get("home_custom_label", "")
        self.home_custom_folders = self.settings.get("home_custom_folders", [])
        self.home_custom_folders = self.settings.get("home_custom_folders", [])
        self.mini_show_documents = self.settings.get("mini_show_documents", True)
        self.mini_show_music = self.settings.get("mini_show_music", True)
        self.mini_show_videos = self.settings.get("mini_show_videos", True)
        self.mini_show_downloads = self.settings.get("mini_show_downloads", True)
        self.mini_show_explore = self.settings.get("mini_show_explore", True)
        self.mini_show_settings = self.settings.get("mini_show_settings", True)
        self.mini_show_all_apps = self.settings.get("mini_show_all_apps", True)
        self.mini_show_favorites = self.settings.get("mini_show_favorites", True)
        self.mini_show_exit = self.settings.get("mini_show_exit", True)
        self.mini_show_icons = self.settings.get("mini_show_icons", True)
        self.mini_apply_to_tray = self.settings.get("mini_apply_to_tray", False)
        self.mini_pinned_apps = self.settings.get("mini_pinned_apps", [])
        self.search_descriptions = self.settings.get("search_descriptions", True)
        self.keep_visible_after_launch = self.settings.get("keep_visible_after_launch", True)
        self.start_minimized = self.settings.get("start_minimized", True)
        self.show_search_bar = self.settings.get("show_search_bar", False)
        self.show_in_taskbar = self.settings.get("show_in_taskbar", False)
        self.theme_mode = self.settings.get("theme_mode", "system")
        self.accent_color = self.settings.get("accent_color", "")
        self.text_color = self.settings.get("text_color", "")
        self.view_mode = self.settings.get("view_mode", "list")
        self.grid_columns = self.settings.get("grid_columns", "auto")
        self.background_type = self.settings.get("background_type", "theme")
        self.background_color = self.settings.get("background_color", "")
        self.background_gradient_start = self.settings.get("background_gradient_start", "")
        self.background_gradient_end = self.settings.get("background_gradient_end", "")
        self.background_image = self.settings.get("background_image", "")
        self.mini_menu_background_type = self.settings.get("mini_menu_background_type", "default")
        self.mini_menu_background_color = self.settings.get("mini_menu_background_color", "")
        self.mini_menu_background_gradient_start = self.settings.get("mini_menu_background_gradient_start", "")
        self.mini_menu_background_gradient_end = self.settings.get("mini_menu_background_gradient_end", "")
        self.mini_menu_scale = self.settings.get("mini_menu_scale", "1.0")
        self.mini_menu_text_color = self.settings.get("mini_menu_text_color", "")
        self.startup_apps = self.settings.get("startup_apps", [])
        self.browser_choice = self.settings.get("browser_choice", "system")
        self.browser_path = self.settings.get("browser_path", "")
        self.always_on_top = self.settings.get("always_on_top", False)
        self.window_x = self.settings.get("window_x", None)
        self.window_y = self.settings.get("window_y", None)

        # Position
        if self.window_x is not None and self.window_y is not None:
            self.apply_saved_position()
        else:
            self.center_on_screen()

        # Theme (must be set before building UI)
        self.apply_theme_mode(self.theme_mode)
        if self.accent_color:
            apply_accent_color(self.accent_color)
        if self.text_color:
            apply_text_color(self.text_color)

        # Apply window flags
        self.apply_always_on_top(self.always_on_top, initial=True)

        # Taskbar icon
        base_dir = get_base_dir()
        icon_path = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "profilepic", "taskbar.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Main Container (The visible card)
        self.container = QWidget(self)
        self.container.setGeometry(10, 10, WINDOW_WIDTH - 20, WINDOW_HEIGHT - 20)
        
        # Main Layout
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Stack for Main View vs Options
        self.main_stack = QStackedWidget()
        self.main_layout.addWidget(self.main_stack)
        
        # 2. Middle Section (Splitter: Apps | Quick Buttons)
        self.setup_middle_section()

        # Defer app loading until the window is visible
        self._refresh_pending = False
        self._initial_refresh_done = False
        self._cache_loaded = False
        self._last_scanned_apps = []
        self._apps_scan_completed = False
        
        # Visual Effects
        self.setup_effects()
        
        # Shortcut
        self.hotkey_id = 101
        self.mini_hotkey_id = 102
        self.winId()  # ensure native handle exists for hotkey registration
        self.register_global_hotkey()
        
        # System Tray
        self.setup_system_tray()
        
        # Fade animation handler
        self.fade_anim = None
        self.setWindowOpacity(1.0)

        # Animation state
        self._is_showing = False
        self._is_hiding = False
        self._target_rect = None

        # Rainbow text
        self._rainbow_timer = None
        self._rainbow_hue = 0
        if self.text_color == "__rainbow__":
            self._start_rainbow()


        # Position save debounce
        self._pos_save_timer = QTimer(self)
        self._pos_save_timer.setSingleShot(True)
        self._pos_save_timer.timeout.connect(self.flush_window_position)
        self._pending_pos = None

        # Hide to tray when app deactivates (some Windows focus changes don't fire on the window)
        app = QApplication.instance()
        if app:
            app.applicationStateChanged.connect(self._on_app_state_changed)

        self._tray_menu_open = False
        self._suppress_auto_hide = False
        self._app_locked = False
        self._force_notice = "--show-notice" in sys.argv or "--force-notice" in sys.argv
        self._notice_shown = False
        self._temp_topmost = False

        self._update_check_in_progress = False
        self._update_progress_dialog = None
        self._pending_update_url = ""
        self._pending_update_version = ""

        QTimer.singleShot(0, self.maybe_show_notice)
        QTimer.singleShot(2500, self.maybe_auto_check_updates)

    def _set_app_locked(self, locked):
        self._app_locked = locked
        if hasattr(self, "container") and self.container:
            self.container.setVisible(not locked)

    def _on_app_state_changed(self, state):
        if state != Qt.ApplicationActive:
            if self._tray_menu_open or self._suppress_auto_hide:
                return
            self._maybe_hide_on_deactivate()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def apply_saved_position(self):
        try:
            x = int(self.window_x)
            y = int(self.window_y)
        except Exception:
            self.center_on_screen()
            return

        window_rect = QRect(x, y, self.width(), self.height())
        for screen in QApplication.screens():
            if window_rect.intersects(screen.availableGeometry()):
                self.move(x, y)
                return

        # Fallback if offscreen
        self.center_on_screen()

    def setup_effects(self):
        pass

    def apply_always_on_top(self, enabled, initial=False):
        was_visible = self.isVisible()
        prev_geom = self.geometry()
        prev_state = self.windowState()

        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)

        if not initial and was_visible:
            try:
                self.setWindowState(prev_state & ~Qt.WindowMinimized)
            except Exception:
                pass
            self.show()
            self.showNormal()
            self.setGeometry(prev_geom)
            self.activateWindow()
            self.raise_()

    def get_system_theme_mode(self):
        palette = QApplication.palette()
        window_color = palette.color(QPalette.Window)
        return "dark" if window_color.lightness() < 128 else "light"

    def apply_theme_mode(self, mode):
        effective = self.get_system_theme_mode() if mode == "system" else mode
        apply_theme(effective)
        self.theme_mode = mode
        self.effective_theme = effective
        self.update_tray_icons()
        self.rebuild_tray_menu()
        self.update()

    def rebuild_main_view(self):
        while self.main_stack.count():
            widget = self.main_stack.widget(0)
            self.main_stack.removeWidget(widget)
            widget.deleteLater()
        self.setup_middle_section()

    def apply_search_bar_visibility(self):
        if hasattr(self, "search_container"):
            self.search_container.setVisible(self.show_search_bar)

    def _quick_button_visible(self, name):
        visibility = {
            "Documents": self.home_show_documents,
            "Music": self.home_show_music,
            "Pictures": self.home_show_pictures,
            "Videos": self.home_show_videos,
            "Downloads": self.home_show_downloads,
            "Explore": self.home_show_explore,
        }
        return visibility.get(name, True)

    def _build_quick_buttons(self):
        if not hasattr(self, "quick_buttons_layout"):
            return
        layout = self.quick_buttons_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.quick_buttons = []

        base_dir = get_base_dir()
        icon_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons")

        icon_map = {
            "Documents": "documents.png",
            "Music": "music.png",
            "Pictures": "pictures.png",
            "Videos": "videos.png",
            "Downloads": "download.png",
            "Explore": "explore.png",
            "Apps": "apps.png",
            "Settings": "options.png",
            "Search": "search.png",
            "Help": "help.png"
        }

        for btn_name in QUICK_BUTTONS:
            if not self._quick_button_visible(btn_name):
                continue
            if btn_name == "Search":
                line = QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet(f"background-color: {qcolor_to_rgba(COLOR_GLASS_BORDER)}; margin: 4px 5px;")
                layout.addWidget(line)

            icon_file = icon_map.get(btn_name, "")
            icon_path = os.path.join(icon_dir, icon_file)
            btn = QuickAccessButton(btn_name, icon_path)
            btn.setObjectName(btn_name)
            btn.clicked.connect(self.handle_quick_button)
            layout.addWidget(btn)
            self.quick_buttons.append(btn)

            if btn_name == "Explore":
                self._add_custom_folder_button(layout)

        layout.addStretch()

        # Close button at bottom-right
        self.close_btn = QPushButton("x")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.confirm_quit_app)
        close_color = COLOR_TEXT_MAIN.name() if self.effective_theme == "dark" else COLOR_TEXT_SUB.name()
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {close_color};
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
        layout.addWidget(self.close_btn, 0, Qt.AlignRight)

    def _add_custom_folder_button(self, layout):
        if not self.home_show_custom_folder:
            return
        folders = self.home_custom_folders or []
        if not folders and self.home_custom_folder:
            folders = [{"path": self.home_custom_folder, "label": self.home_custom_label}]
        if not folders:
            return
        seen = set()
        for entry in folders:
            if isinstance(entry, dict):
                path = entry.get("path", "")
                label = entry.get("label", "")
                enabled = entry.get("enabled", True)
            else:
                path = str(entry)
                label = ""
                enabled = True
            if not path:
                continue
            if not enabled:
                continue
            try:
                key = os.path.normpath(path).lower()
            except Exception:
                key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            if not os.path.exists(path):
                continue
            display = label or os.path.basename(path) or "Custom Folder"
            icon = self._get_folder_icon(path)
            btn = QuickAccessButton(display, icon)
            btn.setObjectName(f"CustomFolder:{display}")
            btn.clicked.connect(lambda _, p=path: self._open_custom_folder(p))
            layout.addWidget(btn)
            self.quick_buttons.append(btn)

    def _get_folder_icon(self, path):
        try:
            provider = QFileIconProvider()
            info = QFileInfo(path)
            return provider.icon(info)
        except Exception:
            return QIcon()

    def _open_custom_folder(self, path=None):
        target = path or self.home_custom_folder
        if target and os.path.exists(target):
            try:
                os.startfile(target)
                return
            except Exception:
                pass
        QMessageBox.information(self, "Custom Folder", "Custom folder path is missing or invalid.")

    def collapse_all_categories(self):
        for widget in self.app_widgets:
            if isinstance(widget, CategoryItem):
                widget.set_expanded(False)

    def paintEvent(self, event):
        # We paint the background on the container, but since container is a standard widget,
        # we can do it here relative to the container geometry or subclass container.
        # To keep it simple, we paint the main window background inside the container area.
        pass

    def setup_middle_section(self):
        middle_frame = QWidget()
        layout = QVBoxLayout(middle_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Main Panel (Combined) ---
        main_panel = GlassPanel(radius=6, opacity=0.05)

        # Use VBox for the panel to stack Search on top of Apps
        panel_layout = QVBoxLayout(main_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(10)

        # --- Search & Profile Section ---
        search_container = QWidget()
        search_container.setFixedHeight(48)  # controls the whole top row height

        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_layout.setSpacing(16)
        search_layout.setAlignment(Qt.AlignVCenter)

        self.search_bar = SearchBar()
        self.search_bar.setFixedHeight(32)    # slim search bar
        self.search_bar.textChanged.connect(self.filter_apps)

        self.profile_pic = ProfilePicture()
        self.profile_pic.setFixedSize(36, 36) # neat, consistent avatar size
        self.profile_pic_container = QWidget()
        pfp_layout = QVBoxLayout(self.profile_pic_container)
        pfp_layout.setContentsMargins(0, 0, 0, 2)
        pfp_layout.addWidget(self.profile_pic, 0, Qt.AlignTop)

        search_layout.addWidget(self.search_bar, 1)
        search_layout.addWidget(self.profile_pic_container, 0)

        self.search_container = search_container
        panel_layout.addWidget(search_container)
        self.apply_search_bar_visibility()

        
        # Separator
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {qcolor_to_rgba(COLOR_GLASS_BORDER)};")
        panel_layout.addWidget(line)

        # --- Content Section (Apps | Buttons) ---
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        self.app_list_container = QWidget()
        self.app_list_container.setStyleSheet("background: transparent;")
        self.app_list_layout = QVBoxLayout(self.app_list_container)
        self.app_list_layout.setContentsMargins(0, 0, 0, 0)
        self.app_list_layout.setSpacing(1)
        # List header (Back button shown when returning from grid "All >")
        self.app_list_header = QWidget()
        header_layout = QHBoxLayout(self.app_list_header)
        header_layout.setContentsMargins(6, 2, 6, 2)
        header_layout.addStretch()
        self.app_list_back_btn = QPushButton("Back")
        self.app_list_back_btn.setCursor(Qt.PointingHandCursor)
        self.app_list_back_btn.setFixedHeight(22)
        self.app_list_back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_TEXT_SUB.name()};
                border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                border-radius: 6px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_MAIN.name()};
                border-color: {COLOR_ACCENT.name()};
            }}
        """)
        self.app_list_back_btn.clicked.connect(self.show_grid_view_from_list)
        header_layout.addWidget(self.app_list_back_btn)
        self.app_list_header.hide()
        self.app_list_layout.addWidget(self.app_list_header)
        # Loading indicator (kept at top of the list)
        self.loading_container = QWidget()
        loading_layout = QVBoxLayout(self.loading_container)
        loading_layout.setContentsMargins(6, 6, 6, 6)
        loading_layout.setSpacing(6)
        loading_label = QLabel("Loading apps...")
        loading_label.setStyleSheet(f"color: {qcolor_to_rgba(COLOR_TEXT_SUB)};")
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
        loading_layout.addWidget(loading_label)
        loading_layout.addWidget(self.loading_bar)
        self.app_list_layout.addWidget(self.loading_container)
        self.loading_container.setVisible(False)
        self.app_list_layout.addStretch() # Bottom spacer

        # Grid container (used for grid view)
        self.app_grid_container = QWidget()
        self.app_grid_container.setStyleSheet("background: transparent;")
        self.app_grid_container.hide()

        grid_container_layout = QVBoxLayout(self.app_grid_container)
        grid_container_layout.setContentsMargins(6, 6, 6, 6)
        grid_container_layout.setSpacing(6)

        self.app_grid_header = QWidget()
        header_layout = QHBoxLayout(self.app_grid_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addStretch()

        self.app_grid_all_btn = QPushButton("All >")
        self.app_grid_all_btn.setCursor(Qt.PointingHandCursor)
        self.app_grid_all_btn.setFixedHeight(22)
        self.app_grid_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_TEXT_SUB.name()};
                border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                border-radius: 6px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_MAIN.name()};
                border-color: {COLOR_ACCENT.name()};
            }}
        """)
        self.app_grid_all_btn.clicked.connect(self.show_all_apps_list_view)
        header_layout.addWidget(self.app_grid_all_btn)

        self.app_grid_grid = QWidget()
        self.app_grid_layout = QGridLayout(self.app_grid_grid)
        self.app_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.app_grid_layout.setSpacing(8)
        self.app_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.app_grid_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        grid_container_layout.addWidget(self.app_grid_header)
        grid_container_layout.addWidget(self.app_grid_grid)

        self.app_list_layout.insertWidget(self.app_list_layout.count() - 1, self.app_grid_container)
        
        # Populate Apps
        self.app_widgets = []

        # Scroll Area for Apps
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.app_list_container)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
        """)
        
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.scroll)
        
        content_layout.addWidget(self.content_stack, 17)
        
        # --- Separator ---
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet(f"background-color: {qcolor_to_rgba(COLOR_GLASS_BORDER)}; margin: 5px 0px;")
        content_layout.addWidget(separator)
        
        # --- Right Side: Quick Buttons ---
        buttons_container = QWidget()
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(2)
        self.quick_buttons_layout = buttons_layout
        self.quick_buttons_container = buttons_container
        self._build_quick_buttons()

        content_layout.addWidget(buttons_container, 3)
        
        panel_layout.addWidget(content_container, 1)
        
        layout.addWidget(main_panel)
        
        self.main_stack.addWidget(middle_frame)

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # Try to set an icon
        base_dir = get_base_dir()
        icon_path = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons", "icon.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
            
        self.tray_icon.setToolTip("Portable Apps Launcher")
        
        self.rebuild_tray_menu()
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.messageClicked.connect(self._on_tray_message_clicked)
        self.tray_icon.show()

    def _tray_exit_color(self):
        return QColor("#e6e6e6") if self.effective_theme == "dark" else QColor(COLOR_TEXT_SUB)

    def _build_exit_icon(self, color, size=16, thickness=2):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        margin = 3
        painter.drawLine(margin, margin, size - margin, size - margin)
        painter.drawLine(size - margin, margin, margin, size - margin)
        painter.end()
        return QIcon(pix)

    def update_tray_icons(self):
        if hasattr(self, "quit_action") and self.quit_action:
            self.quit_action.setIcon(self._build_exit_icon(self._tray_exit_color()))

    def _add_tray_app_action(self, menu, app):
        icon_path = app.get("icon", "")
        if (not icon_path or not os.path.exists(icon_path)) and app.get("exe"):
            icon_path = app.get("exe")
        icon = QIcon(icon_path) if icon_path and os.path.exists(icon_path) else QIcon()
        action = menu.addAction(icon, app["name"])
        action.triggered.connect(lambda _=False, p=app["exe"]: self.launch_app(p))

    def _populate_favorites_menu(self, menu):
        menu.clear()
        apps = self._get_apps_snapshot()
        if not apps:
            if not getattr(self, "_apps_scan_completed", False):
                if not getattr(self, "_refresh_pending", False):
                    try:
                        self.refresh_apps()
                    except Exception:
                        pass
                empty = menu.addAction("Loading apps...")
            else:
                empty = menu.addAction("No apps found")
            empty.setEnabled(False)
            return
        apps = [a for a in apps if a.get("is_favorite")]
        if not apps:
            empty = menu.addAction("No favorites yet")
            empty.setEnabled(False)
            return
        for app in apps:
            self._add_tray_app_action(menu, app)

    def _populate_all_apps_menu(self, menu):
        menu.clear()
        apps = self._get_apps_snapshot()
        if not apps:
            if not getattr(self, "_apps_scan_completed", False):
                if not getattr(self, "_refresh_pending", False):
                    try:
                        self.refresh_apps()
                    except Exception:
                        pass
                empty = menu.addAction("Loading apps...")
            else:
                empty = menu.addAction("No apps found")
            empty.setEnabled(False)
            return

        grouped = {}
        for app in apps:
            cat = app.get("category", "No Category") or "No Category"
            grouped.setdefault(cat, []).append(app)

        for cat in self.CATEGORIES:
            if cat not in grouped:
                continue
            cat_menu = QMenu(cat, menu)
            for app in grouped[cat]:
                self._add_tray_app_action(cat_menu, app)
            action = menu.addMenu(cat_menu)
            icon_path = get_category_icon_path(cat)
            if icon_path and os.path.exists(icon_path):
                action.setIcon(QIcon(icon_path))

    def _populate_tray_favorites_menu(self):
        if not hasattr(self, "tray_favorites_menu"):
            return
        self._populate_favorites_menu(self.tray_favorites_menu)

    def _populate_tray_all_apps_menu(self):
        if not hasattr(self, "tray_all_apps_menu"):
            return
        self._populate_all_apps_menu(self.tray_all_apps_menu)

    def _get_mini_menu_config(self):
        return {
            "show_documents": self.mini_show_documents,
            "show_music": self.mini_show_music,
            "show_videos": self.mini_show_videos,
            "show_downloads": self.mini_show_downloads,
            "show_explore": self.mini_show_explore,
            "show_settings": self.mini_show_settings,
            "show_all_apps": self.mini_show_all_apps,
            "show_favorites": self.mini_show_favorites,
            "show_exit": self.mini_show_exit,
            "show_icons": self.mini_show_icons,
        }

    def _build_custom_menu(self, menu, config, use_icons=True, force_default=False):
        icon_dir = os.path.join(get_base_dir(), "PortableApps", "PortableX", "Graphics", "sidebaricons")
        self._apply_mini_menu_style(menu, force_default=force_default)
        self._apply_mini_menu_scale(menu)

        def _icon(name):
            if not use_icons:
                return QIcon()
            path = os.path.join(icon_dir, name)
            return QIcon(path) if os.path.exists(path) else QIcon()

        def _add_action(label, icon_file, handler):
            action = menu.addAction(_icon(icon_file), label) if use_icons else menu.addAction(label)
            action.triggered.connect(handler)
            return action

        has_top = False
        if config.get("show_documents", True):
            _add_action("Documents", "documents.png", lambda: self.handle_quick_button("Documents"))
            has_top = True
        if config.get("show_music", True):
            _add_action("Music", "music.png", lambda: self.handle_quick_button("Music"))
            has_top = True
        if config.get("show_videos", True):
            _add_action("Videos", "videos.png", lambda: self.handle_quick_button("Videos"))
            has_top = True
        if config.get("show_downloads", True):
            _add_action("Downloads", "download.png", lambda: self.handle_quick_button("Downloads"))
            has_top = True
        if config.get("show_explore", True):
            _add_action("Explore", "explore.png", lambda: self.handle_quick_button("Explore"))
            has_top = True
        if config.get("show_settings", True):
            _add_action("Settings", "options.png", lambda: self.open_settings_from_menu())
            has_top = True

        if has_top and (config.get("show_all_apps", True) or config.get("show_favorites", True)):
            menu.addSeparator()

        pinned_apps = self._get_pinned_apps()
        if pinned_apps:
            for app in pinned_apps:
                if use_icons and app.get("icon"):
                    icon = QIcon(app["icon"])
                    action = menu.addAction(icon, app["name"])
                else:
                    action = menu.addAction(app["name"])
                action.triggered.connect(lambda _=False, p=app["exe"]: self.launch_app(p))
            menu.addSeparator()

        if config.get("show_all_apps", True):
            all_menu = QMenu("All Apps", menu)
            self._apply_mini_menu_scale(all_menu)
            all_menu.aboutToShow.connect(lambda m=all_menu: self._populate_all_apps_menu(m))
            menu.addMenu(all_menu).setIcon(_icon("apps.png"))

        if config.get("show_favorites", True):
            fav_menu = QMenu("Favorites", menu)
            self._apply_mini_menu_scale(fav_menu)
            fav_menu.aboutToShow.connect(lambda m=fav_menu: self._populate_favorites_menu(m))
            menu.addMenu(fav_menu).setIcon(_icon("favourites.png"))

        if config.get("show_exit", True):
            menu.addSeparator()
            self.quit_action = menu.addAction(self._build_exit_icon(self._tray_exit_color()), "Exit")
            self.quit_action.triggered.connect(self.confirm_quit_app)

    def _apply_mini_menu_style(self, menu, force_default=False):
        if (self.mini_menu_background_type == "solid" and self.mini_menu_background_color) and not force_default:
            if self.mini_menu_text_color == "__rainbow__":
                text_color = self._current_rainbow_color().name()
            else:
                text_color = self.mini_menu_text_color or ("#101318" if QColor(self.mini_menu_background_color).lightness() >= 128 else "#ffffff")
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {self.mini_menu_background_color};
                    border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                    border-radius: 8px;
                    padding: 4px;
                    color: {text_color};
                }}
                QMenu::item {{
                    color: {text_color};
                    padding: 6px 20px;
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)
        elif (self.mini_menu_background_type == "gradient" and self.mini_menu_background_gradient_start and self.mini_menu_background_gradient_end) and not force_default:
            avg = QColor(self.mini_menu_background_gradient_start)
            avg2 = QColor(self.mini_menu_background_gradient_end)
            if self.mini_menu_text_color == "__rainbow__":
                text_color = self._current_rainbow_color().name()
            else:
                text_color = self.mini_menu_text_color or ("#101318" if (avg.lightness() + avg2.lightness()) / 2 >= 128 else "#ffffff")
            menu.setStyleSheet(f"""
                QMenu {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {self.mini_menu_background_gradient_start}, stop:1 {self.mini_menu_background_gradient_end});
                    border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                    border-radius: 8px;
                    padding: 4px;
                    color: {text_color};
                }}
                QMenu::item {{
                    color: {text_color};
                    padding: 6px 20px;
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)
        else:
            default_bg = "#060606" if self.effective_theme == "dark" else "#FDFDFD"
            if self.mini_menu_text_color == "__rainbow__":
                text_color = self._current_rainbow_color().name()
            else:
                text_color = self.mini_menu_text_color or ("#ffffff" if self.effective_theme == "dark" else "#101318")
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {default_bg};
                    border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                    border-radius: 8px;
                    padding: 4px;
                    color: {text_color};
                }}
                QMenu::item {{
                    color: {text_color};
                    padding: 6px 20px;
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)

    def _apply_mini_menu_scale(self, menu):
        try:
            scale = float(self.mini_menu_scale or "1.0")
        except Exception:
            scale = 1.0
        if abs(scale - 1.0) < 0.001:
            return
        font = menu.font()
        base = font.pointSizeF()
        if base <= 0:
            base = 9.0
        font.setPointSizeF(base * scale)
        menu.setFont(font)

    def _current_rainbow_color(self):
        hue = int((time.time() * 60) % 360)
        return QColor.fromHsv(hue, 255, 255)

    def _start_rainbow(self):
        if self._rainbow_timer is None:
            self._rainbow_timer = QTimer(self)
            self._rainbow_timer.timeout.connect(self._tick_rainbow)
        if not self._rainbow_timer.isActive():
            self._rainbow_timer.start(120)
        self._tick_rainbow()

    def _stop_rainbow(self):
        if self._rainbow_timer and self._rainbow_timer.isActive():
            self._rainbow_timer.stop()

    def _tick_rainbow(self):
        color = self._current_rainbow_color()
        COLOR_TEXT_MAIN.setRgb(color.red(), color.green(), color.blue(), color.alpha())
        COLOR_TEXT_SUB.setRgb(color.red(), color.green(), color.blue(), 160)
        self._apply_text_color_to_widgets(color.name())

    def _apply_text_color_to_widgets(self, color_hex):
        for item in getattr(self, "app_widgets", []):
            if isinstance(item, CategoryItem):
                header = getattr(item, "header", None)
                if header and hasattr(header, "text_label"):
                    header.text_label.setStyleSheet(f"color: {color_hex}; background: transparent;")
                if header and hasattr(header, "arrow_label"):
                    header.arrow_label.setStyleSheet(f"color: {color_hex}; background: transparent;")
                for child in getattr(item, "app_items", []):
                    if hasattr(child, "text_label"):
                        child.text_label.setStyleSheet(f"color: {color_hex}; background: transparent;")
            else:
                if hasattr(item, "text_label"):
                    item.text_label.setStyleSheet(f"color: {color_hex}; background: transparent;")
        for btn in getattr(self, "quick_buttons", []):
            if hasattr(btn, "label"):
                btn.label.setStyleSheet(f"color: {color_hex}; background: transparent;")
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.apply_rainbow_text(color_hex)
            except Exception:
                pass
        if hasattr(self, "close_btn") and self.close_btn:
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
        if hasattr(self, "search_bar") and self.search_bar:
            try:
                self.search_bar.input.setStyleSheet(f"""
                    QLineEdit {{
                        background: transparent;
                        border: none;
                        color: {color_hex};
                        selection-background-color: {COLOR_ACCENT.name()};
                    }}
                """)
                if hasattr(self.search_bar, "icon_lbl"):
                    if hasattr(self.search_bar.icon_lbl, "set_color"):
                        self.search_bar.icon_lbl.set_color(QColor(color_hex))
                    else:
                        self.search_bar.icon_lbl.update()
            except Exception:
                pass
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                if hasattr(self.options_panel, "search_bar"):
                    self.options_panel.search_bar.input.setStyleSheet(f"""
                        QLineEdit {{
                            background: transparent;
                            border: none;
                            color: {color_hex};
                            selection-background-color: {COLOR_ACCENT.name()};
                        }}
                    """)
                    if hasattr(self.options_panel.search_bar, "icon_lbl"):
                        if hasattr(self.options_panel.search_bar.icon_lbl, "set_color"):
                            self.options_panel.search_bar.icon_lbl.set_color(QColor(color_hex))
                        else:
                            self.options_panel.search_bar.icon_lbl.update()
                if hasattr(self.options_panel, "btn_keybind"):
                    self.options_panel.btn_keybind.setStyleSheet(self.options_panel.get_button_style(font_size=12).replace(COLOR_TEXT_MAIN.name(), color_hex))
                for combo in self.options_panel.findChildren(QComboBox):
                    if hasattr(combo, "set_rainbow_text_color"):
                        combo.set_rainbow_text_color(color_hex)
            except Exception:
                pass

    def rebuild_tray_menu(self):
        if not hasattr(self, "tray_icon") or not self.tray_icon:
            return
        tray_menu = QMenu()
        if self.mini_apply_to_tray:
            config = self._get_mini_menu_config()
            self._build_custom_menu(tray_menu, config, use_icons=self.mini_show_icons)
        else:
            config = {
                "show_documents": True,
                "show_music": True,
                "show_videos": True,
                "show_explore": True,
                "show_settings": True,
                "show_all_apps": True,
                "show_favorites": True,
                "show_exit": True,
            }
            self._build_custom_menu(tray_menu, config, use_icons=True, force_default=True)

        tray_menu.aboutToHide.connect(self._on_tray_menu_closed)
        self.tray_icon.setContextMenu(tray_menu)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_app_visibility()

    def show_tray_menu_from_hotkey(self):
        if not hasattr(self, "tray_icon") or not self.tray_icon:
            return
        if self._tray_menu_open:
            if hasattr(self, "_mini_menu_instance") and self._mini_menu_instance:
                self._mini_menu_instance.close()
            self._tray_menu_open = False
        self._tray_menu_open = True
        self._suppress_auto_hide = True
        if self.isVisible():
            self.hide()
            QTimer.singleShot(50, self._open_tray_menu_at_cursor)
            return
        self._open_tray_menu_at_cursor()

    def _open_tray_menu_at_cursor(self):
        if hasattr(self, "_mini_menu_instance") and self._mini_menu_instance:
            try:
                self._mini_menu_instance.close()
            except Exception:
                pass
        menu = QMenu()
        config = self._get_mini_menu_config()
        self._build_custom_menu(menu, config, use_icons=self.mini_show_icons)
        menu.aboutToHide.connect(self._on_tray_menu_closed)
        self._mini_menu_instance = menu
        menu.exec(QCursor.pos())

    def _on_tray_menu_closed(self):
        self._tray_menu_open = False
        self._suppress_auto_hide = False

    def _close_tray_menu(self):
        if not hasattr(self, "tray_icon") or not self.tray_icon:
            return
        menu = self.tray_icon.contextMenu()
        if menu and menu.isVisible():
            menu.close()
        self._tray_menu_open = False

    def toggle_app_visibility(self):
        # Prevent rapid toggles from breaking animations
        if self._is_hiding or self._is_showing:
            return
        self._maybe_reset_home_state()
        self._close_tray_menu()
        if hasattr(self, "_mini_menu_instance") and self._mini_menu_instance:
            try:
                self._mini_menu_instance.close()
            except Exception:
                pass
        if self.isVisible():
            # If visible but not focused, bring it forward instead of hiding
            if not self.isActiveWindow():
                self.activateWindow()
                self.raise_()
                return
            self._maybe_reset_home_state()
            if self.collapse_on_minimize:
                self.collapse_all_categories()
            self.animate_hide()
        else:
            self._maybe_reset_home_state()
            self.animate_show()

    def animate_show(self):
        if self.require_app_password and self._password_is_set():
            if self._is_trusted_device():
                self._set_app_locked(False)
            elif self.app_session_unlock and self._app_unlocked_session:
                self._set_app_locked(False)
            else:
                self._set_app_locked(True)
                ok, remember = self._prompt_password_with_trust("Unlock", "Enter password to open the app:")
                if not ok:
                    try:
                        self.hide()
                    except Exception:
                        pass
                    self._is_showing = False
                    return
                self._set_app_locked(False)
                if remember:
                    self._remember_trusted_device()
                if self.app_session_unlock:
                    self._app_unlocked_session = True
        else:
            self._set_app_locked(False)
        if self.fade_anim:
            self.fade_anim.stop()
            self.fade_anim = None
        self._is_showing = True

        screen = self.screen().availableGeometry()
        snap_margin = 20
        target_rect = self.geometry()
        if hasattr(self, "_last_visible_rect") and self._last_visible_rect:
            target_rect = QRect(self._last_visible_rect)
        self._target_rect = QRect(target_rect)

        is_bottom_snap = abs((target_rect.y() + target_rect.height() - 10) - screen.bottom()) < snap_margin

        if is_bottom_snap:
            end_y = target_rect.y()
            start_y = screen.bottom() + self.height() + 20
            start_rect = QRect(target_rect.x(), start_y, target_rect.width(), target_rect.height())
            end_rect = QRect(target_rect.x(), end_y, target_rect.width(), target_rect.height())
            self.setGeometry(start_rect)

            self.show()
            self.activateWindow()
            self.raise_()

            anim_group = QParallelAnimationGroup(self)
            geo_anim = QPropertyAnimation(self, b"geometry", self)
            geo_anim.setDuration(360)
            geo_anim.setStartValue(start_rect)
            geo_anim.setEndValue(end_rect)
            geo_anim.setEasingCurve(QEasingCurve.OutCubic)
            anim_group.addAnimation(geo_anim)

            if self.fade_enabled:
                self.setWindowOpacity(0.0)
                fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
                fade_anim.setDuration(360)
                fade_anim.setStartValue(0.0)
                fade_anim.setEndValue(1.0)
                fade_anim.setEasingCurve(QEasingCurve.OutCubic)
                anim_group.addAnimation(fade_anim)
            else:
                self.setWindowOpacity(1.0)

            self.fade_anim = anim_group
            anim_group.finished.connect(lambda: self._finish_show())
            anim_group.start()
        else:
            self.show()
            self.activateWindow()
            self.raise_()
            # Restore last visible position when not bottom-snapped
            if hasattr(self, "_last_visible_rect") and self._last_visible_rect:
                self.setGeometry(self._last_visible_rect)
            if self.fade_enabled:
                self.setWindowOpacity(0.0)
                self.fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
                self.fade_anim.setDuration(260)
                self.fade_anim.setStartValue(0.0)
                self.fade_anim.setEndValue(1.0)
                self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
                self.fade_anim.finished.connect(lambda: self._finish_show())
                self.fade_anim.start()
            else:
                self.setWindowOpacity(1.0)
                self._finish_show()

    def animate_hide(self):
        if self.fade_anim:
            self.fade_anim.stop()
            self.fade_anim = None
        self._is_hiding = True

        screen = self.screen().availableGeometry()
        snap_margin = 20
        is_bottom_snap = abs((self.y() + self.height() - 10) - screen.bottom()) < snap_margin
        # Remember last visible position for restore
        if self._is_showing and self._target_rect:
            self._last_visible_rect = QRect(self._target_rect)
        else:
            self._last_visible_rect = QRect(self.geometry())

        if is_bottom_snap:
            start_rect = QRect(self.x(), self.y(), self.width(), self.height())
            end_y = screen.bottom() + self.height() + 20
            end_rect = QRect(self.x(), end_y, self.width(), self.height())

            anim_group = QParallelAnimationGroup(self)
            geo_anim = QPropertyAnimation(self, b"geometry", self)
            geo_anim.setDuration(360)
            geo_anim.setStartValue(start_rect)
            geo_anim.setEndValue(end_rect)
            geo_anim.setEasingCurve(QEasingCurve.OutCubic)
            anim_group.addAnimation(geo_anim)

            if self.fade_enabled:
                fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
                fade_anim.setDuration(360)
                fade_anim.setStartValue(self.windowOpacity())
                fade_anim.setEndValue(0.0)
                fade_anim.setEasingCurve(QEasingCurve.OutCubic)
                anim_group.addAnimation(fade_anim)

            def _hide():
                self.hide()
                if self.fade_enabled:
                    self.setWindowOpacity(1.0)
                self._finish_hide()

            anim_group.finished.connect(_hide)
            self.fade_anim = anim_group
            anim_group.start()
        else:
            if self.fade_enabled:
                self.fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
                self.fade_anim.setDuration(260)
                self.fade_anim.setStartValue(self.windowOpacity())
                self.fade_anim.setEndValue(0.0)
                self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)
                def _hide_simple():
                    self.hide()
                    self.setWindowOpacity(1.0)
                    self._finish_hide()
                self.fade_anim.finished.connect(_hide_simple)
                self.fade_anim.start()
            else:
                self.hide()
                self._finish_hide()

    def _finish_show(self):
        self._is_showing = False
        self._target_rect = None

    def _finish_hide(self):
        self._is_hiding = False

    def confirm_quit_app(self):
        if self._show_quit_confirmation():
            self.quit_app()

    def _show_quit_confirmation(self):
        if not self.confirm_exit:
            return True
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Exit Portable Apps Launcher")
        msg.setText("Close the app?")
        msg.setInformativeText("The app will keep running in the system tray unless you exit.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        return msg.exec() == QMessageBox.Yes


    def quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()

    def restart_app(self):
        try:
            if getattr(sys, "frozen", False):
                args = [sys.executable] + sys.argv[1:]
            else:
                script = os.path.abspath(sys.argv[0])
                args = [sys.executable, script] + sys.argv[1:]
            subprocess.Popen(args, cwd=os.getcwd())
        finally:
            self.quit_app()

    def register_global_hotkey(self):
        if os.name == 'nt':
            user32 = ctypes.windll.user32
            # Unregister previous hotkey to avoid conflicts
            user32.UnregisterHotKey(0, self.hotkey_id)
            user32.UnregisterHotKey(0, self.mini_hotkey_id)
            
            def _parse_hotkey(key_str):
                parts = key_str.split('+')
                mods = 0
                vk = 0
                for part in parts:
                    part = part.strip()
                    if part == 'Ctrl': mods |= 0x0002
                    elif part == 'Shift': mods |= 0x0004
                    elif part == 'Alt': mods |= 0x0001
                    elif part == 'Meta': mods |= 0x0008
                    else:
                        if len(part) == 1:
                            vk = ord(part.upper())
                        elif part.startswith('F') and part[1:].isdigit():
                            vk = 0x70 + int(part[1:]) - 1
                        elif part == 'Space': vk = 0x20
                        elif part == 'Esc': vk = 0x1B
                        elif part == 'Tab': vk = 0x09
                return mods, vk

            mods, vk = _parse_hotkey(self.menu_key)
            if vk != 0:
                # Register on thread queue so it works when window is hidden
                user32.RegisterHotKey(0, self.hotkey_id, mods, vk)

            mods, vk = _parse_hotkey(self.mini_key)
            if vk != 0:
                user32.RegisterHotKey(0, self.mini_hotkey_id, mods, vk)
        else:
            if not hasattr(self, 'options_shortcut'):
                self.options_shortcut = QShortcut(QKeySequence(self.menu_key), self)
                self.options_shortcut.activated.connect(self.toggle_app_visibility)
            else:
                self.options_shortcut.setKey(QKeySequence(self.menu_key))
            if not hasattr(self, 'mini_shortcut'):
                self.mini_shortcut = QShortcut(QKeySequence(self.mini_key), self)
                self.mini_shortcut.activated.connect(self.show_tray_menu_from_hotkey)
            else:
                self.mini_shortcut.setKey(QKeySequence(self.mini_key))

    def nativeEvent(self, eventType, message):
        # Hotkey handled via HotkeyFilter when registered on thread queue
        return super().nativeEvent(eventType, message)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_initial_refresh_done", False):
            self._initial_refresh_done = True
            # Let the UI become responsive first, then load apps.
            QTimer.singleShot(900, self.refresh_apps)

    def scan_portable_apps(self):
        apps = []
        base_dir = get_base_dir()
        apps_dir = os.path.join(base_dir, "PortableApps")
        
        if not os.path.exists(apps_dir):
            return []

        # Load Settings
        settings_config, _ = self.get_settings()
        allowed_categories = _build_allowed_categories(settings_config, BASE_CATEGORIES)
        
        for entry in os.scandir(apps_dir):
            if entry.is_dir():
                potential_apps = []
                ini_path = os.path.join(entry.path, "App", "AppInfo", "appinfo.ini")
                
                if os.path.exists(ini_path):
                    try:
                        app_config = configparser.ConfigParser()
                        app_config.read(ini_path)
                        
                        name = app_config.get("Details", "Name", fallback=entry.name)
                        name = name.replace("Portable", "").replace("  ", " ").strip()
                        category = app_config.get("Details", "Category", fallback="No Category")
                        start_exe = app_config.get("Control", "Start", fallback=None)
                        version = app_config.get("Version", "DisplayVersion", fallback="")
                        description = app_config.get("Details", "Description", fallback="")
                        
                        if start_exe:
                            exe_path = os.path.join(entry.path, start_exe)
                            
                            # Icon Logic
                            icon_path = None
                            # Priority 1: App/AppInfo/appicon.ico
                            ico_file = os.path.join(entry.path, "App", "AppInfo", "appicon.ico")
                            if os.path.exists(ico_file):
                                icon_path = ico_file
                            else:
                                # Priority 2: The executable itself (fallback)
                                icon_path = exe_path
                            
                            potential_apps.append((name, exe_path, icon_path, version, description, category))
                    except:
                        pass
                else:
                    # Fallback: Scan for .exe files
                    try:
                        for file in os.scandir(entry.path):
                            if file.is_file() and file.name.lower().endswith(".exe"):
                                name = os.path.splitext(file.name)[0]
                                name = name.replace("Portable", "").replace("  ", " ").strip()
                                potential_apps.append((name, file.path, file.path, "", "", "No Category"))
                    except:
                        pass

                for name, exe_path, icon_path, version, description, default_cat in potential_apps:
                    # Check Settings Overrides
                    is_fav = False
                    is_hidden = False
                    category = default_cat
                    
                    # Normalize path for config key
                    key = self.get_app_key(exe_path)
                    
                    if settings_config.has_option("Renames", key):
                        name = settings_config.get("Renames", key)
                    if settings_config.has_option("Categories", key):
                        category = settings_config.get("Categories", key)
                    if settings_config.has_option("Favorites", key):
                        is_fav = settings_config.getboolean("Favorites", key, fallback=False)
                    if settings_config.has_option("Hidden", key):
                        is_hidden = settings_config.getboolean("Hidden", key, fallback=False)

                    category = resolve_category_name(category, allowed_categories)
                        
                    if is_hidden and not self.show_hidden:
                        continue
                    
                    apps.append({
                        "name": name,
                        "exe": exe_path,
                        "icon": icon_path,
                        "is_favorite": is_fav,
                        "is_hidden": is_hidden,
                        "category": category,
                        "version": version,
                        "description": description
                    })
        # Sort: Favorites first, then Name
        return sorted(apps, key=lambda x: (not x["is_favorite"], x["name"].lower()))

    def _get_apps_cache_path(self):
        try:
            data_dir = get_data_dir()
        except Exception:
            data_dir = get_base_dir()
        return os.path.join(data_dir, "apps_cache.json")

    def _normalize_cache_path(self, path):
        if not path:
            return ""
        if not os.path.isabs(path):
            return path.replace("\\", "/")
        base_dir = get_base_dir()
        try:
            rel = os.path.relpath(path, base_dir)
        except ValueError:
            return path.replace("\\", "/")
        if rel.startswith(".."):
            return path.replace("\\", "/")
        return rel.replace("\\", "/")

    def _expand_cache_path(self, path):
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.normpath(os.path.join(get_base_dir(), path))

    def _load_apps_cache(self):
        cache_path = self._get_apps_cache_path()
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        apps = payload.get("apps")
        if not isinstance(apps, list):
            return None
        hydrated = []
        for item in apps:
            if not isinstance(item, dict):
                continue
            app = dict(item)
            app["exe"] = self._expand_cache_path(app.get("exe", ""))
            app["icon"] = self._expand_cache_path(app.get("icon", ""))
            hydrated.append(app)
        return hydrated

    def _write_apps_cache(self, apps):
        try:
            cache_path = self._get_apps_cache_path()
            payload = {
                "version": 1,
                "apps": [],
            }
            for app in apps or []:
                if not isinstance(app, dict):
                    continue
                payload["apps"].append({
                    "name": app.get("name", ""),
                    "exe": self._normalize_cache_path(app.get("exe", "")),
                    "icon": self._normalize_cache_path(app.get("icon", "")),
                    "is_favorite": bool(app.get("is_favorite")),
                    "is_hidden": bool(app.get("is_hidden")),
                    "category": app.get("category", ""),
                    "version": app.get("version", ""),
                    "description": app.get("description", ""),
                })
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass

    def _filter_apps_for_view(self, apps):
        if self.show_hidden:
            return apps
        return [a for a in apps if not a.get("is_hidden")]

    def _get_apps_snapshot(self):
        """
        Fast, non-blocking snapshot of apps for UI elements like tray menus.
        Prefers the last background scan, falls back to the on-disk cache.
        Never scans the PortableApps folder on the GUI thread.
        """
        apps = []
        try:
            apps = list(getattr(self, "_last_scanned_apps", []) or [])
        except Exception:
            apps = []
        if not apps:
            try:
                cached = self._load_apps_cache()
                if cached:
                    apps = cached
            except Exception:
                apps = []
        return self._filter_apps_for_view(apps)

    def load_settings_dict(self):
        config, _ = self.get_settings()
        raw_bg_image = config.get("Settings", "BackgroundImage", fallback="")
        home_custom_folder = config.get("Settings", "HomeCustomFolder", fallback="")
        home_custom_label = config.get("Settings", "HomeCustomLabel", fallback="")
        home_custom_folders = self._parse_custom_folders(
            config.get("Settings", "HomeCustomFolders", fallback="")
        )
        if not home_custom_folders and home_custom_folder:
            home_custom_folders = [{"path": home_custom_folder, "label": home_custom_label, "enabled": True}]

        updates_repo = config.get("Updates", "Repo", fallback="").strip() or DEFAULT_GITHUB_REPO
        updates_auto_check = config.getboolean("Updates", "AutoCheck", fallback=True)
        try:
            updates_interval_hours = float(
                config.get(
                    "Updates",
                    "IntervalHours",
                    fallback=str(DEFAULT_UPDATE_CHECK_INTERVAL_HOURS),
                )
            )
        except Exception:
            updates_interval_hours = float(DEFAULT_UPDATE_CHECK_INTERVAL_HOURS)
        try:
            updates_last_check_epoch = float(config.get("Updates", "LastCheckEpoch", fallback="0"))
        except Exception:
            updates_last_check_epoch = 0.0
        return {
            "show_hidden": config.getboolean("Settings", "ShowHidden", fallback=False),
            "expand_default": config.getboolean("Settings", "ExpandDefault", fallback=False),
            "accordion": config.getboolean("Settings", "Accordion", fallback=False),
            "fade": config.getboolean("Settings", "FadeAnimation", fallback=True),
            "menu_key": config.get("Settings", "MenuKey", fallback="Ctrl+R"),
            "mini_key": config.get("Settings", "MiniKey", fallback="Ctrl+E"),
            "gui_scale": config.get("Settings", "GuiScale", fallback="1.0"),
            "collapse_on_minimize": config.getboolean("Settings", "CollapseOnMinimize", fallback=True),
            "remember_last_screen": config.getboolean("Settings", "RememberLastScreen", fallback=False),
            "home_show_documents": config.getboolean("Settings", "HomeShowDocuments", fallback=True),
            "home_show_music": config.getboolean("Settings", "HomeShowMusic", fallback=True),
            "home_show_pictures": config.getboolean("Settings", "HomeShowPictures", fallback=True),
            "home_show_videos": config.getboolean("Settings", "HomeShowVideos", fallback=True),
            "home_show_downloads": config.getboolean("Settings", "HomeShowDownloads", fallback=True),
            "home_show_explore": config.getboolean("Settings", "HomeShowExplore", fallback=True),
            "home_show_custom_folder": config.getboolean("Settings", "HomeShowCustomFolder", fallback=False),
            "home_custom_folder": home_custom_folder,
            "home_custom_label": home_custom_label,
            "home_custom_folders": home_custom_folders,
            "mini_show_documents": config.getboolean("Settings", "MiniShowDocuments", fallback=True),
            "mini_show_music": config.getboolean("Settings", "MiniShowMusic", fallback=True),
            "mini_show_videos": config.getboolean("Settings", "MiniShowVideos", fallback=True),
            "mini_show_downloads": config.getboolean("Settings", "MiniShowDownloads", fallback=True),
            "mini_show_explore": config.getboolean("Settings", "MiniShowExplore", fallback=True),
            "mini_show_settings": config.getboolean("Settings", "MiniShowSettings", fallback=True),
            "mini_show_all_apps": config.getboolean("Settings", "MiniShowAllApps", fallback=True),
            "mini_show_favorites": config.getboolean("Settings", "MiniShowFavorites", fallback=True),
            "mini_show_exit": config.getboolean("Settings", "MiniShowExit", fallback=True),
            "mini_show_icons": config.getboolean("Settings", "MiniShowIcons", fallback=True),
            "mini_apply_to_tray": config.getboolean("Settings", "MiniApplyToTray", fallback=False),
            "mini_pinned_apps": self._parse_pinned_apps(config.get("Settings", "MiniPinnedApps", fallback="")),
            "search_descriptions": config.getboolean("Settings", "SearchDescriptions", fallback=True),
            "keep_visible_after_launch": config.getboolean("Settings", "KeepVisibleAfterLaunch", fallback=True),
            "start_minimized": config.getboolean("Settings", "StartMinimized", fallback=True),
            "show_search_bar": config.getboolean("Settings", "ShowSearchBar", fallback=False),
            "show_in_taskbar": config.getboolean("Settings", "ShowInTaskbar", fallback=False),
            "confirm_launch": config.getboolean("Settings", "ConfirmLaunch", fallback=False),
            "confirm_web": config.getboolean("Settings", "ConfirmWeb", fallback=False),
            "confirm_exit": config.getboolean("Settings", "ConfirmExit", fallback=True),
            "notice_accepted": config.getboolean("Settings", "NoticeAccepted", fallback=False),
            "require_app_password": config.getboolean("Security", "RequireAppPassword", fallback=False),
            "require_settings_password": config.getboolean("Security", "RequireSettingsPassword", fallback=False),
            "protected_apps": self._parse_pinned_apps(config.get("Security", "ProtectedApps", fallback="")),
            "password_salt": config.get("Security", "PasswordSalt", fallback=""),
            "password_hash": config.get("Security", "PasswordHash", fallback=""),
            "trusted_devices": self._parse_pinned_apps(config.get("Security", "TrustedDevices", fallback="")),
            "app_session_unlock": config.getboolean(
                "Security",
                "AppSessionUnlock",
                fallback=config.getboolean("Security", "SessionUnlock", fallback=False),
            ),
            "theme_mode": config.get("Settings", "ThemeMode", fallback="system"),
            "accent_color": config.get("Settings", "AccentColor", fallback=""),
            "text_color": config.get("Settings", "TextColor", fallback=""),
            "background_type": config.get("Settings", "BackgroundType", fallback="theme"),
            "background_color": config.get("Settings", "BackgroundColor", fallback=""),
            "background_gradient_start": config.get("Settings", "BackgroundGradientStart", fallback=""),
            "background_gradient_end": config.get("Settings", "BackgroundGradientEnd", fallback=""),
            "background_image": self._resolve_setting_path(raw_bg_image),
            "view_mode": config.get("Settings", "ViewMode", fallback="list"),
            "grid_columns": config.get("Settings", "GridColumns", fallback="auto"),
            "mini_menu_background_type": config.get("Settings", "MiniMenuBackgroundType", fallback="default"),
            "mini_menu_background_color": config.get("Settings", "MiniMenuBackgroundColor", fallback=""),
            "mini_menu_background_gradient_start": config.get("Settings", "MiniMenuBackgroundGradientStart", fallback=""),
            "mini_menu_background_gradient_end": config.get("Settings", "MiniMenuBackgroundGradientEnd", fallback=""),
            "mini_menu_scale": config.get("Settings", "MiniMenuScale", fallback="1.0"),
            "mini_menu_text_color": config.get("Settings", "MiniMenuTextColor", fallback=""),
            "startup_apps": self._parse_pinned_apps(config.get("Settings", "StartupApps", fallback="")),
            "browser_choice": config.get("Settings", "BrowserChoice", fallback="system"),
            "browser_path": config.get("Settings", "BrowserPath", fallback=""),
            "always_on_top": config.getboolean("Settings", "AlwaysOnTop", fallback=False),
            "window_x": config.get("Settings", "WindowX", fallback=None),
            "window_y": config.get("Settings", "WindowY", fallback=None),
            "updates_repo": updates_repo,
            "updates_auto_check": updates_auto_check,
            "updates_interval_hours": updates_interval_hours,
            "updates_last_check_epoch": updates_last_check_epoch,
        }

    def _refresh_category_list(self, settings_config=None):
        if settings_config is None:
            settings_config, _ = self.get_settings()
        self.CATEGORIES = _build_allowed_categories(settings_config, BASE_CATEGORIES)

    def _resolve_setting_path(self, value):
        if not value:
            return ""
        if os.path.isabs(value):
            return value
        return os.path.join(get_base_dir(), value)

    def _normalize_setting_path(self, value):
        if not value:
            return ""
        base_dir = get_base_dir()
        try:
            rel = os.path.relpath(value, base_dir)
            if not rel.startswith("..") and not os.path.isabs(rel):
                return rel.replace("\\", "/")
        except Exception:
            pass
        return value

    def _parse_pinned_apps(self, raw):
        if not raw:
            return []
        return [p for p in raw.split(";") if p]

    def _serialize_pinned_apps(self, items):
        return ";".join(items or [])

    def _normalize_custom_folders(self, items):
        if not items:
            return []
        seen = {}
        normalized = []
        for item in items:
            if isinstance(item, str):
                path = item
                label = ""
                enabled = True
            elif isinstance(item, dict):
                path = item.get("path", "")
                label = item.get("label", "")
                enabled = item.get("enabled", True)
            else:
                continue
            if not path:
                continue
            try:
                key = os.path.normpath(path).lower()
            except Exception:
                key = path.lower()
            if key in seen:
                existing = seen[key]
                if enabled and not existing.get("enabled", True):
                    existing["enabled"] = True
                if label and not existing.get("label"):
                    existing["label"] = label
                continue
            entry = {"path": path, "label": label, "enabled": bool(enabled)}
            seen[key] = entry
            normalized.append(entry)
        return normalized

    def _parse_custom_folders(self, raw):
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return self._normalize_custom_folders(data)
        except Exception:
            pass
        parts = [p.strip() for p in raw.split("|") if p.strip()]
        return self._normalize_custom_folders(parts)

    def refresh_apps(self):
        if getattr(self, "_refresh_pending", False):
            return
        self._refresh_pending = True
        self._set_loading(True)
        if not getattr(self, "_cache_loaded", False):
            self._cache_loaded = True
            cached = self._load_apps_cache()
            if cached:
                self._refresh_apps_from_scan(cached, keep_loading=True, keep_pending=True)
        self._start_app_scan()

    def _start_app_scan(self):
        try:
            if hasattr(self, "_scan_thread") and self._scan_thread and self._scan_thread.isRunning():
                return
        except Exception:
            pass
        try:
            self._scan_thread = QThread(self)
            self._scan_worker = AppScanWorker(get_base_dir(), True)
            self._scan_worker.moveToThread(self._scan_thread)
            self._scan_thread.started.connect(self._scan_worker.run)
            self._scan_worker.finished.connect(self._scan_thread.quit)
            self._scan_worker.error.connect(self._scan_thread.quit)
            self._scan_worker.finished.connect(self._scan_worker.deleteLater)
            self._scan_worker.error.connect(self._scan_worker.deleteLater)
            self._scan_thread.finished.connect(self._scan_thread.deleteLater)
            self._scan_worker.finished.connect(self._on_app_scan_finished)
            self._scan_worker.error.connect(self._on_app_scan_error)
            self._scan_thread.start()
        except Exception:
            # Fallback to synchronous scan if thread startup fails
            try:
                apps = _scan_portable_apps_on_disk(get_base_dir(), True)
            except Exception:
                apps = []
            try:
                self._last_scanned_apps = list(apps or [])
            except Exception:
                self._last_scanned_apps = []
            self._apps_scan_completed = True
            self._refresh_apps_from_scan(apps)

    def _on_app_scan_finished(self, apps):
        try:
            self._last_scanned_apps = list(apps or [])
        except Exception:
            self._last_scanned_apps = []
        self._apps_scan_completed = True
        self._write_apps_cache(apps)
        self._refresh_apps_from_scan(apps)
        try:
            if self.mini_pinned_apps:
                QTimer.singleShot(0, self.rebuild_tray_menu)
        except Exception:
            pass

    def _on_app_scan_error(self, error):
        try:
            print(f"Error scanning apps: {error}")
        except Exception:
            pass
        try:
            self._last_scanned_apps = []
        except Exception:
            pass
        self._apps_scan_completed = True
        self._refresh_apps_from_scan([])

    def _refresh_apps_from_scan(self, apps, keep_loading=False, keep_pending=False):
        build_token = getattr(self, "_build_token", 0) + 1
        self._build_token = build_token
        apps = self._filter_apps_for_view(apps or [])
        # Save expansion state
        self._favorites_separator = None
        expanded_categories = set()
        for widget in self.app_widgets:
            if isinstance(widget, CategoryItem) and widget.expanded:
                expanded_categories.add(widget.name)

        # Clear layout (except stretch at end)
        last_index = self.app_list_layout.count() - 1
        for i in range(last_index, -1, -1):
            item = self.app_list_layout.itemAt(i)
            if not item:
                continue
            w = item.widget()
            if w and w is self.loading_container:
                continue
            if w and w is getattr(self, "app_list_header", None):
                continue
            if w and w is getattr(self, "app_grid_container", None):
                continue
            if item.spacerItem() and i == last_index:
                continue
            item = self.app_list_layout.takeAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        
        self.app_widgets.clear()
        if hasattr(self, "app_grid_container") and self.app_grid_container:
            self.app_grid_container.setVisible(self.view_mode == "grid")
            while self.app_grid_layout.count():
                grid_item = self.app_grid_layout.takeAt(0)
                if grid_item and grid_item.widget():
                    grid_item.widget().deleteLater()
            if self.view_mode == "list":
                self.app_grid_container.hide()
        
        if self.view_mode == "grid":
            query = ""
            if hasattr(self, "search_bar") and self.search_bar:
                query = self.search_bar.input.text().strip()
            show_all = bool(query)
            self._grid_showing_all = show_all

            grid_apps = apps
            if not show_all:
                grid_apps = [a for a in apps if a.get("is_favorite")]

            viewport_w = 0
            if hasattr(self, "app_grid_grid") and self.app_grid_grid:
                viewport_w = self.app_grid_grid.width()
                if viewport_w > 0:
                    self.app_grid_grid.setMinimumWidth(viewport_w)
            if viewport_w <= 0 and hasattr(self, "scroll") and self.scroll:
                viewport_w = self.scroll.viewport().width()
            if viewport_w <= 0:
                viewport_w = self.app_list_container.width()
            spacing = 6
            cols = None
            try:
                raw_cols = str(self.grid_columns)
                digits = "".join([c for c in raw_cols if c.isdigit()])
                if digits:
                    cols = max(1, int(digits))
            except Exception:
                cols = None
            if cols is None:
                cols = max(1, int((viewport_w - 10) / (110 + spacing)))

            if cols >= 4:
                spacing = 4
            usable_w = max(1, viewport_w - ((cols - 1) * spacing))
            cell_w = max(40, int(usable_w / cols))
            cell_h = max(70, int(cell_w * 0.95))
            if hasattr(self, "app_grid_layout") and self.app_grid_layout:
                self.app_grid_layout.setSpacing(spacing)

            state = {
                "apps": grid_apps,
                "index": 0,
                "row": 0,
                "col": 0,
                "cols": cols,
                "cell_w": cell_w,
                "cell_h": cell_h,
            }

            def _build_grid_chunk():
                if build_token != self._build_token:
                    return
                count = 0
                while state["index"] < len(state["apps"]) and count < 32:
                    app = state["apps"][state["index"]]
                    state["index"] += 1
                    font_size = None
                    if cols == 3:
                        if cell_w <= 60:
                            font_size = 9
                        elif cell_w <= 80:
                            font_size = 10
                        elif cell_w <= 110:
                            font_size = 11
                        else:
                            font_size = 12
                    elif cols == 4:
                        if cell_w <= 60:
                            font_size = 7
                        elif cell_w <= 80:
                            font_size = 8
                        elif cell_w <= 110:
                            font_size = 9
                        else:
                            font_size = 10
                    item = AppGridItem(
                        app["name"],
                        app["icon"],
                        app["exe"],
                        app["is_favorite"],
                        app["is_hidden"],
                        app["category"],
                        app["version"],
                        app["description"],
                        tile_width=cell_w,
                        tile_height=cell_h,
                        font_size=font_size,
                    )
                    item.clicked.connect(self.launch_app)
                    self.app_widgets.append(item)
                    self.app_grid_layout.addWidget(item, state["row"], state["col"])
                    state["col"] += 1
                    if state["col"] >= state["cols"]:
                        state["col"] = 0
                        state["row"] += 1
                    count += 1

                if state["index"] < len(state["apps"]):
                    QTimer.singleShot(0, _build_grid_chunk)
                else:
                    if not keep_loading:
                        self._set_loading(False)
                    if not keep_pending:
                        self._refresh_pending = False
                    if hasattr(self, "search_bar") and self.search_bar:
                        self.filter_apps(self.search_bar.input.text())

            QTimer.singleShot(0, _build_grid_chunk)
            return

        # Group by category
        grouped_apps = {}
        top_level_apps = []
        favorites = []
        merge_favorites = getattr(self, "_merge_favorites_in_list", False)
        
        for app in apps:
            if app["is_favorite"] and not merge_favorites:
                favorites.append(app)
                continue

            cat = app["category"]
            if cat == "No Category":
                top_level_apps.append(app)
            else:
                if cat not in grouped_apps:
                    grouped_apps[cat] = []
                grouped_apps[cat].append(app)

        build_tasks = []
        if not merge_favorites:
            for app in favorites:
                build_tasks.append(("item", app))
            if favorites and (grouped_apps or top_level_apps):
                build_tasks.append(("separator", None))

        for cat in sorted(grouped_apps.keys()):
            build_tasks.append(("category", cat, grouped_apps[cat]))

        for app in top_level_apps:
            build_tasks.append(("item", app))

        if not build_tasks:
            if not keep_loading:
                self._set_loading(False)
            if not keep_pending:
                self._refresh_pending = False
            if hasattr(self, "search_bar") and self.search_bar:
                self.filter_apps(self.search_bar.input.text())
            return

        state = {"index": 0}

        def _build_list_chunk():
            if build_token != self._build_token:
                return
            count = 0
            while state["index"] < len(build_tasks) and count < 24:
                task = build_tasks[state["index"]]
                state["index"] += 1
                kind = task[0]
                if kind == "item":
                    app = task[1]
                    item = AppListItem(app["name"], app["icon"], app["exe"], app["is_favorite"], app["is_hidden"], app["category"], app["version"], app["description"])
                    item.clicked.connect(self.launch_app)
                    self.app_widgets.append(item)
                    self.app_list_layout.insertWidget(self.app_list_layout.count()-1, item)
                elif kind == "separator":
                    line = QFrame()
                    line.setFixedHeight(1)
                    line.setStyleSheet(f"background-color: {qcolor_to_rgba(COLOR_GLASS_BORDER)}; margin: 4px 5px;")
                    self.app_list_layout.insertWidget(self.app_list_layout.count()-1, line)
                    self._favorites_separator = line
                elif kind == "category":
                    cat = task[1]
                    cat_apps = task[2]
                    icon_path = get_category_icon_path(cat)
                    cat_item = CategoryItem(cat, icon_path, cat_apps, parent=self.app_list_container, lazy=True)
                    cat_item.app_clicked.connect(self.launch_app)
                    cat_item.toggled.connect(self.on_category_toggled)
                    if self.expand_default or cat in expanded_categories:
                        cat_item.set_expanded(True)
                    self.app_list_layout.insertWidget(self.app_list_layout.count()-1, cat_item)
                    self.app_widgets.append(cat_item)
                count += 1

            if state["index"] < len(build_tasks):
                QTimer.singleShot(0, _build_list_chunk)
            else:
                if not keep_loading:
                    self._set_loading(False)
                if not keep_pending:
                    self._refresh_pending = False
                if hasattr(self, "search_bar") and self.search_bar:
                    self.filter_apps(self.search_bar.input.text())

        QTimer.singleShot(0, _build_list_chunk)

    def _set_loading(self, visible):
        if hasattr(self, "loading_container") and self.loading_container:
            self.loading_container.setVisible(visible)

    def on_category_toggled(self, expanded, widget):
        if expanded and self.accordion_mode:
            for w in self.app_widgets:
                if isinstance(w, CategoryItem) and w != widget and w.expanded:
                    w.set_expanded(False, animate=True)

    def launch_app(self, exe_path):
        if exe_path and os.path.exists(exe_path):
            key = self.get_app_key(exe_path)
            if key in set(self.protected_apps or []) and self._password_is_set():
                if not self._prompt_password("Protected App", "Enter password to launch this app:"):
                    return
            if self.confirm_launch:
                name = QFileInfo(exe_path).baseName() or "this app"
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle("Launch App")
                msg.setText(f"Launch {name}?")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.Yes)
                if msg.exec() != QMessageBox.Yes:
                    return
            try:
                subprocess.Popen(exe_path, cwd=os.path.dirname(exe_path))
            except Exception as e:
                # If the app requires elevation, re-run with UAC prompt
                if isinstance(e, OSError) and getattr(e, "winerror", None) == 740:
                    try:
                        ctypes.windll.shell32.ShellExecuteW(
                            None,
                            "runas",
                            exe_path,
                            None,
                            os.path.dirname(exe_path),
                            1,
                        )
                    except Exception as inner:
                        print(f"Error launching {exe_path} (elevation failed): {inner}")
                else:
                    print(f"Error launching {exe_path}: {e}")
            self._maybe_reset_home_state()
            if not self.keep_visible_after_launch:
                self.animate_hide()

    def handle_quick_button(self, name):
        base_dir = get_base_dir()
        target_path = None
        
        if name in ["Documents", "Music", "Pictures", "Videos", "Downloads"]:
            target_path = os.path.join(base_dir, name)
        elif name == "Explore":
            target_path = base_dir
        elif name == "Apps":
            QTimer.singleShot(0, self.show_apps_menu)
            return
        elif name == "Settings":
            self.show_options_menu(target_widget=self.sender())
            return
        elif name == "Search":
            QTimer.singleShot(0, self.show_search_menu)
            return
        elif name == "Help":
            if self._confirm_web_action():
                webbrowser.open("https://portableapps.com/support")
            return
            
        if target_path and os.path.exists(target_path):
            os.startfile(target_path)

    def open_settings_from_menu(self):
        self.show_options_menu()
        if not self.isVisible():
            self.animate_show()
        else:
            self.raise_()
            self.activateWindow()

    def open_keybind_settings(self):
        self.show_options_menu()
        if not self.isVisible():
            self.animate_show()
        else:
            self.raise_()
            self.activateWindow()
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.set_category("Shortcuts")
            except Exception:
                pass

    def show_options_menu(self, target_widget=None):
        # General settings never require a password; only the Security tab is locked.
        self._settings_unlocked = False
        prev_category = "Behavior"
        prev_search = ""
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                if hasattr(self.options_panel, "_cleanup_threads"):
                    self.options_panel._cleanup_threads()
                prev_category = getattr(self.options_panel, "current_category", "Behavior")
                if hasattr(self.options_panel, "search_bar") and self.options_panel.search_bar:
                    prev_search = self.options_panel.search_bar.input.text()
            except RuntimeError:
                prev_category = "Behavior"
                prev_search = ""
        if self.main_stack.count() > 1:
            widget = self.main_stack.widget(1)
            self.main_stack.removeWidget(widget)
            widget.deleteLater()

        # Update settings dict for popup
        self.settings["show_hidden"] = self.show_hidden
        self.settings["expand_default"] = self.expand_default
        self.settings["accordion"] = self.accordion_mode
        self.settings["fade"] = self.fade_enabled
        self.settings["menu_key"] = self.menu_key
        self.settings["mini_key"] = self.mini_key
        self.settings["gui_scale"] = self.gui_scale
        self.settings["collapse_on_minimize"] = self.collapse_on_minimize
        self.settings["remember_last_screen"] = self.remember_last_screen
        self.settings["mini_show_documents"] = self.mini_show_documents
        self.settings["mini_show_music"] = self.mini_show_music
        self.settings["mini_show_videos"] = self.mini_show_videos
        self.settings["mini_show_explore"] = self.mini_show_explore
        self.settings["mini_show_settings"] = self.mini_show_settings
        self.settings["mini_show_all_apps"] = self.mini_show_all_apps
        self.settings["mini_show_favorites"] = self.mini_show_favorites
        self.settings["mini_show_exit"] = self.mini_show_exit
        self.settings["mini_show_icons"] = self.mini_show_icons
        self.settings["mini_apply_to_tray"] = self.mini_apply_to_tray
        self.settings["mini_pinned_apps"] = self.mini_pinned_apps
        self.settings["mini_pinned_preview"] = self._get_pinned_app_names()
        self.settings["mini_pinned_apps"] = self.mini_pinned_apps
        self.settings["search_descriptions"] = self.search_descriptions
        self.settings["keep_visible_after_launch"] = self.keep_visible_after_launch
        self.settings["start_minimized"] = self.start_minimized
        self.settings["show_search_bar"] = self.show_search_bar
        self.settings["show_in_taskbar"] = self.show_in_taskbar
        self.settings["confirm_launch"] = self.confirm_launch
        self.settings["confirm_web"] = self.confirm_web
        self.settings["confirm_exit"] = self.confirm_exit
        self.settings["require_app_password"] = self.require_app_password
        self.settings["require_settings_password"] = self.require_settings_password
        self.settings["protected_apps"] = self.protected_apps
        self.settings["password_salt"] = self.password_salt
        self.settings["password_hash"] = self.password_hash
        self.settings["trusted_devices"] = self.trusted_devices
        self.settings["app_session_unlock"] = self.app_session_unlock
        # Always re-lock security when opening settings.
        self.settings["security_unlocked"] = False
        self.settings["theme_mode"] = self.theme_mode
        self.settings["effective_theme"] = self.effective_theme
        self.settings["accent_color"] = self.accent_color
        self.settings["text_color"] = self.text_color
        self.settings["background_type"] = self.background_type
        self.settings["background_color"] = self.background_color
        self.settings["background_gradient_start"] = self.background_gradient_start
        self.settings["background_gradient_end"] = self.background_gradient_end
        self.settings["background_image"] = self.background_image
        self.settings["view_mode"] = self.view_mode
        self.settings["grid_columns"] = self.grid_columns
        self.settings["mini_menu_background_type"] = self.mini_menu_background_type
        self.settings["mini_menu_background_color"] = self.mini_menu_background_color
        self.settings["mini_menu_background_gradient_start"] = self.mini_menu_background_gradient_start
        self.settings["mini_menu_background_gradient_end"] = self.mini_menu_background_gradient_end
        self.settings["mini_menu_scale"] = self.mini_menu_scale
        self.settings["mini_menu_text_color"] = self.mini_menu_text_color
        self.settings["startup_apps"] = self.startup_apps
        self.settings["browser_choice"] = self.browser_choice
        self.settings["browser_path"] = self.browser_path
        self.settings["current_category"] = prev_category
        self.settings["settings_search"] = prev_search
        self.settings["always_on_top"] = self.always_on_top
        try:
            updates_enabled, _, _, _ = self._read_updates_config()
            self.settings["updates_auto_check"] = bool(updates_enabled)
        except Exception:
            pass

        self.options_panel = OptionsPanel(self.settings, self)
        self._options_target_widget = target_widget
        
        self.options_panel.refresh_clicked.connect(self.on_options_refresh)
        self.options_panel.add_cat_clicked.connect(self.add_global_category)
        self.options_panel.settings_clicked.connect(self.open_settings_file)
        self.options_panel.import_settings_clicked.connect(self.import_settings)
        self.options_panel.export_settings_clicked.connect(self.export_settings)
        self.options_panel.restart_clicked.connect(self.restart_app)
        self.options_panel.exit_clicked.connect(self.quit_app)
        self.options_panel.close_clicked.connect(self.show_apps_view)
        self.options_panel.hidden_toggled.connect(self.set_show_hidden)
        
        self.options_panel.expand_default_toggled.connect(self.set_expand_default)
        self.options_panel.accordion_toggled.connect(self.set_accordion_mode)
        self.options_panel.fade_toggled.connect(self.set_fade_enabled)
        self.options_panel.keybind_changed.connect(lambda x: self.update_setting("Settings", "MenuKey", x))
        self.options_panel.mini_keybind_changed.connect(lambda x: self.update_setting("Settings", "MiniKey", x))
        self.options_panel.gui_scale_changed.connect(self.set_gui_scale)
        self.options_panel.mini_menu_setting_changed.connect(self.update_mini_menu_setting)
        self.options_panel.home_shortcuts_changed.connect(self.update_home_shortcuts)
        self.options_panel.collapse_on_minimize_toggled.connect(self.set_collapse_on_minimize)
        self.options_panel.remember_last_screen_toggled.connect(self.set_remember_last_screen)
        self.options_panel.search_desc_toggled.connect(self.set_search_descriptions)
        self.options_panel.keep_visible_toggled.connect(self.set_keep_visible_after_launch)
        self.options_panel.start_minimized_toggled.connect(self.set_start_minimized)
        self.options_panel.show_search_toggled.connect(self.set_show_search_bar)
        self.options_panel.show_in_taskbar_toggled.connect(self.set_show_in_taskbar)
        self.options_panel.confirm_launch_toggled.connect(self.set_confirm_launch)
        self.options_panel.confirm_web_toggled.connect(self.set_confirm_web)
        self.options_panel.confirm_exit_toggled.connect(self.set_confirm_exit)
        self.options_panel.app_session_unlock_toggled.connect(self.set_app_session_unlock)
        self.options_panel.set_password_clicked.connect(self.set_password)
        self.options_panel.clear_password_clicked.connect(self.clear_password)
        self.options_panel.protected_apps_clicked.connect(self.open_protected_apps_dialog)
        self.options_panel.trusted_devices_clear_clicked.connect(self.clear_trusted_devices_clicked)
        self.options_panel.require_app_password_toggled.connect(self.set_require_app_password)
        self.options_panel.require_settings_password_toggled.connect(self.set_require_settings_password)
        self.options_panel.theme_mode_changed.connect(self.set_theme_mode)
        self.options_panel.accent_color_changed.connect(self.set_accent_color)
        self.options_panel.text_color_changed.connect(self.set_text_color)
        self.options_panel.background_changed.connect(self.set_background)
        self.options_panel.view_mode_changed.connect(self.set_view_mode)
        self.options_panel.grid_columns_changed.connect(self.set_grid_columns)
        self.options_panel.mini_menu_background_changed.connect(self.set_mini_menu_background)
        self.options_panel.mini_menu_scale_changed.connect(self.set_mini_menu_scale)
        self.options_panel.mini_menu_text_color_changed.connect(self.set_mini_menu_text_color)
        self.options_panel.always_on_top_toggled.connect(self.set_always_on_top)
        self.options_panel.manage_pinned_clicked.connect(self.open_pinned_apps_dialog)
        self.options_panel.startup_apps_clicked.connect(self.open_startup_apps_dialog)
        self.options_panel.fix_settings_clicked.connect(self.run_fix_settings)
        self.options_panel.check_updates_clicked.connect(lambda: self.check_for_updates(manual=True))
        self.options_panel.updates_auto_check_toggled.connect(self.set_updates_auto_check)
        self.options_panel.browser_changed.connect(self.set_default_browser)
        self.options_panel.browser_install_clicked.connect(self.open_browser_download)
        self.options_panel.browser_open_folder_clicked.connect(self.open_browser_folder)
        self.options_panel.software_notice_clicked.connect(self.show_notice_dialog)
        
        self.main_stack.addWidget(self.options_panel)
        self.main_stack.setCurrentWidget(self.options_panel)
        self.animate_options_panel()
        self._options_target_widget = None

    def show_all_apps_from_tray(self):
        self._favorites_only = False
        self._clear_search_bars()
        self.show_apps_view()
        if hasattr(self, "search_bar") and self.search_bar:
            self.filter_apps(self.search_bar.input.text())
        if not self.isVisible():
            self.animate_show()
        else:
            self.raise_()
            self.activateWindow()

    def show_favorites_from_tray(self):
        self._favorites_only = True
        self._clear_search_bars()
        self.show_apps_view()
        if hasattr(self, "search_bar") and self.search_bar:
            self.filter_apps(self.search_bar.input.text())
        if not self.isVisible():
            self.animate_show()
        else:
            self.raise_()
            self.activateWindow()

    def animate_options_panel(self):
        if not hasattr(self, "options_panel") or not self.options_panel:
            return
        panel = self.options_panel
        try:
            effect = QGraphicsOpacityEffect(panel)
            panel.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
        except Exception:
            return

        end_pos = panel.pos()
        start_pos = end_pos + QPoint(12, 0)
        panel.move(start_pos)

        anim_opacity = QPropertyAnimation(effect, b"opacity", panel)
        anim_opacity.setDuration(180)
        anim_opacity.setEasingCurve(QEasingCurve.OutCubic)
        anim_opacity.setStartValue(0.0)
        anim_opacity.setEndValue(1.0)

        anim_pos = QPropertyAnimation(panel, b"pos", panel)
        anim_pos.setDuration(180)
        anim_pos.setEasingCurve(QEasingCurve.OutCubic)
        anim_pos.setStartValue(start_pos)
        anim_pos.setEndValue(end_pos)

        group = QParallelAnimationGroup(panel)
        group.addAnimation(anim_opacity)
        group.addAnimation(anim_pos)
        self._options_anim = group
        group.finished.connect(lambda: panel.setGraphicsEffect(None))
        group.start()

    def show_apps_menu(self):
        menu = QMenu(self)
        dark = self.effective_theme == "dark"
        bg = "#1b1f26" if dark else "#FDFDFD"
        fg = COLOR_TEXT_MAIN.name()
        border = "rgba(255, 255, 255, 0.2)" if dark else "rgba(0, 0, 0, 0.2)"
        def _apply_style():
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {bg};
                    color: {COLOR_TEXT_MAIN.name()};
                    border: 1px solid {border};
                    padding-left: 1px;
                }}
                QMenu::icon {{
                    margin-left: 1px;
                    margin-right: 4px;
                }}
                QMenu::item {{
                    padding: 6px 12px 6px 7px;
                    color: {COLOR_TEXT_MAIN.name()};
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)
        _apply_style()
        if self.text_color == "__rainbow__":
            timer = QTimer(menu)
            timer.timeout.connect(_apply_style)
            timer.start(120)
            menu.aboutToHide.connect(timer.stop)

        base_dir = get_base_dir()
        icon_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons")
        def _icon(name):
            path = os.path.join(icon_dir, name)
            return QIcon(path) if os.path.exists(path) else QIcon()

        def _add_action(icon_name, text, icon_override=None):
            action = QAction(menu)
            icon = icon_override if icon_override is not None else _icon(icon_name)
            if not icon.isNull():
                action.setIcon(QIcon(icon.pixmap(16, 16)))
            action.setText(text)
            menu.addAction(action)
            return action

        menu.setContentsMargins(6, 4, 6, 4)

        refresh_action = _add_action("", "Refresh App List", self.style().standardIcon(QStyle.SP_BrowserReload))
        manage_action = _add_action("apps.png", "Manage Apps")
        browse_action = _add_action("browseapps.png", "Browse Apps (PortableApps.com)")
        install_action = _add_action("app.png", "Install .paf.exe")
        open_folder_action = _add_action("explore.png", "Open PortableApps Folder")

        action = menu.exec(QCursor.pos())
        if action == refresh_action:
            self.refresh_apps()
        elif action == manage_action:
            self.open_manage_apps_dialog()
        elif action == browse_action:
            if self._confirm_web_action():
                webbrowser.open("https://portableapps.com/apps")
        elif action == install_action:
            self.install_paf_app()
        elif action == open_folder_action:
            base_dir = get_base_dir()
            target_path = os.path.join(base_dir, "PortableApps")
            if os.path.exists(target_path):
                os.startfile(target_path)

    def _focus_search_bar(self):
        self.show_apps_view()
        if hasattr(self, "search_container") and self.search_container:
            self.search_container.setVisible(True)
        if hasattr(self, "search_bar") and self.search_bar:
            self.search_bar.input.setFocus()
            self.search_bar.input.selectAll()

    def _get_search_query(self):
        if hasattr(self, "search_bar") and self.search_bar:
            return self.search_bar.input.text().strip()
        return ""

    def open_url(self, url):
        choice = self.browser_choice or "system"
        raw_path = self.browser_path or ""
        path = self._resolve_setting_path(raw_path) if raw_path else ""
        if choice in {"chrome", "firefox", "opera", "operagx", "brave", "custom"}:
            if not path or not os.path.exists(path):
                self._show_missing_browser_dialog(choice)
                return
            try:
                subprocess.Popen([path, url], cwd=os.path.dirname(path))
                return
            except Exception:
                pass
        if choice == "edge":
            try:
                os.startfile(f"microsoft-edge:{url}")
                return
            except Exception:
                pass
        webbrowser.open(url)

    def open_browser_download(self, choice):
        self.install_browser(choice)

    def install_browser(self, choice):
        choice = choice or self.browser_choice or ""
        if choice in {"system", "edge", "custom"}:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Install Browser")
            msg.setText("No installer is available for the selected browser.")
            msg.setInformativeText("Choose a portable browser to install.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return

        download_url = self._browser_download_url(choice)
        if not download_url:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Installer Not Found")
            msg.setText("Browser installer URL not found.")
            msg.setInformativeText("Check the browser download settings.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return

        base_dir = get_base_dir()
        portableapps_dir = os.path.join(base_dir, "PortableApps")
        os.makedirs(portableapps_dir, exist_ok=True)

        installer_path = self._download_browser_installer(choice, download_url)
        if not installer_path:
            return

        try:
            if choice == "brave":
                self._install_brave_portable(installer_path)
            else:
                self._install_paf_installer(installer_path)
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Install Failed")
            msg.setText("Failed to launch the installer.")
            msg.setInformativeText(str(e))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

    def _get_download_dir(self):
        try:
            base = get_data_dir()
        except Exception:
            base = get_base_dir()
        target = os.path.join(base, "_tmp", "installers")
        os.makedirs(target, exist_ok=True)
        return target

    def _download_browser_installer(self, choice, url):
        filename = os.path.basename(urllib.parse.urlparse(url).path) or f"{choice}.exe"
        dest_path = os.path.join(self._get_download_dir(), filename)
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except Exception:
            pass
        title = "Downloading Browser"
        label = f"Downloading {choice} installer..."
        if not self._download_file(url, dest_path, title, label):
            return ""
        return dest_path

    def _download_file(self, url, dest_path, title, label):
        dlg = QProgressDialog(label, "Cancel", 0, 100, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.show()

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PortableX"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = resp.headers.get("Content-Length")
                try:
                    total = int(total) if total else 0
                except Exception:
                    total = 0

                if total > 0:
                    dlg.setRange(0, total)
                else:
                    dlg.setRange(0, 0)

                downloaded = 0
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            dlg.setValue(downloaded)
                        if dlg.wasCanceled():
                            raise RuntimeError("download cancelled")
                        app = QApplication.instance()
                        if app:
                            app.processEvents()

            if total > 0:
                dlg.setValue(total)
            return True
        except Exception as e:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception:
                pass
            if str(e).lower().startswith("download cancelled"):
                return False
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Download Failed")
            msg.setText("Failed to download browser installer.")
            msg.setInformativeText(str(e))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return False
        finally:
            dlg.close()

    def _watch_install_process(self, proc, on_finished=None):
        def _poll():
            try:
                running = proc.poll() is None
            except Exception:
                running = False
            if running:
                QTimer.singleShot(800, _poll)
                return
            if on_finished:
                on_finished()
        QTimer.singleShot(800, _poll)

    def _delete_file(self, path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def _install_paf_installer(self, installer_path):
        base_dir = get_base_dir()
        portableapps_dir = os.path.join(base_dir, "PortableApps")
        try:
            proc = subprocess.Popen([installer_path], cwd=os.path.dirname(installer_path))
        except Exception:
            self._delete_file(installer_path)
            raise
        try:
            if os.path.exists(portableapps_dir):
                os.startfile(portableapps_dir)
        except Exception:
            pass

        def _after():
            self._delete_file(installer_path)
        self._watch_install_process(proc, _after)

    def _install_brave_portable(self, installer_path):
        base_dir = get_base_dir()
        portableapps_dir = os.path.join(base_dir, "PortableApps")
        try:
            proc = subprocess.Popen([installer_path], cwd=portableapps_dir)
        except Exception:
            self._delete_file(installer_path)
            raise

        def _after():
            self._finalize_brave_install(installer_path)
        self._watch_install_process(proc, _after)

    def _finalize_brave_install(self, installer_path):
        base_dir = get_base_dir()
        portableapps_dir = os.path.join(base_dir, "PortableApps")
        candidates = [
            os.path.join(portableapps_dir, "brave-portable"),
            os.path.join(portableapps_dir, "BravePortable"),
            os.path.join(base_dir, "brave-portable"),
            os.path.join(base_dir, "BravePortable"),
        ]
        src_dir = ""
        for path in candidates:
            if os.path.isdir(path):
                src_dir = path
                break

        if not src_dir:
            self._delete_file(installer_path)
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Brave Install")
            msg.setText("Brave install finished, but the folder was not found.")
            msg.setInformativeText("Install Brave Portable into the PortableApps folder, then try again.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return

        target_dir = os.path.join(portableapps_dir, "BravePortable")
        if os.path.normcase(os.path.abspath(src_dir)) != os.path.normcase(os.path.abspath(target_dir)):
            if os.path.exists(target_dir):
                self._delete_file(installer_path)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Brave Install")
                msg.setText("BravePortable already exists.")
                msg.setInformativeText("Remove or rename the existing BravePortable folder and try again.")
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                return
            try:
                shutil.move(src_dir, target_dir)
            except Exception as e:
                self._delete_file(installer_path)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Brave Install Failed")
                msg.setText("Failed to rename brave-portable to BravePortable.")
                msg.setInformativeText(str(e))
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                return
        else:
            target_dir = src_dir

        appinfo_src = os.path.join(get_data_dir(), "brave appinfo", "appinfo")
        if not os.path.isdir(appinfo_src):
            appinfo_src = os.path.join(base_dir, "brave appinfo", "appinfo")
        appinfo_dst = os.path.join(target_dir, "app", "appinfo")
        if os.path.isdir(appinfo_src):
            try:
                os.makedirs(os.path.dirname(appinfo_dst), exist_ok=True)
                shutil.copytree(appinfo_src, appinfo_dst, dirs_exist_ok=True)
            except Exception as e:
                self._delete_file(installer_path)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Brave Install Failed")
                msg.setText("Failed to copy Brave appinfo folder.")
                msg.setInformativeText(str(e))
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                return
        else:
            self._delete_file(installer_path)
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Brave Install")
            msg.setText("Brave appinfo folder not found.")
            msg.setInformativeText("Missing: PortableApps\\PortableX\\Data\\brave appinfo\\appinfo")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return

        self._delete_file(installer_path)
        self.refresh_apps()

    def open_browser_folder(self, choice):
        base_dir = get_base_dir()
        portableapps_dir = os.path.join(base_dir, "PortableApps")
        expected_path = self._browser_expected_path(choice)

        if not expected_path or not os.path.exists(expected_path):
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Browser Not Found")
            msg.setText("Browser executable not found.")
            msg.setInformativeText("Check the path is correct or install the browser. Opening PortableApps folder.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            if os.path.exists(portableapps_dir):
                os.startfile(portableapps_dir)
            else:
                os.startfile(base_dir)
            return

        try:
            os.startfile(os.path.dirname(expected_path))
        except Exception:
            if os.path.exists(portableapps_dir):
                os.startfile(portableapps_dir)
            else:
                os.startfile(base_dir)

    def _browser_download_url(self, choice):
        urls = {
            "chrome": "https://download2.portableapps.com/portableapps/GoogleChromePortable/GoogleChromePortable_144.0.7559.133_online.paf.exe",
            "firefox": "https://download2.portableapps.com/portableapps/FirefoxPortable/FirefoxPortable_147.0.3_English.paf.exe",
            "opera": "https://download2.portableapps.com/portableapps/OperaPortable/OperaPortable_127.0.5778.14.paf.exe",
            "operagx": "https://download2.portableapps.com/portableapps/OperaGXPortable/OperaGXPortable_126.0.5750.112.paf.exe",
            "brave": "https://github.com/portapps/brave-portable/releases/download/1.85.118-98/brave-portable-win64-1.85.118-98-setup.exe",
        }
        return urls.get(choice or "", "")

    def _browser_expected_path(self, choice):
        if not choice:
            return ""
        defaults = self._browser_default_paths()
        if choice in defaults:
            return defaults[choice]
        if choice == "custom":
            return self._resolve_setting_path(self.browser_path or "")
        return ""

    def _browser_expected_dir(self, choice):
        path = self._browser_expected_path(choice)
        if path:
            return os.path.dirname(path)
        return os.path.join(get_base_dir(), "PortableApps")

    def _show_missing_browser_dialog(self, choice):
        labels = {
            "chrome": "Chrome Portable",
            "firefox": "Firefox Portable",
            "opera": "Opera Portable",
            "operagx": "Opera GX Portable",
            "brave": "Brave Portable",
            "custom": "Custom browser",
        }
        title = labels.get(choice, "Browser")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Browser Not Found")
        msg.setText(f"{title} was not found.")
        msg.setInformativeText("Check the path is correct or install the browser.")
        install_btn = msg.addButton("Install Browser", QMessageBox.ActionRole)
        open_btn = msg.addButton("Open Folder", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Cancel)

        download_url = self._browser_download_url(choice)
        if not download_url:
            install_btn.setEnabled(False)

        msg.exec()
        clicked = msg.clickedButton()
        if clicked == install_btn and download_url:
            self.install_browser(choice)
        elif clicked == open_btn:
            folder = self._browser_expected_dir(choice)
            if folder and os.path.exists(folder):
                os.startfile(folder)
            else:
                os.startfile(get_base_dir())

    # -------------------------------------------------------------------------
    # Updates
    # -------------------------------------------------------------------------

    def set_updates_auto_check(self, enabled):
        self._write_settings_value_quiet("Updates", "AutoCheck", "true" if enabled else "false")
        try:
            self.settings["updates_auto_check"] = bool(enabled)
            if hasattr(self, "options_panel") and self.options_panel:
                self.options_panel.settings["updates_auto_check"] = bool(enabled)
        except Exception:
            pass

    def _read_updates_config(self):
        enabled = True
        repo = ""
        interval_hours = float(DEFAULT_UPDATE_CHECK_INTERVAL_HOURS)
        last_check_epoch = 0.0

        try:
            config, _ = self.get_settings()
            repo = config.get("Updates", "Repo", fallback="").strip()
            enabled = config.getboolean("Updates", "AutoCheck", fallback=True)
            try:
                interval_hours = float(
                    config.get(
                        "Updates",
                        "IntervalHours",
                        fallback=str(DEFAULT_UPDATE_CHECK_INTERVAL_HOURS),
                    )
                )
            except Exception:
                interval_hours = float(DEFAULT_UPDATE_CHECK_INTERVAL_HOURS)
            try:
                last_check_epoch = float(config.get("Updates", "LastCheckEpoch", fallback="0"))
            except Exception:
                last_check_epoch = 0.0
        except Exception:
            pass

        repo = repo or DEFAULT_GITHUB_REPO
        return enabled, repo, max(1.0, interval_hours), last_check_epoch

    def _write_settings_value_quiet(self, section, key, value):
        try:
            config, path = self.get_settings()
            if not config.has_section(section):
                config.add_section(section)
            if value is None:
                config.remove_option(section, key)
            else:
                config.set(section, key, str(value))
            with open(path, "w") as f:
                config.write(f)
        except Exception:
            pass

    def _updates_repo(self):
        _, repo, _, _ = self._read_updates_config()
        return repo

    def _updates_interval_hours(self):
        _, _, interval_hours, _ = self._read_updates_config()
        return interval_hours

    def _updates_last_check_epoch(self):
        _, _, _, last_check_epoch = self._read_updates_config()
        return last_check_epoch

    def maybe_auto_check_updates(self):
        try:
            enabled, repo, interval_hours, last_check = self._read_updates_config()
            if not enabled:
                return
            if not repo:
                return
            now = time.time()
            if now - last_check < interval_hours * 3600:
                return
            # Startup auto-check: be silent if up-to-date, but prompt if an update exists.
            self.check_for_updates(manual=False, prompt_on_update=True, allow_never=True)
        except Exception:
            pass

    def check_for_updates(self, manual=False, prompt_on_update=False, allow_never=False):
        if getattr(self, "_update_check_in_progress", False):
            if manual:
                QMessageBox.information(self, "Updates", "An update check is already running.")
            return

        _, repo, _, _ = self._read_updates_config()
        if not repo:
            if not manual:
                return
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Updates")
            msg.setText("Update checking is not configured yet.")
            msg.setInformativeText(
                "Add this to your settings.ini:\n\n"
                "[Updates]\n"
                "Repo = owner/repo\n\n"
                "Then try again."
            )
            open_btn = msg.addButton("Open settings.ini", QMessageBox.ActionRole)
            msg.addButton(QMessageBox.Ok)
            msg.exec()
            if msg.clickedButton() == open_btn:
                try:
                    self.open_settings_file()
                except Exception:
                    pass
            return

        self._update_check_in_progress = True
        self._update_check_cancelled = False
        self._update_check_manual = bool(manual)
        self._update_check_prompt_on_update = bool(prompt_on_update)
        self._update_check_allow_never = bool(allow_never)

        if manual:
            try:
                dlg = QProgressDialog("Checking for updates...", "Hide", 0, 0, self)
                dlg.setWindowTitle("Updates")
                dlg.setWindowModality(Qt.WindowModal)
                dlg.setMinimumDuration(0)
                dlg.setAutoClose(False)
                dlg.setAutoReset(False)
                dlg.canceled.connect(self._cancel_update_check)
                dlg.show()
                self._update_progress_dialog = dlg
            except Exception:
                self._update_progress_dialog = None

        self._write_settings_value_quiet("Updates", "LastCheckEpoch", str(int(time.time())))

        try:
            self._update_thread = QThread(self)
            self._update_worker = UpdateCheckWorker(repo)
            self._update_worker.moveToThread(self._update_thread)
            self._update_thread.started.connect(self._update_worker.run)
            # Connect directly to ensure the slot runs on the GUI thread (queued connection).
            self._update_worker.finished.connect(self._on_update_check_finished)
            self._update_worker.error.connect(self._on_update_check_failed)
            self._update_worker.finished.connect(self._update_worker.deleteLater)
            self._update_worker.error.connect(self._update_worker.deleteLater)
            self._update_worker.finished.connect(self._update_thread.quit)
            self._update_worker.error.connect(self._update_thread.quit)
            self._update_thread.finished.connect(self._update_thread.deleteLater)
            self._update_thread.start()
        except Exception as e:
            self._on_update_check_failed(str(e))

    def _cancel_update_check(self):
        # We can't reliably abort the in-flight network request, so treat this as "Hide".
        self._close_update_progress()

    def _close_update_progress(self):
        if hasattr(self, "_update_progress_dialog") and self._update_progress_dialog:
            try:
                self._update_progress_dialog.close()
            except Exception:
                pass
            self._update_progress_dialog = None

    def _show_update_available_dialog(self, current_version, latest_version, url, allow_never=False):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Update Available")
        msg.setText("A new version of Portable X is available")
        msg.setInformativeText(f"Installed: v{current_version}\nLatest: v{latest_version}")
        download_btn = msg.addButton("Download Update", QMessageBox.ActionRole)
        msg.addButton("Later", QMessageBox.RejectRole)
        never_btn = None
        if allow_never:
            never_btn = msg.addButton("Never", QMessageBox.DestructiveRole)
        msg.setDefaultButton(download_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == download_btn:
            if self._confirm_web_action():
                self.open_url(url)
        elif allow_never and never_btn and clicked == never_btn:
            self.set_updates_auto_check(False)

    def _on_update_check_finished(self, info):
        manual = bool(getattr(self, "_update_check_manual", False))
        prompt_on_update = bool(getattr(self, "_update_check_prompt_on_update", False))
        allow_never = bool(getattr(self, "_update_check_allow_never", False))
        try:
            self._update_check_in_progress = False
            self._close_update_progress()

            info = info or {}
            latest_version = str(info.get("version") or "").strip()
            html_url = str(info.get("html_url") or "").strip()
            repo = str(info.get("repo") or "").strip() or self._updates_repo()
            current_version = (get_app_version() or "").strip()

            if latest_version:
                self._write_settings_value_quiet("Updates", "LatestVersion", latest_version)
            if html_url:
                self._write_settings_value_quiet("Updates", "LatestUrl", html_url)

            if not latest_version:
                if manual:
                    QMessageBox.warning(
                        self, "Update Check Failed", "Failed to check for updates (no version found)."
                    )
                return

            try:
                has_update = update_checker.is_newer_version(current_version, latest_version)
            except Exception as e:
                if manual:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle("Update Check Failed")
                    msg.setText("Failed to check for updates.")
                    msg.setInformativeText(str(e))
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec()
                return

            if has_update:
                if not html_url and repo:
                    html_url = f"https://github.com/{repo}/releases/latest"
                self._pending_update_url = html_url
                self._pending_update_version = latest_version

                if manual or prompt_on_update:
                    self._show_update_available_dialog(
                        current_version,
                        latest_version,
                        html_url,
                        allow_never=allow_never,
                    )
                else:
                    try:
                        if hasattr(self, "tray_icon") and self.tray_icon:
                            self.tray_icon.showMessage(
                                "Update Available",
                                f"A new version of Portable X is available\nLatest: v{latest_version}",
                                QSystemTrayIcon.Information,
                                15000,
                            )
                    except Exception:
                        pass
                return

            if manual:
                QMessageBox.information(
                    self,
                    "Updates",
                    f"You are already on the latest version.\nInstalled: v{current_version}",
                )
        except Exception as e:
            self._update_check_in_progress = False
            self._close_update_progress()
            if manual:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Update Check Failed")
                msg.setText("Failed to check for updates.")
                msg.setInformativeText(str(e))
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
        finally:
            self._update_check_manual = False
            self._update_check_prompt_on_update = False
            self._update_check_allow_never = False

    def _on_update_check_failed(self, error):
        manual = bool(getattr(self, "_update_check_manual", False))
        try:
            self._update_check_in_progress = False
            self._close_update_progress()

            if manual:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("Update Check Failed")
                msg.setText("Failed to check for updates.")
                msg.setInformativeText(str(error or ""))
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
        except Exception:
            pass
        finally:
            self._update_check_manual = False
            self._update_check_prompt_on_update = False
            self._update_check_allow_never = False

    def _on_tray_message_clicked(self):
        url = getattr(self, "_pending_update_url", "") or ""
        if not url:
            return
        if self._confirm_web_action():
            self.open_url(url)

    def maybe_show_notice(self):
        if self._notice_shown:
            return
        first_time = not self.settings.get("notice_accepted", False)
        force_notice = bool(self._force_notice)
        if not force_notice and not first_time:
            return
        self._notice_shown = True
        self._force_notice = False
        force_topmost = first_time or force_notice
        if force_topmost:
            self._set_temp_always_on_top(True)
        self.show_notice_dialog(mark_seen=True, force_topmost=force_topmost)
        if force_topmost:
            self._set_temp_always_on_top(False)

    def _set_temp_always_on_top(self, enable):
        if enable:
            if self.always_on_top:
                self._temp_topmost = False
                return
            self._temp_topmost = True
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            if self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()
        else:
            if not self._temp_topmost:
                return
            self._temp_topmost = False
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            if self.isVisible():
                self.show()

    def show_notice_dialog(self, mark_seen=False, force_topmost=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(NOTICE_TITLE)
        flags = dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint
        if force_topmost:
            flags |= Qt.WindowStaysOnTopHint
        dialog.setWindowFlags(flags)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignHCenter)
        base_dir = get_base_dir()
        icon_candidates = [
            os.path.join(base_dir, "icon.png"),
            os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons", "icon.png"),
            os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "profilepic", "taskbar.png"),
        ]
        icon_path = ""
        for candidate in icon_candidates:
            if os.path.exists(candidate):
                icon_path = candidate
                break
        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(icon_label)

        title_label = QLabel(NOTICE_TITLE)
        title_font = QFont(FONT_FAMILY, 13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignHCenter)
        title_label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()};")
        layout.addWidget(title_label)

        body_label = QLabel(NOTICE_BODY)
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body_label.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 11px;")
        layout.addWidget(body_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        if mark_seen:
            keybind_btn = buttons.addButton("Set keybinds", QDialogButtonBox.ActionRole)
            def _open_keybinds():
                dialog.accept()
                QTimer.singleShot(0, self.open_keybind_settings)
            keybind_btn.clicked.connect(_open_keybinds)
        layout.addWidget(buttons)

        dialog.setMinimumWidth(520)
        dialog.exec()

        if mark_seen:
            self.update_setting("Settings", "NoticeAccepted", "true")

    def show_search_menu(self):
        menu = QMenu(self)
        dark = self.effective_theme == "dark"
        bg = "#1b1f26" if dark else "#FDFDFD"
        border = "rgba(255, 255, 255, 0.2)" if dark else "rgba(0, 0, 0, 0.2)"

        def _apply_style():
            menu.setStyleSheet(f"""
                QMenu {{
                    background-color: {bg};
                    color: {COLOR_TEXT_MAIN.name()};
                    border: 1px solid {border};
                    padding-left: 1px;
                }}
                QMenu::icon {{
                    margin-left: 1px;
                    margin-right: 4px;
                }}
                QMenu::item {{
                    padding: 6px 12px 6px 7px;
                    color: {COLOR_TEXT_MAIN.name()};
                }}
                QMenu::item:selected {{
                    background-color: {COLOR_ACCENT.name()};
                    color: #ffffff;
                }}
            """)

        _apply_style()
        if self.text_color == "__rainbow__":
            timer = QTimer(menu)
            timer.timeout.connect(_apply_style)
            timer.start(120)
            menu.aboutToHide.connect(timer.stop)

        base_dir = get_base_dir()
        icon_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "sidebaricons")
        def _icon(name):
            path = os.path.join(icon_dir, name)
            return QIcon(path) if os.path.exists(path) else QIcon()

        def _add_action(icon_name, text):
            action = QAction(menu)
            icon = _icon(icon_name)
            if not icon.isNull():
                action.setIcon(QIcon(icon.pixmap(16, 16)))
            action.setText(text)
            menu.addAction(action)
            return action

        menu.setContentsMargins(6, 4, 6, 4)

        installed_action = _add_action("search.png", "Search installed apps")
        device_action = _add_action("usb.png", "Search this device")
        computer_action = _add_action("thispc.png", "Search this computer")
        web_action = _add_action("web.png", "Search the web")

        action = menu.exec(QCursor.pos())
        if action == installed_action:
            self._focus_search_bar()
        elif action == device_action:
            base_dir = get_base_dir()
            query = self._get_search_query()
            try:
                if query:
                    location = urllib.parse.quote(base_dir, safe=":\\/")
                    os.startfile(f"search-ms:query={urllib.parse.quote(query)}&crumb=location:{location}")
                else:
                    os.startfile(base_dir)
            except Exception:
                try:
                    os.startfile(base_dir)
                except Exception:
                    pass
        elif action == computer_action:
            query = self._get_search_query()
            try:
                if query:
                    os.startfile(f"ms-search:query={urllib.parse.quote(query)}")
                else:
                    os.startfile("ms-search:")
            except Exception:
                pass
        elif action == web_action:
            query = self._get_search_query()
            if query:
                url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
            else:
                url = "https://www.google.com"
            if self._confirm_web_action():
                self.open_url(url)

    def install_paf_app(self):
        base_dir = get_base_dir()
        start_dir = os.path.join(base_dir, "PortableApps")
        if not os.path.exists(start_dir):
            start_dir = base_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PortableApps Installer",
            start_dir,
            "PortableApps Installer (*.paf.exe *.exe)"
        )
        if path and os.path.exists(path):
            try:
                subprocess.Popen(path, cwd=os.path.dirname(path))
            except Exception as e:
                print(f"Error launching installer {path}: {e}")


    def show_apps_view(self):
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.collapse_expanded_sections()
            except RuntimeError:
                pass
        self.main_stack.setCurrentIndex(0)
        if self.main_stack.count() > 1:
            widget = self.main_stack.widget(1)
            self.main_stack.removeWidget(widget)
            widget.deleteLater()
        if hasattr(self, "search_bar") and hasattr(self.search_bar, "input"):
            if self.search_bar.input.text():
                self.search_bar.input.clear()
                self.filter_apps("")

    def show_all_apps_list_view(self):
        self._favorites_only = False
        self._list_back_to_grid = True
        self._merge_favorites_in_list = True
        if hasattr(self, "app_list_header") and self.app_list_header:
            self.app_list_header.setVisible(True)
        if self.view_mode != "list":
            self.set_view_mode("list")
        else:
            self.refresh_apps()
        self.show_apps_view()

    def show_grid_view_from_list(self):
        self._list_back_to_grid = False
        self._merge_favorites_in_list = False
        if hasattr(self, "app_list_header") and self.app_list_header:
            self.app_list_header.hide()
        if self.view_mode != "grid":
            self.set_view_mode("grid")
        else:
            self.refresh_apps()
        self.show_apps_view()

    def open_pinned_apps_dialog(self):
        apps = self.scan_portable_apps()
        dlg = QDialog(self)
        dlg.setWindowTitle("Pinned Apps")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIndentation(14)
        tree.setTextElideMode(Qt.ElideNone)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        tree.setColumnWidth(1, 18)
        pinned = set(self.mini_pinned_apps or [])
        grouped = {}
        for app in apps:
            cat = app.get("category", "No Category") or "No Category"
            grouped.setdefault(cat, []).append(app)

        for cat in self.CATEGORIES:
            if cat not in grouped:
                continue
            cat_item = QTreeWidgetItem([cat])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            cat_icon = get_category_icon_path(cat)
            if cat_icon and os.path.exists(cat_icon):
                cat_item.setIcon(0, QIcon(cat_icon))
            tree.addTopLevelItem(cat_item)
            toggle_btn = QToolButton()
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(True)
            toggle_btn.setArrowType(Qt.DownArrow)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setFixedSize(12, 12)
            toggle_btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
            def _make_toggle(item, btn):
                def _toggle():
                    expanded = btn.isChecked()
                    item.setExpanded(expanded)
                    btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
                return _toggle
            toggle_btn.clicked.connect(_make_toggle(cat_item, toggle_btn))
            tree.setItemWidget(cat_item, 1, toggle_btn)
            for app in grouped[cat]:
                key = self.get_app_key(app["exe"])
                item = QTreeWidgetItem([app["name"]])
                icon_path = app.get("icon", "")
                if icon_path and os.path.exists(icon_path):
                    item.setIcon(0, QIcon(icon_path))
                item.setData(0, Qt.UserRole, key)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked if key in pinned else Qt.Unchecked)
                cat_item.addChild(item)
        tree.expandAll()
        layout.addWidget(tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            selected = []
            for i in range(tree.topLevelItemCount()):
                cat_item = tree.topLevelItem(i)
                for j in range(cat_item.childCount()):
                    item = cat_item.child(j)
                    if item.checkState(0) == Qt.Checked:
                        selected.append(item.data(0, Qt.UserRole))
            self.mini_pinned_apps = selected
            self.update_setting("Settings", "MiniPinnedApps", self._serialize_pinned_apps(selected))
            self.rebuild_tray_menu()
            if hasattr(self, "options_panel") and self.options_panel:
                self.settings["mini_pinned_apps"] = self.mini_pinned_apps
                self.settings["mini_pinned_preview"] = self._get_pinned_app_names()
                self.options_panel.settings = self.settings
                if hasattr(self.options_panel, "mini_preview") and self.options_panel.mini_preview:
                    self.options_panel.mini_preview.update_config(self.settings)

    def open_startup_apps_dialog(self):
        apps = self.scan_portable_apps()
        dlg = QDialog(self)
        dlg.setWindowTitle("Startup Apps")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIndentation(14)
        tree.setTextElideMode(Qt.ElideNone)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        tree.setColumnWidth(1, 18)

        selected = set(self.startup_apps or [])
        grouped = {}
        for app in apps:
            cat = app.get("category", "No Category") or "No Category"
            grouped.setdefault(cat, []).append(app)

        for cat in self.CATEGORIES:
            if cat not in grouped:
                continue
            cat_item = QTreeWidgetItem([cat])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            cat_icon = get_category_icon_path(cat)
            if cat_icon and os.path.exists(cat_icon):
                cat_item.setIcon(0, QIcon(cat_icon))
            tree.addTopLevelItem(cat_item)
            toggle_btn = QToolButton()
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(True)
            toggle_btn.setArrowType(Qt.DownArrow)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setFixedSize(12, 12)
            toggle_btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
            def _make_toggle(item, btn):
                def _toggle():
                    expanded = btn.isChecked()
                    item.setExpanded(expanded)
                    btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
                return _toggle
            toggle_btn.clicked.connect(_make_toggle(cat_item, toggle_btn))
            tree.setItemWidget(cat_item, 1, toggle_btn)
            for app in grouped[cat]:
                key = self.get_app_key(app["exe"])
                item = QTreeWidgetItem([app["name"]])
                icon_path = app.get("icon", "")
                if icon_path and os.path.exists(icon_path):
                    item.setIcon(0, QIcon(icon_path))
                item.setData(0, Qt.UserRole, key)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked if key in selected else Qt.Unchecked)
                cat_item.addChild(item)
        tree.expandAll()
        layout.addWidget(tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            selected_keys = []
            for i in range(tree.topLevelItemCount()):
                cat_item = tree.topLevelItem(i)
                for j in range(cat_item.childCount()):
                    item = cat_item.child(j)
                    if item.checkState(0) == Qt.Checked:
                        selected_keys.append(item.data(0, Qt.UserRole))
            self.startup_apps = selected_keys
            self.update_setting("Settings", "StartupApps", self._serialize_pinned_apps(selected_keys))

    def open_protected_apps_dialog(self):
        apps = self.scan_portable_apps()
        dlg = QDialog(self)
        dlg.setWindowTitle("Protected Apps")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIndentation(14)
        tree.setTextElideMode(Qt.ElideNone)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        tree.setColumnWidth(1, 18)

        selected = set(self.protected_apps or [])
        grouped = {}
        for app in apps:
            cat = app.get("category", "No Category") or "No Category"
            grouped.setdefault(cat, []).append(app)

        for cat in self.CATEGORIES:
            if cat not in grouped:
                continue
            cat_item = QTreeWidgetItem([cat])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            cat_icon = get_category_icon_path(cat)
            if cat_icon and os.path.exists(cat_icon):
                cat_item.setIcon(0, QIcon(cat_icon))
            tree.addTopLevelItem(cat_item)
            toggle_btn = QToolButton()
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(True)
            toggle_btn.setArrowType(Qt.DownArrow)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setFixedSize(12, 12)
            toggle_btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
            def _make_toggle(item, btn):
                def _toggle():
                    expanded = btn.isChecked()
                    item.setExpanded(expanded)
                    btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
                return _toggle
            toggle_btn.clicked.connect(_make_toggle(cat_item, toggle_btn))
            tree.setItemWidget(cat_item, 1, toggle_btn)
            for app in grouped[cat]:
                key = self.get_app_key(app["exe"])
                item = QTreeWidgetItem([app["name"]])
                icon_path = app.get("icon", "")
                if icon_path and os.path.exists(icon_path):
                    item.setIcon(0, QIcon(icon_path))
                item.setData(0, Qt.UserRole, key)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked if key in selected else Qt.Unchecked)
                cat_item.addChild(item)
        tree.expandAll()
        layout.addWidget(tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            selected_keys = []
            for i in range(tree.topLevelItemCount()):
                cat_item = tree.topLevelItem(i)
                for j in range(cat_item.childCount()):
                    item = cat_item.child(j)
                    if item.checkState(0) == Qt.Checked:
                        selected_keys.append(item.data(0, Qt.UserRole))
            self.protected_apps = selected_keys
            self.update_setting("Security", "ProtectedApps", self._serialize_pinned_apps(selected_keys))

    def _get_pinned_app_names(self):
        apps = self._get_pinned_apps()
        return [a["name"] for a in apps]

    def on_options_refresh(self):
        self.refresh_apps()
        self.show_apps_view()

    def set_show_hidden(self, show):
        self.show_hidden = show
        self.refresh_apps()
        self.update_setting("Settings", "ShowHidden", "true" if show else "false")

    def set_expand_default(self, enabled):
        self.expand_default = enabled
        if not enabled:
            self.collapse_all_categories()
        self.update_setting("Settings", "ExpandDefault", "true" if enabled else "false")

    def set_accordion_mode(self, enabled):
        self.accordion_mode = enabled
        self.update_setting("Settings", "Accordion", "true" if enabled else "false")

    def set_fade_enabled(self, enabled):
        self.fade_enabled = enabled
        self.update_setting("Settings", "FadeAnimation", "true" if enabled else "false")

    def set_collapse_on_minimize(self, enabled):
        self.collapse_on_minimize = enabled
        self.update_setting("Settings", "CollapseOnMinimize", "true" if enabled else "false")

    def set_remember_last_screen(self, enabled):
        self.remember_last_screen = enabled
        self.update_setting("Settings", "RememberLastScreen", "true" if enabled else "false")

    def set_search_descriptions(self, enabled):
        self.search_descriptions = enabled
        self.update_setting("Settings", "SearchDescriptions", "true" if enabled else "false")
        if hasattr(self, "search_bar"):
            self.filter_apps(self.search_bar.input.text())

    def set_keep_visible_after_launch(self, enabled):
        self.keep_visible_after_launch = enabled
        self.update_setting("Settings", "KeepVisibleAfterLaunch", "true" if enabled else "false")

    def set_start_minimized(self, enabled):
        self.start_minimized = enabled
        self.update_setting("Settings", "StartMinimized", "true" if enabled else "false")

    def set_show_search_bar(self, enabled):
        self.show_search_bar = enabled
        if not enabled and hasattr(self, "search_bar"):
            self.search_bar.input.clear()
            self.filter_apps("")
        self.update_setting("Settings", "ShowSearchBar", "true" if enabled else "false")
        self.apply_search_bar_visibility()

    def set_show_in_taskbar(self, enabled):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Restart Required")
        msg.setText("Changing taskbar visibility requires a restart.")
        msg.setInformativeText("Restart now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec() != QMessageBox.Yes:
            return
        self.show_in_taskbar = enabled
        self.update_setting("Settings", "ShowInTaskbar", "true" if enabled else "false")
        self.restart_app()

    def set_confirm_launch(self, enabled):
        self.confirm_launch = enabled
        self.update_setting("Settings", "ConfirmLaunch", "true" if enabled else "false")

    def set_confirm_web(self, enabled):
        self.confirm_web = enabled
        self.update_setting("Settings", "ConfirmWeb", "true" if enabled else "false")

    def set_confirm_exit(self, enabled):
        self.confirm_exit = enabled
        self.update_setting("Settings", "ConfirmExit", "true" if enabled else "false")

    def set_app_session_unlock(self, enabled):
        self.app_session_unlock = enabled
        self.update_setting("Security", "AppSessionUnlock", "true" if enabled else "false")
        if not enabled:
            self._app_unlocked_session = False
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.set_app_session_unlock(enabled)
            except RuntimeError:
                pass

    def _password_is_set(self):
        return bool(self.password_hash and self.password_salt)

    def _hash_password(self, password, salt_hex):
        try:
            salt = bytes.fromhex(salt_hex)
        except Exception:
            salt = salt_hex.encode("utf-8")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return digest.hex()

    def _verify_password(self, password):
        if not self._password_is_set():
            return False
        return self._hash_password(password, self.password_salt) == self.password_hash

    def _device_fingerprint(self):
        computer = os.environ.get("COMPUTERNAME") or platform.node() or ""
        user = os.environ.get("USERNAME") or getpass.getuser() or ""
        fingerprint = f"{computer}|{user}".strip().lower()
        return fingerprint

    def _device_token(self):
        fingerprint = self._device_fingerprint()
        if not fingerprint:
            return ""
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _is_trusted_device(self):
        token = self._device_token()
        if not token:
            return False
        return token in set(self.trusted_devices or [])

    def _remember_trusted_device(self):
        token = self._device_token()
        if not token:
            return
        devices = list(self.trusted_devices or [])
        if token in devices:
            return
        devices.append(token)
        self.trusted_devices = devices
        self.update_setting("Security", "TrustedDevices", self._serialize_pinned_apps(devices))

    def _clear_trusted_devices(self):
        self.trusted_devices = []
        self.update_setting("Security", "TrustedDevices", None)

    def _prompt_password(self, title, text):
        while True:
            pwd, ok = QInputDialog.getText(self, title, text, QLineEdit.Password)
            if not ok:
                return False
            if self._verify_password(pwd):
                return True
            QMessageBox.warning(self, "Incorrect Password", "The password you entered is incorrect.")

    def _prompt_password_with_trust(self, title, text):
        while True:
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            layout = QVBoxLayout(dlg)
            label = QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)
            pwd_input = QLineEdit()
            pwd_input.setEchoMode(QLineEdit.Password)
            pwd_input.setPlaceholderText("Password")
            layout.addWidget(pwd_input)
            trust_box = QCheckBox("Automatically unlock on this PC")
            layout.addWidget(trust_box)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            ok_btn = buttons.button(QDialogButtonBox.Ok)
            if ok_btn:
                ok_btn.setDefault(True)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            layout.addWidget(buttons)
            pwd_input.setFocus()

            if dlg.exec() != QDialog.Accepted:
                return False, False
            if self._verify_password(pwd_input.text()):
                return True, trust_box.isChecked()
            QMessageBox.warning(self, "Incorrect Password", "The password you entered is incorrect.")

    def _prompt_set_password(self):
        pwd1, ok1 = QInputDialog.getText(self, "Set Password", "Enter a new password:", QLineEdit.Password)
        if not ok1 or not pwd1:
            return False
        pwd2, ok2 = QInputDialog.getText(self, "Set Password", "Confirm the password:", QLineEdit.Password)
        if not ok2 or not pwd2:
            return False
        if pwd1 != pwd2:
            QMessageBox.warning(self, "Passwords do not match", "Please try again.")
            return False
        salt = secrets.token_hex(8)
        hashed = self._hash_password(pwd1, salt)
        self.password_salt = salt
        self.password_hash = hashed
        self.update_setting("Security", "PasswordSalt", salt)
        self.update_setting("Security", "PasswordHash", hashed)
        return True

    def set_password(self):
        if self._password_is_set():
            if not self._prompt_password("Change Password", "Enter current password:"):
                return
        if self._prompt_set_password():
            self._clear_trusted_devices()
            self._app_unlocked_session = False
            if hasattr(self, "options_panel") and self.options_panel:
                try:
                    self.options_panel.settings["password_salt"] = self.password_salt
                    self.options_panel.settings["password_hash"] = self.password_hash
                    self.options_panel.on_password_state_changed(True, relock=True)
                except RuntimeError:
                    pass
            QMessageBox.information(self, "Password Set", "Your password has been updated.")

    def clear_password(self):
        if not self._password_is_set():
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Clear Password")
        msg.setText("Remove the current password?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            return
        self.password_salt = ""
        self.password_hash = ""
        self._clear_trusted_devices()
        self.require_app_password = False
        self.require_settings_password = False
        self._app_unlocked_session = False
        self.update_setting("Security", "PasswordSalt", None)
        self.update_setting("Security", "PasswordHash", None)
        self.update_setting("Security", "RequireAppPassword", "false")
        self.update_setting("Security", "RequireSettingsPassword", "false")
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.settings["password_salt"] = ""
                self.options_panel.settings["password_hash"] = ""
                self.options_panel.on_password_state_changed(False, relock=False)
            except RuntimeError:
                pass
        self.show_options_menu()

    def clear_trusted_devices_clicked(self):
        if not self.trusted_devices:
            QMessageBox.information(self, "Trusted Devices", "No trusted devices are saved.")
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Trusted Devices")
        msg.setText("Clear all trusted devices?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            return
        self._clear_trusted_devices()
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.settings["trusted_devices"] = []
                if hasattr(self.options_panel, "trusted_devices_row") and self.options_panel.trusted_devices_row:
                    self.options_panel.trusted_devices_row.setDisabled(True)
            except RuntimeError:
                pass

    def set_require_app_password(self, enabled):
        if enabled and not self._password_is_set():
            if not self._prompt_set_password():
                self.update_setting("Security", "RequireAppPassword", "false")
                self.show_options_menu()
                return
        self.require_app_password = enabled
        self.update_setting("Security", "RequireAppPassword", "true" if enabled else "false")

    def set_require_settings_password(self, enabled):
        if enabled and not self._password_is_set():
            if not self._prompt_set_password():
                self.update_setting("Security", "RequireSettingsPassword", "false")
                self.show_options_menu()
                return
        self.require_settings_password = enabled
        self.update_setting("Security", "RequireSettingsPassword", "true" if enabled else "false")

    def _confirm_web_action(self):
        if not self.confirm_web:
            return True
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Open Web Link")
        msg.setText("Open your web browser?")
        msg.setInformativeText("This will open your default browser.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        return msg.exec() == QMessageBox.Yes

    def set_theme_mode(self, mode):
        if getattr(self, "view_mode", "list") == "grid":
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Restart Required")
            msg.setText("Changing theme while Grid view is active requires a restart.")
            msg.setInformativeText("Restart now?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            if msg.exec() != QMessageBox.Yes:
                return
            self.update_setting("Settings", "ThemeMode", mode)
            self.restart_app()
            return
        self.update_setting("Settings", "ThemeMode", mode)
        self.apply_theme_mode(mode)
        if self.accent_color:
            apply_accent_color(self.accent_color)
        if self.text_color and self.text_color != "__rainbow__":
            apply_text_color(self.text_color)
        self.rebuild_main_view()
        self.refresh_apps()
        self.show_options_menu()

    def set_accent_color(self, value):
        self.accent_color = value or ""
        if self.accent_color:
            self.update_setting("Settings", "AccentColor", self.accent_color)
        else:
            self.update_setting("Settings", "AccentColor", None)
        self.apply_theme_mode(self.theme_mode)
        if self.accent_color:
            apply_accent_color(self.accent_color)
        if self.text_color:
            apply_text_color(self.text_color)
        self.rebuild_main_view()
        self.show_options_menu()

    def set_text_color(self, value):
        self.text_color = value or ""
        if self.text_color:
            self.update_setting("Settings", "TextColor", self.text_color)
        else:
            self.update_setting("Settings", "TextColor", None)
        self.apply_theme_mode(self.theme_mode)
        if self.accent_color:
            apply_accent_color(self.accent_color)
        if self.text_color == "__rainbow__":
            self._start_rainbow()
        else:
            self._stop_rainbow()
            if self.text_color:
                apply_text_color(self.text_color)
        self.rebuild_main_view()
        self.show_options_menu()

    def set_view_mode(self, value):
        value = value or "list"
        if value == self.view_mode:
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Restart Required")
        msg.setText("Switching between Grid and List view requires a restart.")
        msg.setInformativeText("Restart now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec() != QMessageBox.Yes:
            return
        self.view_mode = value
        if value != "list":
            self._list_back_to_grid = False
            if hasattr(self, "app_list_header") and self.app_list_header:
                self.app_list_header.hide()
        self.update_setting("Settings", "ViewMode", value)
        self.restart_app()

    def set_grid_columns(self, value):
        value = value or "auto"
        self.grid_columns = value
        self.update_setting("Settings", "GridColumns", value)

    def set_background(self, payload):
        payload = payload or {}
        self.background_type = payload.get("type", "theme")
        self.background_color = payload.get("color", "")
        self.background_gradient_start = payload.get("gradient_start", "")
        self.background_gradient_end = payload.get("gradient_end", "")
        raw_image = payload.get("image", "")
        stored_image = self._normalize_setting_path(raw_image)
        self.background_image = self._resolve_setting_path(stored_image)

        self.update_setting("Settings", "BackgroundType", self.background_type)
        self.update_setting("Settings", "BackgroundColor", self.background_color or None)
        self.update_setting("Settings", "BackgroundGradientStart", self.background_gradient_start or None)
        self.update_setting("Settings", "BackgroundGradientEnd", self.background_gradient_end or None)
        self.update_setting("Settings", "BackgroundImage", stored_image or None)

        self.update()

    def set_mini_menu_background(self, payload):
        payload = payload or {}
        self.mini_menu_background_type = payload.get("type", "default")
        self.mini_menu_background_color = payload.get("color", "")
        self.mini_menu_background_gradient_start = payload.get("gradient_start", "")
        self.mini_menu_background_gradient_end = payload.get("gradient_end", "")
        config, path = self.get_settings()
        if not config.has_section("Settings"):
            config.add_section("Settings")
        config.set("Settings", "MiniMenuBackgroundType", self.mini_menu_background_type)
        if self.mini_menu_background_color:
            config.set("Settings", "MiniMenuBackgroundColor", self.mini_menu_background_color)
        else:
            config.remove_option("Settings", "MiniMenuBackgroundColor")
        if self.mini_menu_background_gradient_start:
            config.set("Settings", "MiniMenuBackgroundGradientStart", self.mini_menu_background_gradient_start)
        else:
            config.remove_option("Settings", "MiniMenuBackgroundGradientStart")
        if self.mini_menu_background_gradient_end:
            config.set("Settings", "MiniMenuBackgroundGradientEnd", self.mini_menu_background_gradient_end)
        else:
            config.remove_option("Settings", "MiniMenuBackgroundGradientEnd")
        with open(path, 'w') as f:
            config.write(f)
        # Refresh local state and menus
        self.settings = self.load_settings_dict()
        self.mini_menu_background_type = self.settings.get("mini_menu_background_type", "default")
        self.mini_menu_background_color = self.settings.get("mini_menu_background_color", "")
        self.mini_menu_background_gradient_start = self.settings.get("mini_menu_background_gradient_start", "")
        self.mini_menu_background_gradient_end = self.settings.get("mini_menu_background_gradient_end", "")
        self.rebuild_tray_menu()

    def set_mini_menu_scale(self, value):
        if not value or value == self.mini_menu_scale:
            return
        self.mini_menu_scale = value
        self.update_setting("Settings", "MiniMenuScale", value)

    def set_mini_menu_text_color(self, value):
        self.mini_menu_text_color = value or ""
        self.update_setting("Settings", "MiniMenuTextColor", self.mini_menu_text_color or None)

    def _browser_default_paths(self):
        base_dir = get_base_dir()
        return {
            "chrome": os.path.join(base_dir, "PortableApps", "GoogleChromePortable", "GoogleChromePortable.exe"),
            "firefox": os.path.join(base_dir, "PortableApps", "FirefoxPortable", "FirefoxPortable.exe"),
            "opera": os.path.join(base_dir, "PortableApps", "OperaPortable", "OperaPortable.exe"),
            "operagx": os.path.join(base_dir, "PortableApps", "OperaGXPortable", "OperaGXPortable.exe"),
            "brave": os.path.join(base_dir, "PortableApps", "BravePortable", "brave-portable.exe"),
        }

    def set_default_browser(self, payload):
        payload = payload or {}
        choice = payload.get("choice", "system")
        path = payload.get("path", "") or ""
        defaults = self._browser_default_paths()

        if choice in defaults:
            path = defaults[choice]
        elif choice in {"system", "edge"}:
            path = ""
        elif choice == "custom":
            path = path or self.browser_path or ""

        self.browser_choice = choice
        self.browser_path = path

        self.update_setting("Settings", "BrowserChoice", choice)
        if path:
            self.update_setting("Settings", "BrowserPath", self._normalize_setting_path(path))
        else:
            self.update_setting("Settings", "BrowserPath", None)

    def set_gui_scale(self, value):
        if not value or value == self.gui_scale:
            return
        self.gui_scale = value
        self.update_setting("Settings", "GuiScale", value)
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Apply GUI Scale")
        msg.setText("Restart required to apply GUI scale.")
        msg.setInformativeText("Restart now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec() == QMessageBox.Yes:
            self.restart_app()

    def set_always_on_top(self, enabled):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Restart Required")
        msg.setText("Changing Always on Top requires a restart.")
        msg.setInformativeText("Restart now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec() != QMessageBox.Yes:
            return
        self.always_on_top = enabled
        self.update_setting("Settings", "AlwaysOnTop", "true" if enabled else "false")
        self.restart_app()


    def add_global_category(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Category")
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        label = QLabel("Category Name")
        label.setStyleSheet(f"color: {COLOR_TEXT_MAIN.name()};")
        layout.addWidget(label)

        input_box = QLineEdit()
        input_box.setPlaceholderText("New category name")
        input_box.setStyleSheet(f"""
            QLineEdit {{
                background: {qcolor_to_rgba(COLOR_GLASS_WHITE)};
                color: {COLOR_TEXT_MAIN.name()};
                border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                border-radius: 6px;
                padding: 6px 8px;
            }}
        """)
        layout.addWidget(input_box)

        instructions = QLabel(
            "Icon instructions:\n"
            "- Use a PNG with a 1:1 (square) ratio\n"
            "- Name it the same as the category (lowercase)\n"
            "- Put it in the icon folder"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {COLOR_TEXT_SUB.name()}; font-size: 10px;")
        layout.addWidget(instructions)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(8)
        open_folder_btn = QPushButton("Open Icon Folder")
        open_folder_btn.setCursor(Qt.PointingHandCursor)
        open_folder_btn.setStyleSheet(f"""
            QPushButton {{
                background: {qcolor_to_rgba(COLOR_GLASS_WHITE)};
                color: {COLOR_TEXT_MAIN.name()};
                border: 1px solid {qcolor_to_rgba(COLOR_GLASS_BORDER)};
                border-radius: 6px;
                padding: 4px 12px;
                font-family: "{FONT_FAMILY}";
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {qcolor_to_rgba(COLOR_HOVER)};
                border-color: {COLOR_ACCENT.name()};
            }}
        """)
        def _open_icon_folder():
            target = os.path.join(get_base_dir(), "PortableApps", "PortableX", "Graphics", "categories")
            try:
                os.startfile(target)
            except Exception:
                pass
        open_folder_btn.clicked.connect(_open_icon_folder)
        buttons_row.addWidget(open_folder_btn, 0, Qt.AlignLeft)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            cat = input_box.text().strip()
            if cat:
                self.update_setting("GlobalCategories", cat, "true")

    def open_settings_file(self):
        target_path = get_settings_path()
        if not os.path.exists(target_path):
            with open(target_path, 'w') as f:
                f.write("[User]\n")
        os.startfile(target_path)

    def export_settings(self):
        source_path = get_settings_path()
        if not os.path.exists(source_path):
            try:
                with open(source_path, 'w') as f:
                    f.write("[User]\n")
            except Exception:
                pass

        default_dir = os.path.dirname(source_path)
        default_path = os.path.join(default_dir, "settings.ini")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Settings", default_path, "INI Files (*.ini)"
        )
        if not path:
            return
        try:
            shutil.copy2(source_path, path)
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Export Settings")
            msg.setText("Settings exported.")
            msg.setInformativeText(path)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Export Failed")
            msg.setText("Failed to export settings.")
            msg.setInformativeText(str(e))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()

    def import_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Settings", "", "INI Files (*.ini)"
        )
        if not path:
            return
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Question)
        confirm.setWindowTitle("Import Settings")
        confirm.setText("Import settings and overwrite your current configuration?")
        confirm.setInformativeText("A backup will be created.")
        confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirm.setDefaultButton(QMessageBox.No)
        if confirm.exec() != QMessageBox.Yes:
            return

        dest_path = get_settings_path()
        try:
            if os.path.exists(dest_path):
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                backup_path = f"{dest_path}.bak-{timestamp}"
                shutil.copy2(dest_path, backup_path)
            shutil.copy2(path, dest_path)
        except Exception as e:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Import Failed")
            msg.setText("Failed to import settings.")
            msg.setInformativeText(str(e))
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Import Settings")
        msg.setText("Settings imported. Restart required to apply all changes.")
        msg.setInformativeText("Restart now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        if msg.exec() == QMessageBox.Yes:
            self.restart_app()

    # -------------------------------------------------------------------------
    # Settings & Context Menu Logic
    # -------------------------------------------------------------------------
    def get_settings(self):
        config = configparser.ConfigParser()
        config.optionxform = str # Preserve case
        path = get_settings_path()
        config.read(path)
        return config, path

    def update_setting(self, section, key, value):
        config, path = self.get_settings()
        if not config.has_section(section):
            config.add_section(section)
        
        if value is None:
            config.remove_option(section, key)
        else:
            config.set(section, key, str(value))
            
        with open(path, 'w') as f:
            config.write(f)
            
        # Update local state
        self.settings = self.load_settings_dict()
        self._refresh_category_list(config)
        self.show_hidden = self.settings["show_hidden"]
        self.expand_default = self.settings["expand_default"]
        self.accordion_mode = self.settings["accordion"]
        self.fade_enabled = self.settings["fade"]
        self.menu_key = self.settings["menu_key"]
        self.mini_key = self.settings.get("mini_key", "Ctrl+E")
        self.gui_scale = self.settings.get("gui_scale", "1.0")
        self.collapse_on_minimize = self.settings["collapse_on_minimize"]
        self.remember_last_screen = self.settings.get("remember_last_screen", False)
        self.home_show_documents = self.settings.get("home_show_documents", True)
        self.home_show_music = self.settings.get("home_show_music", True)
        self.home_show_pictures = self.settings.get("home_show_pictures", True)
        self.home_show_videos = self.settings.get("home_show_videos", True)
        self.home_show_downloads = self.settings.get("home_show_downloads", True)
        self.home_show_explore = self.settings.get("home_show_explore", True)
        self.home_show_custom_folder = self.settings.get("home_show_custom_folder", False)
        self.home_custom_folder = self.settings.get("home_custom_folder", "")
        self.home_custom_label = self.settings.get("home_custom_label", "")
        self.mini_show_documents = self.settings.get("mini_show_documents", True)
        self.mini_show_music = self.settings.get("mini_show_music", True)
        self.mini_show_videos = self.settings.get("mini_show_videos", True)
        self.mini_show_downloads = self.settings.get("mini_show_downloads", True)
        self.mini_show_explore = self.settings.get("mini_show_explore", True)
        self.mini_show_settings = self.settings.get("mini_show_settings", True)
        self.mini_show_all_apps = self.settings.get("mini_show_all_apps", True)
        self.mini_show_favorites = self.settings.get("mini_show_favorites", True)
        self.mini_show_exit = self.settings.get("mini_show_exit", True)
        self.mini_show_icons = self.settings.get("mini_show_icons", True)
        self.mini_apply_to_tray = self.settings.get("mini_apply_to_tray", False)
        self.mini_menu_scale = self.settings.get("mini_menu_scale", "1.0")
        self.search_descriptions = self.settings["search_descriptions"]
        self.keep_visible_after_launch = self.settings["keep_visible_after_launch"]
        self.start_minimized = self.settings["start_minimized"]
        self.show_search_bar = self.settings["show_search_bar"]
        self.show_in_taskbar = self.settings.get("show_in_taskbar", False)
        self.confirm_launch = self.settings.get("confirm_launch", False)
        self.confirm_web = self.settings.get("confirm_web", False)
        self.confirm_exit = self.settings.get("confirm_exit", True)
        self.require_app_password = self.settings.get("require_app_password", False)
        self.require_settings_password = self.settings.get("require_settings_password", False)
        self.protected_apps = self.settings.get("protected_apps", [])
        self.password_salt = self.settings.get("password_salt", "")
        self.password_hash = self.settings.get("password_hash", "")
        self.trusted_devices = self.settings.get("trusted_devices", [])
        self.app_session_unlock = self.settings.get("app_session_unlock", False)
        self.theme_mode = self.settings["theme_mode"]
        self.always_on_top = self.settings["always_on_top"]
        self.mini_menu_background_type = self.settings.get("mini_menu_background_type", "default")
        self.mini_menu_background_color = self.settings.get("mini_menu_background_color", "")
        self.mini_menu_background_gradient_start = self.settings.get("mini_menu_background_gradient_start", "")
        self.mini_menu_background_gradient_end = self.settings.get("mini_menu_background_gradient_end", "")
        self.mini_menu_scale = self.settings.get("mini_menu_scale", "1.0")
        self.mini_menu_text_color = self.settings.get("mini_menu_text_color", "")
        self.view_mode = self.settings.get("view_mode", "list")
        self.grid_columns = self.settings.get("grid_columns", "auto")
        self._list_back_to_grid = False
        self.browser_choice = self.settings.get("browser_choice", "system")
        self.browser_path = self.settings.get("browser_path", "")
        self.register_global_hotkey()
        self.rebuild_tray_menu()
        self.refresh_apps()

    def update_mini_menu_setting(self, key, value):
        mapping = {
            "mini_show_documents": "MiniShowDocuments",
            "mini_show_music": "MiniShowMusic",
            "mini_show_videos": "MiniShowVideos",
            "mini_show_downloads": "MiniShowDownloads",
            "mini_show_explore": "MiniShowExplore",
            "mini_show_settings": "MiniShowSettings",
            "mini_show_all_apps": "MiniShowAllApps",
            "mini_show_favorites": "MiniShowFavorites",
            "mini_show_exit": "MiniShowExit",
            "mini_show_icons": "MiniShowIcons",
            "mini_apply_to_tray": "MiniApplyToTray",
        }
        setting_key = mapping.get(key)
        if not setting_key:
            return
        self.update_setting("Settings", setting_key, "true" if value else "false")

    def update_home_shortcuts(self, updates):
        if not updates:
            return
        mapping = {
            "home_show_documents": "HomeShowDocuments",
            "home_show_music": "HomeShowMusic",
            "home_show_pictures": "HomeShowPictures",
            "home_show_videos": "HomeShowVideos",
            "home_show_downloads": "HomeShowDownloads",
            "home_show_explore": "HomeShowExplore",
            "home_show_custom_folder": "HomeShowCustomFolder",
            "home_custom_folder": "HomeCustomFolder",
            "home_custom_label": "HomeCustomLabel",
            "home_custom_folders": "HomeCustomFolders",
        }
        config, path = self.get_settings()
        if not config.has_section("Settings"):
            config.add_section("Settings")
        for key, value in updates.items():
            setting_key = mapping.get(key)
            if not setting_key:
                continue
            if isinstance(value, bool):
                config.set("Settings", setting_key, "true" if value else "false")
            elif setting_key == "HomeCustomFolders" and isinstance(value, (list, tuple)):
                config.set("Settings", setting_key, json.dumps(value, ensure_ascii=True))
            else:
                config.set("Settings", setting_key, str(value))
        with open(path, 'w') as f:
            config.write(f)

        self.settings = self.load_settings_dict()
        self.home_show_documents = self.settings.get("home_show_documents", True)
        self.home_show_music = self.settings.get("home_show_music", True)
        self.home_show_pictures = self.settings.get("home_show_pictures", True)
        self.home_show_videos = self.settings.get("home_show_videos", True)
        self.home_show_downloads = self.settings.get("home_show_downloads", True)
        self.home_show_explore = self.settings.get("home_show_explore", True)
        self.home_show_custom_folder = self.settings.get("home_show_custom_folder", False)
        self.home_custom_folder = self.settings.get("home_custom_folder", "")
        self.home_custom_label = self.settings.get("home_custom_label", "")
        self.home_custom_folders = self.settings.get("home_custom_folders", [])
        self._build_quick_buttons()

    def _get_pinned_apps(self):
        pinned = set(self.mini_pinned_apps or [])
        if not pinned:
            return []
        apps = self._get_apps_snapshot()
        if apps:
            return [a for a in apps if self.get_app_key(a.get("exe", "")) in pinned]

        base_dir = get_base_dir()
        hidden_map = {}
        if not self.show_hidden:
            try:
                config, _ = self.get_settings()
                if config.has_section("Hidden"):
                    for key in self.mini_pinned_apps or []:
                        if not key:
                            continue
                        hidden_map[key] = config.getboolean("Hidden", key, fallback=False)
            except Exception:
                hidden_map = {}
        pinned_apps = []
        for key in self.mini_pinned_apps or []:
            if not key:
                continue
            if not self.show_hidden and hidden_map.get(key, False):
                continue
            exe_path = key
            if not os.path.isabs(exe_path):
                exe_path = os.path.normpath(os.path.join(base_dir, exe_path))
            if not exe_path or not os.path.exists(exe_path):
                continue
            name = QFileInfo(exe_path).baseName() or os.path.splitext(os.path.basename(exe_path))[0] or "App"
            pinned_apps.append(
                {
                    "name": name,
                    "exe": exe_path,
                    "icon": exe_path,
                    "is_favorite": False,
                    "is_hidden": False,
                    "category": "No Category",
                    "version": "",
                    "description": "",
                }
            )
        return pinned_apps

    def launch_startup_apps(self):
        if not self.startup_apps:
            return
        base_dir = get_base_dir()
        hidden_map = {}
        if not self.show_hidden:
            try:
                config, _ = self.get_settings()
                if config.has_section("Hidden"):
                    for key in self.startup_apps:
                        if not key:
                            continue
                        hidden_map[key] = config.getboolean("Hidden", key, fallback=False)
            except Exception:
                hidden_map = {}
        for key in self.startup_apps:
            if not key:
                continue
            if not self.show_hidden and hidden_map.get(key, False):
                continue
            exe_path = key
            if not os.path.isabs(exe_path):
                exe_path = os.path.normpath(os.path.join(base_dir, exe_path))
            if not exe_path or not os.path.exists(exe_path):
                continue
            try:
                subprocess.Popen(exe_path, cwd=os.path.dirname(exe_path))
            except Exception as e:
                print(f"Error launching startup app {exe_path}: {e}")

    def run_fix_settings(self):
        if getattr(self, "_fix_settings_running", False):
            return
        self._fix_settings_running = True
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.set_fix_settings_busy(True)
            except Exception:
                pass

        try:
            self._fix_thread = QThread(self)
            self._fix_worker = FixSettingsWorker()
            self._fix_worker.moveToThread(self._fix_thread)
            self._fix_thread.started.connect(self._fix_worker.run)
            self._fix_worker.finished.connect(self._fix_thread.quit)
            self._fix_worker.error.connect(self._fix_thread.quit)
            self._fix_worker.finished.connect(self._fix_worker.deleteLater)
            self._fix_worker.error.connect(self._fix_worker.deleteLater)
            self._fix_thread.finished.connect(self._fix_thread.deleteLater)
            self._fix_worker.finished.connect(self._on_fix_settings_done)
            self._fix_worker.error.connect(self._on_fix_settings_error)
            self._fix_thread.start()
        except Exception as e:
            self._fix_settings_running = False
            if hasattr(self, "options_panel") and self.options_panel:
                try:
                    self.options_panel.set_fix_settings_busy(False)
                except Exception:
                    pass
            QMessageBox.warning(self, "Fix Settings", f"Failed to run fix_settings.py: {e}")

    def _on_fix_settings_done(self, result):
        self._fix_settings_running = False
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.set_fix_settings_busy(False)
            except Exception:
                pass
        message = ""
        if isinstance(result, dict):
            message = result.get("message") or ""
        if not message:
            message = "Fix settings completed."
        QMessageBox.information(self, "Fix Settings", message)
        self.refresh_apps()

    def _on_fix_settings_error(self, error):
        self._fix_settings_running = False
        if hasattr(self, "options_panel") and self.options_panel:
            try:
                self.options_panel.set_fix_settings_busy(False)
            except Exception:
                pass
        QMessageBox.warning(self, "Fix Settings", f"Failed to run fix_settings.py: {error}")

    def save_window_position(self, pos):
        config, path = self.get_settings()
        if not config.has_section("Settings"):
            config.add_section("Settings")
        config.set("Settings", "WindowX", str(pos.x()))
        config.set("Settings", "WindowY", str(pos.y()))
        with open(path, 'w') as f:
            config.write(f)

    def flush_window_position(self):
        if self._pending_pos is None:
            return
        self.save_window_position(self._pending_pos)
        self._pending_pos = None

    def get_app_key(self, exe_path):
        base_dir = get_base_dir()
        try:
            return os.path.relpath(exe_path, base_dir).replace("\\", "/")
        except ValueError:
            return exe_path.replace("\\", "/")

    def toggle_favorite(self, exe_path):
        config, _ = self.get_settings()
        key = self.get_app_key(exe_path)
        is_fav = False
        if config.has_section("Favorites"):
            is_fav = config.getboolean("Favorites", key, fallback=False)
        
        # Toggle
        self.update_setting("Favorites", key, "false" if is_fav else "true")

    def toggle_hide(self, exe_path):
        config, _ = self.get_settings()
        key = self.get_app_key(exe_path)
        is_hidden = False
        if config.has_section("Hidden"):
            is_hidden = config.getboolean("Hidden", key, fallback=False)
            
        self.update_setting("Hidden", key, "false" if is_hidden else "true")

    def toggle_show_hidden(self):
        self.show_hidden = not self.show_hidden
        self.refresh_apps()

    def request_rename(self, exe_path, current_name):
        new_name, ok = QInputDialog.getText(self, "Rename App", "New Name:", text=current_name)
        if ok and new_name:
            key = self.get_app_key(exe_path)
            self.update_setting("Renames", key, new_name)

    def request_category(self, exe_path):
        # Just storing it for now as requested
        config, _ = self.get_settings()
        key = self.get_app_key(exe_path)
        current_cat = "No Category"
        if config.has_section("Categories"):
            current_cat = config.get("Categories", key, fallback="No Category")
        else:
            # Try to find in current widgets
            for item in self.app_widgets:
                if item.exe_path == exe_path:
                    current_cat = item.category
                    break
            
        index = self.CATEGORIES.index(current_cat) if current_cat in self.CATEGORIES else 0
        dialog = CategorySelectionDialog(self.CATEGORIES, current_cat, self)
        if dialog.exec() == QDialog.Accepted:
            new_cat = dialog.get_selected_category()
            self.update_setting("Categories", key, new_cat)

    def explore_app_dir(self, exe_path):
        if exe_path and os.path.exists(exe_path):
            folder = os.path.dirname(exe_path)
            os.startfile(folder)

    def _get_portable_app_root(self, exe_path):
        if not exe_path:
            return ""
        base_dir = get_base_dir()
        portableapps_dir = os.path.join(base_dir, "PortableApps")
        try:
            rel = os.path.relpath(exe_path, portableapps_dir)
        except Exception:
            return ""
        if rel.startswith(".."):
            return ""
        parts = rel.split(os.sep)
        if not parts:
            return ""
        root = os.path.join(portableapps_dir, parts[0])
        return root

    def _remove_app_keys_from_settings(self, keys):
        if not keys:
            return
        config, path = self.get_settings()
        for section in ("Renames", "Categories", "Favorites", "Hidden"):
            if not config.has_section(section):
                continue
            for key in keys:
                if config.has_option(section, key):
                    config.remove_option(section, key)

        def _filter_list(section, option):
            if not config.has_option(section, option):
                return
            raw = config.get(section, option, fallback="")
            items = [p for p in raw.split(";") if p and p not in keys]
            if items:
                config.set(section, option, ";".join(items))
            else:
                config.remove_option(section, option)

        _filter_list("Security", "ProtectedApps")
        _filter_list("Settings", "StartupApps")
        _filter_list("Settings", "MiniPinnedApps")

        with open(path, 'w') as f:
            config.write(f)

        self.settings = self.load_settings_dict()
        self.protected_apps = self.settings.get("protected_apps", [])
        self.startup_apps = self.settings.get("startup_apps", [])
        self.mini_pinned_apps = self.settings.get("mini_pinned_apps", [])
        self.rebuild_tray_menu()

    def open_manage_apps_dialog(self):
        apps = self.scan_portable_apps()
        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Apps")
        dlg.resize(620, 520)
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderHidden(False)
        tree.setHeaderLabels(["App", "Folder"])
        tree.setRootIsDecorated(False)
        tree.setIndentation(14)
        tree.setTextElideMode(Qt.ElideRight)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setSectionResizeMode(1, QHeaderView.Fixed)
        tree.setColumnWidth(1, 160)

        grouped = {}
        for app in apps:
            root = self._get_portable_app_root(app.get("exe", ""))
            if not root or not os.path.isdir(root):
                continue
            root_name = os.path.basename(root)
            if root_name.lower() in {"portablex", "portableapps.com"}:
                continue
            cat = app.get("category", "No Category") or "No Category"
            grouped.setdefault(cat, []).append((app, root))

        for cat in sorted(grouped.keys()):
            cat_item = QTreeWidgetItem([cat, ""])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            cat_icon = get_category_icon_path(cat)
            if cat_icon and os.path.exists(cat_icon):
                cat_item.setIcon(0, QIcon(cat_icon))
            tree.addTopLevelItem(cat_item)
            toggle_btn = QToolButton()
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(True)
            toggle_btn.setArrowType(Qt.DownArrow)
            toggle_btn.setCursor(Qt.PointingHandCursor)
            toggle_btn.setFixedSize(12, 12)
            toggle_btn.setStyleSheet("QToolButton { border: none; background: transparent; }")
            def _make_toggle(item, btn):
                def _toggle():
                    expanded = btn.isChecked()
                    item.setExpanded(expanded)
                    btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
                return _toggle
            toggle_btn.clicked.connect(_make_toggle(cat_item, toggle_btn))
            tree.setItemWidget(cat_item, 1, toggle_btn)
            for app, root in grouped[cat]:
                key = self.get_app_key(app["exe"])
                item = QTreeWidgetItem([app["name"], os.path.basename(root)])
                icon_path = app.get("icon", "")
                if icon_path and os.path.exists(icon_path):
                    item.setIcon(0, QIcon(icon_path))
                item.setData(0, Qt.UserRole, {"root": root, "key": key, "name": app["name"]})
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Unchecked)
                cat_item.addChild(item)
        tree.expandAll()
        layout.addWidget(tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        if ok_button:
            ok_button.setText("Delete")
        layout.addWidget(buttons)

        def _delete_selected():
            to_delete = []
            for i in range(tree.topLevelItemCount()):
                cat_item = tree.topLevelItem(i)
                for j in range(cat_item.childCount()):
                    item = cat_item.child(j)
                    if item.checkState(0) == Qt.Checked:
                        payload = item.data(0, Qt.UserRole) or {}
                        if payload:
                            to_delete.append(payload)

            if not to_delete:
                QMessageBox.information(dlg, "Manage Apps", "No apps selected.")
                return

            msg = QMessageBox(dlg)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Delete Apps")
            msg.setText(f"Delete {len(to_delete)} app(s)?")
            msg.setInformativeText("This will remove their folders from PortableApps.")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.No)
            if msg.exec() != QMessageBox.Yes:
                return

            deleted_keys = []
            errors = []

            def _on_remove_error(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    raise

            for payload in to_delete:
                root = payload.get("root", "")
                key = payload.get("key", "")
                name = payload.get("name", root)
                if not root or not os.path.isdir(root):
                    continue
                base_dir = get_base_dir()
                portableapps_dir = os.path.join(base_dir, "PortableApps")
                try:
                    if os.path.commonpath([portableapps_dir, root]) != portableapps_dir:
                        errors.append(f"{name}: invalid path")
                        continue
                except Exception:
                    errors.append(f"{name}: invalid path")
                    continue
                root_name = os.path.basename(root)
                if root_name.lower() in {"portablex", "portableapps.com"}:
                    errors.append(f"{name}: protected folder")
                    continue
                try:
                    shutil.rmtree(root, onerror=_on_remove_error)
                    if key:
                        deleted_keys.append(key)
                except Exception as e:
                    errors.append(f"{name}: {e}")

            if deleted_keys:
                self._remove_app_keys_from_settings(deleted_keys)
                self.refresh_apps()

            if errors:
                QMessageBox.warning(dlg, "Manage Apps", "Some apps could not be deleted:\n" + "\n".join(errors))
            else:
                QMessageBox.information(dlg, "Manage Apps", "Selected apps deleted.")
            dlg.accept()

        buttons.accepted.connect(_delete_selected)
        buttons.rejected.connect(dlg.reject)

        dlg.exec()

    def filter_apps(self, text):
        if not hasattr(self, "_rainbow_search_active_main"):
            self._rainbow_search_active_main = False
        if "rainbow" in text.lower():
            if not self._rainbow_search_active_main:
                self._rainbow_search_active_main = True
                self.set_text_color("__rainbow__")
        else:
            self._rainbow_search_active_main = False
        if self.view_mode == "grid":
            query = text.strip()
            showing_all = getattr(self, "_grid_showing_all", False)
            if (query and not showing_all) or (not query and showing_all):
                self.refresh_apps()
                return
        grid_query_active = self.view_mode == "grid" and text.strip()
        text = text.lower()
        for item in self.app_widgets:
            if isinstance(item, CategoryItem):
                if self._favorites_only:
                    item.hide()
                else:
                    item.filter(text, self.search_descriptions)
            else:
                matches_text = text in item.name.lower() or (self.search_descriptions and text in (item.description or "").lower())
                if self._favorites_only and not grid_query_active and not item.is_favorite:
                    item.hide()
                elif matches_text:
                    item.show()
                else:
                    item.hide()
        if hasattr(self, "_favorites_separator") and self._favorites_separator:
            self._favorites_separator.setVisible(not self._favorites_only)

    # -------------------------------------------------------------------------
    # Custom Painting for the Main Container (Gradient + Rounded Corners)
    # -------------------------------------------------------------------------
    def apply_window_mask(self):
        # Keep rounded corners even when snapped to edges
        path = QPainterPath()
        path.addRoundedRect(self.rect(), BORDER_RADIUS, BORDER_RADIUS)
        region = path.toFillPolygon().toPolygon()
        self.setMask(region)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized() and self.collapse_on_minimize:
                self.collapse_all_categories()
            if self.isMinimized():
                self._maybe_reset_home_state()
                if hasattr(self, "options_panel") and self.options_panel:
                    try:
                        self.options_panel.collapse_expanded_sections()
                    except RuntimeError:
                        pass
                    try:
                        self.options_panel.lock_security()
                    except RuntimeError:
                        pass
        elif event.type() == QEvent.WindowDeactivate:
            self._maybe_hide_on_deactivate()
        super().changeEvent(event)

    def resizeEvent(self, event):
        self.container.setGeometry(10, 10, self.width() - 20, self.height() - 20)
        self.apply_window_mask()
        if getattr(self, "view_mode", "list") == "grid":
            try:
                self.refresh_apps()
            except Exception:
                pass
        super().resizeEvent(event)

    def focusOutEvent(self, event):
        self._maybe_hide_on_deactivate()
        super().focusOutEvent(event)

    def _maybe_hide_on_deactivate(self):
        if not self.isVisible() or self._is_hiding or self._is_showing:
            return
        if self._tray_menu_open or self._suppress_auto_hide:
            return
        active = QApplication.activeWindow()
        if not active or (active is not self and not self.isAncestorOf(active)):
            self._maybe_reset_home_state()
            if self.collapse_on_minimize:
                self.collapse_all_categories()
            if hasattr(self, "options_panel") and self.options_panel:
                try:
                    self.options_panel.lock_security()
                except RuntimeError:
                    pass
            self.animate_hide()

    def _maybe_reset_home_state(self):
        if not self.remember_last_screen:
            self.show_apps_view()
        self._clear_search_bars()

    def _clear_search_bars(self):
        if hasattr(self, "search_bar") and hasattr(self.search_bar, "input"):
            if self.search_bar.input.text():
                self.search_bar.input.clear()
                self.filter_apps("")
        if hasattr(self, "options_panel") and self.options_panel:
            if hasattr(self.options_panel, "search_bar") and self.options_panel.search_bar:
                try:
                    if self.options_panel.search_bar.input.text():
                        self.options_panel.search_bar.input.clear()
                except RuntimeError:
                    pass


    # We override the container's paint event by installing an event filter 
    # or subclassing. Since we used QWidget for container, let's just 
    # paint the background in the main window's paintEvent but clipped to container.
    # Actually, simpler to subclass container. But for single file, let's do this:
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Define the main shape
        rect = self.container.geometry()
        
        # Clip to rounded rect for background fill
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)
        painter.setClipPath(clip_path)

        # Background fill
        if self.background_type == "image" and self.background_image and os.path.exists(self.background_image):
            pixmap = QPixmap(self.background_image)
            if not pixmap.isNull():
                scaled = pixmap.scaled(rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = rect.x() + (rect.width() - scaled.width()) // 2
                y = rect.y() + (rect.height() - scaled.height()) // 2
                painter.drawPixmap(QRect(x, y, scaled.width(), scaled.height()), scaled)
            else:
                painter.fillPath(clip_path, QBrush(COLOR_BG_END))
        elif self.background_type == "solid" and self.background_color:
            painter.fillPath(clip_path, QBrush(QColor(self.background_color)))
        elif self.background_type == "gradient" and self.background_gradient_start and self.background_gradient_end:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor(self.background_gradient_start))
            gradient.setColorAt(1.0, QColor(self.background_gradient_end))
            painter.fillPath(clip_path, QBrush(gradient))
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, COLOR_BG_START)
            gradient.setColorAt(1.0, COLOR_BG_END)
            painter.fillPath(clip_path, QBrush(gradient))

        painter.setClipping(False)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1))

        # Draw Main Body border
        painter.drawRoundedRect(rect, BORDER_RADIUS, BORDER_RADIUS)
        
        # Draw a subtle inner glow (simulated with a gradient stroke or inner rect)
        # Top highlight
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawLine(rect.left()+BORDER_RADIUS, rect.top(), rect.right()-BORDER_RADIUS, rect.top())

    # -------------------------------------------------------------------------
    # Window Dragging Logic
    # -------------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Only allow dragging from the top region
            if event.position().y() <= 50:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            else:
                return

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if not hasattr(self, "drag_pos"):
                return
            new_pos = event.globalPosition().toPoint() - self.drag_pos
            
            # Screen Snapping Logic
            screen = self.screen().availableGeometry()
            snap_margin = 20
            
            # Account for the 10px transparent border/shadow area
            border_offset = 10
            
            x = new_pos.x()
            y = new_pos.y()
            
            # Snap Left
            if abs((x + border_offset) - screen.left()) < snap_margin:
                x = screen.left() - border_offset
            # Snap Right
            elif abs((x + self.width() - border_offset) - screen.right()) < snap_margin:
                x = screen.right() - self.width() + border_offset
                
            # Snap Top
            if abs((y + border_offset) - screen.top()) < snap_margin:
                y = screen.top() - border_offset
            # Snap Bottom
            elif abs((y + self.height() - border_offset) - screen.bottom()) < snap_margin:
                y = screen.bottom() - self.height() + border_offset
                
            self.move(x, y)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and hasattr(self, "drag_pos"):
            delattr(self, "drag_pos")
        super().mouseReleaseEvent(event)

    def moveEvent(self, event):
        if not self.isMinimized():
            self._pending_pos = self.pos()
            self._pos_save_timer.start(200)
        super().moveEvent(event)
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.main_stack.currentIndex() == 1:
                self.show_apps_view()
            else:
                pass
        elif event.key() == Qt.Key_F5:
            self.refresh_apps()

if __name__ == "__main__":
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass
    # Apply GUI scale before creating QApplication
    os.environ["QT_SCALE_FACTOR"] = read_gui_scale_setting()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Set Application Font
    font = QFont(FONT_FAMILY, 10)
    app.setFont(font)
    
    window = LauncherWindow()

    # Single-instance guard: one instance per executable path
    try:
        instance_path = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
    except Exception:
        instance_path = os.path.abspath(sys.executable)
    instance_key = instance_path.lower()
    instance_hash = hashlib.sha1(instance_key.encode("utf-8")).hexdigest()[:12]
    server_name = f"PortableX_{instance_hash}"
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if socket.waitForConnected(200):
        socket.write(b"raise")
        socket.flush()
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        sys.exit(0)

    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    if server.listen(server_name):
        def _on_new_connection():
            client = server.nextPendingConnection()
            if not client:
                return
            def _on_ready():
                client.readAll()  # consume message
                if window.isMinimized():
                    window.showNormal()
                if window.isVisible():
                    window.raise_()
                    window.activateWindow()
                else:
                    window.animate_show()
                client.disconnectFromServer()
                client.deleteLater()
            client.readyRead.connect(_on_ready)
        server.newConnection.connect(_on_new_connection)
        window._single_instance_server = server
    # Ensure global hotkey works even when hidden
    window._hotkey_filter = HotkeyFilter(window)
    app.installNativeEventFilter(window._hotkey_filter)
    window.register_global_hotkey()
    force_notice = "--show-notice" in sys.argv or "--force-notice" in sys.argv
    first_time = not window.settings.get("notice_accepted", False)
    force_show = "--show-notice" in sys.argv or "--force-show" in sys.argv or first_time
    force_topmost = first_time or force_notice
    def _force_foreground():
        try:
            window.showNormal()
            window.raise_()
            window.activateWindow()
        except Exception:
            pass
    if force_topmost:
        window._set_temp_always_on_top(True)
    if window.start_minimized and not force_show:
        window.hide()
    else:
        window.animate_show()
        if force_show:
            QTimer.singleShot(350, _force_foreground)
    QTimer.singleShot(500, window.launch_startup_apps)
    
    sys.exit(app.exec())
