@echo off
cd /d C:\dev\01_projects\06_mcp-memory
set PYTHONIOENCODING=utf-8
python scripts\daily_enrich.py >> data\reports\enrich-log.txt 2>&1
