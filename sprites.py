import pygame, time, random
from random import randint
from resource import resource_path
from render import loadSprite, scaleSprite, grid_to_pixel, recolourSprite, pixel_to_grid
from config import config

# Directories
sprites_dir = resource_path("sprites")
ball_dir = sprites_dir / "ball"
paddle_dir = sprites_dir / "paddle"


class Sprite:
    #region __Init__
    def __init__(self):
        # (Float) Pixel coords
        self.pos_x, self.pos_y = 0, 0
        self.pos_row, self.pos_col = int(0), int(0)
        self.POS_X_OFFSET, self.POS_Y_OFFSET = 0, 0
        self.POS_X_PREV, self.POS_Y_PREV = 0, 0
        
        # (Ideal: Integer) (const) 
        self.SCALE = 1

        # (Integer) How many updates this sprite has recieved
        self.tick = 0

        # sprite resources
        self.spritesheet = []
        self.sprite_rect: pygame.Rect | None = None
        self._oscillator = 0

        # team
        self.team = None

        # mark
        self.mark_for_deletion = False

        # SURFACE LIFECYCLE (single rendered surface):
        # - self.surface_original: the raw image loaded from disk (unscaled, unmodified)
        # - self.surface_tinted_original: the tinted version of the original (unscaled) if a tint is applied
        # - self.surface_render: the final scaled surface that is actually blitted to screen
        self.surface_original: pygame.Surface | None = None
        self.surface_tinted_original: pygame.Surface | None = None
        self.surface_render: pygame.Surface | None = None
        self.surface_tint_color: tuple[int,int,int] | None = None

        assert self.SCALE >= 0.25, "resolution_scale must be greater than 0.25"

    #region Surfacing
    def _tint_surface(self, surface: pygame.Surface, colour: tuple[int,int,int]) -> pygame.Surface:
        """Return a new Surface that is the multiplicative tint of `surface` by `colour`.
        Uses BLEND_RGBA_MULT to preserve alpha while multiplying RGB channels.
        """
        if surface is None:
            return None
        tinted = surface.copy().convert_alpha()
        tint_surf = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
        # ensure full-alpha overlay with the chosen colour
        tint_surf.fill((*colour, 255))
        tinted.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return tinted

    def _build_render_surface(self, source_surface: pygame.Surface) -> pygame.Surface:
        """Scale `source_surface` according to the global config and per-sprite `self.SCALE`.
        Returns a new Surface suitable for blitting.
        """
        if source_surface is None:
            return None
        final_factor = config.resolution_scale * self.SCALE
        # print(final_factor, config.resolution_scale, self.SCALE)
        if final_factor > 1024:
            pass
        return scaleSprite(self, source_surface, factor=final_factor, smooth=False)
    
    def rebuild_surfaces(self, tint: tuple[int, int, int] | None = None):
        """
        Rebuilds all surfaces:
        - Updates tint colour if provided
        - Regenerates tinted original surface
        - Regenerates final scaled render surface
        - Updates sprite rect
        This is the correct one-stop shop for recolouring + scaling.
        """

        # Update tint if specified
        if tint is not None:
            self.surface_tint_color = tint

        # Choose source: original or tint-original
        if self.surface_tint_color is not None:
            # Build tinted original
            self.surface_tinted_original = self._tint_surface(
                self.surface_original,
                self.surface_tint_color
            )
            source = self.surface_tinted_original
        else:
            self.surface_tinted_original = None
            source = self.surface_original

        # Now build the scaled render surface
        self.surface_render = self._build_render_surface(source)

        # Update rect
        if self.sprite_rect and self.surface_render:
            self.sprite_rect.size = self.surface_render.get_size()

    ####


    #region Summon
    def summon(
        self,
        target_row=None,
        target_col=None,
        target_pos_x=None,
        target_pos_y=None,
        screen=None,
        colour: tuple[int, int, int] = None,
        offset_x=None,
        offset_y=None
    ):
        """
        Spawn sprite using spritesheet[0][0] as initial frame.
        Ensure we use the same loading path as set_sprite so tint and surface_original are consistent.
        """

        # --- OFFSET RESOLUTION ---
        # If offsets are provided, use them; otherwise fall back to the object's defaults
        ox = offset_x*config.resolution_scale if offset_x is not None else self.POS_X_OFFSET
        oy = offset_y*config.resolution_scale if offset_y is not None else self.POS_Y_OFFSET

        # --- INPUT RESOLUTION ---
        # Allow EITHER grid coords (row/col) OR pixel coords (pos_x/pos_y)
        if target_pos_x is not None or target_pos_y is not None:
            # Pixel‑based spawn
            self.pos_x = (target_pos_x if target_pos_x is not None else 0) + ox
            self.pos_y = (target_pos_y if target_pos_y is not None else 0) + oy

            # Convert pixel → grid (keeps your original behaviour)
            coord_grid = pixel_to_grid(x=int(self.pos_x), y=int(self.pos_y))
            self.pos_row, self.pos_col = coord_grid["row"], coord_grid["col"]

        else:
            # Grid‑based spawn (your original behaviour)
            coord_pixel = grid_to_pixel(row=target_row, col=target_col)
            self.pos_x = coord_pixel["x"] + ox
            self.pos_y = coord_pixel["y"] + oy

            # From coord_pixel + offsets, translate into pixelspace | LOSES ACCURACY WITH OFFSET
            coord_grid = pixel_to_grid(x=int(self.pos_x), y=int(self.pos_y))
            self.pos_row, self.pos_col = coord_grid["row"], coord_grid["col"]

        # If a colour was passed, stash it (so future animations/rescales reuse it)
        if colour is not None:
            self.surface_tint_color = tuple(colour)

        # Use set_sprite to load frame and apply tint/scaling logic consistently
        try:
            self.set_sprite(0, 0, recolour=self.surface_tint_color)
        except Exception:
            # fallback if spritesheet not available
            if self.spritesheet and self.spritesheet[0]:
                raw = loadSprite([self.spritesheet[0][0]])
                self.surface_original = raw.convert_alpha()
                if self.surface_tint_color is not None:
                    self.surface_tinted_original = self._tint_surface(self.surface_original, self.surface_tint_color)
                source = self.surface_tinted_original if self.surface_tinted_original else self.surface_original
                self.surface_render = self._build_render_surface(source)

        if self.surface_render:
            self.sprite_rect = self.surface_render.get_rect(topleft=(self.pos_x, self.pos_y))
        else:
            self.sprite_rect = pygame.Rect(self.pos_x, self.pos_y, 0, 0)

        self.screen = screen
        return self



    #region rescale
    def rescale(self):
        """Called when the global config.resolution_scale has changed.
        This method will:
         - compute the pixel-space ratio and update positions
         - rebuild the render surface from the ORIGINAL (unscaled) bitmaps so we never compound
        """
        new_scale = config.resolution_scale
        old_scale = config.last_resolution_scale

        if new_scale == old_scale:
            return

        print("Rescaling from", old_scale, "to", new_scale)

        # Compute correct relative ratio
        scale_ratio = new_scale / old_scale

        # Update config tracking
        config.last_resolution_scale = new_scale

        # Update pixel positions based on ratio
        self.pos_x = int(self.pos_x * scale_ratio)
        self.pos_y = int(self.pos_y * scale_ratio)

        # Update grid coords using your existing logic
        coord_grid = pixel_to_grid(int(self.pos_x), int(self.pos_y))
        self.pos_col = coord_grid["col"]
        self.pos_row = coord_grid["row"]

        # Scale surface from ORIGINAL source (tinted-original preferred)
        source_surface = self.surface_tinted_original if self.surface_tinted_original else self.surface_original
        if source_surface is not None:
            self.surface_render = self._build_render_surface(source_surface)

        # Update rect
        if self.sprite_rect and self.surface_render:
            self.sprite_rect.size = self.surface_render.get_size()
            self.sprite_rect.topleft = (self.pos_x, self.pos_y)
        
        # return new_scale

    #region draw
    def draw(self, screen):
        if not self.surface_render:
            return

        # (Integer) Grids
        coord_grid = pixel_to_grid(int(self.pos_x),int(self.pos_y))
        self.pos_col = coord_grid["col"]
        self.pos_row = coord_grid["row"]
        if self.sprite_rect:
            self.sprite_rect.topleft = (self.pos_x, self.pos_y)

        screen.blit(self.surface_render, (self.pos_x, self.pos_y))

    #region Spritesheet
    def set_spritesheet(self, new_spritesheet):
        self.spritesheet = new_spritesheet
        # reset oscillator and surfaces
        self._oscillator = 0
        # reload initial frame using set_sprite to keep tint behaviour consistent
        self.set_sprite(0, 0, recolour=self.surface_tint_color)
    
    def set_sprite(self, anim_index: int, frame_index: int, recolour: tuple[int,int,int] | None = None):
        """
        Load frame from disk into surface_original, optionally recolour it and cache the tinted original.
        Then scale and set surface_render (the one surface used for drawing).
        """
        # Update tint color if recolour explicitly provided
        if recolour is not None:
            self.surface_tint_color = tuple(recolour)

        # Load raw frame
        raw = loadSprite([self.spritesheet[anim_index][frame_index]])
        self.surface_original = raw.convert_alpha()

        # If a tint colour exists, produce a tinted original; else clear it
        if self.surface_tint_color is not None:
            self.surface_tinted_original = self._tint_surface(self.surface_original, self.surface_tint_color)
            source = self.surface_tinted_original
        else:
            self.surface_tinted_original = None
            source = self.surface_original

        # Scale to current global * per-sprite scale
        self.surface_render = self._build_render_surface(source)

        if self.sprite_rect and self.surface_render:
            self.sprite_rect.size = self.surface_render.get_size()

    def oscillate_sprite(self, oscillator_override: int | None = None):
        """
        Swap animation frame but keep tint if present.
        """
        assert len(self.spritesheet[0]) > 0, "[oscillate_sprite] No frames available in spritesheet!"

        if oscillator_override is not None:
            self._oscillator = oscillator_override % len(self.spritesheet[0])
        else:
            self._oscillator = (self._oscillator + 1) % len(self.spritesheet[0])

        anim_index = 0
        frame_index = self._oscillator
        # Load new base frame and apply current tint (if any)
        raw = loadSprite([self.spritesheet[anim_index][frame_index]])
        self.surface_original = raw.convert_alpha()

        # Reapply tint cache if we have tint_color
        if self.surface_tint_color is not None:
            self.surface_tinted_original = self._tint_surface(self.surface_original, self.surface_tint_color)
            source = self.surface_tinted_original
        else:
            self.surface_tinted_original = None
            source = self.surface_original

        self.surface_render = self._build_render_surface(source)
        if self.sprite_rect and self.surface_render:
            self.sprite_rect.size = self.surface_render.get_size()

    #region Positioning
    def move_position(self, dx=0, dy=0, drow=0, dcol=0, use_direction_multiplier=False):

        # Convert row/col movement to pixel movement (unscaled)
        cell = config.CELL_SIZE
        if drow or dcol:
            dx, dy = dcol * cell, drow * cell

        # Apply sprite direction multiplier (still world units)
        if use_direction_multiplier:
            dx *= self.sprite_direction[0]
            dy *= self.sprite_direction[1]

        # SCALE MOVEMENT TO MATCH RENDER SCALE :sob:
        scale = config.resolution_scale
        dx *= scale
        dy *= scale

        # Apply position
        self.pos_x += dx
        self.pos_y += dy

        # Update grid coords
        grid = pixel_to_grid(x=self.pos_x, y=self.pos_y)
        self.pos_row, self.pos_col = grid["row"], grid["col"]

        if self.sprite_rect:
            self.sprite_rect.topleft = (self.pos_x, self.pos_y)


    
    #region Tasking
    def ticker(self):
        self.tick += 1

    def _task_demo(self):
        match self.__class__.__name__:
            case _:
                if self.tick % 10+randint(-3,3) == 0:
                    self.oscillate_sprite()
                    self.move_position(dx=self._demo_x,dy=0,use_direction_multiplier=False)
    
    def task_queryIsOutOfBounds(self):
        grid_coords = pixel_to_grid(self.pos_x,self.pos_y)
        return grid_coords["col"] > config.MAX_COL or grid_coords["col"] < 1 or grid_coords["row"] > config.MAX_ROW or grid_coords["row"] < 2

    def task(self):
        pass






