#!/usr/bin/env python3
"""
Kisan Awaaz — dialect agronomy hotline (MVP)

Pipeline:
  1. STT  — Saaras v4 transcribes farmer's speech (code-mixed Hindi / dialect)
  2. LLM  — sarvam-105b reasons over the transcript (+ optional image description)
  3. TTS  — Bulbul v3 speaks the advice back in Hindi

Usage:
  # Generate a synthetic test clip, then run the full loop on it:
  python kisan.py --generate-test

  # Run on your own audio (WAV/MP3, ≤30s):
  python kisan.py farmer_query.wav

  # Run on audio + leaf photo:
  python kisan.py farmer_query.wav --photo leaf.jpg
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

# ── Load .env before anything else ──────────────────────────────────────────
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

from sarvamai import SarvamAI  # noqa: E402

client = SarvamAI(api_subscription_key=api_key)

AGRI_SYSTEM_PROMPT = """\
You are Kisan Awaaz, an agricultural advisory assistant for Indian farmers.
You receive the farmer's spoken query (transcribed from speech, possibly code-mixed
Hindi/regional dialect) and optionally a description of a crop/leaf photo.

Respond in HINDI (Devanagari), structured exactly as:

**समस्या:** <one-line diagnosis>
**कारण:** <likely cause — pest, disease, deficiency, weather>
**उपाय:** <concrete action — product name, dose, method, timing>
**सावधानी:** <safety / environmental warning>
**डॉक्टर से पूछें:** <yes/no — recommend visiting a KVK or agronomist?>

Keep it under 200 words. Use simple Hindi a farmer would understand.
Do NOT add disclaimers about being an AI. Just give the advice.
"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def generate_test_clip(out_path: Path) -> Path:
    """Use Bulbul to synthesise a fake farmer query in Hindi."""
    test_text = (
        "भैया, मेरे धान के पत्ते पीले हो रहे हैं और किनारे से सूख रहे हैं। "
        "पिछले हफ्ते बारिश बहुत हुई थी। क्या करूँ?"
    )
    print(f"🔊 Generating test clip with Bulbul …")
    tts = client.text_to_speech.convert(
        text=test_text,
        language_code="hi-IN",
        model="bulbul:v3",
    )
    audio_bytes = base64.b64decode(tts.audios[0])
    out_path.write_bytes(audio_bytes)
    print(f"   ✅ Saved {out_path} ({len(audio_bytes):,} bytes)")
    return out_path


def transcribe(audio_path: Path) -> str:
    """STT: Saaras v4, auto-detect language, transcribe mode."""
    print(f"🎤 Transcribing {audio_path.name} with Saaras v4 …")
    with open(audio_path, "rb") as f:
        resp = client.speech_to_text.transcribe(
            file=f,
            model="saaras:v4",
            mode="transcribe",
            language_code="unknown",
        )
    lang = resp.language_code or "?"
    prob = f" ({resp.language_probability:.0%})" if resp.language_probability else ""
    print(f"   🗣️  Detected language: {lang}{prob}")
    print(f"   📝 Transcript: {resp.transcript}")
    return resp.transcript


def analyse_photo(photo_path: Path) -> str:
    """Use glm5.3-flash via responses API to describe a crop/leaf photo."""
    print(f"📷 Analysing {photo_path.name} with glm5.3-flash …")
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = "image/jpeg" if photo_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    data_url = f"data:{mime};base64,{b64}"
    resp = client.responses.create(
        model="glm5.3-flash",
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "Describe this crop/leaf photo for an agronomist. "
                        "Note the colour, spots, wilting, pest marks, and any visible disease symptoms. "
                        "Be specific and concise (3-4 sentences). Respond in English."
                    ),
                },
                {
                    "type": "input_image",
                    "image_url": data_url,
                },
            ],
        }],
    )
    extracted = []
    if hasattr(resp, "output") and resp.output:
        for item in resp.output:
            if getattr(item, "type", None) == "message" and hasattr(item, "content"):
                for part in item.content:
                    if hasattr(part, "text") and part.text:
                        extracted.append(part.text)
    desc = " ".join(extracted)
    print(f"   🌿 Photo description: {desc}")
    return desc


