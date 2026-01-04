import pygame

from math import ceil as floor
# from math import floor

class Config:
    # PLEASE DO NOT TOUCH THE SCALE VALUE
    def __init__(self, scale=1, framerate=60):

        # consts
        self.RES_X_INIT, self.RES_Y_INIT = 280, 184 #  was x286, y175, but caused sprite cutoffs, and we needed a centre column #  original x858, y525
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
    
    def calculate_scale_against_pc_resolution(self, desktop_res_x, desktop_res_y) -> int:
        """
        Calculate the next scale, wrapping back to 1 if it exceeds PC resolution.
        Returns -1 to indicate fullscreen mode when at max scale.
        """

        # Find the maximum scale that fits within the PC resolution
        max_scale_x = desktop_res_x // self.RES_X_INIT
        max_scale_y = desktop_res_y // self.RES_Y_INIT
        max_scale = min(max_scale_x, max_scale_y)

        # Increment scale
        next_scale = self.resolution_scale + 1
        
        # # If we're one away from max, go fullscreen
        # if next_scale == max_scale:
        #     return -1  # Signal for fullscreen
        
        # If we exceed max, wrap back to 1
        if next_scale > max_scale:
            return 1
        
        return next_scale

    def calculate_best_fit_scale(self, desktop_res_x, desktop_res_y) -> int:
        """
        Calculate the best fit scale for the given desktop resolution.
        Scales to approximately 50% of the available screen space.
        """

        # Find the maximum scale that fits within the PC resolution
        max_scale_x = desktop_res_x // self.RES_X_INIT
        max_scale_y = desktop_res_y // self.RES_Y_INIT
        max_scale = min(max_scale_x, max_scale_y)
        
        # Use half of the maximum scale for middle-ground sizing
        half_scale = max_scale // 2
        
        # Ensure we have at least scale of 1
        return max(1, half_scale)


# Singleton instance
config = Config()