@echo off
title PyPong Online Server
cd /d %~dp0

pip install fastapi uvicorn websockets


echo ================================
echo Starting local WebSocket server
echo ================================

uvicorn server:app ^
  --host 0.0.0.0 ^
  --port 8000 ^
  --reload

pause
