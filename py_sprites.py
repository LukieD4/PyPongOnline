from __future__ import annotations

import pygame, time, random

from random import randint

from py_resource import resource_path
from py_render import loadSprite, scaleSprite, grid_to_pixel, pixel_to_grid
from py_config import config
from py_input import inputManager

# Directories
sprites_dir = resource_path("sprites")
ball_dir = sprites_dir / "ball"
paddle_dir = sprites_dir / "paddle"


class Sprite:
    #region __Init__
    def __init__(self):
        # (Float) Pixel coords
        self.pos_x, self.pos_y = 0, 0
        self.pos_row, self.pos_col = 0,0
        # (Float) (consts)
        self.POS_X_OFFSET, self.POS_Y_OFFSET = 0, 0
        self.POS_X_PREV, self.POS_Y_PREV = 0, 0
        
        # Spawned
        self.SUMMONED_POS_X, self.SUMMONED_POS_Y = 0, 0
        self.SUMMONED_POS_ROW, self.SUMMONED_POS_COL = 0,0
        
        # (Ideal: Integer) (const) 
        self.__SCALE = 1

        # (Integer) How many updates this sprite has recieved
        self.tick = 0

        # sprite resources
        self.spritesheet = [[sprites_dir / "missing.png"]]
        self.sprite_rect: pygame.Rect | None = None
        self.sprite_index = 0
        # don't tamper
        self._sprite_oscillator = 0

        # team
        self.team = "decor" # (default: a vegatative state)

        # mark
        self.mark_for_deletion = False
        self.mark_for_respawn = False

        # SURFACE LIFECYCLE (single rendered surface):
        # - self.surface_original: the raw image loaded from disk (unscaled, unmodified)
        # - self.surface_tinted_original: the tinted version of the original (unscaled) if a tint is applied
        # - self.surface_render: the final scaled surface that is actually blitted to screen
        self.surface_original: pygame.Surface | None = None
        self.surface_tinted_original: pygame.Surface | None = None
        self.surface_render: pygame.Surface | None = None
        self.surface_tint_colour: tuple[int,int,int] | None = None

        assert self.__SCALE >= 0.25, "resolution_scale must be greater than 0.25"

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
        """Scale `source_surface` according to the global config and per-sprite `self.__SCALE`.
        Returns a new Surface suitable for blitting.
        """
        if source_surface is None:
            return None
        final_factor = config.resolution_scale * self.__SCALE
        # print(final_factor, config.resolution_scale, self.__SCALE)
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
            self.surface_tint_colour = tint

        # Choose source: original or tint-original
        if self.surface_tint_colour is not None:
            # Build tinted original
            self.surface_tinted_original = self._tint_surface(
                self.surface_original,
                self.surface_tint_colour
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
        offset_y=None,
        initial_sprite_index=None  # NEW PARAMETER
    ):
        """
        Spawn sprite using spritesheet[anim_index][initial_sprite_index] as initial frame.
        Ensure we use the same loading path as set_sprite so tint and surface_original are consistent.
        """

        # Check if a screen has been assigned (doesn't apply to ui sprites as they render on an independent layer)
        if not screen and (not hasattr(self, 'team') or self.team != "ui"):
            print(f"⚠️  No `screen` arg has been passed to {self.__class__.__name__}'s `Summon`, the sprite will not be visible.")


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
        
        # Update empty spawn constants
        coord_grid = pixel_to_grid(x=int(self.pos_x), y=int(self.pos_y))
        self.SUMMONED_POS_X, self.SUMMONED_POS_Y = self.pos_x, self.pos_y
        self.SUMMONED_POS_ROW, self.SUMMONED_POS_COL = coord_grid["row"], coord_grid["col"]

        # If a colour was passed, stash it (so future animations/rescales reuse it)
        if colour is not None:
            self.surface_tint_colour = tuple(colour)
        
        # Fallback to sprite's index if none
        if initial_sprite_index is None:
            initial_sprite_index = self.sprite_index

        # Use set_sprite to load frame and apply tint/scaling logic consistently
        # NOW RESPECTS THE initial_sprite_index PARAMETER
        try:
            self.set_sprite(0, initial_sprite_index, recolour=self.surface_tint_colour)
        except Exception:
            # fallback if spritesheet not available
            if self.spritesheet and self.spritesheet[0]:
                raw = loadSprite([self.spritesheet[0][initial_sprite_index]])
                self.surface_original = raw.convert_alpha()
                if self.surface_tint_colour is not None:
                    self.surface_tinted_original = self._tint_surface(self.surface_original, self.surface_tint_colour)
                source = self.surface_tinted_original if self.surface_tinted_original else self.surface_original
                self.surface_render = self._build_render_surface(source)

        if self.surface_render:
            self.sprite_rect = self.surface_render.get_rect(topleft=(self.pos_x, self.pos_y))
        else:
            self.sprite_rect = pygame.Rect(self.pos_x, self.pos_y, 0, 0)

        self.screen = screen
        return self

    def respawn(self) -> None:
        self.move_position(dx=self.SUMMONED_POS_X,dy=self.SUMMONED_POS_Y,set_position=True)

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
    def replace_spritesheet(self, new_spritesheet):
        self.spritesheet = new_spritesheet
        # reset oscillator and surfaces
        self._sprite_oscillator = 0
        # reload initial frame using set_sprite to keep tint behaviour consistent
        self.set_sprite(0, 0, recolour=self.surface_tint_colour)
    
    def set_sprite(self, anim_index: int, frame_index: int, recolour: tuple[int,int,int] | None = None):
        """
        Load frame from disk into surface_original, optionally recolour it and cache the tinted original.
        Then scale and set surface_render (the one surface used for drawing).
        """
        # Update tint colour if recolour explicitly provided
        if recolour is not None:
            self.surface_tint_colour = tuple(recolour)

        # Load raw frame
        raw = loadSprite([self.spritesheet[anim_index][frame_index]])
        self.surface_original = raw.convert_alpha()

        # If a tint colour exists, produce a tinted original; else clear it
        if self.surface_tint_colour is not None:
            self.surface_tinted_original = self._tint_surface(self.surface_original, self.surface_tint_colour)
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
            self._sprite_oscillator = oscillator_override % len(self.spritesheet[0])
        else:
            self._sprite_oscillator = (self._sprite_oscillator + 1) % len(self.spritesheet[0])

        anim_index = 0
        frame_index = self._sprite_oscillator
        # Load new base frame and apply current tint (if any)
        raw = loadSprite([self.spritesheet[anim_index][frame_index]])
        self.surface_original = raw.convert_alpha()

        # Reapply tint cache if we have tint_colour
        if self.surface_tint_colour is not None:
            self.surface_tinted_original = self._tint_surface(self.surface_original, self.surface_tint_colour)
            source = self.surface_tinted_original
        else:
            self.surface_tinted_original = None
            source = self.surface_original

        self.surface_render = self._build_render_surface(source)
        if self.sprite_rect and self.surface_render:
            self.sprite_rect.size = self.surface_render.get_size()

    #region Positioning
    def move_position(self, dx=0, dy=0, drow=0, dcol=0, set_position=False):

        # Convert row/col movement to pixel movement (unscaled)
        cell = config.CELL_SIZE
        if drow or dcol:
            dx, dy = dcol * cell, drow * cell

        # __SCALE MOVEMENT TO MATCH RENDER __SCALE
        scale = config.resolution_scale
        
        if set_position:
            # DIRECTLY SET POSITION (resolution_scale already applied)
            self.pos_x = dx
            self.pos_y = dy
        else:
            # APPLY SCALING BASED ON RESOLUTION
            dx *= scale
            dy *= scale
            # APPLY MOVEMENT
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
                    self.move_position(dx=self._demo_x,dy=0)
    
    def query_isOffscreen(self):
        return self.pos_col > config.MAX_COL or self.pos_col < 1 or self.pos_row > config.MAX_ROW or self.pos_row < -1

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
        self.spritesheet = [[sprites_dir / "logo150x44_1.png"]]





