import os
import json
import datetime as dt
import requests
from PIL import Image, ImageDraw, ImageFont

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_PATH = os.path.join(BASE_DIR, "content.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
OUT_IMG = os.path.join(BASE_DIR, "card.png")

# Buenos Aires timezone UTC-3 (без переходов)
TZ = dt.timezone(dt.timedelta(hours=-3))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def now_ba():
    return dt.datetime.now(tz=TZ)


def pick_post_kind(now: dt.datetime):
    """
    Расписание:
    - vocab: каждые 2 часа
    - life_phrase: каждые 3 часа
    - grammar: каждые 4 часа
    - daily_check: 1 раз в день (в 21:00 BA)
    
    Приоритет, если совпало несколько:
    1) daily_check
    2) vocab
    3) life_phrase
    4) grammar
    """
    hour = now.hour
    if hour == 21:
        return "daily_check"
    if hour % 2 == 0:
        return "vocab"
    if hour % 3 == 0:
        return "life_phrase"
    if hour % 4 == 0:
        return "grammar"
    # если ни одно не подошло — публикуем vocab (чтобы было стабильно)
    return "vocab"


def make_card(title: str, subtitle: str):
    """
    Делает простую картинку: фон + крупный текст.
    Это MVP: 1080x1080, читаемо.
    """
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    # Шрифты: используем базовый, если нет системных
    try:
        font_big = ImageFont.truetype("DejaVuSans.ttf", 90)
        font_med = ImageFont.truetype("DejaVuSans.ttf", 52)
    except:
        font_big = ImageFont.load_default()
        font_med = ImageFont.load_default()

    # рамка
    pad = 70
    draw.rounded_rectangle([pad, pad, W - pad, H - pad], radius=48, outline=(0, 0, 0), width=4)

    # текст
    draw.text((pad + 60, pad + 140), title, fill=(0, 0, 0), font=font_big)
    draw.text((pad + 60, pad + 290), subtitle, fill=(40, 40, 40), font=font_med)

    # маленькая подпись
    small = "Испанский по-аргентински 🇦🇷"
    try:
        font_small = ImageFont.truetype("DejaVuSans.ttf", 34)
    except:
        font_small = ImageFont.load_default()
    draw.text((pad + 60, H - pad - 90), small, fill=(90, 90, 90), font=font_small)

    img.save(OUT_IMG, "PNG")


def tg_send_photo(caption: str, photo_path: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    with open(photo_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": TG_CHAT_ID, "caption": caption, "parse_mode": "HTML"}
        r = requests.post(url, data=data, files=files, timeout=30)
    r.raise_for_status()
    return r.json()


def tg_send_poll(question: str, options: list):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPoll"
    data = {
        "chat_id": TG_CHAT_ID,
        "question": question,
        "options": json.dumps(options, ensure_ascii=False),
        "is_anonymous": False
    }
    r = requests.post(url, data=data, timeout=30)
    r.raise_for_status()
    return r.json()


def format_vocab(item):
    word = item["word"]
    tr = item["translation"]
    ex = item.get("examples", [])
    ph = item.get("phrases", [])

    lines = []
    lines.append(f"🧉 <b>Слово (AR):</b> <b>{word}</b>")
    lines.append(f"Это значит: <b>{tr}</b>")
    lines.append("")
    lines.append("<b>Скажи так:</b>")
    for e in ex[:3]:
        lines.append(f"• {e}")
    if ph:
        lines.append("")
        lines.append("<b>Ещё варианты:</b>")
        for p in ph[:2]:
            lines.append(f"• {p}")
    return "\n".join(lines), word, tr


def format_life_phrase(item):
    phrase = item["phrase"]
    tr = item["translation"]
    ex = item.get("examples", [])
    lines = []
    lines.append(f"🗣 <b>Фраза для жизни:</b> <b>{phrase}</b>")
    lines.append(f"Значит: <b>{tr}</b>")
    if ex:
        lines.append("")
        lines.append("<b>Примеры:</b>")
        for e in ex[:2]:
            lines.append(f"• {e}")
    return "\n".join(lines), phrase, tr


def format_grammar(item):
    title = item["title"]
    rule = item["rule"]
    ex = item.get("examples", [])
    note = item.get("note", "")
    lines = []
    lines.append(f"🧩 <b>Грамматика:</b> <b>{title}</b>")
    lines.append(f"{rule}")
    if ex:
        lines.append("")
        lines.append("<b>Примеры:</b>")
        for e in ex[:2]:
            lines.append(f"• {e}")
    if note:
        lines.append("")
        lines.append(f"💡 {note}")
    return "\n".join(lines), "Грамматика", title


def run_daily_check(content, state, now):
    # 1 раз в день: если уже постили сегодня — выходим
    today = now.date().isoformat()
    if state.get("daily_check_last_date") == today:
        return False

    item = content["daily_check"][0]
    title = item["title"]
    # публикуем опросы по одному
    for q in item["questions"]:
        tg_send_poll(q["q"], q["options"])

    state["daily_check_last_date"] = today
    save_json(STATE_PATH, state)
    return True


def main():
    content = load_json(CONTENT_PATH)
    state = load_json(STATE_PATH)

    now = now_ba()
    kind = pick_post_kind(now)

    if kind == "daily_check":
        posted = run_daily_check(content, state, now)
        if not posted:
            print("Daily check already posted today.")
        else:
            print("Daily check posted.")
        return

    if kind == "vocab":
        items = content["vocab"]
        idx = state.get("vocab_idx", 0) % max(len(items), 1)
        item = items[idx]
        caption, title, subtitle = format_vocab(item)
        make_card(title=title, subtitle=subtitle)
        tg_send_photo(caption=caption, photo_path=OUT_IMG)
        state["vocab_idx"] = idx + 1

    elif kind == "life_phrase":
        items = content["life_phrase"]
        idx = state.get("life_phrase_idx", 0) % max(len(items), 1)
        item = items[idx]
        caption, title, subtitle = format_life_phrase(item)
        make_card(title=title, subtitle=subtitle)
        tg_send_photo(caption=caption, photo_path=OUT_IMG)
        state["life_phrase_idx"] = idx + 1

    elif kind == "grammar":
        items = content["grammar"]
        idx = state.get("grammar_idx", 0) % max(len(items), 1)
        item = items[idx]
        caption, title, subtitle = format_grammar(item)
        make_card(title=title, subtitle=subtitle)
        tg_send_photo(caption=caption, photo_path=OUT_IMG)
        state["grammar_idx"] = idx + 1

    save_json(STATE_PATH, state)
    print(f"Posted kind={kind} at {now.isoformat()}")


if __name__ == "__main__":
    main()
