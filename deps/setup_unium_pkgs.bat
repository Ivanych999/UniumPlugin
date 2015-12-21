@echo off
call "%~dp0\o4w_env.bat"
@echo off
"%OSGEO4W_ROOT%"\bin\python-qgis.bat "%OSGEO4W_ROOT%"\apps\Python27\Lib\site-packages\ez_setup.py
"%OSGEO4W_ROOT%"\bin\python-qgis.bat "%OSGEO4W_ROOT%"\apps\qgis\python\plugins\UniumPlugin\deps\openpyxl-2.3.1\setup.py install
pause()