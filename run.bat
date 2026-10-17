@echo off
cd /d "%~dp0"
python -m streamlit run app.py --theme.base=dark --theme.primaryColor=#00E5FF --theme.backgroundColor=#07080C --theme.secondaryBackgroundColor=#11131A --theme.textColor=#F8FAFC
pause
