"""Telegram Bot API sender. Token and chat id come only from the environment, never from files:
TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (same names as LeverageTrading), or the older BISS_TG_TOKEN / BISS_TG_CHAT.
"""
from __future__ import annotations

import os

import requests


def _creds() -> tuple[str, str]:
    env = os.environ
    return (env.get("TELEGRAM_BOT_TOKEN") or env.get("BISS_TG_TOKEN") or "",
            env.get("TELEGRAM_CHAT_ID") or env.get("BISS_TG_CHAT") or "")


def configured() -> bool:
    token, chat = _creds()
    return bool(token and chat)


def send_detail(text: str) -> tuple[bool, str]:
    """(sent, what Telegram said). The detail never contains the token."""
    token, chat = _creds()
    if not token or not chat:
        print("[telegram not configured]\n" + text, flush=True)
        return False, "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set"
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}, timeout=20)
    except requests.RequestException as e:
        print("telegram error", type(e).__name__, flush=True)  # never print the URL: it holds the token
        return False, f"network error ({type(e).__name__})"
    if r.status_code != 200:
        try:
            desc = r.json().get("description", "")
        except ValueError:
            desc = r.text[:200]
        print("telegram error", r.status_code, desc, flush=True)
        hint = (" - open the bot in Telegram and press Start, then check TELEGRAM_CHAT_ID"
                if r.status_code in (400, 403) else "")
        return False, f"Telegram {r.status_code}: {desc}{hint}"
    return True, "sent"


def send(text: str) -> bool:
    return send_detail(text)[0]
