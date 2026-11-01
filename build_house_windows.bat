@echo off
REM Builds the full hobbit house in your own Blender, then opens it ready to walk around.
REM Needs Blender 4.2 or newer: https://www.blender.org/download/
setlocal
set BLENDER="C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
for /d %%D in ("C:\Program Files\Blender Foundation\Blender *") do if exist "%%D\blender.exe" set BLENDER="%%D\blender.exe"
if not exist %BLENDER% (
  echo Could not find Blender. Install it from https://www.blender.org/download/ and run this again.
  pause
  exit /b 1
)
echo Building the house with %BLENDER% ... this takes 10-30 minutes the first time.
%BLENDER% --background --python "%~dp0blender\build_scene.py" -- --blend "%~dp0hobbit_house.blend"
if errorlevel 1 ( echo Build failed - see the messages above. & pause & exit /b 1 )
echo Done. Opening hobbit_house.blend ...
start "" %BLENDER% "%~dp0hobbit_house.blend"
