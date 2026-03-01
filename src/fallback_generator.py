import json
import re
from .groq_text import groq_chat

SYSTEM = """Ты создаёшь контент для канала по аргентинскому испанскому (Buenos Aires).
Пиши просто для новичка.

Верни СТРОГО один JSON без markdown.

Схема JSON (для ЛЮБОГО kind):
{
  "term": "...",
  "translation_ru": "...",
  "examples": [{"es":"...","ru":"..."}, {"es":"...","ru":"..."}, {"es":"...","ru":"..."}],
  "collocations": [{"es":"...","ru":"..."}, {"es":"...","ru":"..."}],
  "note_ru": "...",
  "image_prompt_en": "..."
}

kind:
- word: одно слово (AR)
- phrase: фраза для жизни
- grammar: тема грамматики (term начинай с "Грамматика: ...")
- daily_check: "Проверка дня" + 3 задания (в examples), ответы НЕ давай, только подсказку в note_ru
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_json(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    m = JSON_RE.search(t)
    return m.group(0).strip() if m else ""

def generate_fallback(kind: str):
    payload = {"kind": kind}
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]
    out1 = groq_chat(messages, temperature=0.8)
    raw1 = (out1 or "").strip()
    j1 = _extract_json(raw1)

    if j1:
        return json.loads(j1)

    # retry
    messages2 = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        {"role": "assistant", "content": raw1[:4000]},
        {"role": "user", "content": "Нужно вернуть ТОЛЬКО JSON по схеме. Без текста."}
    ]
    out2 = groq_chat(messages2, temperature=0.2)
    raw2 = (out2 or "").strip()
    j2 = _extract_json(raw2)
    if j2:
        return json.loads(j2)

    raise RuntimeError(f"Fallback Groq JSON failed.\nRAW1:\n{raw1[:1200]}\n\nRAW2:\n{raw2[:1200]}")
