ADMIN_PASSWORD = "Admin@123"
DEFAULT_LICENSE_VALID_DAYS = 365
DEFAULT_LICENSE_KEY = "CAFINAL-2026-PRO"
DEFAULT_APP_TITLE = "CA Next Door"
DEFAULT_FOOTER_TEXT = "Built by Chitransh & Yashashvi-Version 1.1"
DEFAULT_ACCENT_PRESET = "blue"
DEFAULT_TELEGRAM_BOT_TOKEN = "8421839445:AAEQcrH3hiSdu1V9fifDrzYzxt0_4z02u6s"
DEFAULT_TELEGRAM_CHAT_ID = "1055501433"

import os
import json
import urllib.request
import urllib.parse
from werkzeug.utils import secure_filename

from flask import Blueprint, render_template, request, redirect, flash, make_response
from core.database import get_connection
from datetime import datetime, timedelta
from core.auth_sync import (
    authenticate,
    connect_drive,
    download_latest_data,
    get_days_remaining,
    get_session_state,
    get_system_id,
    is_session_active,
    set_drive_status,
)

student_bp = Blueprint("student", __name__)

SUBJECT_WEIGHTS = {
    "FR": 1.4,
    "DT": 1.4,
    "AFM": 1.1,
    "Audit": 1.1,
    "IDT": 1.0,
    "IBS": 0.8
}

BASE_MULTIPLIERS = {
    "Low": 1.3,
    "Medium": 1.0,
    "High": 0.8
}

GROUP_SUBJECTS = {
    "G1": ["FR", "AFM", "Audit"],
    "G2": ["DT", "IDT", "IBS"],
    "Both": ["FR", "DT", "AFM", "Audit", "IDT", "IBS"]
}

HIGH_PRIORITY_TOPICS = {
    "FR": ["Consolidation", "Financial Instruments", "Revenue", "Lease"],
    "DT": ["Capital Gains", "PGBP", "Transfer Pricing"],
    "AFM": ["Derivatives", "Forex", "Risk Management"],
    "Audit": ["SA", "Company Audit", "Reporting"],
    "IDT": ["ITC", "Supply", "Returns"],
    "IBS": ["Case Writing Practice"]
}

FEATURES_GUIDE_VERSION = "2.0"
FEATURES_GUIDE_LAST_UPDATED = "2026-02-16"
FEATURES_GUIDE_QUICK_STEPS = [
    "Add subjects and chapters first",
    "Update class/revision toggles daily",
    "Use planner + weak/category views to prioritize"
]
FEATURES_GUIDE_SECTIONS = [
    {
        "title": "Subjects & Chapters",
        "description": "Create your syllabus structure and track chapter-level completion.",
        "steps": [
            "Go to Subjects and add paper names.",
            "Open a subject and add chapters.",
            "Toggle Class, Rev1, Rev2, Rev3 as you complete stages."
        ]
    },
    {
        "title": "Revision Tracker",
        "description": "View completed chapters stage-wise for each subject.",
        "steps": [
            "Open Revision Tracker and choose a subject.",
            "Review Rev1/Rev2/Rev3 cards.",
            "Use page search and quick action buttons to continue revisions."
        ]
    },
    {
        "title": "Weak Chapters",
        "description": "Find where progress is stuck between revision stages.",
        "steps": [
            "Open Weak Chapters.",
            "Review Class->Rev1, Rev1->Rev2, Rev2->Rev3 buckets.",
            "Use Send to Task Planner directly from rows."
        ]
    },
    {
        "title": "ABC Analysis",
        "description": "Prioritize chapters by impact and effort.",
        "steps": [
            "Assign category A/B/C from chapter list.",
            "Open ABC Analysis to review grouped chapters.",
            "Use inline A/B/C pills to recategorize quickly."
        ]
    },
    {
        "title": "Task Planner + Backlog",
        "description": "Plan daily execution and track overdue tasks.",
        "steps": [
            "Add tasks with date in Task Planner.",
            "Mark tasks complete as you finish them.",
            "Check Backlog to clear pending old tasks."
        ]
    },
    {
        "title": "Study Hours + Streak",
        "description": "Monitor consistency and effort over time.",
        "steps": [
            "Use Mark Today Present on dashboard.",
            "Log daily hours in Study Hours.",
            "Watch trend to identify low-output days."
        ]
    },
    {
        "title": "Tests",
        "description": "Track marks and observe performance trend.",
        "steps": [
            "Add every test with marks and date.",
            "Edit incorrect entries when needed.",
            "Review dashboard trend for direction."
        ]
    },
    {
        "title": "Revision Planner",
        "description": "See scheduled revision follow-ups from progress actions.",
        "steps": [
            "Mark Rev1 done to create upcoming revision slots.",
            "Open Revision Planner to view upcoming items.",
            "Use it as a daily revision queue."
        ]
    },
    {
        "title": "Goal Tracker",
        "description": "Set milestones and monitor whether you are on track.",
        "steps": [
            "Create goals with date and target percent.",
            "Edit and complete goals as progress improves.",
            "Use with Weak Chapters for recovery planning."
        ]
    },
    {
        "title": "AI Recommendation + Adaptive Planner",
        "description": "Generate practical focus plans from your current status.",
        "steps": [
            "Use AI Recommendation for study split guidance.",
            "Use Adaptive Planner to generate high-impact tasks.",
            "Add selected suggestions directly to today tasks."
        ]
    },
    {
        "title": "Useful Links",
        "description": "Keep all study resources in one place.",
        "steps": [
            "Add video/course/resource links with clear titles.",
            "Edit links when sources change.",
            "Use as your single resource hub."
        ]
    },
    {
        "title": "File Settings + Chapter Files + Notes",
        "description": "Organize chapter files and notes systematically.",
        "steps": [
            "Set your base folder path in File Settings.",
            "Open chapter files from chapter actions.",
            "Maintain concise notes for rapid revision."
        ]
    }
]


