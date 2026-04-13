@echo off
cd /d C:\dev\01_projects\06_mcp-memory
set PYTHONIOENCODING=utf-8
set PATH=C:\Users\pauls\AppData\Local\Programs\Python\Python312;%PATH%
python scripts\daily_enrich.py %* >> data\reports\enrich-log.txt 2>&1
