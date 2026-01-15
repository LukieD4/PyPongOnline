from __future__ import annotations

import pygame, os, time, asyncio, websockets, queue, threading, json, sys

import py_sprites

from py_stager import Stager
from py_config import config
from py_resource import resource_path
from py_input import inputManager
from py_ui_sprites import render_text
from py_soundmixer import soundMixer

from socket import gethostname
from hashlib import sha256
from random import randint




debug = False
gamesettings_filename = "game_settings.txt" # don't use resource_path for user settings
os.environ['SDL_VIDEO_CENTERED'] = '1'

def running_as_exe():
    # Nuitka sets __compiled__ = True
    if "__compiled__" in globals():
        return True

    # PyInstaller sets sys.frozen = True
    if getattr(sys, "frozen", False):
        return True

    return False


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
        print(f"set_always_on_top : WARN : Could not set always on top: {e}")


class ClientGame:

    def __init__(self):
        self.uri = "wss://pypongonline.onrender.com/ws"
        # self.uri = "ws://localhost:8000/ws" # local testing, comment out for production
    

        # --- entities ---
        self.entities = {
            "ai": [],
            "players": [],
            "goals": [],
            "balls": [],
            "ui": [],
            "decor": [],
        }

        # initialise pygame
        self.pygame_init = pygame.init()
        display_info = pygame.display.Info()
        self.desktop_res_x, self.desktop_res_y = display_info.current_w, display_info.current_h


        self.screen = pygame.display.set_mode((config.res_x, config.res_y))
        self.clock = pygame.time.Clock()
        self.current_scale = config.resolution_scale
        self.frame_count = 0

        # Set stage
        self.stager = Stager(self.screen,self.entities)

        # --- user unique id ---
        self.client_id_hash = sha256(gethostname().encode()).hexdigest()

        # --- mode ---
        self.mode = "menu-init"
        self.mode_old = None

        # Main Menu
        self.main_menu_tick = 0
        self.main_menu_speaker = None
        self.menu_index = 0
        self.menu_items = ["SOLO", "ONLINE", "SCREEN", "QUIT"]
        self.menu_actions = {
            "SOLO": self.action_playOffline,
            "ONLINE": self.action_playOnline,
            "SCREEN": self.action_screen,
            "QUIT": self.action_quit,
        }

        self.menu_input_epoch = time.time()
        self.menu_input_cooldown = 0.19
        self.menu_credit_image = False

        # Main loop
        self.mainloop_halt_for_x_ticks = 0

        # Transition
        self.transition_tick = 0
        self.transition_sfx_interval = 0
        self.transition_spawned_cols = 0
        self.transition_spawned_rows = 0

        # Playing offline
        self.playOFF_tick = 0
        self.playOFF_countdown_epoch = 0
        self.playOFF_draw_line = False
        self.playOFF_drawn_lines = 0
        self.playOFF_began = False

        # Game tracking
        self.game_volume = 1 # THIS GETS SET UPON SETTINGS LOAD ("volume=")
        self.game_scores = [0,0,0,0] # for now, 4 players is enough :3
        self._game_client_username = "LUKIE"
        self.game_player_names = [self._game_client_username,"WAYNE","JONAH","BOZZY"]
        self.game_halt_for_x_ticks = 0
        self.game_goal_scored = False

        # Networking
        self.net_connected = False
        self.net_wasConnected = False
        self.network_thread = None
        self.net_in = queue.Queue()
        self.net_out = queue.Queue()

        self.net_connected_epoch = 0
        self.net_rendercom_timeout = 150
        self.net_rendercom_retry_s = 15
        self.net_timeout = 60
        self.net_last_error = None
        self.net_lost_tick = 0
        # Retry throttling (prevents spam reconnects)
        self.net_last_epoch_attempt = 0
        self.net_is_rate_limited = False
        self.net_is_rate_limited_prev = False

        # Online
        self.online_tick = 0
        self.online_connect_tick = 0
        self.online_waiting_tick = 0
        self.online_offline_tick = 0

        # Lobby
        self.lobbies = []
        self.lobby_browser_tick = 0
        self.lobby_index = 0
        self.lobby_input_epoch = 0
        self.lobby_id, self.lobby_name = None, None

        # ui
        self.ui_ellipse = 0
        self.dots = ""

        # load everything
        self.loadGameSettings()

        # Mode dispatch
        self.update_methods = {
            # menus
            "menu-init": self.initMainMenu,
            "menu": self.updateMainMenu,
            # "menu": self.updateOfflineGame, # comment out later

            # online
            "online-connect-init": self.initOnlineConnect,
            "online-connect": self.updateOnlineConnect,

            "online-waiting-init": self.initOnlineWaiting,
            "online-waiting": self.updateOnlineWaiting,

            "online-offline-init": self.initOnlineOffline,
            "online-offline": self.updateOnlineOffline,

            "lobby-browser-init": self.initLobbyBrowser,
            "lobby-browser": self.updateLobbyBrowser,

            "online-game-init": self.initOnlineGame,
            "online-game": self.updateOnlineGame,

            # offline
            "offline-game-init": self.initOfflineGame,
            "offline-game": self.updateOfflineGame,

            # trans
            "transON-init": self.initTransToPlayOnline,
            "transOFF-init": lambda:self.renderTransition(new_mode="offline-game-init"),

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
                print(f"websocket_loop : DEBUG : connected to server")

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
            print(f"websocket_loop : DEBUG : websocket error (self.net_last_error) :", self.net_last_error)

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
    
    def has_connection_refused(self):
        return (
            self.net_last_error
            and any(err in self.net_last_error for err in ( "remote computer refused", "getaddrinfo failed", "http 404", "http 403"))
        )

    def clear_network_queues(self):
        while not self.net_in.empty():
            self.net_in.get_nowait()
        while not self.net_out.empty():
            self.net_out.get_nowait()

    # ========================================================
    # Menu Actions
    #region Actions

    def action_playOnline(self):
        # reset ticks
        self.online_tick = 0

        # reset lobby state
        self.lobby_id = None
        self.lobby_name = None
        self.lobby_index = 0

        # switch mode
        self.mode = "online-connect-init" # -> self.updateOnlineConnect
        self.start_network()
    
    def action_playOffline(self):
        # switch mode
        self.mode = "transOFF-init"
        self.transOFF_tick = 0

    def action_screen(self):
        self.rescaleWindow()
    
    def action_quit(self):
        # errorless exit because I think I'm ocd
        try:
            quit()
        finally:
            exit()

    # ========================================================
    # Main Menu
    #region MainMenu

    def initMainMenu(self):
        self.main_menu_tick = 0
        self.entitiesAllDelete()
        self.mode = "menu"

    def updateMainMenu(self):
        self.main_menu_tick += 1
        keys = pygame.key.get_pressed()
        now = time.time()

        # Volume sprites
        if self.main_menu_tick == 1:
            self.main_menu_speaker = py_sprites.Speaker()

            # Volume sprite
            self.entities["decor"].append(self.main_menu_speaker.summon(target_row=config.MAX_ROW-3,target_col=2, screen=self.screen))

            # Generate demo sprites
            self.entities["ai"].append(py_sprites.CPUPlayer().summon(target_row=5,target_col=config.MAX_COL-2,initial_sprite_index=2,screen=self.screen))
            self.entities["ai"].append(py_sprites.CPUPlayer().summon(target_row=5,target_col=2,initial_sprite_index=0,screen=self.screen))

            self.entities["balls"].append(py_sprites.Ball().summon(target_col=config.MAX_COL//2, target_row=5, screen=self.screen))
            # self.entities["balls"][0].set_velocity(1,0)
        
        self.main_menu_speaker.sync_sprite_with_volume()
        
        # --- Demo gameplay ---
        for entity in self.entitiesAllReturn():
            entity.ticker()
            if hasattr(entity, "_do_task_demo"):
                if "CPU" in entity.__class__.__name__:
                    entity._do_task_demo(self.entities["balls"][0])
                else:
                    entity._do_task_demo()
            

            # Collision check demo
            for ball in self.entities["balls"]:
                # -- Ball v. Player
                for player in self.entities["ai"]:
                    if self.check_collision(ball.sprite_rect, player.sprite_rect):

                        # Successful hit, but check owner to prevent multiple hit registrations
                        if not ball.owner or ball.owner != player:
                            print(f"updateMainMenu: {ball.owner} hit by {player}")
                            soundMixer.play("bonk", f"audio/bonk{randint(1,2)}.ogg",vol_mult=self.game_volume)
                            ball.owner = player
                            ball.set_velocity_basedOnPlayerMotion(player)
            
            # Check screen edge for ball redirect
            ball: py_sprites.Ball
            for ball in self.entities["balls"]:
                ball.redirect_if_on_edge(soundMixer=soundMixer,soundVolumeOverride=0)
                if ball.query_isOffscreen() and ball.edge_collision_buffer_ignore > 0:
                    ball.respawn()
                    
                    inverse = -1 if randint(0,1) == 0 else 1
                    ball.set_velocity(velocity_x=1*inverse,velocity_y=1*inverse)
            
        # --- --- --- --- --- --- --- --- --- --- --- --- #

        # Determine actions made by the user's key presses
        if now - self.menu_input_epoch > self.menu_input_cooldown:

            # Check if we need to save settings or not.
            settingsChanged = False 

            if inputManager.get_action("up", keys):
                soundMixer.play("scroll", "audio/scroll.ogg",vol_mult=self.game_volume)
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
                self.menu_input_epoch = now

            elif inputManager.get_action("down", keys):
                soundMixer.play("scroll", "audio/scroll.ogg",vol_mult=self.game_volume)
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
                self.menu_input_epoch = now

            elif inputManager.get_action("select", keys):
                self.menu_input_epoch = now
                soundMixer.play("select", "audio/select.ogg",vol_mult=self.game_volume)
                action = self.menu_actions.get(self.menu_items[self.menu_index])
                if action:
                    action()
                    self.entities["decor"].clear() # clears the Speaker sprite
                    self.menu_input_epoch = now + 0.1
                    self.lobby_input_epoch = now + 0.1 # prevents the user from accidentally falling into a lobby
                    return
            
            # Volume
            elif inputManager.get_action("vol-down",keys):
                soundMixer.play("bonk", f"audio/bonk{randint(1,2)}.ogg",vol_mult=self.game_volume)
                # Save new volume
                new_sound_volume = round( max(0, self.game_volume - .1), 1)
                config.redefine(volume=new_sound_volume)
                self.game_volume = new_sound_volume

                # update menu input epoch
                self.menu_input_epoch = now

                # flag the change
                settingsChanged = True
            elif inputManager.get_action("vol-up",keys):
                soundMixer.play("bonk", f"audio/bonk{randint(1,2)}.ogg",vol_mult=self.game_volume)
                # Save new volume
                new_sound_volume = round( min(1.0, self.game_volume + .1), 1)
                config.redefine(volume=new_sound_volume)
                self.game_volume = new_sound_volume

                # update epoch
                self.menu_input_epoch = now

                # flag change
                settingsChanged = True

            
            if settingsChanged:
                # save settings
                self.saveGameSettings()


        self.renderMenuText(volume=self.game_volume)

    # ========================================================
    # Online Connect / Waiting
    #region OnlineConnect
    def initOnlineConnect(self):
        self.online_connect_tick = 0
        self.entitiesAllDelete()
        self.mode = "online-connect"

    def updateOnlineConnect(self):
        self.online_connect_tick += 1

        # Escalate into cold-boot waiting state
        if self.has_handshake_timeout():
            self.net_connected_epoch = time.time()
            self.net_last_epoch_attempt = 0
            self.mode = "online-waiting" # -> self.updateOnlineWaiting
            
            return
        
        # Dev: the user forgot to launch their server
        if self.has_connection_refused():
            self.entities["ui"] = render_text(f"````(DEV)`Server settings failed```{self.net_last_error}`````@This screen is permanent``until restart.&")
            return
            

        # Defer to only every 30 frames, (2 times a second)
        if self.online_connect_tick % 30 == 0:
            self.ui_ellipse += 1
            self.dots = "." * ((self.ui_ellipse % 3) + 1)

        # If the player is ALREADY CONNECTED online, redirect to lobby menu
        if self.net_connected:
            soundMixer.play("connection_connected", "audio/connection_connected.ogg",vol_mult=self.game_volume)
            self.net_out.put(json.dumps({"type": "list_lobbies"}))
            self.mode = "lobby-browser" # -> self.updateLobbyBrowser
            return

        # Failsafe: eject to lost connection menu after timeout
        if self.online_connect_tick >= config.frame_rate * self.net_timeout/2:
            self.mode = "lost-init" # -> self.updateLost
            return

        self.entities["ui"] = render_text(
            f"``CONNECTING TO`¬@ONRENDER.COM{self.dots}``"
        )

    #region OnlineWaiting
    def initOnlineWaiting(self):
        self.online_waiting_tick = 0
        self.entitiesAllDelete()
        self.mode = "online-waiting"


    def updateOnlineWaiting(self):
        # duplicate tick so we can reuse ellipse dotting
        self.online_waiting_tick += 1

        # SUCCESS: connection established while waiting
        if self.net_connected:
            self.net_last_error = None
            self.net_connected_epoch = 0
            self.net_last_epoch_attempt = 0

            self.net_out.put(json.dumps({"type": "list_lobbies"}))
            self.mode = "lobby-browser" # -> self.updateLobbyBrowser
            return

        # capture epoch of connection (INTEGER) a bit hacky but works
        elapsed = int(f"{(time.time() - self.net_connected_epoch):.0f}")

        # Defer to every 30 frames, (2 times a second)
        if self.online_waiting_tick % 30 == 0:
            self.ui_ellipse += 1
            self.dots = "." * ((self.ui_ellipse % 3) + 1)

            # change the colour of the elapsed time to indicate sent attempt
            elapsed_net_out_colour = "@" if elapsed % self.net_rendercom_retry_s == 0 else ""

            self.entities["ui"] = render_text(
                 "``SERVER IS COLD BOOTING``"
                f"``THIS MAY TAKE UP TO {self.net_rendercom_timeout} SECONDS.`BUT USUALLY TAKES 60`"
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
    def initOnlineOffline(self):
        self.online_offline_tick = 0
        self.entitiesAllDelete()
        self.mode = "online-offline"

    def updateOnlineOffline(self):
        self.online_offline_tick += 1

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
    #region Lobby Browse
    def initLobbyBrowser(self):
        self.lobby_browser_tick = 0
        self.entitiesAllDelete()
        self.mode = "lobby-browser"

    def updateLobbyBrowser(self):
        self.lobby_browser_tick += 1

        keys = pygame.key.get_pressed()
        now = time.time()


        while not self.net_in.empty():
            raw = self.net_in.get()

            # Ignore non-JSON noise (+prevent crashes)
            if not raw or raw[0] != "{":
                continue

            msg = json.loads(raw)
            msg_type = msg.get("type")

            # --- Check if the user got rate limited ---
            self.net_is_rate_limited = ("rate_limited" in msg_type)
            if self.net_is_rate_limited_prev != self.net_is_rate_limited:
                self.net_is_rate_limited_prev = self.net_is_rate_limited
                soundMixer.play("connection_rl", "audio/connection_rl.ogg",vol_mult=self.game_volume)
            print(f"updateLobbyBrowser: net_is_rate_limited: {self.net_is_rate_limited}")

            # --- Check for lobby assoicated things ---
            if not self.net_is_rate_limited:

                if msg_type == "lobby_list":
                    self.lobbies = msg.get("lobbies", [])

                elif msg_type == "lobby_status":
                    # set lobby info if joined
                    
                    self.lobby_id = msg.get("id")
                    self.lobby_name = msg.get("name")

                    if self.lobby_id and self.lobby_name:
                        soundMixer.play("lobby_create", "audio/lobby_create.ogg",vol_mult=self.game_volume)
                    else:
                        soundMixer.play("lobby_leave", "audio/lobby_leave.ogg",vol_mult=self.game_volume)

                elif msg_type == "start_game":
                    self.mode = "transON-init"
        

        # User inputs
        if now - self.lobby_input_epoch > 0.2 and not self.mode in ["transON-init", "transOFF-init"]:
            
            # Run these always
            # print(f"updateLobbyBrowser: .get_action('create' : {inputManager.get_action("create", keys)} : .get_action('leave', keys) : {inputManager.get_action("leave", keys)}")
            if inputManager.get_action("create", keys) and (not self.lobby_id) and (not self.net_is_rate_limited):
                print(f"updateLobbyBrowser : creating lobby")
                self.net_out.put(json.dumps({
                    "type": "create_lobby",
                    "owner": self.client_id_hash
                }))
                self.lobby_input_epoch = now
            
            elif inputManager.get_action("leave", keys) and (self.lobby_id) and (not self.net_is_rate_limited):
                print(f"updateLobbyBrowser : checking input keys")
                if self.lobby_id and inputManager.get_action("leave", keys):
                    print(f"updateLobbyBrowser : leave lobby")
                    self.net_out.put(json.dumps({"type": "leave_lobby"}))
                    self.lobby_input_epoch = now

            elif inputManager.get_action("back", keys):
                self.mode = "menu-init"


            # !! Gatekeep any further actions if CLIENT IS IN A LOBBY !!
            elif self.lobby_id is not None:
                return # <-- exit early
            

            if inputManager.get_action("up", keys):
                soundMixer.play("scroll", "audio/scroll.ogg",vol_mult=self.game_volume)
                self.lobby_index = max(0, self.lobby_index - 1)
                self.lobby_input_epoch = now

            elif inputManager.get_action("down", keys):
                soundMixer.play("scroll", "audio/scroll.ogg",vol_mult=self.game_volume)
                self.lobby_index = min(len(self.lobbies) - 1, self.lobby_index + 1)
                self.lobby_input_epoch = now

            elif inputManager.get_action("select", keys):
                soundMixer.play("scroll", "audio/scroll.ogg",vol_mult=self.game_volume)
                if not self.lobby_id:
                    # Prevent an index in empty 'self.lobbies[]' crash
                    if len(self.lobbies) == 0:
                        return
                    # Join a lobby
                    lobby_id = self.lobbies[self.lobby_index]["id"]
                    self.net_out.put(json.dumps({
                        "type": "join_lobby",
                        "id": lobby_id
                    }))
                self.lobby_input_epoch = now

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
                    py_sprites.Cell().summon(
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
                self.mode = "online-gamee"
                self.trans_spawned_cols = 0
                self.trans_spawned_rows = 0
                return

            ui_entities.pop(0)

    def initOnlineGame(self):
        self.mode = "online-game"

    def updateOnlineGame(self):
        # # UPDATE LOGIC: 60FPS
        # self.playON_tick += 1
        # keys = pygame.key.get_pressed()

        # # --- Setup on first frame ---
        # if self.playON_tick == 1:

        #     self.net_in.get()
        #     self.playON_draw_line = True

        #     # Load stage, auto assigns
        #     self.entities = self.entitiesAppend(self.stager.load_stage(resource_path("stages/classic.stage")))


        # # Draw one dash 12 times a second
        # if self.playOFF_tick % 5 == 0 and self.playOFF_draw_line:
        #     center_col = config.MAX_COL // 2
        #     # spawn a single dash at the next row
        #     dash_row = self.playOFF_drawn_lines % (config.RES_Y_INIT // 8)
        #     self.entities["decor"].append(
        #         sprites.Dashline().summon(
        #             screen=self.screen,
        #             target_col=center_col,
        #             target_row=dash_row
        #         )
        #     )
        #     if self.playOFF_drawn_lines >= 22:
        #         self.playOFF_draw_line = False
            
        #     self.playOFF_drawn_lines += 1

            
        # # --- Game only starts once line has been drawn. ---
        # if self.playOFF_draw_line:
        #     return
        # # --- --- --- --- --- ---

        # player60: sprites.Player
        # ball60: sprites.Ball
        # ai60: sprites.CPUPlayer
        # # Update the players
        # for player60 in self.entities["players"]:
        #     player60.task_wss(keys)
        #     self.net_out.put()
        
        # # Update the balls
        # for ball60 in self.entities["balls"]:
        #     ball60.task()

        
        # # Check collisions
        # goal: sprites.Goal
        # ball: sprites.ClientBall
        # player: sprites.ClientPlayer

        # for ball in self.entities["balls"]:
        #     # -- Ball v. Player
        #     for player in self.entities["players"]+self.entities["ai"]:
        #         if self.check_collision(ball.sprite_rect, player.sprite_rect):

        #             # Successful hit, but check owner to prevent multiple hit registrations
        #             if not ball.owner or ball.owner != player:
        #                 print(ball.owner, "hit by", player)
        #                 ball.owner = player
        #                 ball.set_velocity_basedOnPlayerMotion(player)
            
        #     # -- Ball v. Goals
        #     for goal in self.entities["goals"]:
        #         if ball.gotScored: continue
        #         if self.check_collision(goal.sprite_rect, ball.sprite_rect):
                    
        #             # Set flag
        #             ball.gotScored = True

        #             # Halt game (starts next frame)
        #             self.game_halt_for_x_ticks = 180
        #             self.game_goal_scored = True

        #             # Which post?
        #             goal_name = goal.__class__.__name__
        #             if "Left" in goal_name:
        #                 self.game_scores[2] += 1
        #                 ball.set_velocity(-1,0) # reset, set velocity toward Left player
        #             elif "Right" in goal_name:
        #                 self.game_scores[0] += 1
        #                 ball.set_velocity(1,0) # reset, set velocity toward Right player

        #             # Check which goal belongs
        #             print(goal.__class__.__name__)
        
        # # Check screen edge for ball redirect
        # for ball in self.entities["balls"]:
        #     # if ball.sprite_rect.left <= 0 or ball.sprite_rect.right >= config.res_x:
        #     #     ball.set_velocity(-ball.velocity_x, ball.velocity_y)
        #     if ball.sprite_rect.top <= 0 or ball.sprite_rect.bottom >= config.res_y:
        #         print("edging!")
        #         ball.set_velocity(ball.velocity_x, -ball.velocity_y)

        
        # # -- debug, return ball back
        # if keys[pygame.K_f]:
        #     print("DEBUG: resetting ball position")
        #     for ball in self.entities["balls"]:
        #         ball.gotScored = False
        #         ball.current_speed = ball.base_speed
        #         ball.owner = None
        #         ball.set_velocity(-1,0)
        #         ball.move_position(dcol=config.MAX_COL // 3, drow=config.MAX_ROW // 2, set_position=True)
        


        # # testing ui
        # ui = render_text(f"¬¬¬   {self.game_scores[0]}   {self.game_scores[2]}`````````````````````(P1) {self.game_player_names[0]}¬¬¬   {self.game_player_names[2]} (P2)", justification=None)
        # # ui = render_text("0   0`A`A`A`A`A`A`A`A`A`A`A`A`A`A")
        
        # self.entities["ui"] = ui
        pass

    
    # ========================================================
    # Offline Game
    # region OfflineGame
    def initOfflineGame(self):
        self.transition_tick = 0

        # Playing offline
        self.playOFF_tick = 0
        self.playOFF_countdown_epoch = 0
        self.playOFF_draw_line = False
        self.playOFF_drawn_lines = 0
        self.playOFF_began = False

        self.game_halt_for_x_ticks = 0
        self.game_goal_scored = False
        self.game_scores = [0,0,0,0]
        self.mode = "offline-game"

    

    
    def updateOfflineGame(self):
        #Type hints
        ball: py_sprites.Ball
        entity: py_sprites.Sprite
        entity60: py_sprites.Sprite
        player: py_sprites.Player
        goal: py_sprites.Goal

        # UPDATE LOGIC: 60FPS
        self.playOFF_tick += 1
        keys = pygame.key.get_pressed()

        # --- Setup on first frame ---
        if self.playOFF_tick == 1:
            self.playOFF_draw_line = True

            # Load stage, auto assigns
            self.entities = self.entitiesAppend(self.stager.load_stage(resource_path("stages/classic.stage")))


        # --- Halt frames ---
        if self.game_halt_for_x_ticks>0:
            self.game_halt_for_x_ticks-=1
            return
        
        # was the game halted because of a scored ball?
        if self.game_goal_scored:
            self.game_goal_scored = False

            # - END GAME?
            if 3 in self.game_scores:
                self.game_verdict = "END"
                self.mode = "menu-init"

            # - respawn balls
            for ball in self.entities["balls"]:
                ball.gotScored = False
                ball.respawn()
                # (velocity is set as the ball is scored.)

            # - respawn players and ai
            for player in self.entities["players"]+self.entities["ai"]:
                player.respawn()

        # should anything respawn?
        for entity60 in self.entities["players"]+self.entities["ai"]+self.entities["balls"]:
            if entity60.mark_for_respawn:
                entity60.respawn()


        # Tick all entities
        for entity60 in self.entitiesAllReturn():
            entity60.ticker()

        # Draw one dash 12 times a second
        if self.playOFF_tick % 5 == 0 and self.playOFF_draw_line:
            center_col = config.MAX_COL // 2
            # spawn a single dash at the next row
            dash_row = self.playOFF_drawn_lines % (config.RES_Y_INIT // 8)
            self.entities["decor"].append(
                py_sprites.Dashline().summon(
                    screen=self.screen,
                    target_col=center_col,
                    target_row=dash_row
                )
            )
            if self.playOFF_drawn_lines >= 22:
                self.playOFF_draw_line = False
            
            self.playOFF_drawn_lines += 1

            
        # --- Game only starts once line has been drawn. ---
        if self.playOFF_draw_line:
            self.playOFF_began = True
            return
        # --- --- --- --- --- ---

        if self.playOFF_began:
            self.playOFF_began = False
            soundMixer.play("initial_velocity", f"audio/initial_velocity.ogg",vol_mult=self.game_volume)

        # Update the player
        for entity60 in self.entities["players"]:
            entity60.task(keys)
        
        # Update the balls
        for entity60 in self.entities["balls"]:
            entity60.task()

        # Update the ai
        for entity60 in self.entities["ai"]:
            entity60.task(self.entities["balls"][0])
        
        # Check collisions
        for ball in self.entities["balls"]:
            # -- Ball v. Player
            for player in self.entities["players"]+self.entities["ai"]:
                if self.check_collision(ball.sprite_rect, player.sprite_rect):

                    # Successful hit, but check owner to prevent multiple hit registrations
                    if not ball.owner or ball.owner != player:
                        print(f"updateOfflineGame: {ball.owner} hit by {player}")
                        soundMixer.play("bonk", f"audio/bonk{randint(1,2)}.ogg",vol_mult=self.game_volume)
                        ball.owner = player
                        ball.set_velocity_basedOnPlayerMotion(player)
            
            # -- Ball v. Goals
            for goal in self.entities["goals"]:
                if ball.gotScored: continue
                if self.check_collision(goal.sprite_rect, ball.sprite_rect):
                    
                    # Set flag
                    ball.gotScored = True


                    # Halt game (starts next frame)
                    self.game_halt_for_x_ticks = 180
                    self.game_goal_scored = True

                    # Which post?
                    goal_name = goal.__class__.__name__
                    if "Left" in goal_name:
                        self.game_scores[2] += 1
                        soundMixer.play("goal_opponent", "audio/scored_opponent.ogg",vol_mult=self.game_volume)
                        ball.set_velocity(-1,0) # reset, set velocity toward Left player
                    elif "Right" in goal_name:
                        self.game_scores[0] += 1
                        soundMixer.play("goal_client", "audio/scored_client.ogg",vol_mult=self.game_volume)
                        ball.set_velocity(1,0) # reset, set velocity toward Right player

                    # Check which goal belongs
                    print(f"updateOfflineGame: goal.__class__.__name__ : {goal.__class__.__name__}")
        
        # Check screen edge for ball redirect
        for ball in self.entities["balls"]:
            ball.redirect_if_on_edge(soundMixer=soundMixer)

        
        # -- debug, return ball back
        if keys[pygame.K_f]:
            print("DEBUG: resetting ball position")
            for ball in self.entities["balls"]:
                ball.gotScored = False
                ball.current_speed = ball.base_speed
                ball.owner = None
                ball.set_velocity(-1,0)
                ball.move_position(dcol=config.MAX_COL // 3, drow=config.MAX_ROW // 2, set_position=True)
        


        # testing ui
        ui = render_text(f"¬¬¬   {self.game_scores[0]}   {self.game_scores[2]}`````````````````````(P1) {self.game_player_names[0]}¬¬¬   {self.game_player_names[2]} (P2)", justification=None)
        # ui = render_text("0   0`A`A`A`A`A`A`A`A`A`A`A`A`A`A")
        
        self.entities["ui"] = ui

     

    # ========================================================
    # Lost Connection
    #region LostConnection

    def initLostConnectionMenu(self):
        self.net_lost_tick = 0
        soundMixer.play("connection_lost", "audio/connection_lost.ogg",vol_mult=self.game_volume)
        self.entitiesAllDelete()
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
            py_sprites.loadSprite([resource_path("sprites/cell.png")])
        )
        pygame.display.set_caption("PyPongOnline")

        set_always_on_top()

        # load UI setting
        saveGameSettings = os.path.exists("game_settings.txt")
        if not saveGameSettings:
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

            # Dev: halt the main loop
            if self.mainloop_halt_for_x_ticks > 0:
                self.mainloop_halt_for_x_ticks -= 1

            # Detect true connection loss (not cold-boot)
            if (
                self.net_wasConnected
                and not self.net_connected
                and self.mode not in ("lost", "lost-init", "online-waiting", "online-offline")
                and not self.has_handshake_timeout()
            ):
                self.mode = "lost-init"


            # Mode dispatch
            self.update_methods.get(self.mode, lambda: print(f"main : ⚠️  Warning: No update method implemented for self.mode: {self.mode}"))()

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
    
    def entitiesAppend(self, new_entities):
        for team, items in new_entities.items():
            for ent in items:
                if ent not in self.entities[team]:
                    self.entities[team].append(ent)
        return self.entities



    def entitiesAllReturn(self):
        return [e for lst in self.entities.values() for e in lst]
    
    def entitiesAllDelete(self):
        self.entities = {k: [] for k in self.entities}
        return self.entities
    
    # -- Collision Detection
    def check_collision(self, rect_a, rect_b):
        """Return True if two rects collide."""
        if not rect_a or not rect_b:
            return False

        collided = rect_a.colliderect(rect_b)
        return collided
    
    # -- File game setting
    def saveGameSettings(self, override_scale=None, override_volume=None):
        scale = override_scale if override_scale is not None else config.resolution_scale
        volume = override_volume if override_volume is not None else config.volume_multiplier

        with open(gamesettings_filename, "w") as f:
            f.write(f"window_scale={scale}\n")
            f.write(f"volume={volume}\n")

    
    def loadGameSettings(self):
        try:
            with open(gamesettings_filename, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("window_scale="):
                        scale = int(line.replace("window_scale=", "").strip())
                        config.redefine(scale=scale)

                    elif line.startswith("volume="):
                        volume = float(line.replace("volume=", "").strip())
                        config.redefine(volume=volume)
                        self.game_volume = config.volume_multiplier # Sets from CONFIG
        except Exception as e:
            print(f"loadGameSettings : settings failed to load (outdated or corrupted? we make a new file instead) : {e}")
            self.saveGameSettings()
            self.loadGameSettings()


    # ========================================================
    # UI Rendering
    #region UI

    def renderTransition(self,new_mode):
        self.transition_tick += 1

        # First-frame cleanup
        if self.transition_tick == 1:
            self.entitiesAllDelete()

        CELLS_PER_FRAME = 14
        ui_entities = self.entities["ui"]

        # Sound timing (every half batch)
        if self.transition_tick % (CELLS_PER_FRAME // 2) == 0:
            self.transition_sfx_interval += 1
            soundMixer.play("transition", "audio/transition.ogg",vol_mult=self.game_volume*0.1)



        for _ in range(CELLS_PER_FRAME):

            # Spawn phase
            if self.transition_spawned_rows <= config.MAX_ROW:
                ui_entities.append(
                    py_sprites.Cell().summon(
                        target_row=self.transition_spawned_rows,
                        target_col=self.transition_spawned_cols,
                        colour=(100, 100, 100),
                        screen=self.screen
                    )
                )

                # Advance grid position
                self.transition_spawned_cols += 1
                if self.transition_spawned_cols >= config.MAX_COL:
                    self.transition_spawned_cols = 0
                    self.transition_spawned_rows += 1
                continue  # do not delete on the same iteration

            # Delete phase
            if not ui_entities:
                # Transition complete
                self.transition_frame_count = 0
                self.mode = new_mode
                print(f"renderTransition : switching to new mode : {self.mode}")
                self.transition_spawned_cols = 0
                self.transition_spawned_rows = 0
                return

            ui_entities.pop(0)

    def renderMenuText(self, volume=None):

        volume = f"@VOL& {volume:.1f}" if volume is not None and debug == True else "`"
        title = f"{volume}````````````&"
        body = ""

        for i, item in enumerate(self.menu_items):
            prefix = "#> " if i == self.menu_index else "&  "
            suffix = "#< " if i == self.menu_index else "&  "
            body += f"{prefix}{item} {suffix}``"

        self.entities["ui"] = render_text(title + body)

    def renderLobbyUI(self):

        # -- Punish rate limiter
        if self.net_is_rate_limited:
            self.entities["ui"] = render_text("``:STOP SPAMMING&``Try again later``````@ESC &Back")
            return


        # -- Generate the usual 
        text = "``AVAILABLE LOBBIES``"

        for i, lobby in enumerate(self.lobbies):

            # Highlight current lobby
            is_current = lobby["id"] == self.lobby_id
            if is_current:
                prefix = "@(YOU) "
            else:
                # else, highlight selection if not in a lobby
                prefix = "#> " if i == self.lobby_index and not self.lobby_id else "&  "
            text += f"{prefix}{lobby['name']} ({lobby['players']}/{lobby['max_players']})``"

        # Bottom UI
        if self.lobby_id:
            text += (
                "````"
                "&@L& LEAVE LOBBY``"
                f"&({self.lobby_name})``"
            )
        else:
            text += "````&@C& CREATE LOBBY``"


        text += "&@ESC& BACK``"

        self.entities["ui"] = render_text(text)



# Entry
if __name__ == "__main__":

    # increase build version
    if not running_as_exe():
        with open("buildver.txt", "r+") as f:
            new = int(f.read() or 0) + 1
            f.seek(0), f.write(str(new)), f.truncate()



    # run the main game
    ClientGame().main()
