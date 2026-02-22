import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from core.database import get_connection


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _api_json_request(method: str, url: str, token: str, payload=None, timeout: int = 20):
    headers = {"Authorization": f"Bearer {token}"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}


def _api_binary_request(method: str, url: str, token: str, body=None, content_type="application/octet-stream", timeout: int = 30):
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _get_admin_google_config() -> Dict[str, str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT google_credentials_path, google_sheet_id, google_sheet_tab, google_api_key
        FROM admin_settings
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()
    return {
        "credentials_path": ((row[0] if row and row[0] else "").strip() or (os.environ.get("GOOGLE_CREDENTIALS_PATH") or "").strip()),
        "sheet_id": ((row[1] if row and row[1] else "").strip() or (os.environ.get("GOOGLE_SHEET_ID") or "").strip()),
        "sheet_tab": ((row[2] if row and row[2] else "users").strip() or (os.environ.get("GOOGLE_SHEET_TAB") or "users").strip() or "users"),
        "api_key": ((row[3] if row and row[3] else "").strip() or (os.environ.get("GOOGLE_API_KEY") or "").strip()),
        "credentials_json_env": (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip(),
    }


def get_google_api_config_error() -> Optional[str]:
    cfg = _get_admin_google_config()
    if not cfg["sheet_id"]:
        return "Google Spreadsheet ID is not configured."
    if not cfg["credentials_path"] and not cfg["credentials_json_env"] and not cfg["api_key"]:
        return "Configure either Service Account JSON path or Google API key."
    return None


def get_google_auth_mode() -> str:
    cfg = _get_admin_google_config()
    if cfg["credentials_path"] or cfg["credentials_json_env"]:
        return "service_account"
    if cfg["api_key"]:
        return "api_key"
    return "none"


def _load_service_account(path: str):
    if path:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    else:
        raw_json = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
        if not raw_json:
            raise FileNotFoundError("Service account JSON is not configured.")
        data = json.loads(raw_json)
    required = ["client_email", "private_key", "token_uri"]
    for key in required:
        if not data.get(key):
            raise ValueError(f"Service account JSON missing '{key}'.")
    return data


def _get_access_token(scopes: List[str]) -> str:
    cfg = _get_admin_google_config()
    sa = _load_service_account(cfg["credentials_path"])
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": sa["client_email"],
        "scope": " ".join(scopes),
        "aud": sa["token_uri"],
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))}.{_b64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
    private_key = serialization.load_pem_private_key(sa["private_key"].encode("utf-8"), password=None)
    signature = private_key.sign(signing_input.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    assertion = f"{signing_input}.{_b64url(signature)}"

    token_payload = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion
    }).encode("utf-8")
    req = urllib.request.Request(sa["token_uri"], data=token_payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        token_res = json.loads(resp.read().decode("utf-8"))
        token = token_res.get("access_token", "")
        if not token:
            raise ValueError("Failed to fetch access token from Google OAuth.")
        return token


def _col_num_to_letter(col_num: int) -> str:
    letters = ""
    n = col_num
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _sheet_values_range(tab: str) -> str:
    return urllib.parse.quote(f"{tab}!A1:Z")


def get_user_row(user_id: str) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, object]], Optional[str]]:
    try:
        cfg = _get_admin_google_config()
        rng = _sheet_values_range(cfg["sheet_tab"])
        if cfg.get("api_key"):
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{cfg['sheet_id']}/values/{rng}?key={urllib.parse.quote(cfg['api_key'])}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        else:
            token = _get_access_token([SHEETS_SCOPE])
            url = f"https://sheets.googleapis.com/v4/spreadsheets/{cfg['sheet_id']}/values/{rng}"
            data = _api_json_request("GET", url, token)
        values = data.get("values", [])
        if not values:
            return None, None, "Users sheet is empty."
        headers = [str(h).strip() for h in values[0]]
        if "user_id" not in headers:
            return None, None, "Sheet header must include 'user_id'."
        for idx, row in enumerate(values[1:], start=2):
            row_data = {}
            for i, key in enumerate(headers):
                row_data[key] = str(row[i]).strip() if i < len(row) and row[i] is not None else ""
            if row_data.get("user_id", "").strip() == user_id.strip():
                return row_data, {"row_index": idx, "headers": headers, "cfg": cfg}, None
        return None, None, "User not found."
    except FileNotFoundError:
        return None, None, "Google credentials JSON file path not found."
    except urllib.error.HTTPError as ex:
        try:
            body = ex.read().decode("utf-8")
            return None, None, f"Google API error: {ex.code} - {body}"
        except Exception:
            return None, None, f"Google API error: {ex.code}"
    except Exception as ex:
        return None, None, str(ex)


