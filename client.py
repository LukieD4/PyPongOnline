import asyncio
import websockets

async def test():
    uri = "wss://pypongonline.onrender.com/ws"
    async with websockets.connect(uri) as ws:
        await ws.send("Hello from UK 🇬🇧")
        print(await ws.recv())

asyncio.run(test())
