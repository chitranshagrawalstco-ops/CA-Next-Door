import hashlib
import hmac
import json
import os
import platform
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import datetime
try:
    import winreg
except Exception:
    winreg = None

from config import DB_NAME
from core.google_api import (
    bind_machine,
    download_user_db,
    ensure_user_drive_folder,
    get_google_auth_mode,
    get_google_api_config_error,
    get_user_row,
    set_drive_status as google_set_drive_status,
    upload_user_db,
)


SYSTEM_ID_CACHE = None


def _get_connection():
    return sqlite3.connect(DB_NAME)


def _get_backend_config():
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT backend_api_url, backend_api_key
            FROM admin_settings
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        conn.close()
        url_db = (row[0] if row and row[0] else "").strip()
        key_db = (row[1] if row and row[1] else "").strip()
        return {
            "url": url_db or (os.environ.get("BACKEND_API_URL") or "").strip(),
            "key": key_db or (os.environ.get("BACKEND_API_KEY") or "").strip(),
        }
    except sqlite3.Error:
        return {
            "url": (os.environ.get("BACKEND_API_URL") or "").strip(),
            "key": (os.environ.get("BACKEND_API_KEY") or "").strip(),
        }


def _post_backend_json(payload, timeout=20):
    cfg = _get_backend_config()
    url = cfg["url"]
    key = cfg["key"]
    if not url:
        return None, "backend API URL is not configured."
    if not key:
        return None, "backend API key is not configured."
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": key},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body else {}), None
    except urllib.error.HTTPError as ex:
        try:
            details = ex.read().decode("utf-8")
        except Exception:
            details = str(ex)
        return None, details
    except Exception as ex:
        return None, str(ex)


def check_internet():
    urls = [
        "https://clients3.google.com/generate_204",
        "https://www.gstatic.com/generate_204"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=4) as response:
                if 200 <= response.status < 400:
                    return True
        except Exception:
            pass
    return False


def get_system_id():
    global SYSTEM_ID_CACHE
    if SYSTEM_ID_CACHE:
        return SYSTEM_ID_CACHE

    raw = ""
    try:
        if winreg is None:
            raise RuntimeError("winreg unavailable")
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        raw = winreg.QueryValueEx(key, "MachineGuid")[0]
    except Exception:
        node = uuid.getnode()
        raw = f"{platform.node()}-{node}"

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    SYSTEM_ID_CACHE = f"SYS-{digest[:24]}"
    return SYSTEM_ID_CACHE


def init_auth_schema():
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """
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
        """
    )
    for ddl in [
        "ALTER TABLE auth_session ADD COLUMN active INTEGER DEFAULT 1",
        "ALTER TABLE auth_session ADD COLUMN expiry_date TEXT",
        "ALTER TABLE auth_session ADD COLUMN drive_connected INTEGER DEFAULT 0",
        "ALTER TABLE auth_session ADD COLUMN drive_folder_id TEXT",
        "ALTER TABLE auth_session ADD COLUMN last_login_at TEXT",
    ]:
        try:
            cur.execute(ddl)
        except Exception:
            pass
    conn.commit()
    conn.close()


