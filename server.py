from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
clients = set()

@app.get("/")
def root():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            msg = await ws.receive_text()
            for client in clients:
                if client != ws:
                    await client.send_text(msg)
    except WebSocketDisconnect:
        clients.remove(ws)
