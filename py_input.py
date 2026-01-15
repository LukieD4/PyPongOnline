import pygame
from pygame import joystick

# Detect controllers
pygame.joystick.init()
controllers = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
for c in controllers:
    c.init()

CONTROLLER_BUTTON_MAP = {
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

CONTROLLER_AXIS_MAP = {
    "left_x": 0,
    "left_y": 1,
    "right_x": 2,
    "right_y": 3,
}


class InputManager:
    def __init__(self):
        self.mode = None  # updated externally in client.py main loop.
    
    def get_action(self, action_name, keys):
        if self.mode not in INPUT_MODES:
            print(f"⚠️  InputManager: INPUT_MODES couldn't find a matching mode for '{self.mode}' (did you spell it correctly? In `client.py` and `input.py`?)")
            return False


        key_list = INPUT_MODES[self.mode].get(action_name, [])

        for key in key_list:

            # Keyboard key
            if isinstance(key, str):
                key_const = getattr(pygame, key, None)
                if key_const is not None and keys[key_const]:
                    return True

            # Controller callable
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

                # First try button map
                if button_name in CONTROLLER_BUTTON_MAP:
                    btn_index = CONTROLLER_BUTTON_MAP[button_name]
                    if joy.get_button(btn_index):
                        return True

                # Then try hat directions
                if button_name.startswith("dpad_"):
                    hat_x, hat_y = joy.get_hat(0)
                    # print(hat_x,hat_y) # returns 0,0 with no inputs

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
