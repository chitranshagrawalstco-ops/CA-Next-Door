import atexit
import os
import sys
import threading
import webbrowser

from flask import Flask, redirect, request

from core.auth_sync import check_internet, get_system_id, reset_runtime_session, upload_latest_data
from core.database import init_db
from modules.dashboard.routes import dashboard_bp
from modules.links.routes import links_bp
from modules.backend_api import backend_api_bp
from modules.student import student_bp
from modules.student.routes import get_branding_settings, is_license_active
from modules.subjects import subjects_bp


BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = os.environ.get("SECRET_KEY", "ca-next-door-local-secret")

app.register_blueprint(student_bp)
app.register_blueprint(subjects_bp)
app.register_blueprint(links_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(backend_api_bp)


@app.before_request
def enforce_license():
    public_paths = {"/activate", "/admin", "/admin-panel"}

    if request.path.startswith("/static/"):
        return None
    if request.path.startswith("/api/"):
        return None

    if is_license_active() and request.path == "/activate":
        return redirect("/")

    if request.path in public_paths:
        return None

    if not is_license_active():
        return redirect("/activate")

    return None


@app.context_processor
def inject_license_state():
    return {
        "license_active": is_license_active(),
        "branding": get_branding_settings()
    }


init_db()


def _sync_on_exit():
    try:
        upload_latest_data()
    except Exception:
        pass


def init_desktop_runtime():
    if not check_internet():
        print("Internet connection is required. Exiting app.")
        sys.exit(1)
    get_system_id()
    reset_runtime_session()
    atexit.register(_sync_on_exit)


def open_browser():
    webbrowser.open("http://127.0.0.1:5010")


if __name__ == "__main__":
    init_desktop_runtime()
    threading.Timer(1.5, open_browser).start()
    app.run(host="127.0.0.1", port=5010, debug=False)
