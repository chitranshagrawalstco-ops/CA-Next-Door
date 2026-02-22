from flask import Blueprint, render_template
from datetime import date
import sqlite3



dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    template_folder="../../templates"
)

@dashboard_bp.route("/dashboard")
def dashboard():

    from core.database import get_connection
    conn = get_connection()

    cur = conn.cursor()

    from datetime import date

    today = date.today().isoformat()

    cur.execute("""
SELECT s.subject_name, c.chapter_name, r.revision_type
FROM revision_schedule r
JOIN subjects s ON r.subject_id = s.id
JOIN chapters c ON r.chapter_id = c.id
WHERE r.revision_date = ?
ORDER BY s.subject_name
""", (today,))

    today_revisions = cur.fetchall()

    


    # Example — adapt to your tables
    today = date.today().isoformat()

    # Today tasks
    cur.execute("SELECT task FROM tasks WHERE task_date=?", (today,))
    today_tasks = cur.fetchall()

    # Example values (replace with real logic)
    streak_count = 5
    days_left = 72
    readiness_score = 75

    total_days = 180
    days_left_percent = int((days_left / total_days) * 100)

    today = date.today()


# ---------------- TEST SUMMARY ----------------

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


# LAST 5 TESTS FOR DASHBOARD GRAPH (X: SUBJECT, Y: SCORE %)
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
    recent_tests.reverse()  # Plot oldest -> newest for a natural line direction

    chart_labels = []
    chart_scores = []
    chart_points = []

    max_points = max(len(recent_tests), 1)

    for idx, row in enumerate(recent_tests):
        _, subject_name, marks_scored, total_marks, test_date = row

        if total_marks and total_marks > 0:
            score_pct = round((marks_scored / total_marks) * 100, 1)
        else:
            score_pct = 0

        chart_labels.append(subject_name)
        chart_scores.append(score_pct)

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







    print("DASHBOARD ALL TESTS:", all_tests)

    

    conn.close()
    

    return render_template(
        "dashboard.html",
        today_tasks=today_tasks,
        streak_count=streak_count,
        days_left=days_left,
        readiness_score=readiness_score,
        days_left_percent=days_left_percent,
        today_revisions=today_revisions,
        avg_score=avg_score,
        test_count=test_count,
        chart_points=chart_points,
        chart_labels=chart_labels,
        chart_scores=chart_scores
    )


