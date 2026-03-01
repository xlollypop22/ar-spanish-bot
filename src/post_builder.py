import json
import re
from .groq_text import groq_chat

SYSTEM = """Ты редактор микро-уроков аргентинского испанского (Buenos Aires).
Пиши просто для новичка. Примеры — естественные, бытовые, без странных конструкций.

Важно:
- Давай перевод на русский ДЛЯ КАЖДОГО примера и ДЛЯ КАЖДОЙ коллокации.
- Не задавай "¿Tenés X?" для прилагательных.
- Если term — существительное: примеры с артиклем и естественными ситуациями.
- Если term — фраза: сделай мини-диалог 2 реплики (но всё равно 3 примера).
- Не выдумывай "школьные" фразы.

Верни СТРОГО один JSON-объект без текста вокруг, без markdown, без ```.

Схема JSON:
{
  "term": "tomacorriente",
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
  "note_ru": "Короткая полезная заметка (1–2 предложения) + при необходимости разговорный вариант в AR.",
  "image_prompt_en": "A simple friendly illustration that clearly shows the meaning, no text"
}
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    if not text:
        return ""
    t = text.strip()

    # иногда модель оборачивает в ```json ... ```
    if t.startswith("```"):
        t = t.strip("`").strip()
        # убрать возможное "json" в первой строке
        if t.lower().startswith("json"):
            t = t[4:].strip()

    m = JSON_RE.search(t)
    return m.group(0).strip() if m else ""


def _normalize(card: dict) -> dict:
    """Подстраховка: приводим к ожидаемой структуре, чтобы форматтер не падал."""
    card = card or {}
    card.setdefault("term", "")
    card.setdefault("translation_ru", "")
    card.setdefault("note_ru", "")
    card.setdefault("image_prompt_en", "A simple illustration, no text")

    ex = card.get("examples") or []
    # допускаем, если модель вернула список строк — конвертируем
    fixed_ex = []
    for e in ex:
        if isinstance(e, dict):
            fixed_ex.append({"es": (e.get("es") or "").strip(), "ru": (e.get("ru") or "").strip()})
        elif isinstance(e, str):
            fixed_ex.append({"es": e.strip(), "ru": ""})
    card["examples"] = fixed_ex[:3]

    col = card.get("collocations") or []
    fixed_col = []
    for c in col:
        if isinstance(c, dict):
            fixed_col.append({"es": (c.get("es") or "").strip(), "ru": (c.get("ru") or "").strip()})
        elif isinstance(c, str):
            fixed_col.append({"es": c.strip(), "ru": ""})
    card["collocations"] = fixed_col[:4]

    return card


def build_post(term: str, translation_ru: str, kind: str, tags: str = ""):
    payload = {"term": term, "translation_ru": translation_ru, "kind": kind, "tags": tags}

    # 1) первая попытка
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]
    out1 = groq_chat(messages, temperature=0.6)
    raw1 = (out1 or "").strip()

    j1 = _extract_json(raw1)
    if j1:
        try:
            return _normalize(json.loads(j1))
        except json.JSONDecodeError:
            pass

    # 2) вторая попытка — жёсткая починка
    messages2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        {"role": "assistant", "content": raw1[:4000] if raw1 else ""},
        {"role": "user", "content": "Ты ответил невалидным JSON или не по схеме. Верни ТОЛЬКО один JSON по схеме. Без пояснений, без markdown."}
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
