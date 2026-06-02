@echo off
cd /d "%~dp0.."
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless true
