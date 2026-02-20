# Portable X
Created by Jacob Nathan.

Portable X is a portable application launcher and organizer for your PortableApps setup. It helps you scan, manage, and launch apps from your drive, and provides system-style folders and settings for your portable environment.

## Features
- Scans `PortableApps\` and reads `appinfo.ini` metadata when available
- Categories, favorites, renames, and hidden apps
- Search and list/grid app views
- Settings and data stored in `PortableApps\PortableX\Data` for portability
- Installer creates portable user folders (Documents, Downloads, Music, Pictures, Videos) with custom icons

## Requirements (from source)
- Windows 10/11
- Python 3.11
- PySide6

## Quick Start
1. Use the installer (`Portable X Installer.exe`) to create the portable folder layout.
2. Launch `PortableX.exe`.
3. Place PortableApps in the `PortableApps\` folder and Portable X will scan them automatically.

## In-App Notice (Settings/About Popup)
Recommended USB setup:
- Use USB 3.0/3.1/3.2 or USB-C drives for the best speed.
- Aim for at least 100 MB/s read and 50 MB/s write for smooth app launching.
- Avoid very slow USB 2.0 drives, as they can cause long load times.

Hotkey: Press Ctrl + R to open/close the menu.

This software is for your personal use only. You may not share, copy, redistribute, or claim any part of this program as your own. Do not remove this notice.

All rights are reserved by the creator.

## About (In-App)
- Software: Portable X v1.1.0
- Version: 1.1.0
- Author: Jacob Nathan

## Build / Packaging
From the project root:
```powershell
python -m PyInstaller PortableX.spec
tools\innosetup\ISCC.exe installer.iss
```
