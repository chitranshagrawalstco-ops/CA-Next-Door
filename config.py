import os
import sys

if getattr(sys, "frozen", False):
    # In PyInstaller builds, keep DB near the executable for stable persistence.
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "database.db")

# Default bootstrap settings for fresh installs.
# Used only when admin_settings has no row yet.
DEFAULT_BACKEND_API_URL = "https://ca-next-door.onrender.com/api/v1/auth"
DEFAULT_BACKEND_API_KEY = "cachitransh@A1"
DEFAULT_GOOGLE_SHEET_ID = "1x0ASbSR8HJo8XXn8CWX7iXrYaZkhs5Fw3mf3R2FyfVg"
DEFAULT_GOOGLE_SHEET_TAB = "users"
