import os
import sys

APP_NAME = "Portable X"
APP_AUTHOR = "Jacob Nathan"

VERSION_FILE_NAME = "version.txt"
DEFAULT_APP_VERSION = "1.1.0"

# GitHub update source (optional).
# You can override this at runtime via settings.ini:
#   [Updates]
#   Repo = owner/repo
DEFAULT_GITHUB_REPO = "JNathan34/Portable-X"

DEFAULT_UPDATE_CHECK_INTERVAL_HOURS = 24


def get_base_dir():
    # When frozen, assets live alongside the .exe.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def read_version_file(base_dir=None):
    base_dir = base_dir or get_base_dir()
    path = os.path.join(base_dir, VERSION_FILE_NAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def get_app_version(base_dir=None):
    return read_version_file(base_dir) or DEFAULT_APP_VERSION


def get_app_display_name(version=None):
    version = version or get_app_version()
    return f"{APP_NAME} v{version}"


def get_app_about_text(version=None):
    version = version or get_app_version()
    return f"Version: {version}\nAuthor: {APP_AUTHOR}"


# Convenience constants (computed once at import time).
APP_VERSION = get_app_version()
APP_DISPLAY_NAME = get_app_display_name(APP_VERSION)
APP_ABOUT_TEXT = get_app_about_text(APP_VERSION)
