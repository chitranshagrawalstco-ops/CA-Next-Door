import sqlite3
from config import DB_NAME

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Student
    cur.execute("""
    CREATE TABLE IF NOT EXISTS student (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        attempt TEXT,
        attempt_date TEXT
    )
    """)

    # Subjects
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_name TEXT
    )
    """)

    # Chapters
    cur.execute("""
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER,
    chapter_name TEXT,

    class_done INTEGER DEFAULT 0,
    rev1_done INTEGER DEFAULT 0,
    rev2_done INTEGER DEFAULT 0,
    rev3_done INTEGER DEFAULT 0
)
""")
    
    cur.execute("""
CREATE TABLE IF NOT EXISTS useful_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    url TEXT
)
""")
    # ADD NOTES COLUMN TO CHAPTERS
    try:
     cur.execute("ALTER TABLE chapters ADD COLUMN notes TEXT")
    except:
     pass

    

    # Add category column if not exists
    try:
     cur.execute("ALTER TABLE chapters ADD COLUMN category TEXT")
    except:
     pass

    # Revision stage completion dates for overdue calculations
    try:
     cur.execute("ALTER TABLE chapters ADD COLUMN class_done_date TEXT")
    except:
     pass
    try:
     cur.execute("ALTER TABLE chapters ADD COLUMN rev1_done_date TEXT")
    except:
     pass
    try:
     cur.execute("ALTER TABLE chapters ADD COLUMN rev2_done_date TEXT")
    except:
     pass
    try:
     cur.execute("ALTER TABLE chapters ADD COLUMN rev3_done_date TEXT")
    except:
     pass

    # Backfill legacy rows so overdue days can be calculated.
    # For old records where a stage is already done but date was never tracked,
    # initialize done_date to today.
    cur.execute("""
    UPDATE chapters
    SET class_done_date = DATE('now')
    WHERE class_done = 1 AND (class_done_date IS NULL OR class_done_date = '')
    """)
    cur.execute("""
    UPDATE chapters
    SET rev1_done_date = DATE('now')
    WHERE rev1_done = 1 AND (rev1_done_date IS NULL OR rev1_done_date = '')
    """)
    cur.execute("""
    UPDATE chapters
    SET rev2_done_date = DATE('now')
    WHERE rev2_done = 1 AND (rev2_done_date IS NULL OR rev2_done_date = '')
    """)
    cur.execute("""
    UPDATE chapters
    SET rev3_done_date = DATE('now')
    WHERE rev3_done = 1 AND (rev3_done_date IS NULL OR rev3_done_date = '')
    """)
    
    # TASK PLANNER TABLE
    cur.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    task_date TEXT
)
""")
    # ---------- ADD COMPLETED COLUMN SAFELY ----------
    try:
        cur.execute(
            "ALTER TABLE tasks ADD COLUMN completed INTEGER DEFAULT 0"
        )
    except:
        pass
# STUDY STREAK TABLE
    cur.execute("""
CREATE TABLE IF NOT EXISTS streak (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_date TEXT UNIQUE
)
""")
    # STUDY HOURS TABLE
    cur.execute("""
CREATE TABLE IF NOT EXISTS study_hours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_date TEXT UNIQUE,
    hours REAL
)
""")
    # TEST LOG TABLE
    cur.execute("""
CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER,
    test_name TEXT,
    marks_scored REAL,
    total_marks REAL,
    test_date TEXT
)
""")
    # FILE MANAGER SETTINGS
    cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_path TEXT
)
""")
    # LICENSE TABLE
    cur.execute("""
CREATE TABLE IF NOT EXISTS license (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT
)
""")
    # ADD MACHINE ID COLUMN IF NOT EXISTS
    try:
     cur.execute("ALTER TABLE license ADD COLUMN machine_id TEXT")
    except:
      pass

    # LICENSE TABLE WITH MACHINE LOCK
    cur.execute("""
