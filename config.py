import os
import sys
import shutil
from PySide6.QtGui import QColor

WINDOW_WIDTH = 424
WINDOW_HEIGHT = 640
BORDER_RADIUS = 10

# Colors (mutable for theme switching)
COLOR_BG_START = QColor("#0e1014")
COLOR_BG_END = QColor("#1b1f26")
COLOR_ACCENT = QColor("#0078d4")  # Windows Blue-ish
COLOR_TEXT_MAIN = QColor("#ffffff")
COLOR_TEXT_SUB = QColor("#a0a0a0")
COLOR_GLASS_WHITE = QColor(255, 255, 255, 10)
COLOR_GLASS_BORDER = QColor(255, 255, 255, 30)
COLOR_HOVER = QColor(255, 255, 255, 20)
COLOR_PRESSED = QColor(255, 255, 255, 40)

_THEME_DARK = {
    "bg_start": "#0e1014",
    "bg_end": "#1b1f26",
    "accent": "#0078d4",
    "text_main": "#ffffff",
    "text_sub": "#a0a0a0",
    "glass_white": (255, 255, 255, 10),
    "glass_border": (255, 255, 255, 30),
    "hover": (255, 255, 255, 20),
    "pressed": (255, 255, 255, 40),
}

_THEME_LIGHT = {
    "bg_start": "#FDFDFD",
    "bg_end": "#FDFDFD",
    "accent": "#0067c0",
    "text_main": "#101318",
    "text_sub": "#4d5561",
    "glass_white": (0, 0, 0, 8),
    "glass_border": (0, 0, 0, 25),
    "hover": (0, 0, 0, 15),
    "pressed": (0, 0, 0, 30),
}

def _set_named(qcolor, value):
    qcolor.setNamedColor(value)

def _set_rgba(qcolor, rgba):
    qcolor.setRgb(rgba[0], rgba[1], rgba[2], rgba[3])

def apply_theme(mode):
    """
    Mutates shared QColor instances so modules with `from config import *`
    can pick up new colors when widgets are rebuilt.
    """
    theme = _THEME_DARK if mode == "dark" else _THEME_LIGHT

    _set_named(COLOR_BG_START, theme["bg_start"])
    _set_named(COLOR_BG_END, theme["bg_end"])
    _set_named(COLOR_ACCENT, theme["accent"])
    _set_named(COLOR_TEXT_MAIN, theme["text_main"])
    _set_named(COLOR_TEXT_SUB, theme["text_sub"])
    _set_rgba(COLOR_GLASS_WHITE, theme["glass_white"])
    _set_rgba(COLOR_GLASS_BORDER, theme["glass_border"])
    _set_rgba(COLOR_HOVER, theme["hover"])
    _set_rgba(COLOR_PRESSED, theme["pressed"])

def apply_accent_color(value):
    if value:
        _set_named(COLOR_ACCENT, value)

def apply_text_color(value):
    if value:
        color = QColor(value)
        _set_named(COLOR_TEXT_MAIN, color.name())
        COLOR_TEXT_SUB.setRgb(color.red(), color.green(), color.blue(), 160)

def qcolor_to_rgba(color):
    r, g, b, a = color.getRgb()
    return f"rgba({r}, {g}, {b}, {a})"

FONT_FAMILY = "Segoe UI"

QUICK_BUTTONS = [
    "Documents", "Music", "Pictures", "Videos", "Downloads",
    "Explore", "Apps", "Settings", "Search", "Help"
]

def normalize_category_name(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return " ".join(text.split())

_NO_CATEGORY_ALIASES = {
    "none",
    "no category",
    "uncategorized",
}

_CATEGORY_ALIASES = {
    "graphics & pictures": "Graphics and Pictures",
    "music & video": "Music and Video",
    "windows utilities": "Utilities",
}

def resolve_category_name(value, allowed=None):
    name = normalize_category_name(value)
    if not name:
        return "No Category"
    lowered = name.lower()
    if lowered in _NO_CATEGORY_ALIASES:
        return "No Category"
    canonical = _CATEGORY_ALIASES.get(lowered, name)
    if allowed is None:
        return canonical
    allowed_map = {}
    for item in allowed:
        norm = normalize_category_name(item)
        if not norm:
            continue
        allowed_map[norm.lower()] = item
    candidates = [canonical, name]
    if "&" in name:
        candidates.append(normalize_category_name(name.replace("&", "and")))
    if " and " in lowered:
        candidates.append(normalize_category_name(name.replace(" and ", " & ")))
    for cand in candidates:
        key = normalize_category_name(cand).lower()
        if key in allowed_map:
            return allowed_map[key]
    return "No Category"

def get_category_icon_path(category):
    name = normalize_category_name(category)
    if not name:
        return ""
    base_dir = get_base_dir()
    icon_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Graphics", "categories")
    lowered = name.lower()
    if lowered in _NO_CATEGORY_ALIASES:
        lookup = "Other"
    else:
        lookup = _CATEGORY_ALIASES.get(lowered, name)

    candidates = [lookup, name]
    if "&" in name:
        candidates.append(normalize_category_name(name.replace("&", "and")))
    if " and " in name.lower():
        candidates.append(normalize_category_name(name.replace(" and ", " & ")))

    for cand in candidates:
        if not cand:
            continue
        path = os.path.join(icon_dir, f"{cand}.png")
        if os.path.exists(path):
            return path

    fallback = os.path.join(icon_dir, "Other.png")
    if os.path.exists(fallback):
        return fallback
    return ""

def get_base_dir():
    # When frozen, assets live alongside the .exe.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_data_dir():
    base_dir = get_base_dir()
    data_dir = os.path.join(base_dir, "PortableApps", "PortableX", "Data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_settings_path():
    data_dir = get_data_dir()
    new_path = os.path.join(data_dir, "settings.ini")
    legacy_path = os.path.join(get_base_dir(), "PortableApps", "PortableX", "settings.ini")
    if not os.path.exists(new_path) and os.path.exists(legacy_path):
        try:
            os.replace(legacy_path, new_path)
        except Exception:
            try:
                shutil.copy2(legacy_path, new_path)
            except Exception:
                pass
    return new_path
