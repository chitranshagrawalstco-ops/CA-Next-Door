from datetime import datetime, timedelta

import os
import subprocess

from flask import Blueprint, render_template, request, redirect, flash
from core.database import get_connection

subjects_bp = Blueprint("subjects", __name__)

# ---------------- SUBJECT LIST ----------------
@subjects_bp.route("/subjects", methods=["GET", "POST"])
def subjects():

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        subject = request.form["subject"]
        cur.execute("INSERT INTO subjects (subject_name) VALUES (?)", (subject,))
        conn.commit()

    cur.execute("SELECT id, subject_name FROM subjects")
    subjects = cur.fetchall()
    conn.close()

    return render_template("subjects.html", subjects=subjects)


# ---------------- EDIT SUBJECT ----------------
@subjects_bp.route("/subjects/edit/<int:id>", methods=["GET", "POST"])
def edit_subject(id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["subject"]
        cur.execute("UPDATE subjects SET subject_name=? WHERE id=?", (name, id))
        conn.commit()
        conn.close()
        flash("Subject updated successfully.", "success")
        return redirect("/subjects")

    cur.execute("SELECT subject_name FROM subjects WHERE id=?", (id,))
    subject = cur.fetchone()[0]
    conn.close()

    return render_template("edit_subject.html", subject=subject, id=id)


# ---------------- DELETE SUBJECT ----------------
@subjects_bp.route("/subjects/delete/<int:id>")
def delete_subject(id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM subjects WHERE id=?", (id,))
    cur.execute("DELETE FROM chapters WHERE subject_id=?", (id,))

    conn.commit()
    conn.close()
    flash("Subject deleted successfully.", "success")

    return redirect("/subjects")


# ---------------- CHAPTER PAGE ----------------
@subjects_bp.route("/subjects/<int:subject_id>/chapters", methods=["GET", "POST"])
def chapters(subject_id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        chapter = request.form["chapter"]

        # SAFE INSERT WITH DEFAULT FLAGS
        cur.execute(
            """INSERT INTO chapters 
            (subject_id, chapter_name, class_done, rev1_done, rev2_done, rev3_done)
            VALUES (?, ?, 0, 0, 0, 0)""",
            (subject_id, chapter)
        )
        conn.commit()

    cur.execute("SELECT subject_name FROM subjects WHERE id=?", (subject_id,))
    subject_name = cur.fetchone()[0]

    # UPDATED QUERY WITH ALL STATUS FIELDS
    cur.execute("""
    SELECT 
    id,
    chapter_name,
    class_done,
    rev1_done,
    rev2_done,
    rev3_done,
    category
    FROM chapters
    WHERE subject_id=?
    """, (subject_id,))

    chapters = cur.fetchall()

    conn.close()

    return render_template(
        "chapters.html",
        chapters=chapters,
        subject_name=subject_name,
        subject_id=subject_id
    )


# ---------------- EDIT CHAPTER ----------------
@subjects_bp.route("/chapters/edit/<int:id>/<int:subject_id>", methods=["GET", "POST"])
def edit_chapter(id, subject_id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form["chapter"]
        cur.execute("UPDATE chapters SET chapter_name=? WHERE id=?", (name, id))
        conn.commit()
        conn.close()
        flash("Chapter updated successfully.", "success")
        return redirect(f"/subjects/{subject_id}/chapters")

    cur.execute("SELECT chapter_name FROM chapters WHERE id=?", (id,))
    chapter = cur.fetchone()[0]
    conn.close()

    return render_template(
        "edit_chapter.html",
        chapter=chapter,
        id=id,
        subject_id=subject_id
    )


# ---------------- DELETE CHAPTER ----------------
@subjects_bp.route("/chapters/delete/<int:id>/<int:subject_id>")
def delete_chapter(id, subject_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM chapters WHERE id=?", (id,))

    conn.commit()
    conn.close()
    flash("Chapter deleted successfully.", "success")

    return redirect(f"/subjects/{subject_id}/chapters")


# ---------- TOGGLE CLASS ----------
@subjects_bp.route("/chapters/toggle/class/<int:id>/<int:subject_id>")
def toggle_class(id, subject_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT class_done FROM chapters WHERE id=?", (id,))
    val = cur.fetchone()[0]

    new_val = 0 if val else 1
    done_date = datetime.now().strftime("%Y-%m-%d") if new_val == 1 else None

    cur.execute(
        "UPDATE chapters SET class_done=?, class_done_date=? WHERE id=?",
        (new_val, done_date, id)
    )

    conn.commit()
    conn.close()

    return redirect(f"/subjects/{subject_id}/chapters")


# ---------- TOGGLE REV 1 ----------
@subjects_bp.route("/chapters/toggle/rev1/<int:id>/<int:subject_id>")
def toggle_rev1(id, subject_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT rev1_done FROM chapters WHERE id=?", (id,))
    val = cur.fetchone()[0]

    new_val = 0 if val else 1
    done_date = datetime.now().strftime("%Y-%m-%d") if new_val == 1 else None

    # Toggle Rev1
    cur.execute(
        "UPDATE chapters SET rev1_done=?, rev1_done_date=? WHERE id=?",
        (new_val, done_date, id)
    )

    # ⭐ IF TURNING ON → INSERT FUTURE SCHEDULE
    if new_val == 1:

        today = datetime.now()

        rev2_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
        rev3_date = (today + timedelta(days=10)).strftime("%Y-%m-%d")

        cur.execute("""
        INSERT INTO revision_schedule
        (subject_id, chapter_id, revision_type, revision_date)
        VALUES (?, ?, ?, ?)
        """, (subject_id, id, "REV2", rev2_date))

        cur.execute("""
        INSERT INTO revision_schedule
        (subject_id, chapter_id, revision_type, revision_date)
        VALUES (?, ?, ?, ?)
        """, (subject_id, id, "REV3", rev3_date))

    # ⭐ IF TURNING OFF → DELETE FUTURE SCHEDULE
    else:

        cur.execute("""
        DELETE FROM revision_schedule
        WHERE chapter_id=?
        AND revision_type IN ('REV2','REV3')
        """, (id,))

    conn.commit()
    conn.close()

    return redirect(f"/subjects/{subject_id}/chapters")




# ---------- TOGGLE REV 2 ----------
@subjects_bp.route("/chapters/toggle/rev2/<int:id>/<int:subject_id>")
def toggle_rev2(id, subject_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT rev2_done FROM chapters WHERE id=?", (id,))
    val = cur.fetchone()[0]

    new_val = 0 if val else 1
    done_date = datetime.now().strftime("%Y-%m-%d") if new_val == 1 else None

    cur.execute(
        "UPDATE chapters SET rev2_done=?, rev2_done_date=? WHERE id=?",
        (new_val, done_date, id)
    )

    conn.commit()
    conn.close()

    return redirect(f"/subjects/{subject_id}/chapters")


# ---------- TOGGLE REV 3 ----------
@subjects_bp.route("/chapters/toggle/rev3/<int:id>/<int:subject_id>")
def toggle_rev3(id, subject_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT rev3_done FROM chapters WHERE id=?", (id,))
    val = cur.fetchone()[0]

    new_val = 0 if val else 1
    done_date = datetime.now().strftime("%Y-%m-%d") if new_val == 1 else None

    cur.execute(
        "UPDATE chapters SET rev3_done=?, rev3_done_date=? WHERE id=?",
        (new_val, done_date, id)
    )

    conn.commit()
    conn.close()

    return redirect(f"/subjects/{subject_id}/chapters")
# ---------- REVISION TRACKER ----------
@subjects_bp.route("/revision-tracker")
def revision_tracker():

    conn = get_connection()
    cur = conn.cursor()

    # Get subjects list
    cur.execute("SELECT id, subject_name FROM subjects")
    subjects = cur.fetchall()

    conn.close()

    return render_template(
        "revision_tracker_subjects.html",
        subjects=subjects
    )


# ---------- REVISION TRACKER SUBJECT DETAIL ----------
@subjects_bp.route("/revision-tracker/<int:subject_id>")
def revision_tracker_subject(subject_id):

    conn = get_connection()
    cur = conn.cursor()

    # Subject Name
    cur.execute("SELECT subject_name FROM subjects WHERE id=?", (subject_id,))
    subject_name = cur.fetchone()[0]

    # REV 1
    cur.execute("""
    SELECT id, chapter_name, COALESCE(rev2_done, 0) FROM chapters
    WHERE subject_id=? AND rev1_done=1
    ORDER BY chapter_name
    """, (subject_id,))
    rev1 = cur.fetchall()

    # REV 2
    cur.execute("""
    SELECT id, chapter_name, COALESCE(rev3_done, 0) FROM chapters
    WHERE subject_id=? AND rev2_done=1
    ORDER BY chapter_name
    """, (subject_id,))
    rev2 = cur.fetchall()

    # REV 3
    cur.execute("""
    SELECT id, chapter_name FROM chapters
    WHERE subject_id=? AND rev3_done=1
    ORDER BY chapter_name
    """, (subject_id,))

    rev3 = cur.fetchall()

    conn.close()

    return render_template(
        "revision_tracker_detail.html",
        subject_name=subject_name,
        subject_id=subject_id,
        rev1=rev1,
        rev2=rev2,
        rev3=rev3
    )
# ---------- WEAK CHAPTER DETECTOR ----------
@subjects_bp.route("/weak-chapters")
def weak_chapters():

    conn = get_connection()
    cur = conn.cursor()

    # Class done but Rev1 pending
    cur.execute("""
    SELECT c.id, c.subject_id, s.subject_name, c.chapter_name
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.class_done = 1 AND (c.rev1_done = 0 OR c.rev1_done IS NULL)
    ORDER BY s.subject_name, c.chapter_name
    """)
    class_only = cur.fetchall()

    # Rev1 done but Rev2 pending
    cur.execute("""
    SELECT c.id, c.subject_id, s.subject_name, c.chapter_name
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.rev1_done = 1 AND (c.rev2_done = 0 OR c.rev2_done IS NULL)
    ORDER BY s.subject_name, c.chapter_name
    """)
    rev1_only = cur.fetchall()

    # Rev2 done but Rev3 pending
    cur.execute("""
    SELECT c.id, c.subject_id, s.subject_name, c.chapter_name
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.rev2_done = 1 AND (c.rev3_done = 0 OR c.rev3_done IS NULL)
    ORDER BY s.subject_name, c.chapter_name
    """)
    rev2_only = cur.fetchall()

    conn.close()

    return render_template(
        "weak_chapters.html",
        class_only=class_only,
        rev1_only=rev1_only,
        rev2_only=rev2_only
    )


@subjects_bp.route("/weak-chapters/add-task/<int:chapter_id>/<int:subject_id>/<stage>")
def add_weak_chapter_task(chapter_id, subject_id, stage):
    stage_map = {
        "class_rev1": "Class -> Rev1",
        "rev1_rev2": "Rev1 -> Rev2",
        "rev2_rev3": "Rev2 -> Rev3"
    }

    if stage not in stage_map:
        return redirect("/weak-chapters")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT s.subject_name, c.chapter_name
    FROM chapters c
    JOIN subjects s ON s.id = c.subject_id
    WHERE c.id=? AND c.subject_id=?
    """, (chapter_id, subject_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return redirect("/weak-chapters")

    subject_name, chapter_name = row
    task_text = f"[WEAK {stage_map[stage]}] {subject_name} - {chapter_name}"
    today_str = datetime.today().strftime("%Y-%m-%d")

    cur.execute(
        "SELECT 1 FROM tasks WHERE task=? AND task_date=? LIMIT 1",
        (task_text, today_str)
    )
    exists = cur.fetchone()

    if not exists:
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
        conn.commit()

    conn.close()
    if exists:
        flash("Task already exists for today.", "info")
    else:
        flash("Task added to today planner.", "success")
    return redirect("/weak-chapters")
# ---------- UPDATE CATEGORY ----------
@subjects_bp.route("/chapters/category/<int:id>/<int:subject_id>/<cat>")
def update_category(id, subject_id, cat):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE chapters SET category=? WHERE id=?",
        (cat, id)
    )

    conn.commit()
    conn.close()
    flash(f"Category updated to {cat}.", "success")

    next_page = request.args.get("next", "").strip().lower()
    if next_page == "category":
        return redirect(f"/category-tracker/{subject_id}")

    return redirect(f"/subjects/{subject_id}/chapters")
# ---------- CATEGORY TRACKER SUBJECT LIST ----------
@subjects_bp.route("/category-tracker")
def category_tracker():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, subject_name FROM subjects")
    subjects = cur.fetchall()

    conn.close()

    return render_template(
        "category_tracker_subjects.html",
        subjects=subjects
    )
# ---------- CATEGORY TRACKER SUBJECT DETAIL ----------
@subjects_bp.route("/category-tracker/<int:subject_id>")
def category_tracker_subject(subject_id):

    conn = get_connection()
    cur = conn.cursor()

    # Subject Name
    cur.execute("SELECT subject_name FROM subjects WHERE id=?", (subject_id,))
    subject_name = cur.fetchone()[0]

    # Category A
    cur.execute("""
    SELECT id, chapter_name FROM chapters
    WHERE subject_id=? AND category='A'
    ORDER BY chapter_name
    """, (subject_id,))
    catA = cur.fetchall()

    # Category B
    cur.execute("""
    SELECT id, chapter_name FROM chapters
    WHERE subject_id=? AND category='B'
    ORDER BY chapter_name
    """, (subject_id,))
    catB = cur.fetchall()

    # Category C
    cur.execute("""
    SELECT id, chapter_name FROM chapters
    WHERE subject_id=? AND category='C'
    ORDER BY chapter_name
    """, (subject_id,))
    catC = cur.fetchall()

    conn.close()

    return render_template(
        "category_tracker_detail.html",
        subject_name=subject_name,
        subject_id=subject_id,
        catA=catA,
        catB=catB,
        catC=catC
    )
# ---------- FILE BASE PATH ----------
@subjects_bp.route("/file-settings", methods=["GET", "POST"])
def file_settings():

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        base_path = request.form["base_path"]

        cur.execute("DELETE FROM settings")
        cur.execute(
            "INSERT INTO settings (base_path) VALUES (?)",
            (base_path,)
        )
        conn.commit()
        flash("File base path saved.", "success")

    cur.execute("SELECT base_path FROM settings LIMIT 1")
    data = cur.fetchone()

    conn.close()

    return render_template(
        "file_settings.html",
        base_path=data[0] if data else ""
    )
# ---------- CHAPTER FILE VIEW ----------
@subjects_bp.route("/files/<int:subject_id>/<int:chapter_id>")
def chapter_files(subject_id, chapter_id):

    conn = get_connection()
    cur = conn.cursor()

    # Base path
    cur.execute("SELECT base_path FROM settings LIMIT 1")
    base = cur.fetchone()

    if not base:
        return "Please set base folder first"

    base = base[0]

    # Subject + Chapter Names
    cur.execute("SELECT subject_name FROM subjects WHERE id=?", (subject_id,))
    subject = cur.fetchone()[0]

    cur.execute("SELECT chapter_name FROM chapters WHERE id=?", (chapter_id,))
    chapter = cur.fetchone()[0]

    # Folder path
    folder = os.path.join(base, subject, chapter)

    # Create if not exists
    os.makedirs(folder, exist_ok=True)

    # List files
    files = os.listdir(folder)

    conn.close()

    return render_template(
        "chapter_files.html",
        files=files,
        folder=folder,
        subject_id=subject_id,
        chapter_id=chapter_id
    )
# ---------- OPEN FILE ----------
@subjects_bp.route("/open-file")
def open_file():

    path = request.args.get("path")

    if os.path.exists(path):
        os.startfile(path)

    return redirect(request.referrer)
# ---------- CHAPTER NOTES ----------
@subjects_bp.route("/chapter-notes/<int:chapter_id>", methods=["GET", "POST"])
def chapter_notes(chapter_id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        notes = request.form["notes"]

        cur.execute("""
        UPDATE chapters
        SET notes=?
        WHERE id=?
        """, (notes, chapter_id))

        conn.commit()
        flash("Chapter notes updated.", "success")

    cur.execute("""
    SELECT chapter_name, notes
    FROM chapters
    WHERE id=?
    """, (chapter_id,))

    data = cur.fetchone()

    conn.close()

    return render_template(
        "chapter_notes.html",
        chapter_id=chapter_id,
        chapter_name=data[0],
        notes=data[1] if data[1] else ""
    )
# ---------- REVISION PLANNER ----------
@subjects_bp.route("/revision-planner")
def revision_planner():

    conn = get_connection()
    cur = conn.cursor()

    # Keep schedule clean in case duplicate rows were created over time.
    cur.execute("""
    DELETE FROM revision_schedule
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM revision_schedule
        GROUP BY subject_id, chapter_id, revision_type, revision_date
    )
    """)
    conn.commit()

    cur.execute("""
    SELECT r.id,
           r.revision_date,
           s.subject_name,
           c.chapter_name,
           r.revision_type
    FROM revision_schedule r
    JOIN subjects s ON r.subject_id = s.id
    JOIN chapters c ON r.chapter_id = c.id
    WHERE (r.revision_type = 'REV2' AND COALESCE(c.rev2_done, 0) = 0)
       OR (r.revision_type = 'REV3' AND COALESCE(c.rev3_done, 0) = 0)
    ORDER BY r.revision_date ASC
    """)

    rows = cur.fetchall()
    today = datetime.today().strftime("%Y-%m-%d")
    data = []
    overdue_count = 0
    today_count = 0
    upcoming_count = 0

    for schedule_id, revision_date, subject_name, chapter_name, revision_type in rows:
        days_left = 0
        status = "today"
        try:
            delta_days = (datetime.strptime(revision_date, "%Y-%m-%d").date() - datetime.today().date()).days
            days_left = delta_days
            if delta_days < 0:
                status = "overdue"
                overdue_count += 1
            elif delta_days == 0:
                status = "today"
                today_count += 1
            else:
                status = "upcoming"
                upcoming_count += 1
        except:
            status = "today"
            today_count += 1

        data.append({
            "id": schedule_id,
            "revision_date": revision_date,
            "subject_name": subject_name,
            "chapter_name": chapter_name,
            "revision_type": revision_type,
            "status": status,
            "days_left": days_left
        })

    conn.close()

    return render_template(
        "revision_planner.html",
        data=data,
        today=today,
        overdue_count=overdue_count,
        today_count=today_count,
        upcoming_count=upcoming_count
    )


@subjects_bp.route("/revision-planner/complete/<int:schedule_id>")
def complete_revision_planner_item(schedule_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT chapter_id, revision_type
    FROM revision_schedule
    WHERE id=?
    """, (schedule_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return redirect("/revision-planner")

    chapter_id, revision_type = row
    done_date = datetime.now().strftime("%Y-%m-%d")

    if revision_type == "REV2":
        cur.execute(
            "UPDATE chapters SET rev2_done=1, rev2_done_date=? WHERE id=?",
            (done_date, chapter_id)
        )
    elif revision_type == "REV3":
        cur.execute(
            "UPDATE chapters SET rev3_done=1, rev3_done_date=? WHERE id=?",
            (done_date, chapter_id)
        )

    # Remove any matching schedule rows to avoid stale duplicates.
    cur.execute(
        "DELETE FROM revision_schedule WHERE chapter_id=? AND revision_type=?",
        (chapter_id, revision_type)
    )

    conn.commit()
    conn.close()
    flash("Revision marked complete.", "success")
    return redirect("/revision-planner")
# ---------- TEST LOG ----------
@subjects_bp.route("/tests", methods=["GET", "POST"])
def tests():

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        subject_id = request.form["subject_id"]
        test_name = request.form["test_name"]
        marks = request.form["marks"]
        total = request.form["total"]
        test_date = request.form["test_date"]

        cur.execute("""
        INSERT INTO tests
        (subject_id, test_name, marks_scored, total_marks, test_date)
        VALUES (?, ?, ?, ?, ?)
        """, (subject_id, test_name, marks, total, test_date))

        conn.commit()

    # Subject dropdown
    cur.execute("SELECT id, subject_name FROM subjects")
    subjects = cur.fetchall()

    # Test list
    cur.execute("""
    SELECT t.id, t.test_name, s.subject_name,
           t.marks_scored, t.total_marks, t.test_date
    FROM tests t
    JOIN subjects s ON s.id = t.subject_id
    ORDER BY t.test_date DESC, t.id DESC
    """)

    tests = cur.fetchall()

    conn.close()

    return render_template(
        "tests.html",
        subjects=subjects,
        tests=tests
    )


@subjects_bp.route("/tests/edit/<int:id>", methods=["GET", "POST"])
def edit_test(id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        subject_id = request.form["subject_id"]
        test_name = request.form["test_name"]
        marks = request.form["marks"]
        total = request.form["total"]
        test_date = request.form["test_date"]

        cur.execute("""
        UPDATE tests
        SET subject_id=?, test_name=?, marks_scored=?, total_marks=?, test_date=?
        WHERE id=?
        """, (subject_id, test_name, marks, total, test_date, id))

        conn.commit()
        conn.close()
        flash("Test updated successfully.", "success")
        return redirect("/tests")

    cur.execute("SELECT id, subject_name FROM subjects")
    subjects = cur.fetchall()

    cur.execute("""
    SELECT id, subject_id, test_name, marks_scored, total_marks, test_date
    FROM tests
    WHERE id=?
    """, (id,))
    test_row = cur.fetchone()

    conn.close()

    if not test_row:
        return redirect("/tests")

    return render_template(
        "edit_test.html",
        test=test_row,
        subjects=subjects
    )


@subjects_bp.route("/tests/delete/<int:id>")
def delete_test(id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM tests WHERE id=?", (id,))

    conn.commit()
    conn.close()
    flash("Test deleted successfully.", "success")

    return redirect("/tests")
