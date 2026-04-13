import json
import re
from pathlib import Path
from typing import Iterable

from .groq_text import groq_chat

HISTORY_PATH = "published_history.json"

TERM_RE = re.compile(r"[^\wáéíóúüñÁÉÍÓÚÜÑ ]+", re.UNICODE)

SYSTEM = """Ты помогаешь выбрать НОВОЕ слово или фразу для Telegram-канала
по аргентинскому испанскому (es-AR, Buenos Aires).

Верни строго JSON без markdown:
{
  "term": "...",
  "kind": "word" | "phrase",
  "translation_ru": "..."
}

Правила:
- Выбирай только реально полезные для жизни в Аргентине слова/фразы.
- Не выбирай слишком абстрактные, книжные или редкие слова.
- Не выбирай ничего из списка recent_terms.
- Не повторяй одно и то же слово в другой форме.
- Для kind=word это должно быть одно слово или короткая устойчивая единица.
- Для kind=phrase — короткая жизненная фраза.
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def normalize_term(term: str) -> str:
    t = (term or "").strip().lower()
    t = TERM_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_history() -> list[dict]:
    p = Path(HISTORY_PATH)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_history(items: list[dict]) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(items[-500:], f, ensure_ascii=False, indent=2)


def recent_terms(history: list[dict], limit: int = 200) -> set[str]:
    out = []
    for row in history[-limit:]:
        n = normalize_term(row.get("term", ""))
        if n:
            out.append(n)
    return set(out)


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    m = JSON_RE.search(text.strip())
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def is_valid_candidate(candidate: dict, recent: set[str]) -> bool:
    if not isinstance(candidate, dict):
        return False

    term = normalize_term(candidate.get("term", ""))
    kind = (candidate.get("kind") or "").strip()
    tr = (candidate.get("translation_ru") or "").strip()

    if not term or not tr:
        return False
    if kind not in {"word", "phrase"}:
        return False
    if term in recent:
        return False
    if len(term) < 2:
        return False

    return True


def pick_ai_term(preferred_kind: str = "word") -> dict:
    history = load_history()
    recent = recent_terms(history)

    payload = {
        "preferred_kind": preferred_kind,
        "recent_terms": sorted(list(recent))[-200:],
        "audience": "beginner",
        "locale": "es-AR",
    }

    for _ in range(5):
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        raw = groq_chat(messages, temperature=0.9)
        candidate = extract_json(raw)

        if is_valid_candidate(candidate, recent):
            return candidate

    raise RuntimeError("AI could not produce a new unique term")
    

def append_history(term: str, kind: str, translation_ru: str) -> None:
    history = load_history()
    history.append({
        "term": term,
        "kind": kind,
        "translation_ru": translation_ru
    })
    save_history(history)


def pick_from_anki_fallback(items: Iterable[dict]) -> dict | None:
    history = load_history()
    recent = recent_terms(history, limit=1000)

    for item in items:
        term = normalize_term(item.get("term", ""))
        tr = (item.get("translation") or "").strip()
        kind = (item.get("kind") or "").strip()

        if term and tr and kind in {"word", "phrase"} and term not in recent:
            return {
                "term": item["term"],
                "kind": kind,
                "translation_ru": tr
            }
    return None
