"""
run.py - Convenience launcher for Novarix (Technical High-Contrast Edition).

Run with:   python run.py
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    app_path = Path(__file__).resolve().parent / "app.py"
    sys.exit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--theme.base=dark",
                "--theme.primaryColor=#00E5FF",
                "--theme.backgroundColor=#07080C",
                "--theme.secondaryBackgroundColor=#11131A",
                "--theme.textColor=#F8FAFC",
            ]
        )
    )
