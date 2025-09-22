# ljobx/ui/main.py
import subprocess
import sys
from pathlib import Path

def launch():
    """Finds and runs the Streamlit web_ui.py file with a custom startup banner."""
    app_path = Path(__file__).parent / "web_ui.py"

    try:
        # Run streamlit as a subprocess and capture its output
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(app_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream output line by line
        for line in process.stdout:
            if "You can now view your Streamlit app in your browser." in line:
                line = line.replace(
                    "You can now view your Streamlit app in your browser.",
                    "You can now view your ljobx app in your browser."
                )
            print(line, end="")

        process.wait()

    except FileNotFoundError:
        print("Error: 'streamlit' is not installed or not in the system's PATH.")
        print("Please make sure you have installed the UI dependencies: pip install ljobx[ui]")
    except subprocess.CalledProcessError as e:
        print(f"Failed to launch Streamlit app: {e}")

if __name__ == "__main__":
    launch()
