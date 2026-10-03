@echo off
setlocal

set "WORKSPACE=%cd%\"

python -m venv %WORKSPACE%.venv
call %WORKSPACE%.venv\Scripts\activate.bat
pip install -r %WORKSPACE%requirements.txt

endlocal