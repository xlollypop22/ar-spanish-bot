import requests, urllib.parse

def generate_image(prompt: str, out_path: str, width=1024, height=1024):
    base = "https://image.pollinations.ai/prompt/"
    q = urllib.parse.quote(prompt)
    url = f"{base}{q}?width={width}&height={height}&nologo=true"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
