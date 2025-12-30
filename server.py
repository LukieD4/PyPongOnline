from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import uuid

app = FastAPI()

# Global state
clients: dict[WebSocket, dict] = {}
lobbies: dict[str, dict] = {}


# -----------------------------
# Helpers
#region Helpers

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


def remove_from_lobby(ws: WebSocket):
    for lobby in lobbies.values():
        if ws in lobby["players"]:
            lobby["players"].remove(ws)


# -----------------------------
# Routes
#region Routes

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

            # Defensive: ignore garbage
            if not raw or raw[0] != "{":
                continue

            msg = json.loads(raw)
            msg_type = msg.get("type")


            # LIST LOBBIES
            if msg_type == "list_lobbies":
                await send(ws, {
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
                })


            # CREATE LOBBY
            elif msg_type == "create_lobby":
                lobby_id = str(uuid.uuid4())[:8]

                lobbies[lobby_id] = {
                    "id": lobby_id,
                    "name": msg.get("name", "Lobby"),
                    "players": [],
                    "max_players": 2,
                }

                await broadcast_lobbies()


            # JOIN LOBBY
            elif msg_type == "join_lobby":
                lobby_id = msg.get("id")
                lobby = lobbies.get(lobby_id)

                if not lobby:
                    continue

                if ws in lobby["players"]:
                    continue

                if len(lobby["players"]) >= lobby["max_players"]:
                    continue

                remove_from_lobby(ws)
                lobby["players"].append(ws)
                clients[ws]["lobby"] = lobby_id

                await send(ws, {
                    "type": "joined_lobby",
                    "id": lobby_id,
                })

                await broadcast_lobbies()

                # Auto-start when full (simple rule)
                if len(lobby["players"]) == lobby["max_players"]:
                    for player in lobby["players"]:
                        await send(player, {"type": "start_game"})

            else:
                pass  # ignore any incorrect calls

    except WebSocketDisconnect:
        pass

    finally:
        # Cleanup
        remove_from_lobby(ws)
        clients.pop(ws, None)
        await broadcast_lobbies()
