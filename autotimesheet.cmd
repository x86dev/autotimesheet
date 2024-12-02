@ECHO OFF
call .venv\Scripts\activate.bat
python autotimesheet.py %*
deactivate