#region Speaker
class Speaker(Sprite):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "volume" / "0.png",
                             sprites_dir / "volume" / "1.png",
                             sprites_dir / "volume" / "2.png",
                             sprites_dir / "volume" / "3.png",
                             sprites_dir / "volume" / "4.png",
                             sprites_dir / "volume" / "5.png",
                             sprites_dir / "volume" / "6.png",
                             sprites_dir / "volume" / "7.png",
                             sprites_dir / "volume" / "8.png",
                             sprites_dir / "volume" / "9.png",
                             sprites_dir / "volume" / "10.png"]]
        self.sprite_index = 2
        self.set_sprite(0,self.sprite_index)
    
    def sync_sprite_with_volume(self):
        # volume_multiplier is between 0 and 1
        vol = config.volume_multiplier

        # Map 0–1 range to 0–4 sprite index
        # Multiply by number of sprites, subtract 1 because index starts at 0
        index = int(vol * (len(self.spritesheet[0]) - 1))

        # Clamp just in case
        index = max(0, min(index, len(self.spritesheet[0]) - 1))

        # Update sprite
        self.sprite_index = index
        self.set_sprite(0, self.sprite_index)






#region Goals
class Goal(Sprite):
    def __init__(self):
        super().__init__()
        self.team = "goals"

