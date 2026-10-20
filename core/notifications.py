import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_pushover_notification(title: str, message: str, url: str = ""):
    """
    Send a push notification via Pushover.
    Fails silently on error — notification failure should not affect the main flow.
    """
    user_key = os.getenv("PUSHOVER_USER_KEY", "").strip()
    app_token = os.getenv("PUSHOVER_APP_TOKEN", "").strip()
    if not user_key or not app_token:
        return

    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
    }
    if url:
        payload["url"] = url
        payload["url_title"] = "View Lead"

    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data=payload,
            timeout=5,
        )
    except requests.RequestException:
        # Notification failure should never break signal persistence.
        pass


def send_pushover_notification_re(title: str, message: str, url: str = ""):
    """
    Send a push notification via Pushover.
    Fails silently on error — notification failure should not affect the main flow.
    """
    user_key = os.getenv("PUSHOVER_USER_KEY_RE", "").strip()
    app_token = os.getenv("PUSHOVER_APP_TOKEN_RE", "").strip()
    if not user_key or not app_token:
        return

    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
    }
    if url:
        payload["url"] = url
        payload["url_title"] = "View Lead"

    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data=payload,
            timeout=5,
        )
    except requests.RequestException:
        # Notification failure should never break signal persistence.
        pass



def send_pushover_notification_gb(title: str, message: str, url: str = ""):
    """
    Send a push notification via Pushover.
    Fails silently on error — notification failure should not affect the main flow.
    """
    user_key = os.getenv("PUSHOVER_USER_KEY_GB", "").strip()
    app_token = os.getenv("PUSHOVER_APP_TOKEN_GB", "").strip()
    if not user_key or not app_token:
        return

    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
    }
    if url:
        payload["url"] = url
        payload["url_title"] = "View Lead"

    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data=payload,
            timeout=5,
        )
    except requests.RequestException:
        # Notification failure should never break signal persistence.
        pass