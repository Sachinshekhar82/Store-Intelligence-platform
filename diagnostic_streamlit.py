import subprocess
import os
import time
import sys

project_dir = r"C:\Users\hp\.gemini\antigravity\scratch\store-intelligence"
python_path = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
streamlit_script = os.path.join(project_dir, "dashboard_streamlit.py")
diagnostic_log = os.path.join(project_dir, "streamlit_diagnostic.log")

print(f"Spawning Streamlit to log: {diagnostic_log}")
try:
    with open(diagnostic_log, "w", encoding="utf-8") as f:
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
            stdout=f,
            stderr=f,
            cwd=project_dir
        )
except Exception as e:
    print(f"Failed to start process: {e}")
    sys.exit(1)

# Sleep for 10 seconds to collect logs
print("Sleeping for 10 seconds to collect bootstrap logs...")
time.sleep(10)

# Terminate process cleanly
print("Terminating process...")
try:
    process.terminate()
    process.wait(timeout=3)
except Exception as e:
    print(f"Failed to terminate process: {e}")

# Read the log content
print("--- STREAMLIT DIAGNOSTIC LOGS ---")
if os.path.exists(diagnostic_log):
    try:
        with open(diagnostic_log, "r", encoding="utf-8") as f:
            print(f.read())
    except Exception as e:
        print(f"Failed to read log file: {e}")
else:
    print("Log file not found!")
print("---------------------------------")