class GoalLeft(Goal):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "font" / "L.png"]]

class GoalRight(Goal):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "font" / "R.png"]]

class GoalUp(Goal):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "font" / "U.png"]]

class GoalDown(Goal):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "font" / "D.png"]]

class OutOfBounds(Goal):
    def __init__(self):
        super().__init__()
        self.spritesheet = [[sprites_dir / "font" / "O.png"]]





#region Dummy
class Dummy(Sprite):
    def __init__(self):
        super().__init__()  
        self.spritesheet = [[paddle_dir / "left.png",
                             paddle_dir / "top.png",
                             paddle_dir / "right.png",
                             paddle_dir / "bottom.png"]]
        self.pos_y_prev = 0
        self.pos_motion_mult = 0
        self.pos_desync_calc = 0
        self.speed = 2
        self.SPEED_INITIAL = self.speed
        self.client = True

#region Player
class Player(Dummy):
    def __init__(self):
        super().__init__()
        self.team = "players"

        # Define movement orientation, future case to if we want Players on different sides of the screen
        self.movement_orientation = {"forward": "up", "backward": "down"}
    
    def task(self, keys=None):

        # Defer further checks via online
        if not self.client:
            self.wss()
            return

        # Check keys if provided
        if keys is None: return

        # Movement parameters
        has_inputted = False
        applied_speed = self.speed
        is_y_upOOB = not (self.pos_y-applied_speed > 0)
        is_y_downOOB = not ((self.pos_y+applied_speed) < config.res_y-(config.CELL_SIZE*config.resolution_scale))

        if inputManager.get_action(self.movement_orientation["forward"], keys) and not is_y_upOOB:
            # has_inputted = True
            self.move_position(dy=-applied_speed)
        if inputManager.get_action(self.movement_orientation["backward"], keys) and not is_y_downOOB:
            # has_inputted = True
            self.move_position(dy=applied_speed)
        
        # Check the pixels the player has moved since last x frames, but skip if player has moved
        if self.tick % 10 == 0 and not has_inputted:
            self.pos_y_prev = self.pos_y
            # print(f"movement delta: {delta_y}")
    
    def wss(self):

        # heartbeat every 10 ticks
        if self.tick % 10 == 0:
            pass


