import os
import sys

if getattr(sys, "frozen", False):
    # In PyInstaller builds, keep DB near the executable for stable persistence.
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "database.db")
