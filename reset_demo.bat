@echo off
REM Clears chats, orders and consent records so the demo starts clean. Stop the server first (Ctrl+C).
cd /d %~dp0
del /q runtime\sessions.json runtime\orders.json runtime\privacy.json 2>nul
echo Demo data cleared. Now run run.bat
