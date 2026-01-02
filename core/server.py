from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import uuid
import random

app = FastAPI()

# -----------------------------
# Global state
# -----------------------------

clients: dict[WebSocket, dict] = {}
lobbies: dict[str, dict] = {}

# -----------------------------
# Helpers
# -----------------------------

async def send(ws: WebSocket, payload: dict):
    await ws.send_text(json.dumps(payload))


async def broadcast_lobbies():
    payload = {
        "type": "lobby_list",
        "lobbies": [
            {
                "id": lid,
                "name": lobby["name"],
                "players": len(lobby["players"]),
                "max_players": lobby["max_players"],
            }
            for lid, lobby in lobbies.items()
        ],
    }

    for ws in list(clients):
        await send(ws, payload)


async def send_lobby_status(ws: WebSocket):
    lobby_id = clients[ws]["lobby"]

    if lobby_id and lobby_id in lobbies:
        lobby = lobbies[lobby_id]
        await send(ws, {
            "type": "lobby_status",
            "id": lobby["id"],
            "name": lobby["name"],
        })
    else:
        await send(ws, {
            "type": "lobby_status",
            "id": None,
            "name": None,
        })


def remove_from_lobby(ws: WebSocket):
    lobby_id = clients.get(ws, {}).get("lobby")
    if not lobby_id:
        return

    lobby = lobbies.get(lobby_id)
    if not lobby:
        return

    if ws in lobby["players"]:
        lobby["players"].remove(ws)

    # Delete empty lobby
    if not lobby["players"]:
        lobbies.pop(lobby_id, None)

    clients[ws]["lobby"] = None


# -----------------------------
# Routes
# -----------------------------

@app.get("/")
def root():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients[ws] = {"lobby": None}

    try:
        while True:
            raw = await ws.receive_text()

            # Ignore non-JSON garbage
            if not raw or raw[0] != "{":
                continue

            msg = json.loads(raw)
            msg_type = msg.get("type")

            # -----------------------------
            # LIST LOBBIES
            # -----------------------------
            if msg_type == "list_lobbies":
                await broadcast_lobbies()
                await send_lobby_status(ws)

            # -----------------------------
            # LEAVE LOBBY
            # -----------------------------
            elif msg_type == "leave_lobby":
                remove_from_lobby(ws)
                await send_lobby_status(ws)
                await broadcast_lobbies()

            # -----------------------------
            # CREATE LOBBY
            # -----------------------------
            elif msg_type == "create_lobby":
                # Already in a lobby → reject
                if clients[ws]["lobby"] is not None:
                    await send(ws, {
                        "type": "error",
                        "message": "already_in_lobby"
                    })
                    continue

                lobby_id = str(uuid.uuid4())[:8]

                words = [
                    "PONG","BALL","WHAM","SPIN","GAME","PLAY","MISS","BEEP",
                    "DING","BUMP","WALL","NETS","EDGE","ZONE","DUEL","COOP",
                    "MODE","FAST","SLOW","HOST","JOIN"
                ]
                name = f"{random.choice(words)}-{random.randint(1000,9999)}"

                lobbies[lobby_id] = {
                    "id": lobby_id,
                    "owner": msg.get("owner", "Anon"),
                    "name": name,
                    "players": [ws],
                    "max_players": 2,
                }

                clients[ws]["lobby"] = lobby_id

                await send_lobby_status(ws)
                await broadcast_lobbies()

            # -----------------------------
            # JOIN LOBBY
            # -----------------------------
            elif msg_type == "join_lobby":
                # Already in a lobby → reject
                if clients[ws]["lobby"] is not None:
                    await send(ws, {
                        "type": "error",
                        "message": "already_in_lobby"
                    })
                    continue

                lobby_id = msg.get("id")
                lobby = lobbies.get(lobby_id)

                if not lobby:
                    continue

                if len(lobby["players"]) >= lobby["max_players"]:
                    continue

                lobby["players"].append(ws)
                clients[ws]["lobby"] = lobby_id

                await send_lobby_status(ws)
                await broadcast_lobbies()

                # Auto-start when full
                if len(lobby["players"]) == lobby["max_players"]:
                    for player in lobby["players"]:
                        await send(player, {"type": "start_game"})

            else:
                pass

    except WebSocketDisconnect:
        pass

    finally:
        remove_from_lobby(ws)
        clients.pop(ws, None)
        await broadcast_lobbies()
