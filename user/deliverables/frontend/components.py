import subprocess
import sys
import time
import webview
from pathlib import Path

APP_PATH = Path(__file__).parent / "main.py"

process = subprocess.Popen([
    sys.executable,
    "-m", "streamlit",
    "run", str(APP_PATH),
    "--server.headless=true",
    "--server.port=8501"
])

time.sleep(3)

webview.create_window(
    "EDETH",
    "http://localhost:8501",
    width=1200,
    height=800
)

webview.start()

process.terminate()
process.wait()