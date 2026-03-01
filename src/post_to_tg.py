import os
import requests


TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()


def _require_env():
    if not TG_BOT_TOKEN:
        raise RuntimeError("TG_BOT_TOKEN is missing (set it in GitHub Secrets).")
    if not TG_CHAT_ID:
        raise RuntimeError("TG_CHAT_ID is missing (set it in GitHub Secrets).")


def format_caption(card: dict) -> str:
    term = (card.get("term") or "").strip()
    tr = (card.get("translation_ru") or "").strip()
    note = (card.get("note_ru") or "").strip()

    lines = []
    lines.append(f"🧉 <b>Слово (AR):</b> <b>{term}</b>")
    if tr:
        lines.append(f"Это значит: <b>{tr}</b>")
    lines.append("")

    ex = card.get("examples") or []
    if ex:
        lines.append("📌 <b>Примеры:</b>")
        for e in ex[:3]:
            if isinstance(e, dict):
                es = (e.get("es") or "").strip()
                ru = (e.get("ru") or "").strip()
            else:
                es = str(e).strip()
                ru = ""
            if es:
                lines.append(f"• {es}")
            if ru:
                lines.append(f"→ {ru}")
        lines.append("")

    col = card.get("collocations") or []
    if col:
        lines.append("🔹 <b>Ещё варианты:</b>")
        for c in col[:4]:
            if isinstance(c, dict):
                es = (c.get("es") or "").strip()
                ru = (c.get("ru") or "").strip()
            else:
                es = str(c).strip()
                ru = ""
            if es:
                lines.append(f"• {es}")
            if ru:
                lines.append(f"→ {ru}")
        lines.append("")

    if note:
        lines.append("💬 <b>Заметка:</b>")
        lines.append(note)

    text = "\n".join(lines).strip()

    # Telegram caption limit ~1024 chars for photos, but message limit is larger.
    # Мы делаем универсально: при фото обрежется на стороне Telegram,
    # поэтому здесь держим безопасно около 3500.
    return text[:3500]


def send_message(text: str):
    _require_env()
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, data=data, timeout=60)
    # если телега ругнулась — покажем текст ошибки в логах Actions
    if r.status_code != 200:
        raise RuntimeError(f"Telegram sendMessage failed: {r.status_code} {r.text}")
    return r.json()


def send_photo(caption: str, image_path: str):
    _require_env()
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": TG_CHAT_ID, "caption": caption, "parse_mode": "HTML"}
        r = requests.post(url, data=data, files=files, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Telegram sendPhoto failed: {r.status_code} {r.text}")
    return r.json()
