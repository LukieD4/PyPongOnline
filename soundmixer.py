# soundmixer.py
import pygame
from pathlib import Path
from resource import resource_path


class SoundMixer:
    """
    Lightweight wrapper around pygame.mixer for cross‑platform audio.
    Designed for:
    - OGG + WAV assets
    - Nuitka onefile/standalone
    - Windows, Linux, macOS
    """

    def __init__(self, frequency=44100, size=-16, channels=2, buffer=512):
        self._initialized = False
        self.sounds = {}

        # Initialize mixer safely
        try:
            pygame.mixer.pre_init(frequency, size, channels, buffer)
            pygame.mixer.init()
            self._initialized = True
        except Exception as e:
            print(f"[SoundMixer] Failed to initialize mixer: {e}")
            self._initialized = False

    def load(self, name: str, relative_path: str):
        """
        Load a sound and store it under a name.
        Example:
            mixer.load("hit", "sounds/hit.ogg")
        """
        if not self._initialized:
            print("[SoundMixer] Mixer not initialized — cannot load sounds")
            return

        path = resource_path(relative_path)

        if not Path(path).exists():
            print(f"[SoundMixer] Missing sound file: {path}")
            return

        try:
            self.sounds[name] = pygame.mixer.Sound(path)
        except Exception as e:
            print(f"[SoundMixer] Failed to load {path}: {e}")

    def play(self, name: str, relative_path: str = None, loops=0):
        """
        Play a sound by name.
        If it's not loaded yet and a path is provided, auto-load it.
        """
        # Auto-load if missing
        if name not in self.sounds:
            if relative_path is None:
                print(f"[SoundMixer] Sound '{name}' not loaded and no path provided")
                return

            # Try to load on demand
            self.load(name, relative_path)

            # If load failed, bail
            if name not in self.sounds:
                return

        # Play the sound
        try:
            self.sounds[name].play(loops=loops)
        except Exception as e:
            print(f"[SoundMixer] Failed to play '{name}': {e}")


    def stop(self, name: str):
        """Stop a specific sound."""
        if name in self.sounds:
            self.sounds[name].stop()

    def set_volume(self, name: str, volume: float):
        """
        Set volume for a specific sound.
        volume: 0.0 → silent, 1.0 → full
        """
        if name in self.sounds:
            self.sounds[name].set_volume(max(0.0, min(1.0, volume)))

    def stop_all(self):
        """Stop all sounds."""
        pygame.mixer.stop()

    def quit(self):
        """Shutdown mixer cleanly."""
        pygame.mixer.quit()
        self._initialized = False


soundMixer = SoundMixer()