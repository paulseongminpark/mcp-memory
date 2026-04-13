@echo off
REM mcp-memory daily enrichment — Task Scheduler용
REM 새벽 6시 자동 실행

cd /d C:\dev\01_projects\06_mcp-memory
set PYTHONIOENCODING=utf-8
set PATH=C:\Users\pauls\AppData\Local\Programs\Python\Python312;%PATH%

echo [%date% %time%] daily-enrich START >> data\daily-enrich.log
python scripts\daily_enrich.py %* >> data\daily-enrich.log 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] daily-enrich END (exit=%EXIT_CODE%) >> data\daily-enrich.log
exit /b %EXIT_CODE%
