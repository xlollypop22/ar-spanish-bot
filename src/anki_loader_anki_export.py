import re
import html

TAG_RE = re.compile(r"<[^>]+>")

def clean_html(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = TAG_RE.sub("", s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def guess_kind(term: str) -> str:
    t = term.lower().strip()
    if " + " in t and ("inf" in t or "infinitivo" in t):
        return "grammar"
    if t.startswith(("hay que", "deber", "es necesario", "tener que", "poder", "estar +", "ser vs", "ir + a")):
        return "grammar"
    if any(ch in term for ch in ["¿", "?", "¡", "!", "…"]) or " " in term:
        return "phrase"
    return "word"

def load_anki_export_tsv(path: str):
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            front = clean_html(parts[0]) if len(parts) > 0 else ""
            back  = clean_html(parts[1]) if len(parts) > 1 else ""
            tags  = clean_html(parts[2]) if len(parts) > 2 else ""
            if not front:
                continue
            kind = guess_kind(front)
            items.append({"term": front, "translation": back, "kind": kind, "tags": tags})
    return items
