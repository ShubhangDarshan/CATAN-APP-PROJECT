"""
main.py - Entry point for Settlers of Catan DOS-Box Edition desktop application.
"""

import sys
import os
import tkinter as tk

# Ensure current project directory is in python module path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Enable DPI awareness on Windows for razor-sharp retro monospace rendering
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from catan_gui import CatanGUI


def main():
    root = tk.Tk()

    # Configure application title and minimum geometry
    root.title("SETTLERS OF CATAN  --  [DOS-BOX EDITION]")
    root.geometry("1300x820")
    root.minsize(1100, 700)

    # Launch GUI
    app = CatanGUI(root)

    # Start main event loop
    root.mainloop()


if __name__ == "__main__":
    main()