def reset_runtime_session():
    init_auth_schema()
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE auth_session SET logged_in=0")
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def _save_session(user_id, active, expiry_date, drive_connected, drive_folder_id, logged_in=1):
    init_auth_schema()
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM auth_session LIMIT 1")
        row = cur.fetchone()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sid = get_system_id()
        if row:
            cur.execute(
                """
                UPDATE auth_session
                SET user_id=?, system_id=?, logged_in=?, active=?, expiry_date=?, drive_connected=?, drive_folder_id=?, last_login_at=?
                WHERE id=?
                """,
                (
                    user_id,
                    sid,
                    1 if logged_in else 0,
                    1 if active else 0,
                    expiry_date,
                    1 if drive_connected else 0,
                    drive_folder_id or "",
                    now_str,
                    row[0]
                )
            )
        else:
            cur.execute(
                """
                INSERT INTO auth_session (user_id, system_id, logged_in, active, expiry_date, drive_connected, drive_folder_id, last_login_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    sid,
                    1 if logged_in else 0,
                    1 if active else 0,
                    expiry_date,
                    1 if drive_connected else 0,
                    drive_folder_id or "",
                    now_str
                )
            )
        conn.commit()
        conn.close()
    except sqlite3.Error:
        return


def _get_session():
    init_auth_schema()
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, system_id, logged_in, active, expiry_date, drive_connected, drive_folder_id, last_login_at
            FROM auth_session
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        conn.close()
    except sqlite3.Error:
        return None
    if not row:
        return None
    return {
        "user_id": row[0] or "",
        "system_id": row[1] or "",
        "logged_in": bool(row[2]),
        "active": bool(row[3]),
        "expiry_date": row[4] or "",
        "drive_connected": bool(row[5]),
        "drive_folder_id": row[6] or "",
        "last_login_at": row[7] or "",
    }


def is_session_active():
    state = _get_session()
    if not state or not state["logged_in"] or not state["user_id"]:
        return False
    if state["system_id"] != get_system_id():
        return False
    if not state["active"]:
        return False
    if state["expiry_date"]:
        try:
            expiry = datetime.strptime(state["expiry_date"], "%Y-%m-%d")
            if datetime.now() > expiry:
                return False
        except Exception:
            return False
    return True


def get_days_remaining():
    state = _get_session()
    if not state or not state.get("expiry_date"):
        return None
    try:
        expiry = datetime.strptime(state["expiry_date"], "%Y-%m-%d")
    except Exception:
        return None
    return (expiry - datetime.now()).days


def get_session_state():
    return _get_session()


def _verify_password(raw_password, stored_hash):
    if not stored_hash:
        return False
    candidate_hex = hashlib.sha256(raw_password.encode("utf-8")).hexdigest()
    stored = stored_hash.strip()
    if stored.startswith("sha256$"):
        stored = stored.split("$", 1)[1]
    if len(stored) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in stored):
        return hmac.compare_digest(candidate_hex.lower(), stored.lower())
    return hmac.compare_digest(raw_password, stored_hash)


def _as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def authenticate(user_id, password):
    if not user_id or not password:
        return {"ok": False, "message": "User ID and password are required."}

    if not check_internet():
        return {"ok": False, "message": "Internet connection is required."}

    backend_cfg = _get_backend_config()
    user = None
    if backend_cfg["url"]:
        response, err = _post_backend_json({"action": "get_user", "user_id": user_id})
        if err or not response or not response.get("ok"):
            return {"ok": False, "message": "Backend user lookup failed." if not err else err}
        user = response.get("user") or {}
    else:
        cfg_err = get_google_api_config_error()
        if cfg_err:
            return {"ok": False, "message": cfg_err}
        user, _, err = get_user_row(user_id)
        if err or not user:
            return {"ok": False, "message": err or "User not found."}

    stored_hash = user.get("password_hash", "")
    if not _verify_password(password, stored_hash):
        return {"ok": False, "message": "Invalid credentials."}

    # Support both column names: "active" and "status".
    raw_active = user.get("active", "")
    if str(raw_active).strip() == "":
        raw_active = user.get("status", "FALSE")
    active = _as_bool(raw_active)
    if not active:
        return {"ok": False, "message": "User is disabled by admin."}

    expiry_date = (user.get("expiry_date") or "").strip()
    if expiry_date:
        try:
            expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
            if datetime.now() > expiry:
                return {"ok": False, "message": "Subscription has expired."}
        except Exception:
            return {"ok": False, "message": "Invalid expiry_date format in sheet (use YYYY-MM-DD)."}

    current_sid = get_system_id()
    bound_sid = (user.get("system_id") or "").strip()
    first_bind = False
    google_mode = get_google_auth_mode()

    if not bound_sid:
        if backend_cfg["url"]:
            response, err = _post_backend_json(
                {"action": "bind_machine", "user_id": user_id, "system_id": current_sid}
            )
            if err or not response or not response.get("ok"):
                return {"ok": False, "message": err or "Machine binding failed."}
        elif google_mode == "service_account":
            bind_err = bind_machine(user_id, current_sid)
            if bind_err:
                return {"ok": False, "message": bind_err}
            bound_sid = current_sid
            first_bind = True
        else:
            # API-key mode cannot write back machine binding.
            bound_sid = current_sid

    if bound_sid != current_sid:
        return {"ok": False, "message": "This account is already linked to another machine."}

    drive_connected = _as_bool(user.get("drive_connected", "FALSE"))
    drive_folder_id = (user.get("drive_folder_id") or "").strip()
    _save_session(
        user_id=user_id,
        active=active,
        expiry_date=expiry_date,
        drive_connected=drive_connected,
        drive_folder_id=drive_folder_id,
        logged_in=1
    )

    return {
        "ok": True,
        "message": "Login successful.",
        "first_bind": first_bind,
        "drive_connected": drive_connected,
        "drive_folder_id": drive_folder_id
    }


def set_drive_status(drive_connected, drive_folder_id):
    state = _get_session()
    if not state:
        return {"ok": False, "message": "No active user session."}

    backend_cfg = _get_backend_config()
    if backend_cfg["url"]:
        response, err = _post_backend_json(
            {
                "action": "set_drive_status",
                "user_id": state["user_id"],
                "drive_connected": bool(drive_connected),
                "drive_folder_id": drive_folder_id or "",
            }
        )
        if err or not response or not response.get("ok"):
            return {"ok": False, "message": err or "Unable to update drive status."}
    else:
        cfg_err = get_google_api_config_error()
        if cfg_err:
            return {"ok": False, "message": cfg_err}
        err = google_set_drive_status(state["user_id"], bool(drive_connected), drive_folder_id or "")
        if err:
            return {"ok": False, "message": err}

    _save_session(
        user_id=state["user_id"],
        active=state["active"],
        expiry_date=state["expiry_date"],
        drive_connected=bool(drive_connected),
        drive_folder_id=drive_folder_id or "",
        logged_in=1
    )
    return {"ok": True, "message": "Drive status updated."}


def connect_drive():
    state = _get_session()
    if not state:
        return {"ok": False, "message": "No active user session."}

    backend_cfg = _get_backend_config()
    if backend_cfg["url"]:
        response, err = _post_backend_json({"action": "drive_setup", "user_id": state["user_id"]})
        if err or not response or not response.get("ok"):
            return {"ok": False, "message": err or "Google Drive connection failed."}
        folder_id = (response.get("drive_folder_id") or "").strip()
        if not folder_id:
            return {"ok": False, "message": "Drive setup did not return a folder id."}
    else:
        cfg_err = get_google_api_config_error()
        if cfg_err:
            return {"ok": False, "message": cfg_err}
        folder_id, err = ensure_user_drive_folder(state["user_id"])
        if err:
            return {"ok": False, "message": err}
        if not folder_id:
            return {"ok": False, "message": "Unable to determine Drive folder for this user."}

    _save_session(
        user_id=state["user_id"],
        active=state["active"],
        expiry_date=state["expiry_date"],
        drive_connected=True,
        drive_folder_id=folder_id,
        logged_in=1
    )
    return {"ok": True, "message": "Google Drive connected.", "drive_folder_id": folder_id}


def download_latest_data():
    state = _get_session()
    if not state or not state["drive_connected"]:
        return {"ok": True, "message": "Drive not connected; using local data."}

    folder_id = state.get("drive_folder_id", "").strip()
    if not folder_id:
        return {"ok": True, "message": "Drive folder not set; local data retained."}
    backend_cfg = _get_backend_config()
    if backend_cfg["url"]:
        response, err = _post_backend_json(
            {"action": "download_db", "user_id": state["user_id"], "drive_folder_id": folder_id},
            timeout=45
        )
        if err or not response or not response.get("ok"):
            return {"ok": False, "message": err or "Download failed."}
        db_blob = (response.get("db_base64") or "").strip()
        if not db_blob:
            return {"ok": True, "message": "No cloud snapshot found; local data retained."}
        try:
            import base64
            db_bytes = base64.b64decode(db_blob)
        except Exception as ex:
            return {"ok": False, "message": f"Invalid cloud payload: {ex}"}
    else:
        cfg_err = get_google_api_config_error()
        if cfg_err:
            return {"ok": False, "message": cfg_err}
        db_bytes, err = download_user_db(state["user_id"], folder_id)
        if err:
            return {"ok": False, "message": err}
        if not db_bytes:
            return {"ok": True, "message": "No cloud snapshot found; local data retained."}

    try:
        with open(DB_NAME, "wb") as fp:
            fp.write(db_bytes)
        _save_session(
            user_id=state["user_id"],
            active=state["active"],
            expiry_date=state["expiry_date"],
            drive_connected=state["drive_connected"],
            drive_folder_id=state["drive_folder_id"],
            logged_in=1
        )
        return {"ok": True, "message": "Loaded latest data from Google Drive."}
    except Exception as ex:
        return {"ok": False, "message": f"Cloud data apply failed: {ex}"}


def upload_latest_data():
    state = _get_session()
    if not state or not state["drive_connected"] or not state["logged_in"]:
        return {"ok": True, "message": "Skip upload."}

    if not os.path.exists(DB_NAME):
        return {"ok": False, "message": "Local database file not found."}

    folder_id = state.get("drive_folder_id", "").strip()
    if not folder_id:
        return {"ok": False, "message": "Drive folder ID is missing."}

    try:
        with open(DB_NAME, "rb") as fp:
            db_bytes = fp.read()
    except Exception as ex:
        return {"ok": False, "message": f"Unable to read local database: {ex}"}

    backend_cfg = _get_backend_config()
    if backend_cfg["url"]:
        import base64
        response, err = _post_backend_json(
            {
                "action": "upload_db",
                "user_id": state["user_id"],
                "drive_folder_id": folder_id,
                "db_base64": base64.b64encode(db_bytes).decode("utf-8"),
            },
            timeout=45
        )
        if err or not response or not response.get("ok"):
            return {"ok": False, "message": err or "Upload failed."}
    else:
        cfg_err = get_google_api_config_error()
        if cfg_err:
            return {"ok": False, "message": cfg_err}
        err = upload_user_db(state["user_id"], folder_id, db_bytes)
        if err:
            return {"ok": False, "message": err}

    return {"ok": True, "message": "Cloud upload successful."}
