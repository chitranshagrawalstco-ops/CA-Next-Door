from flask import Blueprint, render_template, request, redirect
from core.database import get_connection

links_bp = Blueprint("links", __name__)


# -------- LIST + ADD --------
@links_bp.route("/links", methods=["GET", "POST"])
def links():

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]
        url = request.form["url"]

        cur.execute(
            "INSERT INTO useful_links (title, url) VALUES (?, ?)",
            (title, url)
        )
        conn.commit()

    cur.execute("SELECT id, title, url FROM useful_links")
    links = cur.fetchall()

    conn.close()

    return render_template("links.html", links=links)


# -------- EDIT --------
@links_bp.route("/links/edit/<int:id>", methods=["GET", "POST"])
def edit_link(id):

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]
        url = request.form["url"]

        cur.execute(
            "UPDATE useful_links SET title=?, url=? WHERE id=?",
            (title, url, id)
        )
        conn.commit()
        conn.close()

        return redirect("/links")

    cur.execute("SELECT title, url FROM useful_links WHERE id=?", (id,))
    link = cur.fetchone()

    conn.close()

    return render_template("edit_link.html", link=link, id=id)


# -------- DELETE --------
@links_bp.route("/links/delete/<int:id>")
def delete_link(id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM useful_links WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/links")
