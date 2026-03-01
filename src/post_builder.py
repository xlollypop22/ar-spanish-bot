import json
import re
from .groq_text import groq_chat

# --- Prompting / schema -------------------------------------------------------

SYSTEM = """Ты редактор микро-уроков аргентинского испанского (Buenos Aires).
Пиши просто для новичка. Примеры — естественные, бытовые, без странных конструкций.

Главные правила:
- Всегда давай перевод на русский ДЛЯ КАЖДОГО примера и ДЛЯ КАЖДОЙ коллокации.
- Не делай шаблоны типа "¿Tenés X?" для прилагательных.
- Не делай бессмысленные фразы вида "Necesito copado/a".
- Если term — существительное: используй артикль (el/la/un/una) в примерах, если это естественно.
- Если term — фраза: сделай жизненные реплики (можно мини-диалог), но всё равно 3 примера.
- Если term — грамматика/суффикс: примеры должны показывать правило; note_ru — коротко и практично.

Верни СТРОГО один JSON-объект без текста вокруг, без markdown, без ```.

Схема JSON:
{
  "term": "tomacorriente",
  "pos_ru": "сущ., м.р." | "гл." | "прил." | "нареч." | "фраза" | "грамматика" | "суффикс",
  "translation_ru": "розетка",
  "examples": [
    {"es": "Necesito un tomacorriente para mi laptop.", "ru": "Мне нужна розетка для ноутбука."},
    {"es": "El tomacorriente está suelto.", "ru": "Розетка болтается."},
    {"es": "No tengo un tomacorriente libre.", "ru": "У меня нет свободной розетки."}
  ],
  "collocations": [
    {"es": "tomacorriente de pared", "ru": "настенная розетка"},
    {"es": "tomacorriente múltiple", "ru": "удлинитель / сетевой фильтр"}
  ],
  "note_ru": "Короткая полезная заметка (1–2 предложения). Если есть — добавь разговорный вариант в AR.",
  "image_prompt_en": "A simple friendly illustration that clearly shows the meaning, no text"
}

Важно: JSON должен быть валидный. Внутри строк не используй необработанные переносы строк.
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    """Tries to extract a single JSON object from model output."""
    if not text:
        return ""
    t = text.strip()

    # Sometimes wrapped in ```json ... ```
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()

    m = JSON_RE.search(t)
    return m.group(0).strip() if m else ""


def _normalize(card: dict) -> dict:
    """Defensive normalization so formatter doesn't break."""
    card = card or {}
    card.setdefault("term", "")
    card.setdefault("pos_ru", "")
    card.setdefault("translation_ru", "")
    card.setdefault("note_ru", "")
    card.setdefault("image_prompt_en", "A simple friendly illustration, no text")

    # examples: [{es,ru}, ...]
    ex = card.get("examples") or []
    fixed_ex = []
    for e in ex:
        if isinstance(e, dict):
            fixed_ex.append(
                {"es": (e.get("es") or "").strip(), "ru": (e.get("ru") or "").strip()}
            )
        elif isinstance(e, str):
            fixed_ex.append({"es": e.strip(), "ru": ""})
    card["examples"] = [x for x in fixed_ex if x.get("es")] [:3]

    # collocations: [{es,ru}, ...]
    col = card.get("collocations") or []
    fixed_col = []
    for c in col:
        if isinstance(c, dict):
            fixed_col.append(
                {"es": (c.get("es") or "").strip(), "ru": (c.get("ru") or "").strip()}
            )
        elif isinstance(c, str):
            fixed_col.append({"es": c.strip(), "ru": ""})
    card["collocations"] = [x for x in fixed_col if x.get("es")] [:4]

    # Hard trim to avoid Telegram caption issues
    card["term"] = card["term"][:120]
    card["pos_ru"] = card["pos_ru"][:40]
    card["translation_ru"] = card["translation_ru"][:200]
    card["note_ru"] = card["note_ru"][:600]
    card["image_prompt_en"] = card["image_prompt_en"][:400]

    return card


# --- Public API ---------------------------------------------------------------

def build_post(term: str, translation_ru: str, kind: str, tags: str = "") -> dict:
    """
    Build a rich post card using Groq:
    - bilingual examples and collocations
    - pos_ru (part of speech / type)
    - safe JSON extraction + retry
    """
    payload = {
        "term": term,
        "translation_ru": translation_ru,
        "kind": kind,
        "tags": tags,
        "locale": "es-AR",
        "audience": "beginner",
    }

    # Attempt 1
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    out1 = groq_chat(messages, temperature=0.6)
    raw1 = (out1 or "").strip()

    j1 = _extract_json(raw1)
    if j1:
        try:
            return _normalize(json.loads(j1))
        except json.JSONDecodeError:
            pass

    # Attempt 2: strict repair
    messages2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        {"role": "assistant", "content": raw1[:4000] if raw1 else ""},
        {
            "role": "user",
            "content": "Твой ответ невалидный JSON или не по схеме. Верни ТОЛЬКО один JSON строго по схеме. Без пояснений, без markdown.",
        },
    ]
    out2 = groq_chat(messages2, temperature=0.2)
    raw2 = (out2 or "").strip()

    j2 = _extract_json(raw2)
    if j2:
        return _normalize(json.loads(j2))

    raise RuntimeError(
        "Groq did not return valid JSON.\n"
        f"RAW1:\n{raw1[:1200]}\n\nRAW2:\n{raw2[:1200]}"
    )
