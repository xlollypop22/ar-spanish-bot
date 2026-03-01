import json
from .groq_text import groq_chat

SYSTEM = """Ты создаёшь контент для канала по аргентинскому испанскому (Буэнос-Айрес).
Пиши просто для новичка.

Требования:
- kind может быть: "word" | "phrase" | "grammar" | "daily_check"
- Стиль: живой, BA/AR (vos где уместно). Без сложных терминов.
- Никаких выдуманных "школьных" примеров. Только естественные фразы.

Верни СТРОГО один JSON без markdown.

Схемы:

1) kind="word" или "phrase":
{
  "term": "...",
  "translation_ru": "...",
  "examples": ["...", "...", "..."],
  "collocations": ["...", "..."],
  "note_ru": "...",
  "image_prompt_en": "..."
}

2) kind="grammar":
{
  "term": "Грамматика: ...",
  "translation_ru": "Коротко о правиле на русском",
  "examples": ["...", "...", "..."],
  "collocations": ["...", "..."],
  "note_ru": "1 практический лайфхак",
  "image_prompt_en": "..."
}

3) kind="daily_check":
{
  "term": "Проверка дня",
  "translation_ru": "Мини-квиз на 3 вопроса",
  "examples": ["1) ...", "2) ...", "3) ..."],
  "collocations": ["Ответы завтра", "Сохрани и проверь себя"],
  "note_ru": "Подсказка: ...",
  "image_prompt_en": "..."
}
"""

def generate_fallback(kind: str):
    payload = {"kind": kind}
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]
    out = groq_chat(messages, temperature=0.8)
    # post_builder уже умеет вытаскивать JSON, но тут проще — ожидаем чистый JSON
    return json.loads(out)
