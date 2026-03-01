def format_caption(card: dict) -> str:
    term = (card.get("term") or "").strip()
    tr = (card.get("translation_ru") or "").strip()
    note = (card.get("note_ru") or "").strip()

    lines = []
    lines.append(f"🧉 <b>Слово (AR):</b> <b>{term}</b>")
    if tr:
        lines.append(f"Это значит: <b>{tr}</b>")
    lines.append("")  # пустая строка

    ex = card.get("examples") or []
    if ex:
        lines.append("📌 <b>Примеры:</b>")
        for e in ex[:3]:
            es = (e.get("es") or "").strip()
            ru = (e.get("ru") or "").strip()
            if es:
                lines.append(f"• {es}")
            if ru:
                lines.append(f"→ {ru}")
        lines.append("")

    col = card.get("collocations") or []
    if col:
        lines.append("🔹 <b>Ещё варианты:</b>")
        for c in col[:4]:
            es = (c.get("es") or "").strip()
            ru = (c.get("ru") or "").strip()
            if es:
                lines.append(f"• {es}")
            if ru:
                lines.append(f"→ {ru}")
        lines.append("")

    if note:
        lines.append("💬 <b>Заметка:</b>")
        lines.append(note)

    # Telegram HTML: убедимся, что длина не улетает сильно
    text = "\n".join(lines).strip()
    return text[:3900]
