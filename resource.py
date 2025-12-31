import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    """
    Get absolute path to resource, works for dev and PyInstaller exe.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(relative)