#region -> SPRITES







#region Dashline
class Dashline(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "dashline.png"]]

#region Cell
class Cell(Sprite):
    def __init__(self):
        super().__init__()
        self.team = "barriers"
        self.spritesheet = [[sprites_dir / "cell.png"]]


#region MissingCell
class MissingCell(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "missing.png"]]

#region Logo
class Logo(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "logo0.png"]]

#region Player
class Player(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[paddle_dir / "left.png",
                             paddle_dir / "top.png",
                             paddle_dir / "right.png",
                             paddle_dir / "bottom.png"]]
        self.speed = 5


#region CPUPlayer
class CPUPlayer(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[]]
        self.speed = 5

#region Ball
class Ball(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[ball_dir / "0.png",
                             ball_dir / "1.png",
                             ball_dir / "2.png",
                             ball_dir / "3.png",]]
        self.speed = -5
        self.velocity_x = 0
        self.velocity_y = 0

    def task(self):
        # move per task
        self.move_position(dx=self.velocity_x, dy=self.velocity_y)

        # oscillate sprite every 5 ticks
        if self.tick % 5 != 0: return
        self.oscillate_sprite()

        # apply random motion for testing
        if self.tick % 10 != 0: return
        self.set_velocity()
        pass

    def set_velocity(self, vel_x=None, vel_y=None):
        self.velocity_x = randint(-2,2)
        self.velocity_y = randint(-2,2)
        