import os, requests, json

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

def groq_chat(messages, model="llama-3.3-70b-versatile", temperature=0.6):
    url = f"{GROQ_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
