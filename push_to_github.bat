@echo off
cd /d "%~dp0"
echo Pushing ClassPilot to https://github.com/7xt5/classpilot.git ...
git remote remove origin 2>nul
git remote add origin https://github.com/7xt5/classpilot.git
git push -u origin main --force
echo.
echo Done! Now go to https://share.streamlit.io to deploy 7xt5/classpilot!
pause
