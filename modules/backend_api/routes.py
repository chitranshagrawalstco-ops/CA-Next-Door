import base64
import os

from flask import Blueprint, jsonify, request

from config import DB_NAME
from core.database import get_connection
from core.google_api import (
    download_user_db,
    ensure_user_drive_folder,
    upload_user_db,
)
from core.supabase_api import (
    bind_machine,
    get_user_row,
    set_drive_status,
)


backend_api_bp = Blueprint("backend_api", __name__, url_prefix="/api/v1")


def _latest_backend_key():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT backend_api_key
        FROM admin_settings
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()
    key_db = (row[0] if row and row[0] else "").strip()
    return key_db or (os.environ.get("BACKEND_API_KEY") or "").strip()


def _authorized():
    expected = _latest_backend_key()
    if not expected:
        return False
    received = (request.headers.get("X-API-Key") or "").strip()
    return received == expected


@backend_api_bp.route("/auth", methods=["POST"])
def auth_api():
    if not _authorized():
        return jsonify({"ok": False, "message": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").strip()

    try:
        if action == "get_user":
            user_id = (payload.get("user_id") or "").strip()
            user, _, err = get_user_row(user_id)
            if err or not user:
                return jsonify({"ok": False, "message": err or "User not found."}), 400
            return jsonify({"ok": True, "user": user})

        if action == "bind_machine":
            user_id = (payload.get("user_id") or "").strip()
            system_id = (payload.get("system_id") or "").strip()
            err = bind_machine(user_id, system_id)
            if err:
                return jsonify({"ok": False, "message": err}), 400
            return jsonify({"ok": True})

        if action == "set_drive_status":
            user_id = (payload.get("user_id") or "").strip()
            drive_connected = bool(payload.get("drive_connected"))
            drive_folder_id = (payload.get("drive_folder_id") or "").strip()
            err = set_drive_status(user_id, drive_connected, drive_folder_id)
            if err:
                return jsonify({"ok": False, "message": err}), 400
            return jsonify({"ok": True})

        if action == "drive_setup":
            user_id = (payload.get("user_id") or "").strip()
            folder_id, err = ensure_user_drive_folder(user_id)
            if err or not folder_id:
                return jsonify({"ok": False, "message": err or "Drive setup failed."}), 400
            return jsonify({"ok": True, "drive_folder_id": folder_id})

        if action == "download_db":
            user_id = (payload.get("user_id") or "").strip()
            drive_folder_id = (payload.get("drive_folder_id") or "").strip()
            blob, err = download_user_db(user_id, drive_folder_id)
            if err:
                return jsonify({"ok": False, "message": err}), 400
            if not blob:
                return jsonify({"ok": True, "db_base64": ""})
            return jsonify({"ok": True, "db_base64": base64.b64encode(blob).decode("utf-8")})

        if action == "upload_db":
            user_id = (payload.get("user_id") or "").strip()
            drive_folder_id = (payload.get("drive_folder_id") or "").strip()
            encoded = (payload.get("db_base64") or "").strip()
            if not encoded:
                return jsonify({"ok": False, "message": "db_base64 is required."}), 400
            data = base64.b64decode(encoded)
            err = upload_user_db(user_id, drive_folder_id, data)
            if err:
                return jsonify({"ok": False, "message": err}), 400
            return jsonify({"ok": True})

        return jsonify({"ok": False, "message": "Invalid action."}), 400
    except Exception as ex:
        return jsonify({"ok": False, "message": str(ex)}), 500
