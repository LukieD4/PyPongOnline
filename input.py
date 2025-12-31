import pygame


class InputManager:
    def __init__(self):
        self.mode = None  # updated externally in client.py main loop.
    
    def get_action(self, action_name, keys):
        if self.mode not in INPUT_MODES:
            return False
        key_names = INPUT_MODES[self.mode].get(action_name, [])
        for key_name in key_names:
            key_const = getattr(pygame, key_name, None)
            if key_const is not None and keys[key_const]:
                return True
        return False
    
    @staticmethod
    def universal_back():
        return ["K_ESCAPE", "K_BACKSPACE"]
    
    @staticmethod
    def universal_select():
        return ["K_RETURN", "K_SPACE"]

# singleton instance
inputManager = InputManager()

# Define input modes and their associated key actions
INPUT_MODES = {
    # SYNC WITH client.py 'mode' VALUES
    "menu": {
        "up": ["K_UP", "K_w"],
        "down": ["K_DOWN", "K_s"],
        "select": InputManager.universal_select()  # Use class method, not instance
    },
    "lobby": {
        "up": ["K_UP", "K_w"],
        "down": ["K_DOWN", "K_s"],
        "select": InputManager.universal_select(),
        "create": ["K_c"],
        "back": InputManager.universal_back()
    },
    "lost": {
        "back": InputManager.universal_back()
    },
    "online-offline": {
        "back": InputManager.universal_back()
    }
}