def get_license_policy():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT license_key, license_valid_days
    FROM admin_settings
    ORDER BY id DESC
    LIMIT 1
    """)
    data = cur.fetchone()
    conn.close()

    if not data:
        return DEFAULT_LICENSE_KEY, DEFAULT_LICENSE_VALID_DAYS

    key = data[0] if data[0] else DEFAULT_LICENSE_KEY

    try:
        valid_days = int(data[1]) if data[1] is not None else DEFAULT_LICENSE_VALID_DAYS
    except:
        valid_days = DEFAULT_LICENSE_VALID_DAYS

    if valid_days < 1:
        valid_days = DEFAULT_LICENSE_VALID_DAYS

    return key, valid_days


def get_admin_password():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT admin_password
    FROM admin_settings
    ORDER BY id DESC
    LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        return row[0]
    return ADMIN_PASSWORD


def get_admin_config():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, license_key, license_valid_days, admin_password, app_title, footer_text, logo_filename, accent_preset, gsheets_webhook_url, google_credentials_path, google_sheet_id, google_sheet_tab, google_api_key, backend_api_url, backend_api_key, telegram_bot_token, telegram_chat_id, supabase_url, supabase_key
    FROM admin_settings
    ORDER BY id DESC
    LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "id": None,
            "license_key": DEFAULT_LICENSE_KEY,
            "license_valid_days": DEFAULT_LICENSE_VALID_DAYS,
            "admin_password": ADMIN_PASSWORD,
            "app_title": DEFAULT_APP_TITLE,
            "footer_text": DEFAULT_FOOTER_TEXT,
            "logo_filename": "",
            "accent_preset": DEFAULT_ACCENT_PRESET,
            "gsheets_webhook_url": "",
            "google_credentials_path": "",
            "google_sheet_id": "",
            "google_sheet_tab": "users",
            "google_api_key": "",
            "backend_api_url": "",
            "backend_api_key": "",
            "telegram_bot_token": DEFAULT_TELEGRAM_BOT_TOKEN,
            "telegram_chat_id": DEFAULT_TELEGRAM_CHAT_ID,
            "supabase_url": "",
            "supabase_key": ""
        }

    try:
        valid_days = int(row[2]) if row[2] is not None else DEFAULT_LICENSE_VALID_DAYS
    except:
        valid_days = DEFAULT_LICENSE_VALID_DAYS

    if valid_days < 1:
        valid_days = DEFAULT_LICENSE_VALID_DAYS

    return {
        "id": row[0],
        "license_key": row[1] if row[1] else DEFAULT_LICENSE_KEY,
        "license_valid_days": valid_days,
        "admin_password": row[3] if row[3] else ADMIN_PASSWORD,
        "app_title": row[4] if row[4] else DEFAULT_APP_TITLE,
        "footer_text": row[5] if row[5] else DEFAULT_FOOTER_TEXT,
        "logo_filename": row[6] if row[6] else "",
        "accent_preset": row[7] if row[7] else DEFAULT_ACCENT_PRESET,
        "gsheets_webhook_url": row[8] if row[8] else "",
        "google_credentials_path": row[9] if row[9] else "",
        "google_sheet_id": row[10] if row[10] else "",
        "google_sheet_tab": row[11] if row[11] else "users",
        "google_api_key": row[12] if row[12] else "",
        "backend_api_url": row[13] if row[13] else "",
        "backend_api_key": row[14] if row[14] else "",
        "telegram_bot_token": row[15] if row[15] else DEFAULT_TELEGRAM_BOT_TOKEN,
        "telegram_chat_id": row[16] if row[16] else DEFAULT_TELEGRAM_CHAT_ID,
        "supabase_url": row[17] if row[17] else "",
        "supabase_key": row[18] if row[18] else ""
    }


def get_branding_settings():
    cfg = get_admin_config()
    logo_url = "/static/images/logo.png"
    if cfg["logo_filename"]:
        logo_url = f"/static/uploads/{cfg['logo_filename']}"

    accent_preset = cfg["accent_preset"] if cfg["accent_preset"] in {"blue", "green", "sunset", "slate"} else DEFAULT_ACCENT_PRESET

    return {
        "app_title": cfg["app_title"],
        "footer_text": cfg["footer_text"],
        "logo_url": logo_url,
        "accent_preset": accent_preset,
        "body_class": f"accent-{accent_preset}"
    }


def log_activation_to_google_sheet(license_key, machine_id, expiry_date):
    cfg = get_admin_config()
    webhook_url = (cfg.get("gsheets_webhook_url") or "").strip()
    if not webhook_url:
        return False

    student = get_student()
    student_name = student[0] if student and student[0] else ""
    attempt = student[1] if student and student[1] else ""
    event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "event": "license_activated",
        "timestamp": event_time,
        "student_name": student_name,
        "attempt": attempt,
        "machine_id": machine_id,
        "license_key": license_key,
        "expiry_date": expiry_date
    }

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return 200 <= response.status < 300
    except:
        return False


def send_activation_to_telegram(license_key, machine_id, expiry_date):
    cfg = get_admin_config()
    token = (cfg.get("telegram_bot_token") or "").strip()
    chat_id = (cfg.get("telegram_chat_id") or "").strip()

    if not token or not chat_id:
        return "not_configured"

    student = get_student()
    student_name = student[0] if student and student[0] else "Unknown"
    attempt = student[1] if student and student[1] else "N/A"
    event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    masked_key = license_key
    if len(license_key) > 4:
        masked_key = f"{license_key[:2]}***{license_key[-2:]}"

    message = (
        f"License Activated\n"
        f"Time: {event_time}\n"
        f"Student: {student_name}\n"
        f"Attempt: {attempt}\n"
        f"Machine ID: {machine_id}\n"
        f"License: {masked_key}\n"
        f"Expiry: {expiry_date}"
    )

    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return "sent" if 200 <= response.status < 300 else "failed"
    except:
        return "failed"


def get_phase_split(days_left):
    if days_left >= 110:
        return {"learning": 0.55, "rev1": 0.25, "rev2": 0.12, "final": 0.08}
    if days_left >= 80:
        return {"learning": 0.50, "rev1": 0.28, "rev2": 0.12, "final": 0.10}
    if days_left >= 50:
        return {"learning": 0.45, "rev1": 0.30, "rev2": 0.15, "final": 0.10}
    return {"learning": 0.35, "rev1": 0.35, "rev2": 0.20, "final": 0.10}


def allocate_subject_time(subjects, base_level):
    scores = {}
    total_score = 0

    for subject in subjects:
        score = SUBJECT_WEIGHTS[subject] * BASE_MULTIPLIERS[base_level]
        scores[subject] = score
        total_score += score

    if total_score == 0:
        return {subject: 0 for subject in subjects}

    return {subject: (score / total_score) for subject, score in scores.items()}


def get_daily_time_split(hours_per_day):
    return {
        "learning": hours_per_day * 0.45,
        "practice": hours_per_day * 0.30,
        "revision": hours_per_day * 0.20,
        "recall": hours_per_day * 0.05
    }


def generate_daily_subjects(day_number, group_type):
    if group_type == "Both":
        if day_number % 2 == 0:
            return ["FR", "AFM", "IDT"]
        return ["DT", "Audit", "IBS"]
    if group_type == "G1":
        return ["FR", "AFM", "Audit"]
    return ["DT", "IDT", "IBS"]


def generate_day_plan(day_number, group_type, daily_time_split):
    day_subjects = generate_daily_subjects(day_number, group_type)
    plan = {
        "day": day_number,
        "subjects": [],
        "revision_block": daily_time_split["revision"],
        "recall_block": daily_time_split["recall"]
    }

    for subject in day_subjects:
        plan["subjects"].append({
            "name": subject,
            "learning_hours": daily_time_split["learning"] / len(day_subjects),
            "practice_hours": daily_time_split["practice"] / len(day_subjects)
        })

    return plan


def hours_to_hm(hours_value):
    total_minutes = int(round(float(hours_value) * 60))
    hrs = total_minutes // 60
    mins = total_minutes % 60
    return f"{hrs}h {mins}m"


def get_subject_progress_percent(cur, subject_id):
    cur.execute("""
    SELECT
        COUNT(id) as total,
        SUM(CASE WHEN class_done=1 THEN 1 ELSE 0 END) as class_done
    FROM chapters
    WHERE subject_id=?
    """, (subject_id,))
    row = cur.fetchone()

    if not row or not row[0]:
        return 0.0

    total = row[0]
    class_done = row[1] or 0
    return round((class_done / total) * 100, 1)


def get_milestone_status(today_date, target_date_str, current_pct, target_pct):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except:
        return "Unknown", 0

    days_diff = (target_date - today_date).days

    if current_pct >= target_pct:
        if days_diff >= 0:
            return "Ahead", days_diff
        return "Achieved Late", abs(days_diff)

    if days_diff < 0:
        return "Behind", abs(days_diff)

    if days_diff <= 7:
        return "At Risk", days_diff

    return "On Track", days_diff


def build_adaptive_recommendations(cur, today_dt):
    recommendations = []
    today_str = today_dt.strftime("%Y-%m-%d")
    today_date = today_dt.date()

    # 1) Overdue revisions (highest impact for immediate recovery)
    cur.execute("""
    SELECT s.subject_name, c.chapter_name, c.class_done_date
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.class_done = 1 AND (c.rev1_done = 0 OR c.rev1_done IS NULL)
    """)
    for subject_name, chapter_name, base_date in cur.fetchall():
        days_pending = 0
        if base_date:
            try:
                days_pending = max((today_date - datetime.strptime(base_date, "%Y-%m-%d").date()).days, 0)
            except:
                days_pending = 0

        task_text = f"[REV1] {subject_name} - {chapter_name}"
        recommendations.append({
            "task": task_text,
            "source": "Overdue Revision",
            "reason": f"Revision 1 pending for {days_pending} day(s)",
            "priority": min(100, 70 + days_pending)
        })

    cur.execute("""
    SELECT s.subject_name, c.chapter_name, c.rev1_done_date
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.rev1_done = 1 AND (c.rev2_done = 0 OR c.rev2_done IS NULL)
    """)
    for subject_name, chapter_name, base_date in cur.fetchall():
        days_pending = 0
        if base_date:
            try:
                days_pending = max((today_date - datetime.strptime(base_date, "%Y-%m-%d").date()).days, 0)
            except:
                days_pending = 0

        task_text = f"[REV2] {subject_name} - {chapter_name}"
        recommendations.append({
            "task": task_text,
            "source": "Overdue Revision",
            "reason": f"Revision 2 pending for {days_pending} day(s)",
            "priority": min(100, 72 + days_pending)
        })

    cur.execute("""
    SELECT s.subject_name, c.chapter_name, c.rev2_done_date
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.rev2_done = 1 AND (c.rev3_done = 0 OR c.rev3_done IS NULL)
    """)
    for subject_name, chapter_name, base_date in cur.fetchall():
        days_pending = 0
        if base_date:
            try:
                days_pending = max((today_date - datetime.strptime(base_date, "%Y-%m-%d").date()).days, 0)
            except:
                days_pending = 0

        task_text = f"[REV3] {subject_name} - {chapter_name}"
        recommendations.append({
            "task": task_text,
            "source": "Overdue Revision",
            "reason": f"Revision 3 pending for {days_pending} day(s)",
            "priority": min(100, 75 + days_pending)
        })

    # 2) At-risk / behind milestones
    cur.execute("""
    SELECT g.subject_id, s.subject_name, g.goal_title, g.target_date, g.target_percent
    FROM goal_milestones g
    JOIN subjects s ON s.id = g.subject_id
    WHERE COALESCE(g.completed, 0) = 0
    """)
    for subject_id, subject_name, goal_title, target_date, target_percent in cur.fetchall():
        current_pct = get_subject_progress_percent(cur, subject_id)
        target_pct = float(target_percent or 100)
        status, days_marker = get_milestone_status(today_date, target_date, current_pct, target_pct)

        if status in ("At Risk", "Behind"):
            if status == "Behind":
                reason = f"Milestone overdue by {days_marker} day(s) ({current_pct}%/{target_pct}%)"
                priority = min(100, 90 + min(days_marker, 10))
            else:
                reason = f"Milestone due in {days_marker} day(s) ({current_pct}%/{target_pct}%)"
                priority = 84

            task_text = f"[GOAL] {subject_name} - {goal_title}"
            recommendations.append({
                "task": task_text,
                "source": "Milestone Risk",
                "reason": reason,
                "priority": priority
            })

    # 3) Weak chapters booster items (light priority)
    cur.execute("""
    SELECT s.subject_name, c.chapter_name
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.class_done = 1 AND (c.rev1_done = 0 OR c.rev1_done IS NULL)
    """)
    for subject_name, chapter_name in cur.fetchall():
        task_text = f"[WEAK] {subject_name} - {chapter_name}"
        recommendations.append({
            "task": task_text,
            "source": "Weak Chapter",
            "reason": "Class done but first revision not completed",
            "priority": 60
        })

    # Deduplicate by task text; keep highest priority entry
    dedup = {}
    for item in recommendations:
        key = item["task"]
        if key not in dedup or item["priority"] > dedup[key]["priority"]:
            dedup[key] = item

    final_list = sorted(dedup.values(), key=lambda x: x["priority"], reverse=True)[:10]
    for idx, item in enumerate(final_list, start=1):
        item["id"] = idx
        item["task_date"] = today_str

    return final_list

def get_student():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name, attempt, attempt_date FROM student LIMIT 1")
    data = cur.fetchone()
    conn.close()
    return data


@student_bp.route("/")
def home():
    if not is_license_active():
     return redirect("/activate")

    student = get_student()

    if not student:
        return redirect("/setup")

    name, attempt, attempt_date = student

    today = datetime.today()
    attempt_dt = datetime.strptime(attempt_date, "%Y-%m-%d")
    days_left = (attempt_dt - today).days

    conn = get_connection()
    cur = conn.cursor()

    # UPDATED SUBJECT PROGRESS QUERY (MULTI TRACK)
    cur.execute("""
    SELECT 
    s.subject_name,
    COUNT(c.id) as total,

    SUM(CASE WHEN c.class_done=1 THEN 1 ELSE 0 END) as class_done,
    SUM(CASE WHEN c.rev1_done=1 THEN 1 ELSE 0 END) as rev1_done,
    SUM(CASE WHEN c.rev2_done=1 THEN 1 ELSE 0 END) as rev2_done,
    SUM(CASE WHEN c.rev3_done=1 THEN 1 ELSE 0 END) as rev3_done

    FROM subjects s
    LEFT JOIN chapters c ON s.id = c.subject_id
    GROUP BY s.id
    """)

    progress = cur.fetchall()

    # ---------- ATTEMPT READINESS SCORE ----------

    total_chapters = 0
    total_class = 0
    total_r1 = 0
    total_r2 = 0
    total_r3 = 0

    for p in progress:
        total_chapters += p[1] or 0
        total_class += p[2] or 0
        total_r1 += p[3] or 0
        total_r2 += p[4] or 0
        total_r3 += p[5] or 0

    readiness_score = 0

    if total_chapters > 0:
        class_pct = total_class / total_chapters
        r1_pct = total_r1 / total_chapters
        r2_pct = total_r2 / total_chapters
        r3_pct = total_r3 / total_chapters

        readiness_score = round(
            (class_pct * 40) +
            (r1_pct * 25) +
            (r2_pct * 20) +
            (r3_pct * 15),
            1
        )

    # Subjects list
    cur.execute("SELECT subject_name FROM subjects")
    subjects = cur.fetchall()

    # ---------- TODAY TASKS ----------
    today_str = today.strftime("%Y-%m-%d")

    cur.execute("""
    SELECT task FROM tasks
    WHERE task_date=?
    """, (today_str,))

    today_tasks = cur.fetchall()

# ---------- STREAK CALCULATION ----------
    cur.execute("""
    SELECT study_date FROM streak
    ORDER BY study_date DESC
    """)

    dates = [d[0] for d in cur.fetchall()]

    streak_count = 0
    check_date = today.date()

    for d in dates:
      if d == check_date.strftime("%Y-%m-%d"):
       streak_count += 1
       check_date = check_date.replace(day=check_date.day - 1)
      else:
        break

    # ---------- OVERDUE REVISIONS (WEAK-CHAPTER LOGIC) ----------
    overdue_revisions = []

    cur.execute("""
    SELECT s.subject_name, c.chapter_name, c.class_done_date
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.class_done = 1 AND (c.rev1_done = 0 OR c.rev1_done IS NULL)
    """)
    rev1_pending = cur.fetchall()

    cur.execute("""
    SELECT s.subject_name, c.chapter_name, c.rev1_done_date
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.rev1_done = 1 AND (c.rev2_done = 0 OR c.rev2_done IS NULL)
    """)
    rev2_pending = cur.fetchall()

    cur.execute("""
    SELECT s.subject_name, c.chapter_name, c.rev2_done_date
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.rev2_done = 1 AND (c.rev3_done = 0 OR c.rev3_done IS NULL)
    """)
    rev3_pending = cur.fetchall()

    def append_overdue(rows, stage_name):
        for subject_name, chapter_name, base_date in rows:
            days_pending = None
            if base_date:
                try:
                    start_dt = datetime.strptime(base_date, "%Y-%m-%d").date()
                    days_pending = max((today.date() - start_dt).days, 0)
                except:
                    days_pending = None

            overdue_revisions.append({
                "stage": stage_name,
                "subject": subject_name,
                "chapter": chapter_name,
                "days": days_pending
            })

    append_overdue(rev1_pending, "REV 1")
    append_overdue(rev2_pending, "REV 2")
    append_overdue(rev3_pending, "REV 3")

    overdue_revisions.sort(key=lambda x: x["days"] if x["days"] is not None else -1, reverse=True)

    # ---------- TEST SUMMARY + LAST 5 TEST GRAPH ----------
    cur.execute("""
    SELECT marks_scored, total_marks
    FROM tests
    """)
    all_tests = cur.fetchall()
    test_count = len(all_tests)

    if test_count > 0:
        valid_scores = []
        for m, t in all_tests:
            if t and t > 0:
                valid_scores.append((m / t) * 100)
        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0
    else:
        avg_score = 0

    cur.execute("""
    SELECT
        t.test_name,
        COALESCE(s.subject_name, 'Unknown') AS subject_name,
        t.marks_scored,
        t.total_marks,
        t.test_date
    FROM tests t
    LEFT JOIN subjects s ON t.subject_id = s.id
    ORDER BY t.test_date DESC, t.id DESC
    LIMIT 5
    """)
    recent_tests = cur.fetchall()
    recent_tests.reverse()

    chart_points = []
    max_points = max(len(recent_tests), 1)

    for idx, row in enumerate(recent_tests):
        _, subject_name, marks_scored, total_marks, test_date = row

        if total_marks and total_marks > 0:
            score_pct = round((marks_scored / total_marks) * 100, 1)
        else:
            score_pct = 0

        if len(recent_tests) == 1:
            x = 40
        else:
            x = round(40 + (idx * (240 / (max_points - 1))), 1)

        y = round(160 - (score_pct * 1.2), 1)

        chart_points.append({
            "x": x,
            "y": y,
            "score": score_pct,
            "subject": subject_name,
            "date": test_date or ""
        })

    conn.close()
    license_days = get_license_days_remaining()

    return render_template(
        "dashboard.html",
        name=name,
        attempt=attempt,
        days_left=days_left,
        subjects=subjects,
        progress=progress,
        readiness_score=readiness_score,
        today_tasks=today_tasks,
        streak_count=streak_count,
        license_days=license_days,
        avg_score=avg_score,
        test_count=test_count,
        chart_points=chart_points,
        today_revisions=[],
        overdue_revisions=overdue_revisions
    )


@student_bp.route("/setup", methods=["GET", "POST"])
def setup():

    if request.method == "POST":

        name = request.form["name"]
        attempt = request.form["attempt"]
        attempt_date = request.form["attempt_date"]

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM student")
        cur.execute(
            "INSERT INTO student (name, attempt, attempt_date) VALUES (?, ?, ?)",
            (name, attempt, attempt_date)
        )

        conn.commit()
        conn.close()

        return redirect("/menu")

    return render_template("student_setup.html")


@student_bp.route("/menu")
def menu():
    return render_template("main_menu.html")


@student_bp.route("/features-guide")
@student_bp.route("/featurs-guide")
def features_guide():
    return render_template(
        "features_guide.html",
        guide_version=FEATURES_GUIDE_VERSION,
        guide_last_updated=FEATURES_GUIDE_LAST_UPDATED,
        quick_steps=FEATURES_GUIDE_QUICK_STEPS,
        sections=FEATURES_GUIDE_SECTIONS
    )


@student_bp.route("/profile", methods=["GET", "POST"])
def profile():

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        attempt = request.form["attempt"]
        attempt_date = request.form["attempt_date"]

        cur.execute("""
        UPDATE student 
        SET name=?, attempt=?, attempt_date=?
        """, (name, attempt, attempt_date))

        conn.commit()
        conn.close()
        flash("Profile updated successfully.", "success")

        return redirect("/")

    cur.execute("SELECT name, attempt, attempt_date FROM student LIMIT 1")
    student = cur.fetchone()

    conn.close()

    return render_template("profile_edit.html", student=student)
# ---------- TASK PLANNER ----------
@student_bp.route("/tasks", methods=["GET", "POST"])
def tasks():

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        task = request.form["task"]
        task_date = request.form["task_date"]

        cur.execute(
            "INSERT INTO tasks (task, task_date, completed) VALUES (?, ?, 0)",
            (task, task_date)
        )
        conn.commit()
        flash("Task added successfully.", "success")

    cur.execute("SELECT id, task, task_date, completed FROM tasks ORDER BY task_date")
    tasks = cur.fetchall()

    conn.close()

    return render_template("tasks.html", tasks=tasks)
# ---------- EDIT TASK ----------
@student_bp.route("/tasks/edit/<int:id>", methods=["GET", "POST"])
def edit_task(id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        task = request.form["task"]
        task_date = request.form["task_date"]

        cur.execute("""
        UPDATE tasks
        SET task=?, task_date=?
        WHERE id=?
        """, (task, task_date, id))

        conn.commit()
        conn.close()
        flash("Task updated successfully.", "success")

        return redirect("/tasks")

    cur.execute("SELECT task, task_date FROM tasks WHERE id=?", (id,))
    task = cur.fetchone()

    conn.close()

    return render_template("edit_task.html", task=task, id=id)
# ---------- DELETE TASK ----------
@student_bp.route("/tasks/delete/<int:id>")
def delete_task(id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM tasks WHERE id=?", (id,))

    conn.commit()
    conn.close()
    flash("Task deleted successfully.", "success")

    return redirect("/tasks")
# ---------- MARK STUDY PRESENT ----------
@student_bp.route("/mark-present")
def mark_present():

    conn = get_connection()
    cur = conn.cursor()

    today = datetime.today().strftime("%Y-%m-%d")

    try:
        cur.execute(
            "INSERT INTO streak (study_date) VALUES (?)",
            (today,)
        )
        conn.commit()
    except:
        pass  # already marked today

    conn.close()

    return redirect("/")
# ---------- TOGGLE TASK COMPLETE ----------
@student_bp.route("/tasks/toggle/<int:id>")
def toggle_task(id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT completed FROM tasks WHERE id=?", (id,))
    val = cur.fetchone()[0]

    cur.execute(
        "UPDATE tasks SET completed=? WHERE id=?",
        (0 if val else 1, id)
    )

    conn.commit()
    conn.close()
    flash("Task status updated.", "success")

    return redirect("/tasks")
# ---------- BACKLOG TRACKER ----------
@student_bp.route("/backlog")
def backlog():

    conn = get_connection()
    cur = conn.cursor()

    today = datetime.today().strftime("%Y-%m-%d")

    cur.execute("""
    SELECT task, task_date
    FROM tasks
    WHERE task_date < ?
    AND (completed=0 OR completed IS NULL)
    ORDER BY task_date
    """, (today,))

    backlog_tasks = cur.fetchall()

    conn.close()

    return render_template(
        "backlog.html",
        backlog_tasks=backlog_tasks
    )
# ---------- STUDY HOURS TRACKER ----------
@student_bp.route("/study-hours", methods=["GET", "POST"])
def study_hours():

    conn = get_connection()
    cur = conn.cursor()

    # -------- SAVE HOURS --------
    if request.method == "POST":

        date = request.form["study_date"]
        hours = request.form["hours"]

        try:
            cur.execute("""
            INSERT INTO study_hours (study_date, hours)
            VALUES (?, ?)
            """, (date, hours))
        except:
            cur.execute("""
            UPDATE study_hours
            SET hours=?
            WHERE study_date=?
            """, (hours, date))

        conn.commit()
        flash("Study hours saved.", "success")

    # -------- LAST 30 DAYS DATA --------
    today = datetime.today()

    dates = []
    hours_list = []

    for i in range(29, -1, -1):

        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")

        cur.execute("""
        SELECT hours FROM study_hours
        WHERE study_date=?
        """, (d,))

        res = cur.fetchone()

        dates.append(d[5:])  # MM-DD format
        hours_list.append(res[0] if res else 0)

    conn.close()

    return render_template(
        "study_hours.html",
        dates=dates,
        hours_list=hours_list
    )


@student_bp.route("/ai-recommendation", methods=["GET", "POST"])
def ai_recommendation():

    student = get_student()
    default_days_left = 90
    if student and student[2]:
        try:
            attempt_dt = datetime.strptime(student[2], "%Y-%m-%d")
            default_days_left = max((attempt_dt - datetime.today()).days, 1)
        except:
            default_days_left = 90

    form_data = {
        "days_left": default_days_left,
        "hours_per_day": 8.0,
        "group_type": "Both",
        "base_level": "Medium"
    }

    result = None

    if request.method == "POST":
        # Keep days_left fully automatic from attempt date.
        form_data["days_left"] = default_days_left

        try:
            form_data["hours_per_day"] = max(float(request.form.get("hours_per_day", 0)), 1.0)
        except:
            form_data["hours_per_day"] = 8.0

        form_data["group_type"] = request.form.get("group_type", "Both")
        if form_data["group_type"] not in GROUP_SUBJECTS:
            form_data["group_type"] = "Both"

        form_data["base_level"] = request.form.get("base_level", "Medium")
        if form_data["base_level"] not in BASE_MULTIPLIERS:
            form_data["base_level"] = "Medium"

        subjects = GROUP_SUBJECTS[form_data["group_type"]]
        phase_split = get_phase_split(form_data["days_left"])
        subject_allocation = allocate_subject_time(subjects, form_data["base_level"])
        daily_split = get_daily_time_split(form_data["hours_per_day"])

        daily_plans = []
        preview_days = min(form_data["days_left"], 7)
        for day_number in range(1, preview_days + 1):
            daily_plans.append(
                generate_day_plan(day_number, form_data["group_type"], daily_split)
            )

        low_time_topics = {}
        if form_data["days_left"] <= 50:
            for subject in subjects:
                low_time_topics[subject] = HIGH_PRIORITY_TOPICS.get(subject, [])

        result = {
            "subjects": subjects,
            "phase_split": phase_split,
            "subject_allocation": subject_allocation,
            "daily_split": daily_split,
            "daily_plans": daily_plans,
            "low_time_topics": low_time_topics
        }

    return render_template(
        "ai_recommendation.html",
        form_data=form_data,
        result=result,
        hours_to_hm=hours_to_hm
    )


@student_bp.route("/adaptive-planner", methods=["GET", "POST"])
def adaptive_planner():
    conn = get_connection()
    cur = conn.cursor()

    today_dt = datetime.today()
    today_str = today_dt.strftime("%Y-%m-%d")
    recommendations = build_adaptive_recommendations(cur, today_dt)

    if request.method == "POST":
        selected_tasks = request.form.getlist("selected_tasks")
        existing_today = set()
        cur.execute("SELECT task FROM tasks WHERE task_date=?", (today_str,))
        for row in cur.fetchall():
            existing_today.add(row[0])

        added = 0
        skipped = 0

        for task_text in selected_tasks:
            if task_text in existing_today:
                skipped += 1
                continue

            try:
                cur.execute(
                    "INSERT INTO tasks (task, task_date, completed) VALUES (?, ?, 0)",
                    (task_text, today_str)
                )
            except:
                cur.execute(
                    "INSERT INTO tasks (task, task_date) VALUES (?, ?)",
                    (task_text, today_str)
                )

            existing_today.add(task_text)
            added += 1

        conn.commit()
        conn.close()
        return redirect(f"/adaptive-planner?added={added}&skipped={skipped}")

    conn.close()
    added = request.args.get("added")
    skipped = request.args.get("skipped")

    return render_template(
        "adaptive_planner.html",
        recommendations=recommendations,
        today_str=today_str,
        added=added,
        skipped=skipped
    )


@student_bp.route("/goals", methods=["GET", "POST"])
def goals():
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        subject_id = request.form.get("subject_id")
        goal_title = request.form.get("goal_title", "").strip()
        target_date = request.form.get("target_date")
        target_percent = request.form.get("target_percent", "100").strip()
        notes = request.form.get("notes", "").strip()

        try:
            target_percent_val = float(target_percent)
        except:
            target_percent_val = 100.0

        if target_percent_val < 1:
            target_percent_val = 1.0
        if target_percent_val > 100:
            target_percent_val = 100.0

        if subject_id and goal_title and target_date:
            cur.execute("""
            INSERT INTO goal_milestones
            (subject_id, goal_title, target_date, target_percent, notes)
            VALUES (?, ?, ?, ?, ?)
            """, (subject_id, goal_title, target_date, target_percent_val, notes))
            conn.commit()

        conn.close()
        return redirect("/goals")

    cur.execute("SELECT id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cur.fetchall()

    cur.execute("""
    SELECT g.id, g.subject_id, s.subject_name, g.goal_title, g.target_date, g.target_percent, g.notes, g.completed, g.completed_date
    FROM goal_milestones g
    JOIN subjects s ON s.id = g.subject_id
    WHERE COALESCE(g.completed, 0) = 0
    ORDER BY g.target_date ASC, g.id DESC
    """)
    raw_goals = cur.fetchall()

    cur.execute("""
    SELECT g.id, g.subject_id, s.subject_name, g.goal_title, g.target_date, g.target_percent, g.notes, g.completed, g.completed_date
    FROM goal_milestones g
    JOIN subjects s ON s.id = g.subject_id
    WHERE COALESCE(g.completed, 0) = 1
    ORDER BY g.completed_date DESC, g.id DESC
    """)
    raw_completed_goals = cur.fetchall()

    today_date = datetime.today().date()
    goals_view = []
    for goal in raw_goals:
        goal_id, subject_id, subject_name, goal_title, target_date, target_percent, notes, completed, completed_date = goal
        current_pct = get_subject_progress_percent(cur, subject_id)
        target_pct = float(target_percent or 100)
        status, days_marker = get_milestone_status(today_date, target_date, current_pct, target_pct)
        if completed == 1:
            status = "Completed"
            days_marker = None
        gap_pct = round(target_pct - current_pct, 1)

        goals_view.append({
            "id": goal_id,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "goal_title": goal_title,
            "target_date": target_date,
            "target_percent": round(target_pct, 1),
            "current_percent": current_pct,
            "gap_percent": gap_pct,
            "status": status,
            "days_marker": days_marker,
            "notes": notes or "",
            "completed": completed == 1,
            "completed_date": completed_date
        })

    completed_goals_view = []
    for goal in raw_completed_goals:
        goal_id, subject_id, subject_name, goal_title, target_date, target_percent, notes, completed, completed_date = goal
        current_pct = get_subject_progress_percent(cur, subject_id)
        target_pct = float(target_percent or 100)
        gap_pct = round(target_pct - current_pct, 1)

        completed_goals_view.append({
            "id": goal_id,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "goal_title": goal_title,
            "target_date": target_date,
            "target_percent": round(target_pct, 1),
            "current_percent": current_pct,
            "gap_percent": gap_pct,
            "status": "Completed",
            "days_marker": None,
            "notes": notes or "",
            "completed": completed == 1,
            "completed_date": completed_date
        })

    conn.close()

    return render_template(
        "goals.html",
        subjects=subjects,
        goals=goals_view,
        completed_goals=completed_goals_view
    )


@student_bp.route("/goals/edit/<int:id>", methods=["GET", "POST"])
def edit_goal(id):
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        subject_id = request.form.get("subject_id")
        goal_title = request.form.get("goal_title", "").strip()
        target_date = request.form.get("target_date")
        target_percent = request.form.get("target_percent", "100").strip()
        notes = request.form.get("notes", "").strip()

        try:
            target_percent_val = float(target_percent)
        except:
            target_percent_val = 100.0

        if target_percent_val < 1:
            target_percent_val = 1.0
        if target_percent_val > 100:
            target_percent_val = 100.0

        cur.execute("""
        UPDATE goal_milestones
        SET subject_id=?, goal_title=?, target_date=?, target_percent=?, notes=?
        WHERE id=?
        """, (subject_id, goal_title, target_date, target_percent_val, notes, id))
        conn.commit()
        conn.close()
        flash("Goal updated successfully.", "success")
        return redirect("/goals")

    cur.execute("SELECT id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cur.fetchall()

    cur.execute("""
    SELECT id, subject_id, goal_title, target_date, target_percent, notes
    FROM goal_milestones
    WHERE id=?
    """, (id,))
    goal = cur.fetchone()
    conn.close()

    if not goal:
        return redirect("/goals")

    return render_template("edit_goal.html", goal=goal, subjects=subjects)


@student_bp.route("/goals/delete/<int:id>")
def delete_goal(id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM goal_milestones WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Goal deleted successfully.", "success")
    return redirect("/goals")


@student_bp.route("/goals/complete/<int:id>")
def complete_goal(id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT completed FROM goal_milestones WHERE id=?", (id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return redirect("/goals")

    current = row[0] or 0
    if current == 1:
        cur.execute("""
        UPDATE goal_milestones
        SET completed=0, completed_date=NULL
        WHERE id=?
        """, (id,))
    else:
        cur.execute("""
        UPDATE goal_milestones
        SET completed=1, completed_date=?
        WHERE id=?
        """, (datetime.now().strftime("%Y-%m-%d"), id))

    conn.commit()
    conn.close()
    flash("Goal status updated.", "success")
    return redirect("/goals")
def is_license_active():
    return is_session_active()


def get_license_days_remaining():
    return get_days_remaining()

@student_bp.route("/activate", methods=["GET","POST"])
def activate():

    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")

        result = authenticate(user_id, password)
        if not result.get("ok"):
            flash(result.get("message", "Login failed."), "error")
            return render_template("activate.html", entered_user_id=user_id, system_id=get_system_id())

        if result.get("drive_connected"):
            cloud_result = download_latest_data()
            if cloud_result.get("ok"):
                flash(cloud_result.get("message", "Loaded data from Drive."), "success")
            else:
                flash(cloud_result.get("message", "Drive download failed, local data loaded."), "warning")
            return redirect("/")

        return redirect("/drive-setup")

    return render_template("activate.html", system_id=get_system_id())


@student_bp.route("/drive-setup", methods=["GET", "POST"])
@student_bp.route("/drive-settings", methods=["GET", "POST"])
def drive_setup():
    if not is_license_active():
        return redirect("/activate")

    state = get_session_state()
    if not state:
        return redirect("/activate")

    if request.method == "POST":
        action = request.form.get("action", "").strip().lower()

        if action == "connect":
            result = connect_drive()
            if not result.get("ok"):
                flash(result.get("message", "Google Drive connection failed."), "error")
                return render_template("drive_setup.html", state=state)

            load_result = download_latest_data()
            if load_result.get("ok"):
                flash("Google Drive connected. Latest cloud data loaded.", "success")
            else:
                flash(load_result.get("message", "Drive connected, but cloud download failed."), "warning")
            return redirect("/")

        if action == "skip":
            skip_result = set_drive_status(False, "")
            if skip_result.get("ok"):
                flash("Drive setup skipped. App will use local storage.", "warning")
            else:
                flash(skip_result.get("message", "Unable to update drive status."), "warning")
            return redirect("/")

    return render_template("drive_setup.html", state=state)

@student_bp.route("/admin", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        pwd = request.form["password"]

        if pwd == get_admin_password():
            return redirect("/admin-panel")

    return render_template("admin_login.html")
@student_bp.route("/admin-panel", methods=["GET","POST"])
def admin_panel():
    config = get_admin_config()

    if request.method == "POST":
        license_key = request.form.get("license_key", "").strip() or DEFAULT_LICENSE_KEY
        license_valid_days = request.form.get("license_valid_days", str(DEFAULT_LICENSE_VALID_DAYS)).strip()
        app_title = request.form.get("app_title", "").strip() or DEFAULT_APP_TITLE
        footer_text = request.form.get("footer_text", "").strip() or DEFAULT_FOOTER_TEXT
        gsheets_webhook_url = request.form.get("gsheets_webhook_url", "").strip()
        google_credentials_path = request.form.get("google_credentials_path", "").strip()
        google_sheet_id = request.form.get("google_sheet_id", "").strip()
        google_sheet_tab = request.form.get("google_sheet_tab", "users").strip() or "users"
        google_api_key = request.form.get("google_api_key", "").strip()
        backend_api_url = request.form.get("backend_api_url", "").strip()
        backend_api_key = request.form.get("backend_api_key", "").strip()
        telegram_bot_token = request.form.get("telegram_bot_token", "").strip()
        telegram_chat_id = request.form.get("telegram_chat_id", "").strip()
        supabase_url = request.form.get("supabase_url", "").strip()
        supabase_key = request.form.get("supabase_key", "").strip()
        accent_preset = request.form.get("accent_preset", DEFAULT_ACCENT_PRESET).strip().lower()
        if accent_preset not in {"blue", "green", "sunset", "slate"}:
            accent_preset = DEFAULT_ACCENT_PRESET
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        logo_filename = config["logo_filename"]

        try:
            license_valid_days = int(license_valid_days)
        except:
            license_valid_days = DEFAULT_LICENSE_VALID_DAYS

        if license_valid_days < 1:
            license_valid_days = DEFAULT_LICENSE_VALID_DAYS

        if (telegram_bot_token and not telegram_chat_id) or (telegram_chat_id and not telegram_bot_token):
            flash("Enter both Telegram Bot Token and Chat ID, or keep both blank.", "error")
            config["license_key"] = license_key
            config["license_valid_days"] = license_valid_days
            config["app_title"] = app_title
            config["footer_text"] = footer_text
            config["accent_preset"] = accent_preset
            config["gsheets_webhook_url"] = gsheets_webhook_url
            config["google_credentials_path"] = google_credentials_path
            config["google_sheet_id"] = google_sheet_id
            config["google_sheet_tab"] = google_sheet_tab
            config["google_api_key"] = google_api_key
            config["backend_api_url"] = backend_api_url
            config["backend_api_key"] = backend_api_key
            config["telegram_bot_token"] = telegram_bot_token
            config["telegram_chat_id"] = telegram_chat_id
            config["supabase_url"] = supabase_url
            config["supabase_key"] = supabase_key
            return render_template("admin_panel.html", admin_config=config)

        password_to_save = config["admin_password"]
        wants_password_change = bool(current_password or new_password or confirm_password)
        can_save = True

        if wants_password_change:
            if current_password != config["admin_password"]:
                flash("Current admin password is incorrect.", "error")
                can_save = False
            elif len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                can_save = False
            elif new_password != confirm_password:
                flash("New password and confirm password do not match.", "error")
                can_save = False
            else:
                password_to_save = new_password

        if can_save:
            conn = get_connection()
            cur = conn.cursor()

            upload = request.files.get("logo_file")
            if upload and upload.filename:
                base_name = secure_filename(upload.filename)
                ext = os.path.splitext(base_name)[1].lower()
                allowed = {".png", ".jpg", ".jpeg", ".webp", ".ico"}
                if ext not in allowed:
                    conn.close()
                    flash("Logo must be PNG/JPG/WEBP/ICO.", "error")
                    config["license_key"] = license_key
                    config["license_valid_days"] = license_valid_days
                    config["app_title"] = app_title
                    config["footer_text"] = footer_text
                    config["accent_preset"] = accent_preset
                    config["gsheets_webhook_url"] = gsheets_webhook_url
                    config["google_credentials_path"] = google_credentials_path
                    config["google_sheet_id"] = google_sheet_id
                    config["google_sheet_tab"] = google_sheet_tab
                    config["google_api_key"] = google_api_key
                    config["backend_api_url"] = backend_api_url
                    config["backend_api_key"] = backend_api_key
                    config["telegram_bot_token"] = telegram_bot_token
                    config["telegram_chat_id"] = telegram_chat_id
                    config["supabase_url"] = supabase_url
                    config["supabase_key"] = supabase_key
                    return render_template("admin_panel.html", admin_config=config)

                upload_dir = os.path.join("static", "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                logo_filename = f"admin_logo{ext}"
                upload.save(os.path.join(upload_dir, logo_filename))

            if config["id"] is None:
                cur.execute("""
                INSERT INTO admin_settings
                (theme_color, font_size, feature_tasks, feature_links, feature_file_manager, license_key, license_valid_days, admin_password, app_title, footer_text, logo_filename, accent_preset, gsheets_webhook_url, google_credentials_path, google_sheet_id, google_sheet_tab, google_api_key, backend_api_url, backend_api_key, telegram_bot_token, telegram_chat_id, supabase_url, supabase_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ("#4f46e5", "14px", 1, 1, 1, license_key, license_valid_days, password_to_save, app_title, footer_text, logo_filename, accent_preset, gsheets_webhook_url, google_credentials_path, google_sheet_id, google_sheet_tab, google_api_key, backend_api_url, backend_api_key, telegram_bot_token, telegram_chat_id, supabase_url, supabase_key))
                config_id = cur.lastrowid
            else:
                config_id = config["id"]
                cur.execute("""
                UPDATE admin_settings
                SET license_key=?, license_valid_days=?, admin_password=?, app_title=?, footer_text=?, logo_filename=?, accent_preset=?, gsheets_webhook_url=?, google_credentials_path=?, google_sheet_id=?, google_sheet_tab=?, google_api_key=?, backend_api_url=?, backend_api_key=?, telegram_bot_token=?, telegram_chat_id=?, supabase_url=?, supabase_key=?
                WHERE id=?
                """, (license_key, license_valid_days, password_to_save, app_title, footer_text, logo_filename, accent_preset, gsheets_webhook_url, google_credentials_path, google_sheet_id, google_sheet_tab, google_api_key, backend_api_url, backend_api_key, telegram_bot_token, telegram_chat_id, supabase_url, supabase_key, config_id))

            conn.commit()
            conn.close()
            flash("Settings updated successfully.", "success")
            return redirect("/admin-panel")

        config["license_key"] = license_key
        config["license_valid_days"] = license_valid_days
        config["app_title"] = app_title
        config["footer_text"] = footer_text
        config["accent_preset"] = accent_preset
        config["gsheets_webhook_url"] = gsheets_webhook_url
        config["google_credentials_path"] = google_credentials_path
        config["google_sheet_id"] = google_sheet_id
        config["google_sheet_tab"] = google_sheet_tab
        config["google_api_key"] = google_api_key
        config["backend_api_url"] = backend_api_url
        config["backend_api_key"] = backend_api_key
        config["telegram_bot_token"] = telegram_bot_token
        config["telegram_chat_id"] = telegram_chat_id

    return render_template(
        "admin_panel.html",
        admin_config=config
    )
