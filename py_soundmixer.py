# soundmixer.py
import pygame
from py_resource import resource_path


class SoundMixer:
    def __init__(self, frequency=44100, size=-16, channels=2, buffer=512):
        self._initialized = False
        self.sounds = {}  # (name, path) -> Sound

        try:
            pygame.mixer.pre_init(frequency, size, channels, buffer)
            pygame.mixer.init()
            self._initialized = True
        except Exception as e:
            print(f"[SoundMixer] Failed to initialize mixer: {e}")

    def _load_sound(self, name: str, relative_path: str):
        path = resource_path(relative_path)

        if not path.exists():
            print(f"[SoundMixer] Missing sound file: {path}")
            return None

        key = (name, str(path))

        if key not in self.sounds:
            try:
                self.sounds[key] = pygame.mixer.Sound(path)
            except Exception as e:
                print(f"[SoundMixer] Failed to load {path}: {e}")
                return None

        return self.sounds[key]

    def play(self, name: str, relative_path: str, vol_mult=1.0, loops=0):
        """
        All-in-one sound playback.
        The same name can map to different files safely.
        """
        if not self._initialized:
            return

        sound = self._load_sound(name, relative_path)
        if not sound:
            return

        sound.set_volume(max(0.0, min(1.0, vol_mult)))

        try:
            sound.play(loops=loops)
        except Exception as e:
            print(f"[SoundMixer] Failed to play '{name}': {e}")

    def stop_all(self):
        pygame.mixer.stop()

    def quit(self):
        pygame.mixer.quit()
        self._initialized = False


soundMixer = SoundMixer()
