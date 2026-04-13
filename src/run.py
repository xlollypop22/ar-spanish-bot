import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.anki_loader_anki_export import load_anki_export_tsv
from src.post_builder import build_post
from src.fallback_generator import generate_fallback
from src.image_pollinations import generate_image
from src.post_to_tg import send_photo, format_caption
from src.groq_text import groq_chat
from src.image_card import make_text_card

DECK_PATH = "anki/anki_export.txt"
STATE_PATH = "state.json"
HISTORY_PATH = "published_history.json"
OUT_IMG = "out.png"

BA_TZ = timezone(timedelta(hours=-3))  # Buenos Aires

TERM_CLEAN_RE = re.compile(r"[^\wáéíóúüñÁÉÍÓÚÜÑ ]+", re.UNICODE)
SPACE_RE = re.compile(r"\s+")
JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def load_state():
    if not Path(STATE_PATH).exists():
        return {
            "word_index": 0,
            "phrase_index": 0,
            "grammar_index": 0,
            "last_daily_check_date": ""
        }
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_history():
    if not Path(HISTORY_PATH).exists():
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[history] load failed: {e!r}")
        return []


def save_history(history):
    history = history[-500:]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def normalize_term(term: str) -> str:
    t = (term or "").strip().lower()
    t = TERM_CLEAN_RE.sub(" ", t)
    t = SPACE_RE.sub(" ", t).strip()

    # убираем частые служебные префиксы/артикли в начале
    for prefix in [
        "el ", "la ", "los ", "las ", "un ", "una ",
        "грамматика: ", "gramática: "
    ]:
        if t.startswith(prefix):
            t = t[len(prefix):].strip()

    return t


def append_history(term: str, kind: str, translation_ru: str):
    history = load_history()
    history.append({
        "term": term,
        "kind": kind,
        "translation_ru": translation_ru,
        "normalized": normalize_term(term),
        "created_at": datetime.now(BA_TZ).isoformat()
    })
    save_history(history)


def get_recent_normalized_terms(limit: int = 250):
    history = load_history()
    out = []
    for row in history[-limit:]:
        n = normalize_term(row.get("term", "") or row.get("normalized", ""))
        if n:
            out.append(n)
    return set(out)


def stable_sort(items):
    return sorted(items, key=lambda x: (x.get("term", "").lower(), x.get("translation", "").lower()))


def dedupe_items(items):
    seen = set()
    result = []
    for item in items:
        norm = normalize_term(item.get("term", ""))
        if not norm:
            continue
        key = (norm, (item.get("kind") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


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
        print(f"[pick_next] No items for {index_key}")
        return None, idx

    if idx >= len(items):
        print(f"[pick_next] Reached end for {index_key}: idx={idx}, len={len(items)} -> fallback")
        return None, idx

    item = items[idx]
    state[index_key] = idx + 1
    print(f"[pick_next] Picked {index_key}: idx={idx} term={item.get('term', '')[:60]!r}")
    return item, idx


def maybe_daily_check(state: dict, now_ba: datetime):
    if now_ba.hour != 9:
        return None

    today = now_ba.strftime("%Y-%m-%d")
    if state.get("last_daily_check_date") == today:
        print("[daily_check] already posted today")
        return None

    state["last_daily_check_date"] = today
    print("[daily_check] generating daily_check")
    return generate_fallback("daily_check")


def extract_json(text: str):
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()

    m = JSON_RE.search(t)
    if not m:
        return None

    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def ai_pick_candidate(preferred_kind: str):
    recent_terms = sorted(list(get_recent_normalized_terms(limit=250)))

    system = """Ты помогаешь выбрать НОВУЮ единицу контента для Telegram-канала
по аргентинскому испанскому (Buenos Aires, es-AR) для новичка.

Верни СТРОГО один JSON без markdown:
{
  "term": "...",
  "kind": "word" | "phrase",
  "translation_ru": "..."
}

Правила:
- Нужны только полезные, живые, естественные слова и фразы для Аргентины.
- Не выбирай слишком абстрактные, книжные, редкие или странные варианты.
- Не повторяй ничего из списка recent_terms.
- Не предлагай очевидные дубли в другой форме.
- Для word лучше одно полезное слово или короткая устойчивая единица.
- Для phrase нужна короткая жизненная фраза.
- Не добавляй объяснений, только JSON.
"""

    payload = {
        "preferred_kind": preferred_kind,
        "recent_terms": recent_terms[-250:],
        "locale": "es-AR",
        "audience": "beginner"
    }

    for attempt in range(1, 6):
        try:
            raw = groq_chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                ],
                temperature=0.9
            )
            data = extract_json(raw)
            print(f"[ai_pick] attempt={attempt} raw_ok={bool(data)}")

            if not isinstance(data, dict):
                continue

            term = (data.get("term") or "").strip()
            kind = (data.get("kind") or "").strip()
            translation_ru = (data.get("translation_ru") or "").strip()

            if kind not in {"word", "phrase"}:
                continue
            if preferred_kind in {"word", "phrase"} and kind != preferred_kind:
                continue
            if not term or not translation_ru:
                continue

            norm = normalize_term(term)
            if not norm or len(norm) < 2:
                continue
            if norm in get_recent_normalized_terms(limit=250):
                print(f"[ai_pick] duplicate rejected: {term!r}")
                continue

            return {
                "term": term,
                "kind": kind,
                "translation_ru": translation_ru
            }

        except Exception as e:
            print(f"[ai_pick] attempt={attempt} failed: {e!r}")

    return None


