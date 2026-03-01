import time
import requests
import urllib.parse

def generate_image(prompt: str, out_path: str, width=1024, height=1024, retries=5):
    base = "https://image.pollinations.ai/prompt/"
    q = urllib.parse.quote(prompt)

    # пробуем сначала большой, потом меньше
    sizes = [(width, height), (768, 768), (640, 640)]

    last_err = None
    for w, h in sizes:
        url = f"{base}{q}?width={w}&height={h}&nologo=true"
        for attempt in range(1, retries + 1):
            try:
                r = requests.get(url, timeout=180, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and r.content and len(r.content) > 10_000:
                    with open(out_path, "wb") as f:
                        f.write(r.content)
                    return True
                last_err = f"HTTP {r.status_code} len={len(r.content) if r.content else 0}"
            except Exception as e:
                last_err = repr(e)

            time.sleep(min(20, 2 * attempt))  # 2s,4s,6s... до 20
    return False
