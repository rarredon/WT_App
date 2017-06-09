@ECHO OFF
ECHO.
ECHO Starting the clash grouper app...
START /B python.exe src\application_local.py 2> NUL
ECHO Started.
ECHO.
ECHO Opening the default web browser...
START "" "http://localhost:5000"
ECHO Opened.
ECHO.
ECHO Notes on using the app:
ECHO.
ECHO     Keep this window open until you are done using the app. 
ECHO.
ECHO     If you close your web browser but this window is still
ECHO     open and you wish to resume using the app, simply type
ECHO     this URL into your browser: http://localhost:5000.
ECHO.
ECHO     Change the default path configuration by editing the
ECHO     file 'clash_util.ini'.
