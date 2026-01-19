import os
import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    """
    Hardcoded extraction path mode:
    If running as an EXE (stub or extracted python.exe), always use:
        %TEMP%\PyPongOnline
    Otherwise, use dev paths.
    """

    # Detect "running as an EXE" in ALL Nuitka modes:
    # - python.exe inside temp (Python-Onefile mode)
    # - frozen EXE (future)
    # - stub EXE
    if getattr(sys, "frozen", False) or "__compiled__" in globals() or sys.executable.lower().endswith(".exe"):
        temp_root = Path(os.environ["TEMP"]) / "PyPongOnline"
        return temp_root / relative

    # Development mode
    return (Path(__file__).resolve().parent / relative).resolve()
