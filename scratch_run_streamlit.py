import subprocess
import os
import sys

project_dir = r"C:\Users\hp\.gemini\antigravity\scratch\store-intelligence"
python_path = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
streamlit_script = os.path.join(project_dir, "dashboard_streamlit.py")
log_path = os.path.join(project_dir, "streamlit_run.log")

print(f"Starting Streamlit dashboard script at: {streamlit_script}")
print(f"Writing output logs to: {log_path}")

try:
    log_file = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(
        [
            python_path,
            "-u",
            "-m",
            "streamlit",
            "run",
            streamlit_script,
            "--server.port",
            "8501",
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true"
        ],
        stdout=log_file,
        stderr=log_file,
        cwd=project_dir,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if os.name == 'nt' else 0
    )
    log_file.close()
    print(f"Successfully launched Streamlit dashboard (PID: {process.pid})")
except Exception as e:
    print(f"Error launching Streamlit subprocess: {e}")
    sys.exit(1)
