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


def send(text: str) -> bool:
    token, chat = _creds()
    if not token or not chat:
        print("[telegram not configured]\n" + text, flush=True)
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}, timeout=20)
    except requests.RequestException as e:
        print("telegram error", type(e).__name__, flush=True)  # never print the URL: it holds the token
        return False
    if r.status_code != 200:
        print("telegram error", r.status_code, r.text[:200], flush=True)
    return r.status_code == 200
