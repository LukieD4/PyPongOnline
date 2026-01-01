# PyPongOnline
*A simple 2D Pong game with robust online connectivity.*

## 📌 Overview
PyPongOnline is a Python-oriented Pong clone featuring:

## Networking
- Connects to https://render.com/.
- Creates a Web Socket Server players can connect to.
- The online service is dormant, and requires cold booting if inactive for too long.
> The service will remain alive as long as render.com is still operational (01/01/2026), and their (hobbyist) free-tier hasn't changed.

## Solo / CPU (AI)
- Classic mode
- Foosball (tbd)
- 4-way pong (tbd)

## Online / Multiplayer
- Lobby system, heavily focussed on UX and UI
- Usernames are 5 characters long (tbd)
- Passwords (tbd)

## Framework
- Based on an older project at 'https://github.com/LukieD4/SpaceInvadies'
- Refactored scripts to offer more scalability

## File size
An unoptimised build takes us to around 50MB, and for a Pong Game it left a bad taste.
- `build_client_nuitka_onefile.bat` impressive compression, instantanious loading times; BUT takes 5 minutes to compile.
> Struggled to embed `sprites/` and `stages/` inside of exe, so they are uploaded individually.
- `build_client_pyinstaller.bat` substandard compression, very elongated loading times; BUT takes 1 minute to compile.
> (Ryzen 7 7800X3D CPU, Samsung SSD 990 PRO 2TB (NVMe))
- `numpyStub.py` to shave off a few MBs; we use only what we NEED to use.

## Server Hosting
- If unchanged it will redirect to my web server hosted on Render.com (for free!)
- Change the uri link in __init__ of `ClientGame`
- Or use a local wss via `server.py` (uncomment out `self.uri = "ws://localhost:8000/ws"`)

---
## @LukieD4 on GitHub, I love programming :3
