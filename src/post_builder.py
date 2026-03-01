import json
import re
from .groq_text import groq_chat

SYSTEM = """Ты редактор микро-уроков аргентинского испанского (Буэнос-Айрес).
Пиши просто для новичка. Только естественные примеры.
Если term = прилагательное, НЕ делай "¿Tenés X?".
Если term = фраза, делай мини-диалог.

Верни СТРОГО один JSON-объект без текста вокруг, без markdown, без ```.

Схема JSON:
{
  "term": "...",
  "translation_ru": "...",
  "examples": ["...", "...", "..."],
  "collocations": ["...", "..."],
  "note_ru": "...",
  "image_prompt_en": "..."
}
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_json(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    # Если модель всё-таки обернула в ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
    m = JSON_RE.search(text)
    return m.group(0).strip() if m else ""

def build_post(term: str, translation_ru: str, kind: str, tags: str = ""):
    payload = {"term": term, "translation_ru": translation_ru, "kind": kind, "tags": tags}

    # 1-я попытка (обычная)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]
    out1 = groq_chat(messages, temperature=0.6)
    raw1 = (out1 or "").strip()

    j1 = _extract_json(raw1)
    if j1:
        try:
            return json.loads(j1)
        except json.JSONDecodeError:
            pass

    # 2-я попытка (жёсткая: просим исправить и вернуть ТОЛЬКО JSON)
    messages2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        {"role": "assistant", "content": raw1[:4000] if raw1 else ""},
        {"role": "user", "content": "Ты ответил невалидным JSON. Верни ТОЛЬКО один JSON-объект по схеме. Без пояснений, без markdown."}
    ]
    out2 = groq_chat(messages2, temperature=0.2)
    raw2 = (out2 or "").strip()

    j2 = _extract_json(raw2)
    if j2:
        return json.loads(j2)

    # Если всё совсем плохо — падаем с понятной диагностикой
    raise RuntimeError(
        "Groq did not return valid JSON.\n"
        f"RAW1:\n{raw1[:1000]}\n\nRAW2:\n{raw2[:1000]}"
    )
