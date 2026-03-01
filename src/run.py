import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.anki_loader_anki_export import load_anki_export_tsv
from src.post_builder import build_post
from src.fallback_generator import generate_fallback
from src.image_pollinations import generate_image
from src.post_to_tg import send_photo, send_message, format_caption

DECK_PATH = "anki/anki_export.txt"
STATE_PATH = "state.json"
OUT_IMG = "out.png"

BA_TZ = timezone(timedelta(hours=-3))  # Buenos Aires


def load_state():
    if not Path(STATE_PATH).exists():
        return {"word_index": 0, "phrase_index": 0, "grammar_index": 0, "last_daily_check_date": ""}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def stable_sort(items):
    # стабильный порядок, чтобы добавление новых карточек не ломало всё
    return sorted(items, key=lambda x: (x.get("term", "").lower(), x.get("translation", "").lower()))


def should_post(kind: str, now_ba: datetime) -> bool:
    h = now_ba.hour

    if kind == "word":
        return h % 2 == 0
    if kind == "phrase":
        return h % 3 == 0
    if kind == "grammar":
        return h % 4 == 0
    return False


def pick_next(items, index_key: str, state: dict):
    idx = int(state.get(index_key, 0))
    if not items:
        return None, idx

    if idx >= len(items):
        # закончились — сигнал на fallback
        return None, idx

    item = items[idx]
    state[index_key] = idx + 1
    return item, idx


def maybe_daily_check(state: dict, now_ba: datetime):
    # 1 раз в день, например в 09:00 BA
    if now_ba.hour != 9:
        return None

    today = now_ba.strftime("%Y-%m-%d")
    if state.get("last_daily_check_date") == today:
        return None

    state["last_daily_check_date"] = today
    return generate_fallback("daily_check")


def post_card(card: dict):
    caption = format_caption(card)

    ok = False
    try:
        ok = generate_image(card.get("image_prompt_en", "simple illustration"), OUT_IMG, 1024, 1024)
    except Exception:
        ok = False

    if ok:
        send_photo(caption, OUT_IMG)
    else:
        send_message(caption)


def main():
    now_ba = datetime.now(BA_TZ)
    state = load_state()

    # 1) Daily check (раз в день)
    daily = maybe_daily_check(state, now_ba)
    if daily:
        post_card(daily)
        save_state(state)
        return

    # 2) Загружаем Anki
    all_items = load_anki_export_tsv(DECK_PATH)
    all_items = [x for x in all_items if (x.get("translation") or "").strip()]
    all_items = stable_sort(all_items)

    words = [x for x in all_items if x.get("kind") == "word"]
    phrases = [x for x in all_items if x.get("kind") == "phrase"]
    grammar = [x for x in all_items if x.get("kind") == "grammar"]

    # 3) Выбираем что постить в этот час
    #    Важно: если совпало несколько (например 0:00) — постим по очереди:
    to_post = []
    if should_post("word", now_ba):
        to_post.append("word")
    if should_post("phrase", now_ba):
        to_post.append("phrase")
    if should_post("grammar", now_ba):
        to_post.append("grammar")

    if not to_post:
        # Нечего постить в этот час — просто сохраняем state (не обязательно)
        save_state(state)
        return

    # 4) По каждому типу: берём из Anki по индексу, иначе fallback генерация
    for kind in to_post:
        if kind == "word":
            item, _ = pick_next(words, "word_index", state)
            if item:
                card = build_post(item["term"], item["translation"], item["kind"], item.get("tags", ""))
            else:
                card = generate_fallback("word")

            post_card(card)

        elif kind == "phrase":
            item, _ = pick_next(phrases, "phrase_index", state)
            if item:
                card = build_post(item["term"], item["translation"], item["kind"], item.get("tags", ""))
            else:
                card = generate_fallback("phrase")

            post_card(card)

        elif kind == "grammar":
            item, _ = pick_next(grammar, "grammar_index", state)
            if item:
                card = build_post(item["term"], item["translation"], item["kind"], item.get("tags", ""))
            else:
                card = generate_fallback("grammar")

            post_card(card)

    save_state(state)


if __name__ == "__main__":
    main()
