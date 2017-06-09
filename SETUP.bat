@ECHO OFF
ECHO.
ECHO Downloading required packages to run clash grouper app...
ECHO.
python.exe -m pip install -U pip
ECHO.
python.exe -m pip install -r requirements.txt
ECHO.
ECHO Done setting up the clash grouper app.
ECHO.
@PAUSE