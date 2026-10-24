@echo off
rem Wird vom Windows Task Scheduler aufgerufen (5x täglich).
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py run_pipeline >> pipeline.log 2>&1