def _update_row_cells(meta: Dict[str, object], updates: Dict[str, object]) -> Optional[str]:
    headers = meta["headers"]
    cfg = meta["cfg"]
    row_index = meta["row_index"]
    data_items = []
    for key, value in updates.items():
        if key not in headers:
            continue
        col_letter = _col_num_to_letter(headers.index(key) + 1)
        data_items.append({
            "range": f"{cfg['sheet_tab']}!{col_letter}{row_index}",
            "values": [[value]]
        })
    if not data_items:
        return None

    token = _get_access_token([SHEETS_SCOPE])
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{cfg['sheet_id']}/values:batchUpdate"
    payload = {"valueInputOption": "RAW", "data": data_items}
    _api_json_request("POST", url, token, payload=payload)
    return None


def bind_machine(user_id: str, system_id: str) -> Optional[str]:
    if get_google_auth_mode() != "service_account":
        return "Machine binding requires service account mode or backend API mode."
    user, meta, err = get_user_row(user_id)
    if err:
        return err
    if not user or not meta:
        return "User not found."
    existing = user.get("system_id", "").strip()
    if existing and existing != system_id:
        return "This account is already linked to another machine."
    return _update_row_cells(meta, {"system_id": system_id})


def set_drive_status(user_id: str, drive_connected: bool, drive_folder_id: str) -> Optional[str]:
    if get_google_auth_mode() != "service_account":
        return "Drive status update requires service account mode or backend API mode."
    user, meta, err = get_user_row(user_id)
    if err:
        return err
    if not user or not meta:
        return "User not found."
    return _update_row_cells(meta, {
        "drive_connected": "TRUE" if drive_connected else "FALSE",
        "drive_folder_id": drive_folder_id or ""
    })


def ensure_user_drive_folder(user_id: str) -> Tuple[Optional[str], Optional[str]]:
    if get_google_auth_mode() != "service_account":
        return None, "Drive setup requires service account mode or backend API mode."
    user, meta, err = get_user_row(user_id)
    if err:
        return None, err
    if not user or not meta:
        return None, "User not found."

    existing_folder = user.get("drive_folder_id", "").strip()
    if existing_folder:
        return existing_folder, None

    try:
        token = _get_access_token([DRIVE_SCOPE, SHEETS_SCOPE])
        payload = {
            "name": f"CA_FINAL_APP_{user_id}",
            "mimeType": "application/vnd.google-apps.folder"
        }
        data = _api_json_request("POST", "https://www.googleapis.com/drive/v3/files", token, payload=payload)
        folder_id = data.get("id", "").strip()
        if not folder_id:
            return None, "Failed to create Google Drive folder."
        upd_err = _update_row_cells(meta, {"drive_connected": "TRUE", "drive_folder_id": folder_id})
        if upd_err:
            return None, upd_err
        return folder_id, None
    except Exception as ex:
        return None, str(ex)


def _find_drive_file_id(token: str, folder_id: str, filename: str) -> Optional[str]:
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    url = "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode({
        "q": q,
        "fields": "files(id,name)",
        "spaces": "drive"
    })
    data = _api_json_request("GET", url, token)
    files = data.get("files", [])
    if not files:
        return None
    return files[0].get("id")


def upload_user_db(user_id: str, folder_id: str, db_bytes: bytes) -> Optional[str]:
    if get_google_auth_mode() != "service_account":
        return "Drive upload requires service account mode or backend API mode."
    try:
        token = _get_access_token([DRIVE_SCOPE])
        filename = f"db_{user_id}.db"
        existing_file_id = _find_drive_file_id(token, folder_id, filename)
        if existing_file_id:
            url = f"https://www.googleapis.com/upload/drive/v3/files/{existing_file_id}?uploadType=media"
            _api_binary_request("PATCH", url, token, body=db_bytes)
            return None

        boundary = "ca-final-app-boundary"
        metadata = json.dumps({"name": filename, "parents": [folder_id]}).encode("utf-8")
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        ).encode("utf-8") + metadata + (
            f"\r\n--{boundary}\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + db_bytes + f"\r\n--{boundary}--".encode("utf-8")
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        _api_binary_request("POST", url, token, body=body, content_type=f"multipart/related; boundary={boundary}")
        return None
    except Exception as ex:
        return str(ex)


def download_user_db(user_id: str, folder_id: str) -> Tuple[Optional[bytes], Optional[str]]:
    if get_google_auth_mode() != "service_account":
        return None, "Drive download requires service account mode or backend API mode."
    try:
        token = _get_access_token([DRIVE_SCOPE])
        filename = f"db_{user_id}.db"
        file_id = _find_drive_file_id(token, folder_id, filename)
        if not file_id:
            return None, None
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        data = _api_binary_request("GET", url, token)
        return data, None
    except Exception as ex:
        return None, str(ex)
