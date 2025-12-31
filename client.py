import pygame, os, time, asyncio, websockets, queue, threading, json
from config import config
from socket import gethostname
from hashlib import sha256
from resource import resource_path
from input import inputManager
import sprites
from ui_sprites import render_text, clear_ui

debug = False
gamesettings_filename = "game_settings.txt" # don't use resource_path for user settings
os.environ['SDL_VIDEO_CENTERED'] = '1'

def set_always_on_top():
    """Set the Pygame window to always stay on top (Windows only)"""
    import sys
    
    # Only run on Windows
    if sys.platform != "win32":
        return
    
    try:
        from ctypes import wintypes
        import ctypes
        
        hwnd = pygame.display.get_wm_info()["window"]  # HWND
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_SHOWWINDOW = 0x0040
        HWND_TOPMOST = -1

        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND,
            ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL

        # Keep size/position, just make topmost
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception as e:
        print(f"Warning: Could not set always on top: {e}")


class ClientGame:

    def __init__(self):
        self.uri = "wss://pypongonline.onrender.com/ws"
        # self.uri = "ws://localhost:8000/ws" # local testing, comment out for production


        # --- entities ---
        self.entities = {
            "players": [],
            "balls": [],
            "ui": [],
        }

        # initialise pygame
        self.pygame_init = pygame.init()
        display_info = pygame.display.Info()
        self.desktop_res_x, self.desktop_res_y = display_info.current_w, display_info.current_h


        self.screen = pygame.display.set_mode((config.res_x, config.res_y))
        self.clock = pygame.time.Clock()
        self.current_scale = config.resolution_scale
        self.frame_count = 0

        # --- user unique id ---
        self.client_id_hash = sha256(gethostname().encode()).hexdigest()

        # --- mode ---
        self.mode = "menu-init"
        self.mode_old = None

        # Main Menu
        self.menu_index = 0
        self.menu_items = ["SOLO", "ONLINE", "SCREEN", "QUIT"]
        self.menu_actions = {
            "SOLO": self.action_initOnlineFromMainMenu,
            "ONLINE": self.action_initOnlineFromMainMenu,
            "SCREEN": self.action_screen,
            "QUIT": self.action_quit,
        }

        self.menu_input_epoch = time.time()
        self.menu_input_cooldown = 0.19
        self.menu_credit_image = False

        # Transition
        self.transON_tick = 0
        self.transOFF_tick = 0
        self.trans_sfx_interval = 0
        self.trans_spawned_cols = 0
        self.trans_spawned_rows = 0

        # Networking
        self.net_connected = False
        self.net_wasConnected = False
        self.network_thread = None
        self.net_in = queue.Queue()
        self.net_out = queue.Queue()

        self.net_connected_epoch = 0
        self.net_rendercom_timeout = 300
        self.net_rendercom_retry_s = 15
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

            # trans
            "transON-init": self.initTransToPlayOnline,
            "transOFF-init": self.initTransToPlayOffline,

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
    
    def action_quit(self):
        pygame.quit()
        exit()

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

            if inputManager.get_action("up", keys):
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                self.menu_input_epoch = now

            elif inputManager.get_action("down", keys):
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                self.menu_input_epoch = now

            elif inputManager.get_action("select", keys):
                action = self.menu_actions.get(self.menu_items[self.menu_index])
                if action:
                    action()
                    self.menu_input_epoch = now + 0.1
                    self.lobby_input_epoch = now + 0.1 # prevents the user from accidentally falling into a lobby
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

        # Failsafe: eject to lost connection menu after timeout
        if self.online_tick >= config.frame_rate * self.net_timeout/2:
            self.mode = "lost-init"
            return

        self.entities["ui"] = render_text(
            f"``CONNECTING TO`¬@ONRENDER.COM{self.dots}``"
        )

    #region OnlineWaiting
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

        # capture epoch of connection (INTEGER) a bit hacky but works
        elapsed = int(f"{(time.time() - self.net_connected_epoch):.0f}")

        # Defer to every 30 frames, (2 times a second)
        if self.online_tick % 30 == 0:
            self.ui_ellipse += 1
            self.dots = "." * ((self.ui_ellipse % 3) + 1)

            # change the colour of the elapsed time to indicate sent attempt
            elapsed_net_out_colour = "@" if elapsed % self.net_rendercom_retry_s == 0 else ""

            self.entities["ui"] = render_text(
                 "``SERVER IS COLD BOOTING``"
                f"``THIS MAY TAKE UP TO {self.net_rendercom_timeout} SECONDS``"
                f"{elapsed_net_out_colour}({self.net_rendercom_timeout-elapsed})&`{self.dots}```#You're the only player online.`thanks for playing my game!"
            )

            # Retry every ~15 seconds (throttled)
            if elapsed - self.net_last_epoch_attempt >= self.net_rendercom_retry_s:
                self.net_last_epoch_attempt = elapsed
                self.start_network()

            # Timeout (+check for edge case where it prevents telling the user that the connection failed if success)
            if elapsed >= self.net_rendercom_timeout and not self.net_connected:
                self.mode = "online-offline"

    #region OnlineOffline
    def updateOnlineOffline(self):
        keys = pygame.key.get_pressed()

        self.entities["ui"] = render_text(
            "```@(SERVER)```"
            "``PLEASE TRY AGAIN LATER``"
            "``ESC BACK TO MENU``"
        )

        if inputManager.get_action("back", keys):
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
                self.mode = "transON-init"

        # User inputs
        if now - self.lobby_input_epoch > 0.2 and not self.mode in ["transON-init", "transOFF-init"]:
            if inputManager.get_action("up", keys):
                self.lobby_index = max(0, self.lobby_index - 1)
                self.lobby_input_epoch = now

            elif inputManager.get_action("down", keys):
                self.lobby_index = min(len(self.lobbies) - 1, self.lobby_index + 1)
                self.lobby_input_epoch = now

            elif inputManager.get_action("select", keys):
                lobby_id = self.lobbies[self.lobby_index]["id"]
                self.net_out.put(json.dumps({"type": "join_lobby", "id": lobby_id}))
                self.lobby_input_epoch = now

            elif inputManager.get_action("create", keys):
                self.net_out.put(json.dumps({"type": "create_lobby", "owner": self.client_id_hash}))
                self.lobby_input_epoch = now

            elif inputManager.get_action("back", keys):
                self.mode = "menu-init"

        self.renderLobbyUI()

    # ========================================================
    # Online Game
    #region OnlineGame
    def initTransToPlayOnline(self):
        self.transON_tick += 1

        # First-frame cleanup
        if self.transON_tick == 1:
            self.entitiesAllDelete()

        CELLS_PER_FRAME = 14
        ui_entities = self.entities["ui"]

        # Sound timing (every half batch)
        if self.transON_tick % (CELLS_PER_FRAME // 2) == 0:
            self.trans_sfx_interval += 1
            # soundManager.play(...)

        for _ in range(CELLS_PER_FRAME):

            # Spawn phase
            if self.trans_spawned_rows <= config.MAX_ROW:
                ui_entities.append(
                    sprites.Cell().summon(
                        target_row=self.trans_spawned_rows,
                        target_col=self.trans_spawned_cols,
                        screen=self.screen
                    )
                )

                # Advance grid position
                self.trans_spawned_cols += 1
                if self.trans_spawned_cols >= config.MAX_COL:
                    self.trans_spawned_cols = 0
                    self.trans_spawned_rows += 1
                continue  # do not delete on the same iteration

            # Delete phase
            if not ui_entities:
                # Transition complete
                self.transition_frame_count = 0
                self.mode = "online-game"
                self.trans_spawned_cols = 0
                self.trans_spawned_rows = 0
                return

            ui_entities.pop(0)


    def updateOnlineGame(self):
        self.entities["ui"] = render_text("``ONLINE GAME (WIP)``")

    
    # ========================================================
    # Offline Game
    # region OfflineGame
    def initTransToPlayOffline(self):
        self.transON_tick += 1
        
        # if self.transON_tick == 1:
        #     self.entitiesAllDelete()

        # # Set intervals for spawning and etc
        # CELLS_PER_FRAME = 28

        # if self.transON_tick % CELLS_PER_FRAME/2 == 0:
        #     self.sfx_interval += 1
        #     # soundManager.play(f"fastinvader{(self.sfx_interval % 3) + 1}",.25)


        # # Spawn cells
        # for _ in range(CELLS_PER_FRAME):

        #     if self.spawn_r > 32:
        #         break  # stop spawning, move to deletion phase

        #     entity = sprites.Cell().summon(
        #         target_row=self.spawn_r,
        #         target_col=self.spawn_c,
        #         screen=self.screen
        #     )
        #     self.entities["ui"].append(entity)

        #     self.spawn_c += 1
        #     if self.spawn_c >= 28:
        #         self.spawn_c = 0
        #         self.spawn_r += 1

        # # Deletion phase (only runs after spawning is finished)
        # if self.spawn_r > 32:

        #     # Delete up to CELLS_PER_FRAME items safely
        #     for _ in range(CELLS_PER_FRAME):
        #         if not self.entities["ui"]:

        #             # ON COMPLETON
        #             # soundManager.stop_music()
        #             self.transition_frame_count = 0
        #             self.mode = "online-game"
        #             self.spawn_c = 0
        #             self.spawn_r = 0
        #             return # just escapes the function
        #         del self.entities["ui"][0]

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
    #region Main
    def main(self):
        running = True

        # NOW create the window
        self.screen = pygame.display.set_mode((config.res_x, config.res_y))

        pygame.display.set_icon(
            sprites.loadSprite([resource_path("sprites/cell.png")])
        )
        pygame.display.set_caption("PyPongOnline")

        set_always_on_top()

        # load UI setting
        saveGameSettings = os.path.exists("game_settings.txt")
        if saveGameSettings:
            self.loadGameSettings()
        else:
            config.redefine(scale=config.calculate_best_fit_scale(self.desktop_res_x, self.desktop_res_y))
            self.saveGameSettings()

        # Main loop
        while running:
            self.frame_count += 1

            # If rescale is detected, update the window
            if self.current_scale != config.resolution_scale:
                self.current_scale = config.resolution_scale
                self.screen = pygame.display.set_mode((config.res_x, config.res_y))
                set_always_on_top() #reapplies to the new game window
            
            # If 'mode' changed, update inputManager
            if self.mode_old != self.mode:
                inputManager.mode = self.mode
                self.mode_old = self.mode

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
    #region Utilities
    def rescaleWindow(self):
        
        # Grab new scale based on desktop resolution
        new_scale = config.calculate_scale_against_pc_resolution(self.desktop_res_x, self.desktop_res_y)

        # should fullscreen? 

        # edit the scale change
        config.redefine(scale=new_scale)

        # apply the scalings to all entities
        for entity in self.entitiesAllReturn():
            entity.rescale()

        # save setting
        self.saveGameSettings()

    def entitiesAllReturn(self):
        return [e for lst in self.entities.values() for e in lst]
    
    def entitiesAllDelete(self):
        self.entities = {k: [] for k in self.entities}
        return self.entities
    
    # -- File game setting
    def saveGameSettings(self, override_scale=None):
        scale = override_scale if override_scale is not None else config.resolution_scale
        with open(gamesettings_filename,"w") as f:
            f.write(f"window_scale={scale}\n")
        f.close()
    
    def loadGameSettings(self):
        with open(gamesettings_filename,"r") as f:
            lines = f.readlines()
            for line in lines:
                if "window_scale=" in line:
                    scale = int(line.replace("window_scale=","").strip())
                    config.redefine(scale=scale)
                    break
        f.close()

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

        text += "````&@C& CREATE LOBBY``&@ESC& BACK``"
        self.entities["ui"] = render_text(text)


# Entry
if __name__ == "__main__":
    ClientGame().main()
