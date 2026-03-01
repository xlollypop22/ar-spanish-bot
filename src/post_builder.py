import json
from .groq_text import groq_chat

SYSTEM = """Ты редактор микро-уроков аргентинского испанского (Буэнос-Айрес).
Пиши просто для новичка. Только естественные примеры.
Если term = прилагательное, НЕ делай "¿Tenés X?".
Если term = фраза, делай мини-диалог.
Верни СТРОГО JSON:
term, translation_ru, examples(3), collocations(2), note_ru, image_prompt_en.
"""

def build_post(term: str, translation_ru: str, kind: str, tags: str = ""):
    payload = {"term": term, "translation_ru": translation_ru, "kind": kind, "tags": tags}
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]
    out = groq_chat(messages)
    return json.loads(out)
