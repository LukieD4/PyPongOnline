import pygame, threading, asyncio
from pygame import joystick
from py_render import pixel_to_grid

# Using Xbox's scheme!
DEFAULT_CONTROLLER_BUTTON_MAP = {
    "a": 0,
    "b": 1,
    "x": 2,
    "y": 3,
    "lb": 4,
    "rb": 5,
    "back": 6,
    "start": 7,
    "dpad_up": 11,
    "dpad_down": 12,
    "dpad_left": 13,
    "dpad_right": 14,
}

CROSS_PLATFORM_SPRITE_MAP = {
    # RESOLVES THE IMAGES (e.g. xbx_a.png)
    "XBOX": {
        "a": "xbx_a",
        "b": "xbx_b",
        "x": "xbx_x",
        "y": "xbx_y",
        "lb": "xbx_lb",
        "rb": "xbx_rb",
        "back": "xbx_back",
        "start": "xbx_start",
    },
    "DUALSHOCK": {
        "a": "psn_cross",
        "b": "psn_circle",
        "x": "psn_square",
        "y": "psn_triangle",
        "lb": "psn_l2",
        "rb": "psn_r2",
        "back": "psn_back",
        "start": "psn_select",
        },
}

CONTROLLER_AXIS_MAP = {
    "left_x": 0,
    "left_y": 1,
    "right_x": 2,
    "right_y": 3,
}





class InputManager:
    def __init__(self):
        self.mode = None  # updated externally in client.py main loop.

        # Mouse tracking
        self.mouse_object = None
        self.mouse_pos_x, self.mouse_pos_y = 0, 0
        self.mouse_pos_row, self.mouse_pos_col = 0, 0

        # Input method tracking
        self.last_input_method = "Default" # Default: Keyboard & Mouse, "Xbox Series X Controller": Controller
        
        # Detect controllers
        pygame.joystick.init()
        self.controller_thread = None
        self.controllers = []
    
    def initialise_cursor(self, cursor_object, screen):
        self.mouse_object = cursor_object.summon(target_row=self.mouse_pos_row, target_col=self.mouse_pos_col,screen=screen)
        return self.mouse_object
    
    def update_mouse_positioning_attributes(self, mouse_position) -> None:
        self.mouse_pos_x, self.mouse_pos_y = mouse_position[0], mouse_position[1]
        grid_space = pixel_to_grid(self.mouse_pos_x, self.mouse_pos_y)
        self.mouse_pos_row, self.mouse_pos_col = grid_space["row"], grid_space["col"]

    def update_mouse_input_state(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            print(f"py_input : update_mouse_input_state (DOWN) : {event.pos}")
            self.update_mouse_positioning_attributes(event.pos)
            self.mouse_object.set_sprite(0,1)
            return pygame.MOUSEBUTTONDOWN
        elif event.type == pygame.MOUSEBUTTONUP:
            print(f"py_input : update_mouse_input_state (UP) : {event.pos}")
            self.update_mouse_positioning_attributes(event.pos)
            self.mouse_object.set_sprite(0,0)
            return pygame.MOUSEBUTTONUP
            
    
    def resolve_active_input_method(self, event):
        if (event.type == pygame.KEYDOWN) or event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
            self.last_input_method = "Default"

        elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION):
            if self.controllers:
                self.last_input_method = self.controllers[0].get_name()

        elif event.type == pygame.JOYAXISMOTION:
            if abs(event.value) > 0.5 and self.controllers:
                self.last_input_method = self.controllers[0].get_name()
        
        return self.last_input_method


    def get_controller_family(self):
        if self.last_input_method == "Default":
            return None

        name = self.last_input_method.lower()
        # name = "sony"

        if "xbox" in name:
            return "XBOX"

        if ("dualshock" in name or 
            "dual sense" in name or 
            "dualsense" in name or 
            "sony" in name or 
            "wireless controller" in name):
            return "DUALSHOCK"

        return "XBOX"  # fallback for generic controllers


    def get_sprite_for_keyboard_key(self, keyboard_key):
        if self.last_input_method == "Default":
            return None

        button = self.translate_keyboard_key_to_controller_key(keyboard_key)
        if button is None:
            return None

        family = self.get_controller_family()
        if family is None:
            return None

        return CROSS_PLATFORM_SPRITE_MAP[family].get(button)



    def translate_keyboard_key_to_controller_key(self, keyboard_key:str):
        if self.mode not in INPUT_MODES:
            return None
        
        # Santise to PyGame formatting
        keyboard_key = keyboard_key.upper() if len(keyboard_key) > 1 else keyboard_key.lower()
        keyboard_key = f"K_{keyboard_key}" if not keyboard_key.startswith("K_") else keyboard_key
            

        mode_map = INPUT_MODES[self.mode]

        for action_name, key_list in mode_map.items():

            if keyboard_key not in key_list:
                continue

            for key in key_list:
                if callable(key) and hasattr(key, "__closure__") and key.__closure__:
                    for cell in key.__closure__:
                        val = cell.cell_contents
                        if isinstance(val, str) and val in DEFAULT_CONTROLLER_BUTTON_MAP:
                            return val

            return None

        return None



    def get_latest_controllers(self):
        while True:
            self.controllers = [
                pygame.joystick.Joystick(i)
                for i in range(pygame.joystick.get_count())
            ]
            for c in self.controllers:
                c.init()

            pygame.time.wait(500)

        
    
    def get_action(self, action_name, keys):
        if self.mode not in INPUT_MODES:
            print(f"⚠️  InputManager: INPUT_MODES couldn't find a matching mode for '{self.mode}'")
            return False

        key_list = INPUT_MODES[self.mode].get(action_name, [])

        for key in key_list:
            if isinstance(key, str):
                key_const = getattr(pygame, key, None)
                if key_const is not None and keys[key_const]:
                    return True

            elif callable(key):
                if key():
                    return True

        return False
    
    @staticmethod
    def universal_back():
        return ["K_ESCAPE", "K_BACKSPACE", InputManager.controller_button("b"), InputManager.controller_button("back")]
    
    @staticmethod
    def universal_select():
        return ["K_RETURN", "K_SPACE", InputManager.controller_button("a"), InputManager.controller_button("start")]
    
    @staticmethod
    def controller_button(button_name):
        def check_button():
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)

                if button_name in DEFAULT_CONTROLLER_BUTTON_MAP:
                    btn_index = DEFAULT_CONTROLLER_BUTTON_MAP[button_name]
                    if joy.get_button(btn_index):
                        return True

                if button_name.startswith("dpad_"):
                    hat_x, hat_y = joy.get_hat(0)

                    if button_name == "dpad_up" and hat_y == 1:
                        return True
                    if button_name == "dpad_down" and hat_y == -1:
                        return True
                    if button_name == "dpad_left" and hat_x == -1:
                        return True
                    if button_name == "dpad_right" and hat_x == 1:
                        return True

            return False
        return check_button


    @staticmethod
    def controller_thumbstick(axis=None, threshold=None, direction=None):
        if None in [axis,threshold,direction]:
            print(f"⚠️  No input was passed into controller_thumbstick: axis: {axis}, threshold {threshold}, direction {direction}")
        def check_thumbstick():
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)
                axis_index = CONTROLLER_AXIS_MAP.get(axis)
                if axis_index is None:
                    continue

                value = joy.get_axis(axis_index)

                if direction == "up" and value < -threshold:
                    return True
                if direction == "down" and value > threshold:
                    return True

            return False
        return check_thumbstick



