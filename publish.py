"""
publish.py - Pure-Python 1-Click Public Publisher for ClassPilot.

Run with:
    python publish.py

What it does:
  1. Ensures ClassPilot's Streamlit server is running on port 8501.
  2. Prints your Local Wi-Fi / LAN URL so anyone on your network can open it.
  3. Opens a free, encrypted Public HTTPS Tunnel (via localhost.run over SSH)
     and prints your shareable public https://*.lhr.life link.
"""

import re
import socket
import subprocess
import sys
import time
from pathlib import Path


def _port_open(port=8501):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main():
    app_path = Path(__file__).resolve().parent / "app.py"
    streamlit_proc = None

    if not _port_open(8501):
        print("■ Starting ClassPilot Streamlit server on port 8501...")
        streamlit_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--server.port=8501",
                "--server.headless=true",
                "--server.enableCORS=false",
                "--server.enableXsrfProtection=false",
                "--theme.base=dark",
                "--theme.primaryColor=#00E5FF",
                "--theme.backgroundColor=#07080C",
                "--theme.secondaryBackgroundColor=#11131A",
                "--theme.textColor=#F8FAFC",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            if _port_open(8501):
                break
            time.sleep(0.5)

    print("=" * 68)
    print("■ CLASSPILOT LIVE URLS")
    print(f"  • Local PC:        http://localhost:8501")
    print(f"  • Same Wi-Fi/LAN:  http://{_lan_ip()}:8501")
    print("=" * 68)
    print("■ Opening Public HTTPS Tunnel (keep this window open)...")

    tunnel_cmd = [
        "ssh",
        "-T",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ServerAliveInterval=30",
        "-R", "80:127.0.0.1:8501",
        "nokey@localhost.run",
    ]
    try:
        proc = subprocess.Popen(
            tunnel_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            m = re.search(r"(https://[a-zA-Z0-9.-]+\.lhr\.life)", line)
            if m:
                print("\n" + "★" * 68)
                print(f"  PUBLIC HTTPS WEBSITE URL:  {m.group(1)}")
                print("★" * 68 + "\n")
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nShutting down public tunnel...")
    finally:
        if streamlit_proc:
            streamlit_proc.terminate()


if __name__ == "__main__":
    main()