def get_advice(transcript: str, photo_desc: str | None = None) -> str:
    """LLM: sarvam-105b reasons over the transcript (+ optional photo)."""
    user_msg = f"किसान ने कहा:\n\"{transcript}\""
    if photo_desc:
        user_msg += f"\n\nफसल/पत्ती की फोटो का विवरण:\n\"{photo_desc}\""

    print(f"🧠 Getting advice from sarvam-105b-conversations …")
    resp = client.chat.completions(
        model="sarvam-105b-conversations",
        messages=[
            {"role": "system", "content": AGRI_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
    )
    msg = resp.choices[0].message
    advice = msg.content
    # sarvam-105b may put its answer in reasoning_content instead
    if not advice and hasattr(msg, "reasoning_content") and msg.reasoning_content:
        advice = msg.reasoning_content
    if not advice:
        raise RuntimeError(
            f"LLM returned empty content. finish_reason={resp.choices[0].finish_reason}, "
            f"message fields: {[k for k, v in msg.__dict__.items() if v]}"
        )
    print(f"   💡 Advice:\n{advice}")
    return advice


def speak_advice(advice: str, out_path: Path) -> Path:
    """TTS: Bulbul v3 reads the advice in Hindi."""
    if not advice:
        raise RuntimeError("No advice text to speak.")
    # Strip markdown bold markers for cleaner speech
    clean = advice.replace("**", "")
    # Bulbul max 2500 chars — truncate if needed
    if len(clean) > 2400:
        clean = clean[:2400] + " … बाकी सलाह के लिए कृपया KVK से संपर्क करें।"

    print(f"🔊 Converting advice to speech with Bulbul v3 …")
    tts = client.text_to_speech.convert(
        text=clean,
        language_code="hi-IN",
        model="bulbul:v3",
    )
    audio_bytes = base64.b64decode(tts.audios[0])
    out_path.write_bytes(audio_bytes)
    print(f"   ✅ Saved {out_path} ({len(audio_bytes):,} bytes)")
    return out_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kisan Awaaz — voice agronomy hotline")
    parser.add_argument("audio", nargs="?", help="Path to farmer's audio file (WAV/MP3, ≤30s)")
    parser.add_argument("--photo", help="Path to crop/leaf photo (JPG/PNG)")
    parser.add_argument("--generate-test", action="store_true",
                        help="Generate a synthetic Hindi test clip, then run the full loop")
    args = parser.parse_args()

    project_dir = Path(__file__).parent

    # Step 0: get audio
    if args.generate_test:
        audio_path = generate_test_clip(project_dir / "test_farmer_query.wav")
    elif args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            raise SystemExit(f"Audio file not found: {audio_path}")
    else:
        parser.print_help()
        raise SystemExit("\nProvide an audio file or use --generate-test")

    print("\n" + "=" * 60)
    print("🌾  KISAN AWAAZ — Dialect Agronomy Hotline")
    print("=" * 60 + "\n")

    # Step 1: STT
    transcript = transcribe(audio_path)

    # Step 2: Photo analysis (optional)
    photo_desc = None
    if args.photo:
        photo_path = Path(args.photo)
        if not photo_path.exists():
            print(f"⚠️  Photo not found: {photo_path}, skipping.")
        else:
            photo_desc = analyse_photo(photo_path)

    print()

    # Step 3: LLM reasoning
    advice = get_advice(transcript, photo_desc)

    print()

    # Step 4: TTS
    advice_wav = speak_advice(advice, project_dir / "advice.wav")

    print("\n" + "=" * 60)
    print("✅ Done!")
    print(f"   📝 Transcript:  (above)")
    print(f"   💡 Advice:      (above)")
    print(f"   🔊 Audio reply: {advice_wav}")
    print("=" * 60)


if __name__ == "__main__":
    main()
