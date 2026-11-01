import os
from pathlib import Path

from sarvamai import SarvamAI

# Load .env if present, without an extra dependency.
env_file = Path(__file__).with_name(".env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    raise SystemExit("SARVAM_API_KEY is not set. Add it to .env or export it.")

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    messages=[{"role": "user", "content": "Say hello and introduce yourself in one sentence."}],
    model="sarvam-105b-conversations",
)

print(response.choices[0].message.content)
