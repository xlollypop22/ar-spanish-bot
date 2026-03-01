import os, requests

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

def format_caption(card: dict) -> str:
    lines = []
    lines.append(f"🧉 <b>{card['term']}</b> — {card['translation_ru']}".strip())
    lines.append("")
    for ex in card["examples"]:
        lines.append(f"• {ex}")
    lines.append("")
    lines.append("<b>Ещё варианты:</b>")
    for c in card["collocations"]:
        lines.append(f"• {c}")
    if card.get("note_ru"):
        lines.append("")
        lines.append(f"💡 {card['note_ru']}")
    return "\n".join(lines)

def send_photo(caption: str, photo_path: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": TG_CHAT_ID, "caption": caption, "parse_mode": "HTML"}
        r = requests.post(url, data=data, files=files, timeout=60)
    r.raise_for_status()