def pick_unique_from_anki(items, kind: str, state: dict, index_key: str):
    """
    Ищет следующий уникальный элемент из Anki, пропуская уже публиковавшееся недавно.
    При этом двигает индекс вперёд, чтобы бот не застревал на дублях.
    """
    recent = get_recent_normalized_terms(limit=1000)
    idx = int(state.get(index_key, 0))

    if not items:
        return None

    while idx < len(items):
        item = items[idx]
        idx += 1
        state[index_key] = idx

        term = (item.get("term") or "").strip()
        translation = (item.get("translation") or "").strip()
        item_kind = (item.get("kind") or "").strip()
        norm = normalize_term(term)

        if item_kind != kind:
            continue
        if not term or not translation or not norm:
            continue
        if norm in recent:
            print(f"[anki_unique] skip duplicate: {term!r}")
            continue

        print(f"[anki_unique] picked {kind}: idx={idx - 1} term={term!r}")
        return item

    print(f"[anki_unique] exhausted items for {kind}")
    return None


def build_card_from_candidate(candidate: dict):
    return build_post(
        candidate["term"],
        candidate["translation_ru"],
        candidate["kind"],
        ""
    )


def post_card(card: dict):
    caption = format_caption(card)

    term = (card.get("term") or "").strip()
    tr = (card.get("translation_ru") or "").strip()
    pos = (card.get("pos_ru") or "").lower()

    force_local = ("граммат" in pos) or ("суффикс" in pos) or term.startswith("Грамматика:")

    if force_local:
        subtitle = tr[:60] if tr else ""
        make_text_card(term, subtitle, OUT_IMG, size=(1024, 1024))
        send_photo(caption, OUT_IMG)
        return

    ok = False
    try:
        img_prompt = card.get("image_prompt_en") or "simple illustration"
        ok = generate_image(img_prompt, OUT_IMG, 1024, 1024)
        print(f"[image] ok={ok}")
    except Exception as e:
        print(f"[image] exception: {e!r}")
        ok = False

    if ok:
        send_photo(caption, OUT_IMG)
    else:
        subtitle = tr[:60] if tr else ""
        make_text_card(term, subtitle, OUT_IMG, size=(1024, 1024))
        send_photo(caption, OUT_IMG)


def main():
    force = os.getenv("FORCE_POST", "").strip() == "1"

    now_ba = datetime.now(BA_TZ)
    print(f"[time] now BA: {now_ba.isoformat()} force={force}")

    state = load_state()

    # 1) Daily check
    if not force:
        daily = maybe_daily_check(state, now_ba)
        if daily:
            post_card(daily)
            append_history(
                daily.get("term", "Проверка дня"),
                "daily_check",
                daily.get("translation_ru", "")
            )
            save_state(state)
            print("[done] daily_check posted")
            return

    # 2) Load Anki
    all_items = load_anki_export_tsv(DECK_PATH)
    all_items = [x for x in all_items if (x.get("translation") or "").strip()]
    all_items = stable_sort(all_items)
    all_items = dedupe_items(all_items)

    words = [x for x in all_items if x.get("kind") == "word"]
    phrases = [x for x in all_items if x.get("kind") == "phrase"]
    grammar = [x for x in all_items if x.get("kind") == "grammar"]

    print(f"[anki] total={len(all_items)} words={len(words)} phrases={len(phrases)} grammar={len(grammar)}")

    # 3) Decide what to post
    to_post = []
    if force:
        # ручной запуск: публикуем одно новое слово
        to_post = ["word"]
    else:
        if should_post("word", now_ba):
            to_post.append("word")
        if should_post("phrase", now_ba):
            to_post.append("phrase")
        if should_post("grammar", now_ba):
            to_post.append("grammar")

    print(f"[plan] to_post={to_post}")

    if not to_post:
        print("[plan] Nothing scheduled this hour. Exiting.")
        save_state(state)
        return

    # 4) Post each kind
    for kind in to_post:
        if kind in {"word", "phrase"}:
            candidate = ai_pick_candidate(kind)

            if candidate:
                print(f"[source] ai {kind}: {candidate['term']!r}")
                try:
                    card = build_card_from_candidate(candidate)
                    post_card(card)
                    append_history(candidate["term"], candidate["kind"], candidate["translation_ru"])
                    continue
                except Exception as e:
                    print(f"[source] ai build/post failed: {e!r}")

            source_items = words if kind == "word" else phrases
            index_key = "word_index" if kind == "word" else "phrase_index"
            item = pick_unique_from_anki(source_items, kind, state, index_key)

            if item:
                print(f"[source] anki {kind}: {item['term']!r}")
                try:
                    card = build_post(item["term"], item["translation"], item["kind"], item.get("tags", ""))
                    post_card(card)
                    append_history(item["term"], item["kind"], item["translation"])
                    continue
                except Exception as e:
                    print(f"[source] anki build/post failed: {e!r}")

            print(f"[source] fallback {kind}")
            card = generate_fallback(kind)
            post_card(card)
            append_history(
                card.get("term", ""),
                kind,
                card.get("translation_ru", "")
            )

        elif kind == "grammar":
            item, _ = pick_next(grammar, "grammar_index", state)
            if item:
                try:
                    card = build_post(item["term"], item["translation"], item["kind"], item.get("tags", ""))
                except Exception as e:
                    print(f"[grammar] build failed: {e!r}")
                    card = generate_fallback("grammar")
            else:
                card = generate_fallback("grammar")

            post_card(card)
            append_history(
                card.get("term", ""),
                "grammar",
                card.get("translation_ru", "")
            )

    save_state(state)
    print("[done] state saved")


if __name__ == "__main__":
    main()
