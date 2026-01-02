import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    """
    Resolve resource paths for:
    - Development
    - Nuitka (onefile & standalone)
    - PyInstaller
    """

    # PyInstaller onefile
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative

    # Nuitka frozen executable (onefile or standalone)
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        return Path(sys.executable).resolve().parent / relative

    # Development mode
    return Path(relative).resolve()
