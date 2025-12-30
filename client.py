import pygame, random, os, ctypes, time, asyncio, websockets, queue, threading, json
import numpy as np
from config import config
from ctypes import wintypes
from pathlib import Path
import sprites
from ui_sprites import render_text, clear_ui

debug = False
os.environ['SDL_VIDEO_CENTERED'] = '1'


def set_always_on_top():
    hwnd = pygame.display.get_wm_info()["window"]
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040
    HWND_TOPMOST = -1

    user32.SetWindowPos(
        hwnd, HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    )


class ClientGame:

    def __init__(self):
        self.uri = "wss://pypongonline.onrender.com/ws"

        # --- entities ---
        self.entities = {
            "players": [],
            "balls": [],
            "ui": [],
        }

        self.screen = pygame.display.set_mode((config.res_x, config.res_y))
        self.clock = pygame.time.Clock()
        self.current_scale = config.resolution_scale
        self.frame_count = 0

        # --- mode ---
        self.mode = "menu-init"

        # Main Menu
        self.menu_index = 0
        self.menu_items = ["SOLO", "ONLINE", "SCREEN", "QUIT"]
        self.menu_actions = {
            "SOLO": self.action_initOnlineFromMainMenu,
            "ONLINE": self.action_initOnlineFromMainMenu,
            "SCREEN": self.action_screen,
        }

        self.menu_input_epoch = time.time()
        self.menu_input_cooldown = 0.19
        self.menu_credit_image = False

        # Networking
        self.net_connected = False
        self.net_wasConnected = False
        self.network_thread = None
        self.net_in = queue.Queue()
        self.net_out = queue.Queue()

        self.net_connected_epoch = 0
        self.net_timeout = 60
        self.net_last_error = None
        self.net_lost_tick = 0

        # Retry throttling (prevents spam reconnects)
        self.net_last_epoch_attempt = 0

        # Online / Lobby
        self.online_tick = 0
        self.ui_ellipse = 0
        self.dots = ""

        self.lobbies = []
        self.lobby_index = 0
        self.lobby_input_epoch = 0
        self.in_lobby = None

        # Mode dispatch
        self.update_methods = {
            # menus
            "menu-init": self.initMainMenu,
            "menu": self.updateMainMenu,

            # online
            "online-connect": self.updateOnlineConnect,
            "online-waiting": self.updateOnlineWaiting,
            "online-offline": self.updateOnlineOffline,
            "lobby": self.updateLobbyBrowser,
            "online-game": self.updateOnlineGame,

            # lost connection
            "lost-init": self.initLostConnectionMenu,
            "lost": self.updateLostConnectionMenu,
        }

    # ========================================================
    # WebSockets
    #region WebSockets

    async def websocket_loop(self):
        try:
            async with websockets.connect(self.uri) as ws:
                # Successful transport connection
                self.net_connected = True
                self.net_wasConnected = True
                self.net_last_error = None  # <<< clear stale failures
                print("DEBUG: connected to server")

                await ws.send("Hello from client")

                while True:
                    # Send queued outbound messages
                    try:
                        msg = self.net_out.get_nowait()
                        await ws.send(msg)
                    except queue.Empty:
                        pass

                    # Receive inbound messages (non-blocking)
                    try:
                        incoming = await asyncio.wait_for(ws.recv(), timeout=0.05)
                        self.net_in.put(incoming)
                    except asyncio.TimeoutError:
                        pass

        except Exception as e:
            # Capture error for main thread to interpret
            self.net_last_error = str(e).lower()
            print("DEBUG: websocket error:", self.net_last_error)

        finally:
            # Socket is definitively closed here
            self.net_connected = False
            self.clear_network_queues()
            self.network_thread = None

    def start_network(self):
        # Prevent duplicate threads
        if self.network_thread and self.network_thread.is_alive():
            return

        # Reset intent + stale state
        self.net_last_error = None
        self.clear_network_queues()

        self.network_thread = threading.Thread(
            target=lambda: asyncio.run(self.websocket_loop()),
            daemon=True
        )
        self.network_thread.start()

    def has_handshake_timeout(self):
        return (
            self.net_last_error
            and "timed out during opening handshake" in self.net_last_error
        )

    def clear_network_queues(self):
        while not self.net_in.empty():
            self.net_in.get_nowait()
        while not self.net_out.empty():
            self.net_out.get_nowait()

    # ========================================================
    # Menu Actions
    #region Actions

    def action_initOnlineFromMainMenu(self):
        self.mode = "online-connect"
        self.online_tick = 0
        self.start_network()

    def action_screen(self):
        self.rescaleWindow()

    # ========================================================
    # Main Menu
    #region MainMenu

    def initMainMenu(self):
        self.mode = "menu"

    def updateMainMenu(self):
        keys = pygame.key.get_pressed()
        now = time.time()

        for entity in self.entitiesAllReturn():
            entity.ticker()
            if hasattr(entity, "_do_task_demo"):
                entity._do_task_demo()

        # Determine actions made by the user's key presses
        if now - self.menu_input_epoch > self.menu_input_cooldown:
            if keys[pygame.K_UP]:
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                self.menu_input_epoch = now

            elif keys[pygame.K_DOWN]:
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                self.menu_input_epoch = now

            elif keys[pygame.K_RETURN]:
                action = self.menu_actions.get(self.menu_items[self.menu_index])
                if action:
                    action()
                    self.menu_input_epoch = now + 0.1
                    return

        self.renderMenuText()

    # ========================================================
    # Online Connect / Waiting
    #region OnlineConnect

    def updateOnlineConnect(self):
        self.online_tick += 1

        # Escalate into cold-boot waiting state
        if self.has_handshake_timeout():
            self.net_connected_epoch = time.time()
            self.net_last_epoch_attempt = 0
            self.mode = "online-waiting"
            return

        # Defer to only every 30 frames, (2 times a second)
        if self.online_tick % 30 == 0:
            self.ui_ellipse += 1
            self.dots = "." * ((self.ui_ellipse % 3) + 1)

        # If the player is connected online, redirect to lobby menu
        if self.net_connected:
            self.net_out.put(json.dumps({"type": "list_lobbies"}))
            self.mode = "lobby"
            return

        self.entities["ui"] = render_text(
            f"``CONNECTING TO`¬@RENDER.COM{self.dots}``"
        )

    def updateOnlineWaiting(self):
        # duplicate tick so we can reuse ellipse dotting
        self.online_tick += 1

        # SUCCESS: connection established while waiting
        if self.net_connected:
            self.net_last_error = None
            self.net_connected_epoch = 0
            self.net_last_epoch_attempt = 0

            self.net_out.put(json.dumps({"type": "list_lobbies"}))
            self.mode = "lobby"
            return

        # capture epoch of connection
        elapsed = time.time() - self.net_connected_epoch

        # Defer to every 30 frames, (2 times a second)
        if self.online_tick % 30 == 0:
            self.ui_ellipse += 1
            self.dots = "." * ((self.ui_ellipse % 3) + 1)

            self.entities["ui"] = render_text(
                "``SERVER IS COLD BOOTING``"
                "``THIS MAY TAKE UP TO 60 SECONDS``"
                f"({60-elapsed:.0f})`{self.dots}```#You must be the only one online.`so thanks for playing my game!"
            )

            # Retry every ~5 seconds (throttled)
            if elapsed - self.net_last_epoch_attempt >= 5:
                self.net_last_epoch_attempt = elapsed
                self.start_network()

            # Timeout (+check for edge case where it prevents telling the user that the connection failed if success)
            if elapsed >= self.net_timeout and not self.net_connected:
                self.mode = "online-offline"

    def updateOnlineOffline(self):
        keys = pygame.key.get_pressed()

        self.entities["ui"] = render_text(
            "```@SERVER IS OFFLINE```"
            "``PLEASE TRY AGAIN LATER``"
            "``ESC BACK TO MENU``"
        )

        if keys[pygame.K_ESCAPE]:
            self.mode = "menu-init"

    # ========================================================
    # Lobby
    #region Lobby

    def updateLobbyBrowser(self):
        keys = pygame.key.get_pressed()
        now = time.time()

        while not self.net_in.empty():
            raw = self.net_in.get()

            # Ignore non-JSON noise (+prevent a crash)
            if not raw or raw[0] != "{":
                continue

            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "lobby_list":
                self.lobbies = msg.get("lobbies", [])

            elif msg_type == "joined_lobby":
                self.in_lobby = msg.get("id")

            elif msg_type == "start_game":
                self.mode = "online-game"

        # User inputs
        if now - self.lobby_input_epoch > 0.2:
            if keys[pygame.K_UP]:
                self.lobby_index = max(0, self.lobby_index - 1)
                self.lobby_input_epoch = now

            elif keys[pygame.K_DOWN]:
                self.lobby_index = min(len(self.lobbies) - 1, self.lobby_index + 1)
                self.lobby_input_epoch = now

            elif keys[pygame.K_RETURN] and self.lobbies:
                lobby_id = self.lobbies[self.lobby_index]["id"]
                self.net_out.put(json.dumps({"type": "join_lobby", "id": lobby_id}))
                self.lobby_input_epoch = now

            elif keys[pygame.K_c]:
                self.net_out.put(json.dumps({"type": "create_lobby", "name": "New Lobby"}))
                self.lobby_input_epoch = now

            elif keys[pygame.K_ESCAPE]:
                self.mode = "menu-init"

        self.renderLobbyUI()

    # ========================================================
    # Online Game
    def updateOnlineGame(self):
        self.entities["ui"] = render_text("``ONLINE GAME (WIP)``")

    # ========================================================
    # Lost Connection
    #region LostConnection

    def initLostConnectionMenu(self):
        self.net_lost_tick = 0
        self.entities["ui"].clear()
        self.mode = "lost"

    def updateLostConnectionMenu(self):
        self.net_lost_tick += 1
        self.entities["ui"] = render_text("```Connection lost. Sorry!```")

        if self.net_lost_tick >= 240:
            self.net_connected = False
            self.net_wasConnected = False
            self.network_thread = None
            self.mode = "menu-init"

    # ========================================================
    # Main Loop
    def main(self):
        pygame.init()
        running = True

        pygame.display.set_icon(
            sprites.loadSprite([Path("sprites") / "cell.png"])
        )
        pygame.display.set_caption("PyPongOnline")
        set_always_on_top()

        while running:
            self.frame_count += 1

            if self.current_scale != config.resolution_scale:
                self.current_scale = config.resolution_scale
                self.screen = pygame.display.set_mode((config.res_x, config.res_y))

            # Detect true connection loss (not cold-boot)
            if (
                self.net_wasConnected
                and not self.net_connected
                and self.mode not in ("lost", "lost-init", "online-waiting", "online-offline")
                and not self.has_handshake_timeout()
            ):
                self.mode = "lost-init"

            self.update_methods[self.mode]()

            self.screen.fill((0, 0, 0))
            for entity in self.entitiesAllReturn():
                entity.draw(self.screen)
                if entity.mark_for_deletion:
                    self.entities[entity.team].remove(entity)

            pygame.display.flip()
            self.clock.tick(config.frame_rate)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

        pygame.quit()

    # ========================================================
    # Utilities

    def rescaleWindow(self):
        new_scale = (config.resolution_scale % 3) + 1
        config.redefine(scale=new_scale)
        for entity in self.entitiesAllReturn():
            entity.rescale()

    def entitiesAllReturn(self):
        return [e for lst in self.entities.values() for e in lst]

    # ========================================================
    # UI Rendering
    #region UI

    def renderMenuText(self):
        title = "`````````````&"
        body = ""

        for i, item in enumerate(self.menu_items):
            prefix = "#> " if i == self.menu_index else "&  "
            suffix = "#< " if i == self.menu_index else "&  "
            body += f"{prefix}{item} {suffix}``"

        self.entities["ui"] = render_text(title + body)

    def renderLobbyUI(self):
        text = "``AVAILABLE LOBBIES``"

        for i, lobby in enumerate(self.lobbies):
            prefix = "#> " if i == self.lobby_index else "&  "
            text += f"{prefix}{lobby['name']} ({lobby['players']}/{lobby['max_players']})``"

        text += "````&C CREATE LOBBY``&ESC BACK``"
        self.entities["ui"] = render_text(text)


# Entry
if __name__ == "__main__":
    ClientGame().main()
