@echo off
cd /d "%~dp0.."
set "CHROMA_PATH=%CD%\.chroma"
python seed_chroma.py
if errorlevel 1 (
  echo.
  echo Chroma index was not built.
) else (
  echo.
  echo Done. Start or restart the Text-to-SQL Lab to use this local index.
)
pause
