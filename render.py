import pygame
import math

from resource import resource_path
from config import config

def recolourSprite(surface: pygame.Surface, new_colour, preserve_alpha=True):
    """
    Tint a surface with new_colour (RGB tuple) while preserving alpha.
    If new_colour is None, returns the original surface copy.
    """
    if new_colour is None:
        return surface.copy()

    surf = surface.copy().convert_alpha()

    # Create solid colour surface the same size and blend multiply
    tint = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    tint.fill((*new_colour, 255))
    surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surf

def loadSprite(spritesheet, pos=(-100, -100)):
    """
    Load a sprite path provided in an iterable (expected: [PathLike]).
    Falls back to sprites/missing.png on error.
    Returns a pygame.Surface with alpha.
    """
    try:
        path = str(spritesheet[0])
        image = pygame.image.load(path).convert_alpha()
    except Exception as e:
        print(f"[loadSprite] Failed to load {spritesheet[0]}: {e}")
        fallback = resource_path("sprites/missing.png")
        image = pygame.image.load(str(fallback)).convert_alpha()
    return image

def scaleSprite(entity, surface, factor, smooth=False):
    """
    Scale surface by 'factor'. Keeps minimum size 1x1.
    This sets entity.scale for compatibility with existing code.
    """
    w, h = surface.get_size()
    new_size = (max(1, int(w * factor)), max(1, int(h * factor)))
    # Keep entity.scale for compatibility (existing code expects it)
    try:
        # entity.scale = factor
        pass
    except Exception:
        # entity may be a plain placeholder; ignore if setting fails
        pass
    return pygame.transform.smoothscale(surface, new_size) if smooth else pygame.transform.scale(surface, new_size)

# Grid/pixel helpers
def grid_to_pixel(row=None, col=None):
    """ Convert from gridspace to pixelspace -> returns dict["x"] and dict["y"]"""
    x = col * config.CELL_SIZE * config.resolution_scale if col is not None else None
    y = row * config.CELL_SIZE * config.resolution_scale if row is not None else None
    return {"x": x, "y": y}


def pixel_to_grid(x=None, y=None): # integers
    """ Convert from pixelspace to gridspace -> returns dict["row"] and dict["col"]"""
    col = math.floor(x / (config.CELL_SIZE * config.resolution_scale))
    row = math.floor(y / (config.CELL_SIZE * config.resolution_scale))

    if type(col) is float or type(row) is float:
        raise ArithmeticError("Must cast `int(pos_x),int(pos_y)`")

    return {"row": row, "col": col}