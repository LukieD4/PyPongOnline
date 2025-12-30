import pygame
from math import ceil as floor

class Config:
    # PLEASE DO NOT TOUCH THE SCALE VALUE
    def __init__(self, scale=1, framerate=60):

        # consts
        self.RES_X_INIT, self.RES_Y_INIT = 286, 175 #    x858, y525
        self.RESOLUTION_SCALE_INIT = scale
        self.CELL_SIZE = 8   # ALWAYS 8
        self.MAX_COL, self.MAX_ROW = floor(self.RES_X_INIT / self.CELL_SIZE), floor(self.RES_Y_INIT / self.CELL_SIZE)
        print(self.MAX_COL,self.MAX_ROW)

        self.resolution_scale = scale
        self.last_resolution_scale = scale
        self.res_x = self.RES_X_INIT * scale
        self.res_y = self.RES_Y_INIT * scale
        self.frame_rate = framerate
        self.clock = pygame.time.Clock()

    def redefine(self, scale=None, framerate=None, clock=None):
        """
        Redefine global configuration values. When `scale` is provided we update
        the derived resolution values but DO NOT mutate `last_resolution_scale` here.
        Sprites are expected to call their own `rescale()` method which will read
        the previous scale from `last_resolution_scale`, compute the ratio and then
        set `last_resolution_scale` to the new scale.
        """
        if scale is not None:
            # Store previous scale (left intact for sprites until they rescale)
            old = self.resolution_scale

            # Update derived values
            self.resolution_scale = scale
            self.res_x = self.RES_X_INIT * scale
            self.res_y = self.RES_Y_INIT * scale

            # Optional: return tuple(old, new) so caller may trigger rescale on sprites
            return scale
        if framerate is not None:
            self.frame_rate = framerate
            return framerate
        if clock is not None:
            self.clock = clock
            return clock

# Singleton instance
config = Config()