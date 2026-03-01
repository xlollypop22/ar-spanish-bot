from PIL import Image, ImageDraw, ImageFont

def make_text_card(term: str, subtitle: str, out_path: str, size=(1024, 1024)):
    img = Image.new("RGB", size, (250, 250, 250))
    draw = ImageDraw.Draw(img)

    # системный шрифт: DejaVu обычно есть на runner'е
    try:
        font_title = ImageFont.truetype("DejaVuSans.ttf", 72)
        font_sub = ImageFont.truetype("DejaVuSans.ttf", 42)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # рамка
    pad = 70
    draw.rounded_rectangle(
        [pad, pad, size[0]-pad, size[1]-pad],
        radius=40,
        outline=(30, 30, 30),
        width=6,
        fill=(255, 255, 255)
    )

    # текст
    y = 200
    draw.text((pad+60, y), term, font=font_title, fill=(20, 20, 20))
    y += 120
    draw.text((pad+60, y), subtitle, font=font_sub, fill=(60, 60, 60))

    img.save(out_path, "PNG")
    return True
