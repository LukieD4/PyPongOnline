import py_numpyStub as np

from py_resource import resource_path
from py_sprites import Sprite
from py_numpyStub import copy as np_copy
from py_config import config
from py_input import inputManager

# Paths
sprites_dir = resource_path("sprites")
fonts_dir = sprites_dir / "font"

# -------------------------
# Constants and lookup tables
# -------------------------

# Map special characters and digits to class names (used by translateIntoClass)
TRANSLATION_TABLE = {
    "*": "Asterix",
    "-": "Dash",
    "_": "Under",
    "=": "Equal",
    "<": "Less",
    ">": "Great",
    "?": "Question",
    ".": "Fullstop",
    "/": "Slashfwd",
    "0": "Zero",
    "1": "One",
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
    "6": "Six",
    "7": "Seven",
    "8": "Eight",
    "9": "Nine",
}

# Abbreviations for long literal keys used by the text renderer in keyboard mode
ABBREVIATION_TABLE = {
    "escape": "esc",
    "return": "",
    # add more as needed: "backspace": "bsp", "enter": "ent", etc.
}

# Special sentinel used to represent a real space cell in the grid
REAL_SPACE = object()

# Inline colour codes used in text strings
colour_CODES = {
    ":": (255, 0, 0),      # red
    "#": (0, 255, 0),      # green
    "@": (255, 255, 0),    # yellow
    "&": None,             # reset / default
}

# -------------------------
# UI base class
# -------------------------

class UI(Sprite):
    """
    Base UI sprite class for rendering text into a fixed grid.
    Each cell holds either:
      - a glyph instance (subclass of UI created dynamically),
      - REAL_SPACE sentinel,
      - or None for empty.
    """

    def __init__(self):
        super().__init__()
        self.team = "ui"
        self.text_array = self.clear()
        self.previous_text_array = np_copy(self.text_array)
        self.current_colour = None
        self.justification = "centre"  # left, right, centre, full

    def clear(self):
        """Reset the text grid to empty (None) cells."""
        self.text_array = np.full((config.MAX_ROW, config.MAX_COL), None)
        return self.text_array

    def translateIntoClass(self, char: str):
        """
        Convert a single character into its corresponding glyph class instance.
        Returns REAL_SPACE for a space character, or None if no glyph exists.
        """
        if char == " ":
            return REAL_SPACE

        key = char.upper()
        key = TRANSLATION_TABLE.get(char, key)
        cls = globals().get(key)
        if not cls:
            return None

        instance = cls()
        instance.colour_override = self.current_colour
        return instance

    # -------------------------
    # Main text rendering
    # -------------------------

    def changeText(self, row=None, text=None, skip_justify=False):
        """
        Render `text` into the internal grid.

        Supported formatting:
          - ~(literal_key) : dynamic input token (controller icon or expanded keyboard text)
          - colour codes: :, #, @, & (reset)
          - backtick ` : newline
          - tab ¬ : insert 4 spaces
        """
        if not text:
            return

        # Start at top if no row specified
        if row is None:
            self.clear()
            row = 0

        self.current_colour = None
        col = 0
        i = 0
        length = len(text)

        while i < length:
            if row >= config.MAX_ROW:
                break

            ch = text[i]

            # Dynamic input token: ~(literal_key)
            if ch == "~" and i + 1 < length and text[i + 1] == "(":
                end = text.find(")", i + 2)
                if end != -1:
                    literal_key = text[i + 2:end]

                    # LONG LITERAL KEYS (e.g., "escape")
                    if len(literal_key) > 1:
                        # Controller mode: insert a single DynamicInput glyph
                        if inputManager.last_input_method != "Default":
                            dyn = DynamicInput()
                            dyn.update_sprite(literal_key)
                            self.text_array[row][col] = dyn
                            col += 1
                            i = end + 1
                            continue

                        # Keyboard mode: expand into abbreviation or the literal text
                        key = literal_key.lower()
                        expanded = ABBREVIATION_TABLE.get(key, key)

                        for ch2 in expanded.upper():
                            if col >= config.MAX_COL:
                                row += 1
                                col = 0
                                if row >= config.MAX_ROW:
                                    break
                            self.text_array[row][col] = self.translateIntoClass(ch2)
                            col += 1

                        i = end + 1
                        continue

                    # SINGLE-CHAR LITERAL (e.g., ~(c))
                    dyn = DynamicInput()
                    dyn.update_sprite(literal_key)
                    self.text_array[row][col] = dyn
                    col += 1
                    i = end + 1
                    continue

            # colour codes
            if ch in colour_CODES:
                self.current_colour = colour_CODES[ch]
                i += 1
                continue

            # Newline/backtick
            if ch == "`":
                row += 1
                if row < config.MAX_ROW:
                    self.text_array[row].fill(None)
                col = 0
                i += 1
                continue

            # Tab (insert 4 spaces)
            if ch == "¬":
                for _ in range(4):
                    if col >= config.MAX_COL:
                        row += 1
                        col = 0
                    if row >= config.MAX_ROW:
                        break
                    col += 1
                i += 1
                continue

            # Regular character
            if col < config.MAX_COL:
                self.text_array[row][col] = self.translateIntoClass(ch)
                col += 1

            # Auto-wrap
            if col >= config.MAX_COL:
                row += 1
                col = 0

            i += 1

        # Apply justification unless explicitly skipped
        if not skip_justify:
            for r in range(config.MAX_ROW):
                self.text_array[r] = self.justify_row(self.text_array[r])

        self.previous_text_array = np_copy(self.text_array)
        return self.text_array

    # -------------------------
    # Justification helpers
    # -------------------------

    def set_justification(self, mode: str):
        if mode in ("left", "right", "centre", "full"):
            self.justification = mode

    def justify_row(self, row_data):
        """Return a new row array with the chosen justification applied."""
        max_col = config.MAX_COL

        def is_real_space(g):
            return g is REAL_SPACE

        glyphs = [g for g in row_data if g is not None]
        count = len(glyphs)

        if count == 0:
            return row_data

        # Left
        if self.justification == "left":
            new_row = np.full(max_col, None)
            new_row[:count] = glyphs
            return new_row

        # Right
        if self.justification == "right":
            new_row = np.full(max_col, None)
            new_row[max_col - count:] = glyphs
            return new_row

        # Centre
        if self.justification == "centre":
            new_row = np.full(max_col, None)
            start = (max_col - count) // 2
            new_row[start:start + count] = glyphs
            return new_row

        # Full justify
        if self.justification == "full":
            if count <= 1:
                new_row = np.full(max_col, None)
                new_row[:count] = glyphs
                return new_row

            # Count gaps between non-space glyphs
            gaps = 0
            for i in range(count - 1):
                if not is_real_space(glyphs[i]) and not is_real_space(glyphs[i + 1]):
                    gaps += 1

            if gaps == 0:
                new_row = np.full(max_col, None)
                new_row[:count] = glyphs
                return new_row

            total_spaces = max_col - count
            base_space = total_spaces // gaps
            extra = total_spaces % gaps

            new_row = []
            gap_index = 0

            for i, g in enumerate(glyphs):
                new_row.append(g)
                if i < count - 1:
                    if not is_real_space(g) and not is_real_space(glyphs[i + 1]):
                        for _ in range(base_space + (1 if gap_index < extra else 0)):
                            new_row.append(None)
                        gap_index += 1

            return np.asarray(new_row[:max_col])