#region CPUPlayer
class CPUPlayer(Dummy):
    def __init__(self):
        super().__init__()
        self.team = "ai"
        self.sprite_index = 2
        
    
    def task(self, ball: Ball, skip_approaching=False):
        # Only react if ball is approaching
        # Skip: if ball_approaching doesn't exist
        if not skip_approaching:
            ball_approaching = ball.velocity_x > 0
            if not ball_approaching:
                return

        # Vertical difference
        dy_to_ball = ball.pos_y - self.pos_y

        # Deadzone to avoid jitter
        DEADZONE = self.speed+4
        if abs(dy_to_ball) < DEADZONE:
            return

        # Decide direction
        direction = 1 if dy_to_ball > 0 else -1

        # Proposed delta movement
        dy = direction * self.speed

        # Clamp delta so we don't move out of bounds
        top_limit = 0
        bottom_limit = config.res_y - (config.CELL_SIZE * config.resolution_scale)

        # If applying dy would go out of bounds, cancel it
        new_y = self.pos_y + dy
        if new_y < top_limit or new_y > bottom_limit:
            dy = 0

        # Apply delta movement (NOT absolute)
        self.move_position(dy=dy)

        # Track movement every X ticks
        if self.tick % 30 == 0:
            self.pos_y_prev = self.pos_y
    
    def _do_task_demo(self, ball):
        if self.tick or randint(0,2) == 1:
            self.speed = randint(self.SPEED_INITIAL,self.SPEED_INITIAL+3)
        
        if randint(0,1) == 0:
            self.task(ball, skip_approaching=True)
        




#region Ball
class Ball(Sprite):
    def __init__(self):
        super().__init__()
        self.team = "balls"
        self.spritesheet = [[
            ball_dir / "0.png",
            ball_dir / "1.png",
            ball_dir / "2.png",
            ball_dir / "3.png",
        ]]

        # Flags
        self.gotScored = False
        self.mark_for_respawn = False
        self.edge_collision_buffer_ignore = 0 # frames

        # Initial velocity
        self.velocity_x = -1
        self.velocity_y = 0

        # Speed control
        self.base_speed = 1
        self.current_speed = self.base_speed
        self.max_speed = 4.0
        self.speed_increment = 0.15

        # Owner tracking
        self.owner = None  # which player last hit the ball
    
    def ticker(self):
        super().ticker()
        if self.edge_collision_buffer_ignore > 0:
            self.edge_collision_buffer_ignore -= 1

    def task(self) -> None:
        # --- movement ---
        # print(self.velocity_x, self.velocity_y)
        self.move_position(dx=self.velocity_x, dy=self.velocity_y)

        # --- animation ---
        if self.tick % 5 == 0:
            self.oscillate_sprite()

        # (optional) debug
        # print(self.velocity_x, self.velocity_y)

    def set_velocity_basedOnPlayerMotion(self, player: Player):
        # influence
        max_influence = .5
        delta = player.pos_y - player.pos_y_prev
        delta = max(-max_influence, min(max_influence, delta))

        # reverse X, add Y influence
        new_x = -self.velocity_x
        new_y = self.velocity_y + delta

        # increase speed slightly
        self.current_speed = min(self.current_speed + self.speed_increment, self.max_speed)

        return self.set_velocity(new_x, new_y)


    def set_velocity(self, velocity_x=None, velocity_y=None):
        if velocity_x is not None:
            self.velocity_x = velocity_x
        if velocity_y is not None:
            self.velocity_y = velocity_y

        # Normalise vertical velocity
        mag = (self.velocity_x**2 + self.velocity_y**2) ** 0.5
        if mag != 0:
            self.velocity_x = (self.velocity_x / mag) * self.current_speed
            self.velocity_y = (self.velocity_y / mag) * self.current_speed

        return self.velocity_x, self.velocity_y
    
    def redirect_if_on_edge(self, soundMixer, soundVolumeOverride=1):
        if self.edge_collision_buffer_ignore <= 0:
            if (self.sprite_rect.top <= 0 or self.sprite_rect.bottom >= config.res_y):
                self.edge_collision_buffer_ignore = 5
                soundMixer.play("initial_velocity", f"audio/initial_velocity.ogg",vol_mult=config.volume_multiplier*soundVolumeOverride)
                self.set_velocity(self.velocity_x, -self.velocity_y)
    
    def respawn(self):
        super().respawn()
        self.owner = None
        
    
    def _do_task_demo(self):
        self.task()