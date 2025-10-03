@echo off
setlocal

REM ---- где держать результат и временные файлы ----
set DIST=build\win
set WORK=build\_work
set SPEC=build\_spec

REM ---- (необязательно) иконка GUI, положи icon.ico рядом с .py ----
set ICON=icon.ico

REM ---- чистим и создаём папки ----
if exist "%DIST%" rmdir /s /q "%DIST%"
if exist "%WORK%" rmdir /s /q "%WORK%"
if exist "%SPEC%" rmdir /s /q "%SPEC%"
mkdir "%DIST%" 2>nul
mkdir "%WORK%" 2>nul
mkdir "%SPEC%" 2>nul

REM ---- активируй своё venv заранее! (.venv\Scripts\activate) ----
REM pip install -U pyinstaller mss pillow pynput

echo [1/3] Building recorder (datagrabber_69)...
pyinstaller --clean --noconfirm ^
  --console ^
  --name datagrabber_69 ^
  --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
  datagrabber_69.py

echo [2/3] Building GUI (TkDatasetRecorder)...
pyinstaller --clean --noconfirm ^
  --windowed ^
  --name TkDatasetRecorder ^
  --distpath "%DIST%" --workpath "%WORK%" --specpath "%SPEC%" ^
  %ICON:%= % ^
  tk_dataset_recorder.py

echo [3/3] Placing recorder next to GUI...
copy /Y "%DIST%\datagrabber_69\datagrabber_69.exe" "%DIST%\TkDatasetRecorder\" >nul

echo.
echo DONE ✅
echo Launch: "%DIST%\TkDatasetRecorder\TkDatasetRecorder.exe"
endlocal
