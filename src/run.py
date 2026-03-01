import random

from src.anki_loader_anki_export import load_anki_export_tsv
from src.post_builder import build_post
from src.image_pollinations import generate_image
from src.post_to_tg import send_photo, send_message, format_caption

DECK_PATH = "anki/anki_export.txt"
OUT_IMG = "out.png"


def pick_item(items):
    # Берём только те карточки, где есть перевод
    candidates = [x for x in items if (x.get("translation") or "").strip()]
    if not candidates:
        raise SystemExit("Нет карточек с переводом в anki_export.txt")
    return random.choice(candidates)


def main():
    items = load_anki_export_tsv(DECK_PATH)
    item = pick_item(items)

    card = build_post(
        item["term"],
        item["translation"],
        item["kind"],
        item.get("tags", "")
    )

    caption = format_caption(card)

    # Пытаемся сгенерить картинку. Если сервис упал — постим без картинки.
    ok = generate_image(card["image_prompt_en"], OUT_IMG, 1024, 1024)
    if ok:
        send_photo(caption, OUT_IMG)
    else:
        send_message(caption)


if __name__ == "__main__":
    main()
