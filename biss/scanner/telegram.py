"""Telegram Bot API sender. Token and chat id come only from the environment (BISS_TG_TOKEN, BISS_TG_CHAT)."""
from __future__ import annotations

import os

import requests


def configured() -> bool:
    return bool(os.environ.get("BISS_TG_TOKEN") and os.environ.get("BISS_TG_CHAT"))


def send(text: str) -> bool:
    token, chat = os.environ.get("BISS_TG_TOKEN"), os.environ.get("BISS_TG_CHAT")
    if not token or not chat:
        print("[telegram not configured]\n" + text, flush=True)
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}, timeout=20)
    if r.status_code != 200:
        print("telegram error", r.status_code, r.text[:200], flush=True)
    return r.status_code == 200
