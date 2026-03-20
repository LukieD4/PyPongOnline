import pygame
from py_resource import resource_path


class SoundMixer:
    def __init__(self, frequency=44100, size=-16, channels=2, buffer=512):
        self._initialized = False
        self.sounds = {}   # (name, path) -> Sound
        self._channels = {}  # (name, path) -> Channel
        self._music = None  # (name, path) -> currently loaded music track
        self._paused = set()

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
                self.sounds[key] = pygame.mixer.Sound(str(path))
            except Exception as e:
                print(f"[SoundMixer] Failed to load {path}: {e}")
                return None

        return self.sounds[key]

    def _load_music(self, name: str, relative_path: str):
        path = resource_path(relative_path)

        if not path.exists():
            print(f"[SoundMixer] Missing music file: {path}")
            return None, None

        key = (name, str(path))
        return key, path

    def play(self, name: str, relative_path: str, vol_mult=1.0, loops=0):
        """
        All-in-one sound playback.
        The same name can map to different files safely.

        Use loops=-1 for indefinite looping. That is routed through
        pygame.mixer.music so long-form music behaves correctly.
        """
        if not self._initialized:
            return

        # Long-running infinite loops are more reliable through pygame.mixer.music.
        if loops == -1:
            key, path = self._load_music(name, relative_path)
            if not key:
                return

            try:
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.set_volume(max(0.0, min(1.0, vol_mult)))
                pygame.mixer.music.play(loops=-1)
                self._music = key
                self._paused.discard(key)
            except Exception as e:
                print(f"[SoundMixer] Failed to play music '{name}': {e}")
            return

        sound = self._load_sound(name, relative_path)
        if not sound:
            return

        sound.set_volume(max(0.0, min(1.0, vol_mult)))

        try:
            channel = sound.play(loops=loops)
            if channel:
                key = (name, str(resource_path(relative_path)))
                self._channels[key] = channel
        except Exception as e:
            print(f"[SoundMixer] Failed to play '{name}': {e}")

    def pause(self, name: str, unpause_only: bool = False, pause_only: bool = False):
        if not hasattr(self, "_paused"):
            self._paused = set()

        # Handle pygame.mixer.music separately, since it is not a normal channel.
        if self._music and self._music[0] == name:
            key = self._music

            if key in self._paused:
                if pause_only:
                    return
                pygame.mixer.music.unpause()
                self._paused.remove(key)
            elif not unpause_only:
                pygame.mixer.music.pause()
                self._paused.add(key)
            return

        for key, channel in list(self._channels.items()):
            if key[0] != name:
                continue

            if key in self._paused:
                if pause_only:
                    continue
                channel.unpause()
                self._paused.remove(key)
            elif not unpause_only:
                channel.pause()
                self._paused.add(key)

    def stop(self, name: str):
        if self._music and self._music[0] == name:
            pygame.mixer.music.stop()
            self._paused.discard(self._music)
            self._music = None
            return

        for key, channel in list(self._channels.items()):
            if key[0] == name:
                channel.stop()
                self._channels.pop(key, None)

    def stop_all(self):
        pygame.mixer.music.stop()
        pygame.mixer.stop()
        self._channels.clear()
        self._paused.clear()
        self._music = None

    def quit(self):
        pygame.mixer.quit()
        self._initialized = False


soundMixer = SoundMixer()