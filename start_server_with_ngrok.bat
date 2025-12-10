@echo off
chcp 65001 >nul
echo ============================================================
echo HS Code 분류 시스템 서버 시작
echo ============================================================
echo.

REM Python 스크립트 실행
python start_server_with_ngrok.py

pause

