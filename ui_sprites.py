from resource import resource_path
from sprites import Sprite
import numpy as np
from config import config

sprites_dir = resource_path("sprites") / "font"

# Translation table for special characters and digits to class names
TRANSLATION_TABLE = {
    # Special symbols
    "*": "Asterix",
    "-": "Dash",
    "_": "Under",
    "=": "Equal",
    "<": "Less",
    ">": "Great",
    "?": "Question",
    ".": "Fullstop",
    "/": "Slashfwd",
    # Digits
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

REAL_SPACE = object()

# Color codes for text rendering (RGB tuples)
COLOR_CODES = {
    ":": (255, 0, 0),      # Colon = red
    "#": (0, 255, 0),      # Hash = green
    "@": (255, 255, 0),    # At symbol = yellow
    "&": None,             # Ampersand = reset to default (no colour)
}


class UI(Sprite):
    """Base UI sprite class for text rendering on the MAX_COL*MAX_ROW grid."""
    
    def __init__(self):
        super().__init__()
        self.text_array = self.clear()
        self.previous_text_array = self.text_array.copy()
        self.current_color = None  # Track current color state (RGB tuple or None)
        self.justification = "center"  # left, right, center, full
    
    def clear(self):
        """Initialize or clear the text array to a MAX_COL*MAX_ROW grid of None values."""
        self.text_array = np.full((config.MAX_ROW, config.MAX_COL), None)
        return self.text_array
    
    def translateIntoClass(self, char: str):
        """
        Convert a character to its corresponding sprite class instance.
        
        Args:
            char: Single character to translate
            
        Returns:
            Instance of the sprite class, or None if not found
        """
        # If it's a space, return empty object
        if char == " ":
            return REAL_SPACE

        # Convert to uppercase for lookup
        key = char.upper()
        
        # Translate special characters and digits using the table
        key = TRANSLATION_TABLE.get(char, key)
        
        # Look up the dynamically created class in globals
        cls = globals().get(key)
        
        if not cls:
            return None
        
        # Create instance and apply current color if set
        instance = cls()
        # Store the color as an attribute that can be accessed later
        instance.color_override = self.current_color
        
        return instance

    def changeText(self, row=None, text=None):
        """
        Render text to the text_array grid with automatic wrapping and formatting.
        
        Rules:
        - Text wraps to next line after 28 characters (columns 0-27)
        - Backtick (`) triggers a newline and clears the new row
        - Tab character (¬) inserts 4 spaces
        - Color codes: : = red, # = green, @ = yellow, & = reset (affects subsequent text)
        - Maximum 32 rows (0-31)
        
        Args:
            row: Starting row (None = clear all and start at row 0)
            text: String to render
            
        Returns:
            Updated text_array
        """
        if not text:
            return
        
        # If no row specified, clear the entire grid and start at top
        if row is None:
            self.clear()
            row = 0
        
        # Reset color state at the start
        self.current_color = None
        col = 0
        i = 0
        
        while i < len(text):
            # Stop if we've exceeded the grid height
            if row >= config.MAX_ROW:
                break
            
            ch = text[i]
            
            # Check for colour code characters (including reset)
            if ch in COLOR_CODES:
                self.current_color = COLOR_CODES[ch]
                i += 1
                continue
            
            # Backtick = move to next row and clear it
            if ch == "`":
                row += 1
                if row < config.MAX_ROW:
                    self.text_array[row].fill(None)
                col = 0
                i += 1
                continue
            
            # Tab character = insert 4 spaces
            if ch == "¬":
                for _ in range(4):
                    if col >= config.MAX_COL:
                        row += 1
                        col = 0
                    if row >= config.MAX_ROW:
                        break
                    # Leave as None (blank space)
                    col += 1
                i += 1
                continue
            
            # Place the character sprite at the current position
            self.text_array[row][col] = self.translateIntoClass(ch)
            col += 1
            
            # Auto-wrap when we reach the column limits
            if col >= config.MAX_COL:
                row += 1
                col = 0
            
            i += 1
        
        
        # Apply justification to each row
        for r in range(config.MAX_ROW):
            self.text_array[r] = self.justify_row(self.text_array[r])

        # Store a copy for comparison/diffing if needed
        self.previous_text_array = self.text_array.copy()
        return self.text_array

    

    def set_justification(self, mode: str):
        if mode in ("left", "right", "center", "full"):
            self.justification = mode
    
    def justify_row(self, row_data):
        """Return a new row array with justification applied."""
        max_col = config.MAX_COL

        # Helper: detect real spaces
        def is_real_space(g):
            return g is REAL_SPACE

        # Extract glyphs (non-None AND including REAL_SPACE)
        glyphs = [g for g in row_data if g is not None]
        count = len(glyphs)

        # Empty row
        if count == 0:
            return row_data

        # LEFT JUSTIFY
        if self.justification == "left":
            new_row = np.full(max_col, None)
            new_row[:count] = glyphs
            return new_row

        # RIGHT JUSTIFY
        if self.justification == "right":
            new_row = np.full(max_col, None)
            new_row[max_col - count:] = glyphs
            return new_row

        # CENTER JUSTIFY
        if self.justification == "center":
            new_row = np.full(max_col, None)
            start = (max_col - count) // 2
            new_row[start:start + count] = glyphs
            return new_row

        # FULL JUSTIFY
        if self.justification == "full":

            # If only one glyph or only spaces. left justify
            if count <= 1:
                new_row = np.full(max_col, None)
                new_row[:count] = glyphs
                return new_row

            # Count gaps ONLY between non-space glyphs
            gaps = 0
            for i in range(count - 1):
                if not is_real_space(glyphs[i]) and not is_real_space(glyphs[i+1]):
                    gaps += 1

            # If no valid gaps (e.g., row is "     "), left justify
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

                # Only stretch between non-space glyphs
                if i < count - 1:
                    if not is_real_space(g) and not is_real_space(glyphs[i+1]):
                        # Insert padding spaces
                        for _ in range(base_space + (1 if gap_index < extra else 0)):
                            new_row.append(None)
                        gap_index += 1

            return np.array(new_row[:max_col])




def make_class_name(filename: str) -> str:
    """
    Convert a sprite filename to a proper class name.
    
    Handles special cases:
    - Numeric filenames (0.png -> Zero)
    - Regular filenames (dash.png -> Dash)
    """
    name = filename.replace(".png", "")
    
    # Convert digit filenames to word names
    if name.isdigit():
        digit_names = ["Zero", "One", "Two", "Three", "Four", 
                       "Five", "Six", "Seven", "Eight", "Nine"]
        return digit_names[int(name)]
    
    return name.capitalize()


def make_init(filepath):
    """
    Factory function to create __init__ methods for dynamically generated classes.
    Each sprite class will load its specific sprite file.
    """
    def __init__(self):
        super(type(self), self).__init__()
        self.spritesheet = [[filepath]]
        self.color_override = None  # Initialize color override attribute
    return __init__


# Dynamically generate a class for each .png file in the font directory
# This creates classes like: A, B, C, Zero, One, Dash, etc.
for file in sprites_dir.iterdir():
    if file.suffix.lower() != ".png":
        continue
    
    class_name = make_class_name(file.name)
    
    # Dynamically create a new class that inherits from UI
    cls = type(
        class_name,
        (UI,),
        {"__init__": make_init(file)}
    )
    
    # Register the class in the global namespace so translateIntoClass can find it
    globals()[class_name] = cls


# Singleton instance for global text rendering
spritesUI = UI()


# ===========================================================
# PUBLIC API - Use these functions to render UI text

def render_text(text: str) -> list:
    """
    Primary function to convert a text string into a list of positioned sprite instances.
    
    Args:
        text: Formatted text string with color codes and newlines
        
    Returns:
        List of sprite instances ready to be added to entities["ui"]
        
    Example:
        entities["ui"] = render_text("#Hello World``&Next line")
    """
    text_array = spritesUI.changeText(text=text)
    
    if text_array is None:
        return []
    
    rows, cols = text_array.shape
    spawned_sprites = []

    for r in range(rows):
        for c in range(cols):
            glyph: Sprite = text_array[r][c]
            if glyph is None:
                continue

            if glyph is REAL_SPACE: # Real space; no sprite, just skip
                continue

            # Check if the glyph has a colour override
            colour = getattr(glyph, 'color_override', None)
            
            # Summon with colour if present, otherwise use default
            spawned: Sprite = glyph.summon(
                target_row=r,
                target_col=c,
                screen=None,
                colour=colour
            )
            
            spawned_sprites.append(spawned)
            
    return spawned_sprites


def clear_ui() -> list:
    """
    Clear all UI text and return an empty list.
    
    Returns:
        Empty list to assign to entities["ui"]
        
    Example:
        entities["ui"] = clear_ui()
    """
    spritesUI.clear()
    return []