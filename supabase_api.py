import os
import requests

from core.database import get_connection


def _get_admin_supabase_config():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT supabase_url, supabase_key
        FROM admin_settings
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return "", ""
        
    url = (row[0] or "").strip()
    key = (row[1] or "").strip()
    return url, key


def _get_supabase_headers():
    url, key = _get_admin_supabase_config()
    if not url or not key:
        return None, None, "Supabase URL and Key are not configured in Admin Settings."
        
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    return url, headers, None


def get_user_row(user_id: str):
    """
    Fetch a user's license/auth details from Supabase using REST API.
    """
    url, headers, err = _get_supabase_headers()
    if err:
        return None, None, err
        
    try:
        endpoint = f"{url}/rest/v1/users?user_id=eq.{user_id}&select=*"
        resp = requests.get(endpoint, headers=headers, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        if not data or len(data) == 0:
            return None, None, "User not found in Supabase database."
            
        user = data[0]
        
        user_dict = {
            "password_hash": user.get("password", ""),
            "system_id": user.get("system_id", ""),
            "active": user.get("active", False),
            "expiry_date": user.get("expiry_date", ""),
            "drive_connected": user.get("drive_connected", False),
            "drive_folder_id": user.get("drive_folder_id", "")
        }
        
        return user_dict, user, None
        
    except requests.exceptions.RequestException as e:
        return None, None, f"Supabase network error: {str(e)}"
    except Exception as e:
        return None, None, f"Supabase error: {str(e)}"


def bind_machine(user_id: str, system_id: str):
    """
    Lock the license to a specific machine ID using REST API.
    """
    url, headers, err = _get_supabase_headers()
    if err:
        return err
        
    try:
        endpoint = f"{url}/rest/v1/users?user_id=eq.{user_id}"
        payload = {"system_id": system_id}
        resp = requests.patch(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return None
    except requests.exceptions.RequestException as e:
        return f"Supabase network error updating machine ID: {str(e)}"
    except Exception as e:
        return f"Supabase error updating machine ID: {str(e)}"


def set_drive_status(user_id: str, drive_connected: bool, drive_folder_id: str):
    """
    Update the Drive connection status in Supabase using REST API.
    """
    url, headers, err = _get_supabase_headers()
    if err:
        return err
        
    try:
        endpoint = f"{url}/rest/v1/users?user_id=eq.{user_id}"
        payload = {
            "drive_connected": drive_connected,
            "drive_folder_id": drive_folder_id
        }
        resp = requests.patch(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return None
    except requests.exceptions.RequestException as e:
        return f"Supabase network error updating Drive status: {str(e)}"
    except Exception as e:
        return f"Supabase error updating Drive status: {str(e)}"
