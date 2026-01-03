# purely ai written, I just wanted something to aid the development :'3
"""
stagemaker.py
Place this file inside your project's `stages/` directory.

- Paint images into tiles when painting IDs
- Palette thumbnails are loaded from sprite frame files
- Supports sprites and ui_sprites resolution
"""

from __future__ import annotations
import os
import sys
import csv
import re
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, messagebox

# Pillow for image handling (thumbnails and canvas images)
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ---------- Paths and project imports ----------
STAGES_DIR = Path(__file__).resolve().parent           # .../PyPongOnline/stages
PROJECT_ROOT = STAGES_DIR.parent                       # .../PyPongOnline
CORE_DIR = PROJECT_ROOT / "core"

# Ensure project root and core dir are importable
for p in (str(PROJECT_ROOT), str(CORE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Try to import resource helper if present
try:
    from resource import resource_path
except Exception:
    resource_path = None

# Try to import render/config if present (not required for editor painting)
try:
    import render # type: ignore
    RENDER_AVAILABLE = True
except Exception:
    render = None
    RENDER_AVAILABLE = False

try:
    cfg_mod = importlib.import_module("config")
    config = getattr(cfg_mod, "config", None)
except Exception:
    try:
        cfg_mod = importlib.import_module("config")
        config = getattr(cfg_mod, "config", None)
    except Exception:
        config = None

# ---------- Constants ----------
DEFAULT_COLS = 35
DEFAULT_ROWS = 23
CELL_SIZE = 28            # pixel size of editor tile (image will be scaled to this)
CELL_PAD = 2
PALETTE_THUMB_SIZE = (48, 48)

# Extended Color schemes
COLOR_SCHEMES = {
    "Default": {
        "empty": "#ffffff",
        "filled": "#e8ffe8",
        "grid": "#888888",
        "canvas_bg": "#ffffff",
        "palette_bg": "#f0f0f0",
        "palette_text": "#000000",
        "palette_frame": "#e0e0e0",
        "button_bg": "#f0f0f0",
        "button_fg": "#000000",
        "status_bg": "#f0f0f0",
        "status_fg": "#000000"
    },
    "Dark": {
        "empty": "#2b2b2b",
        "filled": "#3d5a3d",
        "grid": "#555555",
        "canvas_bg": "#1e1e1e",
        "palette_bg": "#2d2d2d",
        "palette_text": "#ffffff",
        "palette_frame": "#3d3d3d",
        "button_bg": "#3d3d3d",
        "button_fg": "#ffffff",
        "status_bg": "#252525",
        "status_fg": "#cccccc"
    },
    "Ocean": {
        "empty": "#e6f3ff",
        "filled": "#b3d9ff",
        "grid": "#6699cc",
        "canvas_bg": "#f0f8ff",
        "palette_bg": "#e6f2ff",
        "palette_text": "#003366",
        "palette_frame": "#cce0ff",
        "button_bg": "#d9ecff",
        "button_fg": "#003366",
        "status_bg": "#e6f2ff",
        "status_fg": "#003366"
    },
    "Sunset": {
        "empty": "#fff5e6",
        "filled": "#ffd9b3",
        "grid": "#cc8866",
        "canvas_bg": "#fffaf0",
        "palette_bg": "#fff0d9",
        "palette_text": "#663300",
        "palette_frame": "#ffddb3",
        "button_bg": "#ffe6cc",
        "button_fg": "#663300",
        "status_bg": "#fff0d9",
        "status_fg": "#663300"
    },
    "Neon": {
        "empty": "#1a1a2e",
        "filled": "#16213e",
        "grid": "#0f3460",
        "canvas_bg": "#0a0a1a",
        "palette_bg": "#16213e",
        "palette_text": "#e94560",
        "palette_frame": "#0f3460",
        "button_bg": "#1a1a2e",
        "button_fg": "#e94560",
        "status_bg": "#16213e",
        "status_fg": "#e94560"
    }
}

# ---------- .stage IO ----------
def parse_stage_file(path: str) -> Tuple[Dict[int, Optional[str]], List[List[str]]]:
    entity_map: Dict[int, Optional[str]] = {}
    grid: List[List[str]] = []
    section = None
    with open(path, 'r', encoding='utf-8') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.lower() == 'entity_map':
                section = 'entity_map'
                continue
            if line.lower() == 'grid':
                section = 'grid'
                continue
            if section == 'entity_map':
                m = re.match(r'(\d+)\s*:\s*(.+)', line)
                if m:
                    idx = int(m.group(1))
                    val = m.group(2).strip()
                    entity_map[idx] = None if val.lower() == 'none' else val
            elif section == 'grid':
                parts = [p.strip() for p in line.split(',')]
                grid.append(parts)
            else:
                continue
    return entity_map, grid

def write_stage_file(path: str, entity_map: Dict[int, Optional[str]], grid: List[List[str]]):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write("# Generated by stagemaker.py\n")
        fh.write("entity_map\n")
        for k in sorted(entity_map.keys()):
            v = entity_map[k]
            fh.write(f"{k}: {v if v is not None else 'None'}\n")
        fh.write("\ngrid\n")
        for row in grid:
            fh.write(", ".join(row) + "\n")

# ---------- class resolution and image helpers ----------
def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def resolve_class(dotted: Optional[str]):
    if dotted is None:
        return None
    dotted = dotted.strip()
    if dotted.lower() == 'none':
        return None
    module_name, _, class_name = dotted.rpartition('.')
    if not module_name:
        raise ImportError(f"Invalid dotted path: {dotted}")

    # try import
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        # try load from project files
        module_path = PROJECT_ROOT / (module_name.replace('.', '/') + '.py')
        if module_path.exists():
            module = _load_module_from_path(module_name, module_path)
        else:
            module_path = STAGES_DIR / (module_name.replace('.', '/') + '.py')
            if module_path.exists():
                module = _load_module_from_path(module_name, module_path)
            else:
                raise

    # direct attribute
    if hasattr(module, class_name):
        return getattr(module, class_name)

    # case-insensitive search
    import inspect
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if name.lower() == class_name.lower():
            return obj

    # try common sibling modules
    for alt in ("sprites", "sprites", "ui_sprites", "ui_sprites"):
        if alt == module_name:
            continue
        try:
            alt_mod = importlib.import_module(alt)
        except Exception:
            continue
        if hasattr(alt_mod, class_name):
            return getattr(alt_mod, class_name)
        for name, obj in inspect.getmembers(alt_mod, inspect.isclass):
            if name.lower() == class_name.lower():
                return obj

    raise AttributeError(f"module '{module_name}' has no attribute '{class_name}'")

def get_first_frame_path_from_class(cls) -> Optional[Path]:
    inst = None
    try:
        inst = cls()
    except Exception:
        inst = cls if hasattr(cls, 'spritesheet') else None
    if inst is None:
        return None
    spritesheet = getattr(inst, 'spritesheet', None)
    if not spritesheet:
        return None
    try:
        first_anim = spritesheet[0]
        first_frame = first_anim[0]
        return Path(first_frame)
    except Exception:
        return None

def resolve_resource_path(p: str) -> Path:
    if resource_path is not None:
        try:
            return resource_path(p)
        except Exception:
            pass
    return (PROJECT_ROOT / p).resolve()

def load_photoimage_from_path(path: Path, size: Tuple[int,int]) -> Optional[tk.PhotoImage]:
    """
    Load an image file into a Tk PhotoImage scaled to `size`.
    Uses Pillow if available; otherwise attempts Tk's PhotoImage (limited formats).
    """
    if not path or not path.exists():
        return None
    try:
        if PIL_AVAILABLE:
            img = Image.open(path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        else:
            # fallback: try Tk PhotoImage (PNG only typically)
            return tk.PhotoImage(file=str(path))
    except Exception:
        return None

# ---------- UI helpers ----------
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

# ---------- Main editor ----------
class StageMaker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StageMaker (.stage editor)")
        self.geometry("1200x760")
        self.minsize(900, 500)

        # model
        self.cols = DEFAULT_COLS
        self.rows = DEFAULT_ROWS
        self.grid_data: List[List[str]] = [['0' for _ in range(self.cols)] for __ in range(self.rows)]
        self.entity_map: Dict[int, Optional[str]] = {0: None}
        self.current_filename: Optional[str] = None
        self.active_id = 1
        self.thumbnails: Dict[int, tk.PhotoImage] = {}   # palette thumbnails (larger)
        self.id_images: Dict[int, tk.PhotoImage] = {}    # tile-sized images (CELL_SIZE)
        self.cell_canvas_images: Dict[Tuple[int,int], int] = {}  # canvas image item ids keyed by (r,c)
        self.left_dragging = False
        self.right_dragging = False
        self._prev_active_id = None
        self.current_color_scheme = "Default"
        self.show_grid_lines = tk.BooleanVar(value=False)  # Grid lines toggle
        self.show_centre_grid = tk.BooleanVar(value=False)  # Centre grid lines toggle

        # top controls
        top_frame = ttk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)
        
        ttk.Button(top_frame, text="Load...", command=self.load_file_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_frame, text="Save As...", command=self.save_as).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_frame, text="Save", command=self.save_current).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_frame, text="New Template", command=self.new_template_dialog).pack(side=tk.LEFT, padx=8)
        ttk.Button(top_frame, text="Export .stage", command=self.export_stage).pack(side=tk.LEFT, padx=8)
        
        # Separator
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=12, fill=tk.Y)
        
        # Grid lines toggle
        ttk.Checkbutton(top_frame, text="Show Grid", variable=self.show_grid_lines,
                       command=self.toggle_grid_lines).pack(side=tk.LEFT, padx=4)
        
        # Centre grid lines toggle
        ttk.Checkbutton(top_frame, text="Centre Grid Lines", variable=self.show_centre_grid,
                       command=self.toggle_centre_grid).pack(side=tk.LEFT, padx=4)
        
        # Separator
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=12, fill=tk.Y)
        
        # Color scheme selector
        ttk.Label(top_frame, text="Color Scheme:").pack(side=tk.LEFT, padx=(16, 4))
        self.scheme_var = tk.StringVar(value=self.current_color_scheme)
        scheme_menu = ttk.OptionMenu(top_frame, self.scheme_var, self.current_color_scheme, 
                                      *COLOR_SCHEMES.keys(), 
                                      command=self.change_color_scheme)
        scheme_menu.pack(side=tk.LEFT, padx=4)

        # main paned window
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # left: canvas area
        canvas_container = ttk.Frame(paned)
        paned.add(canvas_container, weight=3)
        self.canvas = tk.Canvas(canvas_container, bg='white')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.grid(row=0, column=1, sticky='ns')
        hbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        # canvas events
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        # right: palette
        palette_container = ttk.Frame(paned, width=320)
        paned.add(palette_container, weight=1)
        
        # Palette header
        self.palette_header = ttk.Label(palette_container, text="Entity Palette", 
                                       font=('Segoe UI', 10, 'bold'))
        self.palette_header.pack(anchor='nw', padx=6, pady=(6,0))
        
        self.palette_frame = ScrollableFrame(palette_container)
        self.palette_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # status
        self.status = ttk.Label(self, text="", anchor='w')
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # Apply initial color scheme
        self.apply_color_scheme()
        
        # initial
        self.redraw()
        self.rebuild_palette()
        self.set_status(f"Ready. Use Load... to open a file from {STAGES_DIR.name}")

    # ---------- color scheme ----------
    def apply_color_scheme(self):
        """Apply current color scheme to all UI elements"""
        colors = self.get_colors()
        
        # Apply to main window
        self.configure(bg=colors["palette_bg"])
        
        # Apply to canvas
        self.canvas.configure(bg=colors["canvas_bg"])
        
        # Apply to palette area
        self.palette_frame.configure(style='Palette.TFrame')
        self.palette_frame.scrollable_frame.configure(style='Palette.TFrame')
        self.palette_header.configure(style='Palette.TLabel')
        
        # Apply to status bar
        self.status.configure(style='Status.TLabel')
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure('Palette.TFrame', background=colors["palette_bg"])
        self.style.configure('Palette.TLabel', 
                           background=colors["palette_bg"], 
                           foreground=colors["palette_text"])
        self.style.configure('Status.TLabel',
                           background=colors["status_bg"],
                           foreground=colors["status_fg"])
        
        # Configure button styles
        self.style.configure('TButton',
                           background=colors["button_bg"],
                           foreground=colors["button_fg"])
        self.style.map('TButton',
                      background=[('active', colors["filled"])],
                      foreground=[('active', colors["palette_text"])])
        
        # Configure scrollbar
        self.style.configure('TScrollbar',
                           background=colors["palette_bg"],
                           troughcolor=colors["palette_frame"])
        
        # Configure option menu
        self.style.configure('TMenubutton',
                           background=colors["button_bg"],
                           foreground=colors["button_fg"])
        
        # Configure checkbutton
        self.style.configure('TCheckbutton',
                           background=colors["palette_bg"],
                           foreground=colors["palette_text"])
        
        # Redraw everything
        self.redraw()
        self.rebuild_palette()

    def change_color_scheme(self, scheme_name):
        self.current_color_scheme = scheme_name
        self.apply_color_scheme()
        self.set_status(f"Color scheme changed to: {scheme_name}")

    def get_colors(self):
        return COLOR_SCHEMES.get(self.current_color_scheme, COLOR_SCHEMES["Default"])

    # ---------- grid lines toggles ----------
    def toggle_grid_lines(self):
        self.redraw()

    def toggle_centre_grid(self):
        self.redraw()

    # ---------- file handling ----------
    def load_file_dialog(self):
        path = filedialog.askopenfilename(
            parent=self,
            initialdir=str(STAGES_DIR),
            title="Load Stage/CSV File",
            filetypes=[("Stage files", "*.stage"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        self.load_file(path)

    def load_file(self, path):
        path = Path(path)
        try:
            if path.suffix.lower() == '.stage':
                entity_map, grid = parse_stage_file(str(path))
                if grid and any(not cell.isdigit() for cell in grid[0]):
                    headers = grid[0]
                    data_rows = grid[1:]
                else:
                    headers = None
                    data_rows = grid
                ncols = len(data_rows[0]) if data_rows else (len(headers) if headers else self.cols)
                nrows = len(data_rows)
                normalized = []
                for r in data_rows:
                    row = [ (cell if cell != '' else '0') for cell in r[:ncols] ]
                    if len(row) < ncols:
                        row += ['0'] * (ncols - len(row))
                    normalized.append(row)
                if nrows == 0:
                    normalized = [['0']*ncols for _ in range(self.rows)]
                    nrows = self.rows
                self.cols = ncols
                self.rows = nrows
                self.grid_data = normalized
                self.entity_map = entity_map or {0: None}
                self.current_filename = str(path)
                self.set_status(f"Loaded {path.name} ({self.cols}×{self.rows})")
                self.rebuild_palette()
                self.redraw()
            else:
                with open(path, newline='') as fh:
                    reader = csv.reader(fh)
                    rows = list(reader)
                if not rows:
                    raise ValueError("Empty CSV")
                headers = rows[0]
                data_rows = rows[1:]
                ncols = len(headers)
                nrows = len(data_rows)
                grid = []
                for r in data_rows:
                    row = [ (cell.strip() if cell.strip()!='' else '0') for cell in r[:ncols] ]
                    if len(row) < ncols:
                        row += ['0'] * (ncols - len(row))
                    grid.append(row)
                if nrows == 0:
                    grid = [['0']*ncols for _ in range(self.rows)]
                    nrows = self.rows
                self.cols = ncols
                self.rows = nrows
                self.grid_data = grid
                self.entity_map = {0: None}
                self.current_filename = str(path)
                self.set_status(f"Loaded CSV {path.name} ({self.cols}×{self.rows})")
                self.rebuild_palette()
                self.redraw()
        except Exception as e:
            messagebox.showerror("Load error", f"Could not load {path.name}:\n{e}", parent=self)

    def save_current(self):
        if not self.current_filename:
            self.save_as()
            return
        path = Path(self.current_filename)
        if path.suffix.lower() == '.stage':
            write_stage_file(str(path), self.entity_map, self.grid_data)
            self.set_status(f"Saved {path.name}")
        else:
            with open(path, 'w', newline='') as fh:
                writer = csv.writer(fh)
                for r in range(self.rows):
                    writer.writerow(self.grid_data[r])
            self.set_status(f"Saved CSV {path.name}")

    def save_as(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            initialdir=str(STAGES_DIR),
            defaultextension=".stage",
            filetypes=[("Stage files","*.stage"), ("CSV files","*.csv")]
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() == '.stage':
            if not self.entity_map:
                self.entity_map = {0: None}
            write_stage_file(str(path), self.entity_map, self.grid_data)
        else:
            with open(path, 'w', newline='') as fh:
                writer = csv.writer(fh)
                for r in range(self.rows):
                    writer.writerow(self.grid_data[r])
        self.current_filename = str(path)
        self.set_status(f"Saved {path.name}")

    def export_stage(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            initialdir=str(STAGES_DIR),
            defaultextension=".stage",
            filetypes=[("Stage files","*.stage")]
        )
        if not path:
            return
        path = Path(path)
        if not self.entity_map:
            self.entity_map = {0: None}
        write_stage_file(str(path), self.entity_map, self.grid_data)
        self.set_status(f"Exported {path.name}")

    # ---------- template / grid ops ----------
    def new_template_dialog(self):
        cols = simpledialog.askinteger("Columns", "Number of columns:", 
                                       parent=self, initialvalue=self.cols, minvalue=1, maxvalue=200)
        if cols is None:
            return
        rows = simpledialog.askinteger("Rows", "Number of rows:", 
                                       parent=self, initialvalue=self.rows, minvalue=1, maxvalue=200)
        if rows is None:
            return
        self.cols = cols
        self.rows = rows
        self.grid_data = [['0' for _ in range(self.cols)] for __ in range(self.rows)]
        self.entity_map = {0: None}
        self.current_filename = None
        self.set_status(f"New template {self.cols}×{self.rows}")
        self.rebuild_palette()
        self.redraw()

    def clear_grid(self):
        for r in range(self.rows):
            for c in range(self.cols):
                self.grid_data[r][c] = '0'
        # remove canvas images
        for key, item in list(self.cell_canvas_images.items()):
            try:
                self.canvas.delete(item)
            except Exception:
                pass
        self.cell_canvas_images.clear()
        self.redraw()

    # ---------- canvas drawing ----------
    def redraw(self):
        # clear canvas and redraw cells and any images
        colors = self.get_colors()
        width = self.cols * (CELL_SIZE + CELL_PAD) + CELL_PAD
        height = self.rows * (CELL_SIZE + CELL_PAD) + CELL_PAD
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0,0,width,height))
        self.cell_canvas_images.clear()

        # Draw cells
        for r in range(self.rows):
            for c in range(self.cols):
                x0 = c * (CELL_SIZE + CELL_PAD) + CELL_PAD
                y0 = r * (CELL_SIZE + CELL_PAD) + CELL_PAD
                x1 = x0 + CELL_SIZE
                y1 = y0 + CELL_SIZE
                val = str(self.grid_data[r][c]) if self.grid_data[r][c] != '' else '0'
                
                # background colour - no outline (grid lines removed)
                bg = colors["empty"] if val == '0' else colors["filled"]
                outline_color = colors["grid"] if self.show_grid_lines.get() else bg
                self.canvas.create_rectangle(x0, y0, x1, y1, 
                                           fill=bg, outline=outline_color, width=1)
                
                # draw image if available for this id
                try:
                    idx = int(val)
                except Exception:
                    idx = 0
                if idx != 0 and idx in self.id_images:
                    img = self.id_images[idx]
                    cx = x0 + CELL_SIZE//2
                    cy = y0 + CELL_SIZE//2
                    item = self.canvas.create_image(cx, cy, image=img)
                    self.cell_canvas_images[(r,c)] = item
                else:
                    # draw text id for visibility
                    text_color = "#ffffff" if self.current_color_scheme in ["Dark", "Neon"] else "#000000"
                    self.canvas.create_text(x0 + CELL_SIZE//2, y0 + CELL_SIZE//2, 
                                          text=val, font=('Consolas', 10), fill=text_color)

        # Draw centre grid lines if enabled
        if self.show_centre_grid.get():
            self.draw_centre_grid_lines()

        fname = Path(self.current_filename).name if self.current_filename else '(unsaved)'
        self.set_status(f"Grid {self.cols}×{self.rows} | Active ID {self.active_id} | File: {fname}")

    def draw_centre_grid_lines(self):
        """Draw grid lines at the centre of cells"""
        colors = self.get_colors()
        
        # Vertical centre lines
        for c in range(self.cols + 1):
            x = c * (CELL_SIZE + CELL_PAD) + CELL_PAD + CELL_SIZE // 2
            y1 = 0
            y2 = self.rows * (CELL_SIZE + CELL_PAD) + CELL_PAD
            # Draw dashed line
            dash_pattern = (2, 2)
            self.canvas.create_line(x, y1, x, y2, 
                                  fill=colors["grid"], 
                                  dash=dash_pattern,
                                  width=1)
        
        # Horizontal centre lines
        for r in range(self.rows + 1):
            y = r * (CELL_SIZE + CELL_PAD) + CELL_PAD + CELL_SIZE // 2
            x1 = 0
            x2 = self.cols * (CELL_SIZE + CELL_PAD) + CELL_PAD
            # Draw dashed line
            dash_pattern = (2, 2)
            self.canvas.create_line(x1, y, x2, y, 
                                  fill=colors["grid"], 
                                  dash=dash_pattern,
                                  width=1)

    def canvas_coords_to_cell(self, x, y):
        c = int((x - CELL_PAD) // (CELL_SIZE + CELL_PAD))
        r = int((y - CELL_PAD) // (CELL_SIZE + CELL_PAD))
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return r, c
        return None, None

    def paint_cell(self, r, c, id_token):
        if r is None or c is None:
            return
        token = str(id_token)
        self.grid_data[r][c] = token
        
        colors = self.get_colors()
        # compute coords
        x0 = c * (CELL_SIZE + CELL_PAD) + CELL_PAD
        y0 = r * (CELL_SIZE + CELL_PAD) + CELL_PAD
        x1 = x0 + CELL_SIZE
        y1 = y0 + CELL_SIZE
        
        # delete existing items in that cell
        if (r,c) in self.cell_canvas_images:
            try:
                self.canvas.delete(self.cell_canvas_images[(r,c)])
            except Exception:
                pass
            del self.cell_canvas_images[(r,c)]
        
        # draw rectangle background - no outline (grid lines removed)
        bg = colors["empty"] if token == '0' else colors["filled"]
        outline_color = colors["grid"] if self.show_grid_lines.get() else bg
        self.canvas.create_rectangle(x0, y0, x1, y1, 
                                   fill=bg, outline=outline_color, width=1)
        
        # draw image if available
        try:
            idx = int(token)
        except Exception:
            idx = 0
        if idx != 0 and idx in self.id_images:
            img = self.id_images[idx]
            cx = x0 + CELL_SIZE//2
            cy = y0 + CELL_SIZE//2
            item = self.canvas.create_image(cx, cy, image=img)
            self.cell_canvas_images[(r,c)] = item
        else:
            # draw text id
            text_color = "#ffffff" if self.current_color_scheme in ["Dark", "Neon"] else "#000000"
            self.canvas.create_text(x0 + CELL_SIZE//2, y0 + CELL_SIZE//2, 
                                  text=token, font=('Consolas', 10), fill=text_color)

    # ---------- painting events ----------
    def on_left_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r, c = self.canvas_coords_to_cell(x, y)
        if r is None:
            return
        self.left_dragging = True
        self.paint_cell(r, c, self.active_id)

    def on_left_drag(self, event):
        if not self.left_dragging:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r, c = self.canvas_coords_to_cell(x, y)
        if r is None:
            return
        self.paint_cell(r, c, self.active_id)

    def on_left_release(self, event):
        self.left_dragging = False

    def on_right_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r, c = self.canvas_coords_to_cell(x, y)
        if r is None:
            return
        self._prev_active_id = self.active_id
        self.active_id = 0
        self.right_dragging = True
        self.paint_cell(r, c, '0')

    def on_right_drag(self, event):
        if not self.right_dragging:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        r, c = self.canvas_coords_to_cell(x, y)
        if r is None:
            return
        self.paint_cell(r, c, '0')

    def on_right_release(self, event):
        self.right_dragging = False
        if self._prev_active_id is not None:
            self.active_id = self._prev_active_id
            self._prev_active_id = None

    # ---------- palette ----------
    def rebuild_palette(self):
        # clear palette widgets
        for child in self.palette_frame.scrollable_frame.winfo_children():
            child.destroy()
        self.thumbnails.clear()
        self.id_images.clear()

        if 0 not in self.entity_map:
            self.entity_map[0] = None

        keys = sorted(self.entity_map.keys())
        row = 0
        for k in keys:
            dotted = self.entity_map[k]
            label_text = f"{k}: {dotted if dotted is not None else 'None'}"
            frame = ttk.Frame(self.palette_frame.scrollable_frame, padding=(4,4))
            frame.grid(row=row, column=0, sticky='ew', pady=2)
            frame.columnconfigure(1, weight=1)

            # thumbnail area
            thumb_widget = ttk.Label(frame, text=' ')
            thumb_widget.grid(row=0, column=0, rowspan=2, sticky='nw')
            thumb = None
            tile_img = None
            if dotted:
                try:
                    cls = resolve_class(dotted)
                    frame_path = get_first_frame_path_from_class(cls)
                    if frame_path:
                        if not frame_path.is_absolute():
                            frame_path = resolve_resource_path(str(frame_path))
                        if frame_path.exists():
                            # palette thumbnail (larger)
                            thumb = load_photoimage_from_path(frame_path, PALETTE_THUMB_SIZE)
                            # tile-sized image for painting
                            tile_img = load_photoimage_from_path(frame_path, (CELL_SIZE, CELL_SIZE))
                except Exception:
                    thumb = None
                    tile_img = None

            if thumb:
                self.thumbnails[k] = thumb
                thumb_widget.configure(image=thumb)
                thumb_widget.image = thumb
            else:
                colors = self.get_colors()
                ph = tk.Canvas(frame, width=PALETTE_THUMB_SIZE[0], height=PALETTE_THUMB_SIZE[1], 
                             bg=colors["palette_frame"], highlightthickness=1,
                             highlightbackground=colors["grid"])
                ph.grid(row=0, column=0, rowspan=2, sticky='nw')
                ph.create_text(PALETTE_THUMB_SIZE[0]//2, PALETTE_THUMB_SIZE[1]//2, 
                             text=str(k), font=('Consolas', 10), fill=colors["palette_text"])

            if tile_img:
                self.id_images[k] = tile_img

            # Apply color scheme to palette labels
            colors = self.get_colors()
            label = ttk.Label(frame, text=label_text, font=('Consolas', 10))
            label.configure(style='Palette.TLabel')
            label.grid(row=0, column=1, sticky='w', padx=6)
            
            btn_frame = ttk.Frame(frame)
            btn_frame.grid(row=1, column=1, sticky='w', padx=6, pady=(4,0))
            
            select_btn = ttk.Button(btn_frame, text="Select", 
                                   command=lambda id=k: self.set_active_id(id))
            select_btn.pack(side=tk.LEFT, padx=(0,6))
            
            edit_btn = ttk.Button(btn_frame, text="Edit", 
                                 command=lambda id=k: self.edit_entity_map_entry(id))
            edit_btn.pack(side=tk.LEFT, padx=(0,6))
            
            row += 1

        bottom = ttk.Frame(self.palette_frame.scrollable_frame, padding=(4,8))
        bottom.grid(row=row, column=0, sticky='ew', pady=(8,4))
        
        add_btn = ttk.Button(bottom, text="Add ID", command=self.add_new_id)
        add_btn.pack(side=tk.LEFT, padx=(0,6))
        
        validate_btn = ttk.Button(bottom, text="Validate Grid", command=self.validate_grid)
        validate_btn.pack(side=tk.LEFT)
        
        # Apply color scheme to bottom frame
        colors = self.get_colors()
        bottom.configure(style='Palette.TFrame')
        
        # After rebuilding palette, update all cells on canvas that use these IDs
        self.update_canvas_cells()

    def update_canvas_cells(self):
        """Update all canvas cells to reflect current id_images"""
        for r in range(self.rows):
            for c in range(self.cols):
                val = str(self.grid_data[r][c])
                try:
                    idx = int(val)
                except Exception:
                    idx = 0
                
                if idx != 0:
                    # Remove old image if exists
                    if (r,c) in self.cell_canvas_images:
                        try:
                            self.canvas.delete(self.cell_canvas_images[(r,c)])
                        except Exception:
                            pass
                        del self.cell_canvas_images[(r,c)]
                    
                    # Add new image if available
                    if idx in self.id_images:
                        x0 = c * (CELL_SIZE + CELL_PAD) + CELL_PAD
                        y0 = r * (CELL_SIZE + CELL_PAD) + CELL_PAD
                        cx = x0 + CELL_SIZE//2
                        cy = y0 + CELL_SIZE//2
                        img = self.id_images[idx]
                        item = self.canvas.create_image(cx, cy, image=img)
                        self.cell_canvas_images[(r,c)] = item

    def set_active_id(self, id_val):
        self.active_id = id_val
        self.set_status(f"Active ID set to {id_val}")

    def add_new_id(self):
        idx = simpledialog.askinteger("New ID", "Integer ID to add:", 
                                      parent=self, minvalue=1, maxvalue=9999)
        if idx is None:
            return
        if idx in self.entity_map:
            messagebox.showinfo("Exists", f"ID {idx} already exists.", parent=self)
            return
        dotted = simpledialog.askstring("Mapping", 
                                       "Dotted class path (e.g. sprites.Squid) or 'None':", 
                                       parent=self, initialvalue="None")
        if dotted is None:
            return
        self.entity_map[idx] = None if dotted.strip().lower() == 'none' else dotted.strip()
        self.rebuild_palette()

    def edit_entity_map_entry(self, id_val):
        current = self.entity_map.get(id_val)
        new = simpledialog.askstring("Edit mapping", 
                                    f"ID {id_val} mapping (dotted path or None):", 
                                    parent=self, 
                                    initialvalue=(current if current is not None else "None"))
        if new is None:
            return
        self.entity_map[id_val] = None if new.strip().lower() == 'none' else new.strip()
        self.rebuild_palette()

    def validate_grid(self):
        missing = set()
        for r, row in enumerate(self.grid_data):
            for c, token in enumerate(row):
                try:
                    idx = int(token)
                except Exception:
                    continue
                if idx == 0:
                    continue
                if idx not in self.entity_map:
                    missing.add(idx)
        if missing:
            messagebox.showwarning("Validation", 
                                 f"Grid contains IDs not in entity_map: {sorted(missing)}", 
                                 parent=self)
        else:
            messagebox.showinfo("Validation", "All IDs present in entity_map.", parent=self)

    # ---------- helpers ----------
    def set_status(self, text):
        self.status.config(text=text)

# ---------- run ----------
if __name__ == "__main__":
    app = StageMaker()
    app.mainloop()