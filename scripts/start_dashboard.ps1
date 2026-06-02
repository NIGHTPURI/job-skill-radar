$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
& ".\.venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless true
