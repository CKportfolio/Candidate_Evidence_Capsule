@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Najpierw uruchom setup.bat
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python story_mapper.py
echo Wyniki sa w output.
pause
