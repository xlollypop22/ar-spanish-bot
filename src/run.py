import random
from src.anki_loader_anki_export import load_anki_export_tsv
from src.post_builder import build_post
from src.image_pollinations import generate_image
from src.post_to_tg import send_photo, format_caption

DECK_PATH = "anki/anki_export.txt"
OUT_IMG = "out.png"

def pick_item(items):
    # пока просто случайно, но только с переводом
    candidates = [x for x in items if (x.get("translation") or "").strip()]
    if not candidates:
        raise SystemExit("Нет карточек с переводом")
    return random.choice(candidates)

def main():
    items = load_anki_export_tsv(DECK_PATH)
    item = pick_item(items)
    card = build_post(item["term"], item["translation"], item["kind"], item.get("tags",""))
    generate_image(card["image_prompt_en"], OUT_IMG, 1024, 1024)
    caption = format_caption(card)
    send_photo(caption, OUT_IMG)

if __name__ == "__main__":
    main()
