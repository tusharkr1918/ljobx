# ljobx/ui/main.py
import subprocess
import sys
from pathlib import Path
import argparse
import os


def launch():
    """Runs the Streamlit web_ui.py file with a custom startup banner."""
    parser = argparse.ArgumentParser(
        description="Launch the ljobx web UI.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # --- Basic Mode Flag ---
    parser.add_argument(
        "--basic",
        action="store_true",
        help="Run the UI in a simplified 'basic' mode, hiding advanced options."
    )

    # --- Override Flags for Basic Mode ---
    parser.add_argument(
        "--concurrency",
        type=int,
        help="(Optional) Override the default concurrency for basic mode."
    )
    parser.add_argument(
        "--delay",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="(Optional) Override the default delay range for basic mode."
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="(Optional) Override the default log level for basic mode."
    )

    args = parser.parse_args()

    app_path = Path(__file__).parent / "web_ui.py"

    command = [sys.executable, "-m", "streamlit", "run", str(app_path)]

    # --- Pass all arguments to the Streamlit script ---
    streamlit_args = []
    if args.basic:
        streamlit_args.append("--basic")
    if args.concurrency is not None:
        streamlit_args.extend(["--concurrency", str(args.concurrency)])
    if args.delay is not None:
        streamlit_args.extend(["--delay", str(args.delay[0]), str(args.delay[1])])
    if args.log_level is not None:
        streamlit_args.extend(["--log-level", args.log_level])

    if streamlit_args:
        command.extend(["--"] + streamlit_args)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

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