# singleton instance
inputManager = InputManager()

inputManager.controller_thread = threading.Thread(
    target=inputManager.get_latest_controllers,
    daemon=True
)
inputManager.controller_thread.start()



# Define input modes and their associated key actions
INPUT_MODES = {
    "menu": {
        "up": [
            "K_UP",
            "K_w",
            InputManager.controller_thumbstick(axis="left_y", threshold=0.5, direction="up"),
            InputManager.controller_button("dpad_up"),
        ],
        "down": [
            "K_DOWN",
            "K_s",
            InputManager.controller_thumbstick(axis="left_y", threshold=0.5, direction="down"),
            InputManager.controller_button("dpad_down"),
        ],
        "select": [
            *InputManager.universal_select(),
        ],
        "vol-down": [
            "K_LEFT",
            "K_a",
            InputManager.controller_button("dpad_left"),
        ],
        "vol-up": [
            "K_RIGHT",
            "K_d",
            InputManager.controller_button("dpad_right"),
        ],
    },

    "lobby-browser": {
        "up": [
            "K_UP",
            "K_w",
            InputManager.controller_thumbstick(axis="left_y", threshold=0.5, direction="up"),
            InputManager.controller_button("dpad_up"),
        ],
        "down": [
            "K_DOWN",
            "K_s",
            InputManager.controller_thumbstick(axis="left_y", threshold=0.5, direction="down"),
            InputManager.controller_button("dpad_down"),
        ],
        "select": [
            *InputManager.universal_select()
        ],
        "create": [
            "K_c",
            InputManager.controller_button("x"),
        ],
        "leave": [
            "K_l",
            InputManager.controller_button("x"),
        ],
        "back": [
            *InputManager.universal_back()
        ],
    },

    "lost": {
        "back": [
            *InputManager.universal_back()
        ],
    },

    "online-offline": {
        "back": [
            *InputManager.universal_back()
        ],
    },

    "offline-game": {
        "up": [
            "K_UP",
            "K_w",
            InputManager.controller_thumbstick(axis="left_y", threshold=0.1, direction="up"),
            InputManager.controller_button("dpad_up"),
        ],
        "down": [
            "K_DOWN",
            "K_s",
            InputManager.controller_thumbstick(axis="left_y", threshold=0.1, direction="down"),
            InputManager.controller_button("dpad_down"),
        ],
        "left": [
            "K_a",
        ],
        "right": [
            "K_d",
        ],
        "pause": [
            "K_p",
        ],
        "sprint": [
            "K_LSHIFT",
            "K_RSHIFT",
        ],
        "back": [
            *InputManager.universal_back()
        ],
    },
}
