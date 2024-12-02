@ECHO OFF
python -m pip install virtualenv
python -m venv .venv
call .venv\Scripts\activate.bat
py -m pip install holidays
deactivate
