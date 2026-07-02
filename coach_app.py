"""LeetCoach desktop GUI entry point.

Run this file with:

    python coach_app.py

The actual Tkinter interface lives in task_board_ui.py. Keeping this file
small makes the recommended startup path obvious and avoids old UI code
drifting out of sync with the product.
"""

from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.task_board_ui import main


if __name__ == "__main__":
    main()