# -------------------------
# Dynamic input glyph
# -------------------------

class DynamicInput(UI):
    """
    Represents a single dynamic input glyph. In controller mode this becomes
    a single controller icon (resolved via inputManager). In keyboard mode
    the changeText() function expands long tokens into multiple glyphs, so
    DynamicInput is only used for single-character tokens like ~(c).
    """

    def __init__(self):
        super().__init__()

    def update_sprite(self, default_bound_key: str):
        """
        Replace this glyph's spritesheet with the appropriate texture.
        Controller mode: use controller icon (e.g., xbx_x.png).
        Keyboard mode: leave to changeText expansion (no single 'ESCAPE.png' lookup).
        """

        if inputManager.last_input_method != "Default":
            translated_key = inputManager.get_sprite_for_keyboard_key(default_bound_key)
            if translated_key:
                self.replace_spritesheet([[fonts_dir / f"{translated_key}.png"]])
        else:
            # In keyboard mode we do not attempt to load a single texture named
            # after the long key (e.g., ESCAPE). changeText expands long keys
            # into multiple glyphs; for single-letter tokens we can still show
            # the letter texture if desired.

            # Always inherit the active colour from the UI renderer
            self.colour_override = spritesUI.current_colour

            # Replace the spritesheet with keyboard equivalents
            self.replace_spritesheet([[fonts_dir / f"{default_bound_key.upper()}.png"]])

# -------------------------
# Dynamic glyph class generation
# -------------------------

def make_class_name(filename: str) -> str:
    """Convert a filename (e.g., 'a.png' or '0.png') into a class name."""
    name = filename.replace(".png", "")
    if name.isdigit():
        digit_names = ["Zero", "One", "Two", "Three", "Four",
                       "Five", "Six", "Seven", "Eight", "Nine"]
        return digit_names[int(name)]
    return name.capitalize()

def make_init(filepath):
    """Factory to create __init__ for dynamically generated glyph classes."""
    def __init__(self):
        super(type(self), self).__init__()
        self.spritesheet = [[filepath]]
        self.colour_override = None
        self.team = "ui"
    return __init__

# Create glyph classes for each PNG in the font directory
for file in fonts_dir.iterdir():
    if file.suffix.lower() != ".png":
        continue
    class_name = make_class_name(file.name)
    cls = type(class_name, (UI,), {"__init__": make_init(file)})
    globals()[class_name] = cls

# Singleton UI instance used by render_text()
spritesUI = UI()

# -------------------------
# Public API
# -------------------------

def render_text(text: str, justification: str | None = "centre") -> list:
    """
    Convert a formatted text string into a list of positioned sprite instances.
    Returns an empty list if nothing to render.
    """
    if justification is not None:
        spritesUI.set_justification(justification)

    text_array = spritesUI.changeText(text=text, skip_justify=(justification is None))
    if text_array is None:
        return []

    rows, cols = text_array.shape
    spawned_sprites = []

    for r in range(rows):
        for c in range(cols):
            glyph = text_array[r][c]
            if glyph is None or glyph is REAL_SPACE:
                continue

            colour = getattr(glyph, "colour_override", None)
            spawned = glyph.summon(
                target_row=r,
                target_col=c,
                screen=None,
                colour=colour
            )
            spawned_sprites.append(spawned)

    return spawned_sprites
