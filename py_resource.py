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
    a = getattr(sys, "frozen", False)
    b = "__compiled__" in globals()
    c = sys.executable.lower().endswith("Online.exe")
    if a or b or c:
        temp_root = Path(os.environ["TEMP"]) / "PyPongOnline"
        return temp_root / relative

    # Development mode
    return (Path(__file__).resolve().parent / relative).resolve()