CREATE TABLE IF NOT EXISTS license (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT,
    machine_id TEXT
)
""")
    # ADD EXPIRY DATE COLUMN SAFELY
    try:
     cur.execute("ALTER TABLE license ADD COLUMN expiry_date TEXT")
    except:
     pass
# ADMIN SETTINGS
    cur.execute("""
CREATE TABLE IF NOT EXISTS admin_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_color TEXT,
    font_size TEXT,
    feature_tasks INTEGER DEFAULT 1,
    feature_links INTEGER DEFAULT 1,
    feature_file_manager INTEGER DEFAULT 1,
    license_key TEXT DEFAULT 'CAFINAL-2026-PRO',
    license_valid_days INTEGER DEFAULT 365,
    admin_password TEXT DEFAULT 'Admin@123',
    app_title TEXT DEFAULT 'CA Next Door',
    footer_text TEXT DEFAULT 'Built by Chitransh & Yashashvi-Version 1.1',
    logo_filename TEXT,
    accent_preset TEXT DEFAULT 'blue',
    gsheets_webhook_url TEXT,
    google_credentials_path TEXT,
    google_sheet_id TEXT,
    google_sheet_tab TEXT DEFAULT 'users',
    google_api_key TEXT,
    backend_api_url TEXT,
    backend_api_key TEXT,
    telegram_bot_token TEXT,
    telegram_chat_id TEXT
)
""")
    # ADD LICENSE CONFIG COLUMNS TO ADMIN SETTINGS IF NOT EXISTS
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN license_key TEXT DEFAULT 'CAFINAL-2026-PRO'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN license_valid_days INTEGER DEFAULT 365")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN admin_password TEXT DEFAULT 'Admin@123'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN app_title TEXT DEFAULT 'CA Next Door'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN footer_text TEXT DEFAULT 'Built by Chitransh & Yashashvi-Version 1.1'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN logo_filename TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN accent_preset TEXT DEFAULT 'blue'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN gsheets_webhook_url TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN google_credentials_path TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN google_sheet_id TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN google_sheet_tab TEXT DEFAULT 'users'")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN google_api_key TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN backend_api_url TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN backend_api_key TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN telegram_bot_token TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE admin_settings ADD COLUMN telegram_chat_id TEXT")
    except:
        pass
    # REVISION SCHEDULER
    cur.execute("""
CREATE TABLE IF NOT EXISTS revision_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER,
    chapter_id INTEGER,
    revision_type TEXT,
    revision_date TEXT
)
""")

    # GOAL + MILESTONE TRACKER
    cur.execute("""
CREATE TABLE IF NOT EXISTS goal_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL,
    goal_title TEXT NOT NULL,
    target_date TEXT NOT NULL,
    target_percent REAL DEFAULT 100,
    notes TEXT,
    completed INTEGER DEFAULT 0,
    completed_date TEXT
)
""")
    try:
        cur.execute("ALTER TABLE goal_milestones ADD COLUMN completed INTEGER DEFAULT 0")
    except:
        pass
    try:
        cur.execute("ALTER TABLE goal_milestones ADD COLUMN completed_date TEXT")
    except:
        pass
    





    # AUTH SESSION (login/subscription/machine binding + optional Drive sync state)
    cur.execute("""
CREATE TABLE IF NOT EXISTS auth_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    system_id TEXT,
    logged_in INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    expiry_date TEXT,
    drive_connected INTEGER DEFAULT 0,
    drive_folder_id TEXT,
    last_login_at TEXT
)
""")
    try:
        cur.execute("ALTER TABLE auth_session ADD COLUMN active INTEGER DEFAULT 1")
    except:
        pass
    try:
        cur.execute("ALTER TABLE auth_session ADD COLUMN expiry_date TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE auth_session ADD COLUMN drive_connected INTEGER DEFAULT 0")
    except:
        pass
    try:
        cur.execute("ALTER TABLE auth_session ADD COLUMN drive_folder_id TEXT")
    except:
        pass
    try:
        cur.execute("ALTER TABLE auth_session ADD COLUMN last_login_at TEXT")
    except:
        pass

    print("DB PATH:", DB_NAME)



    conn.commit()
    conn.close()
