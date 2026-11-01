"""
Kisan Awaaz — Web Application
FastAPI backend for the voice-first agronomy hotline.

Run:  .venv/bin/uvicorn app:app --reload --port 8000
"""
import base64
import json
import os
import time
import traceback
from datetime import datetime
from io import BytesIO
from pathlib import Path

# ── Load .env ────────────────────────────────────────────────────────────────
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

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from sarvamai import SarvamAI

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Kisan Awaaz", version="1.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

client = SarvamAI(api_subscription_key=api_key)

# ── Constants ────────────────────────────────────────────────────────────────

AGRI_SYSTEM_PROMPT = """\
You are Kisan Awaaz, an agricultural advisory assistant for Indian farmers.
You receive the farmer's spoken query (transcribed from speech, possibly code-mixed
Hindi/regional dialect) and optionally:
- A description of a crop/leaf photo
- Structured data extracted from a soil health card

Respond in HINDI (Devanagari), structured exactly as:

**समस्या:** <one-line diagnosis>
**कारण:** <likely cause — pest, disease, deficiency, weather>
**उपाय:** <concrete action — product name, dose, method, timing>
**सावधानी:** <safety / environmental warning>
**डॉक्टर से पूछें:** <yes/no — recommend visiting a KVK or agronomist?>

Keep it under 250 words. Use simple Hindi a farmer would understand.
Do NOT add disclaimers about being an AI. Just give the advice.
If soil health card data is available, incorporate soil nutrient levels into your recommendation.
"""

SOIL_HEALTH_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "farmer_name": {"type": "string", "description": "Name of the farmer"},
        "village": {"type": "string", "description": "Village or location name"},
        "sample_date": {"type": "string", "description": "Date the soil sample was collected"},
        "pH": {"type": "number", "description": "Soil pH value"},
        "organic_carbon_percent": {"type": "number", "description": "Organic carbon percentage"},
        "nitrogen_kg_per_ha": {"type": "number", "description": "Available nitrogen in kg/ha"},
        "phosphorus_kg_per_ha": {"type": "number", "description": "Available phosphorus in kg/ha"},
        "potassium_kg_per_ha": {"type": "number", "description": "Available potassium in kg/ha"},
        "sulphur_ppm": {"type": "number", "description": "Available sulphur in ppm"},
        "zinc_ppm": {"type": "number", "description": "Available zinc in ppm"},
        "iron_ppm": {"type": "number", "description": "Available iron in ppm"},
        "recommendations": {"type": "string", "description": "Any fertiliser or crop recommendations printed on the card"}
    }
})


# ── Helper functions ─────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, filename: str) -> dict:
    """STT: Saaras v4 transcribes farmer's speech."""
    resp = client.speech_to_text.transcribe(
        file=(filename, BytesIO(audio_bytes)),
        model="saaras:v4",
        mode="transcribe",
        language_code="unknown",
    )
    return {
        "transcript": resp.transcript,
        "language": resp.language_code or "unknown",
        "confidence": resp.language_probability,
    }


def analyse_photo(photo_bytes: bytes, mime_type: str) -> str:
    """Use glm5.3-flash via responses API to describe a crop/leaf photo."""
    b64 = base64.b64encode(photo_bytes).decode()
    data_url = f"data:{mime_type};base64,{b64}"
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
    return " ".join(extracted)


def extract_soil_health_card(doc_bytes: bytes, filename: str) -> dict:
    """Use Sarvam Vision (doc_ai) to extract structured data from a soil health card."""
    # Submit extraction job
    job = client.doc_ai.extract(
        file=[(filename, BytesIO(doc_bytes))],
        schema=SOIL_HEALTH_SCHEMA,
        output_format="json",
    )
    job_id = job.job_id

    # Poll until complete (max 60s)
    for _ in range(30):
        status = client.doc_ai.get_status(job_id)
        if status.status in ("completed", "partially_completed"):
            results = client.doc_ai.get_results(job_id, format="json")
            # results may have a 'result' field with the extracted data
            result_data = {}
            if hasattr(results, "result") and results.result:
                result_data = results.result if isinstance(results.result, dict) else {}
            elif hasattr(results, "__dict__"):
                result_data = {k: v for k, v in results.__dict__.items()
                               if v and k not in ("job_id", "type", "status", "usage", "version")}
            return {"status": "ok", "data": result_data, "job_id": job_id}
        elif status.status in ("failed", "rejected"):
            return {"status": "failed", "error": f"Job {status.status}", "job_id": job_id}
        time.sleep(2)

    return {"status": "timeout", "error": "Extraction timed out after 60s", "job_id": job_id}


def get_advice(transcript: str, photo_desc: str | None = None,
               soil_data: dict | None = None) -> str:
    """LLM: sarvam-105b-conversations reasons over the inputs."""
    user_msg = f'किसान ने कहा:\n"{transcript}"'
    if photo_desc:
        user_msg += f'\n\nफसल/पत्ती की फोटो का विवरण:\n"{photo_desc}"'
    if soil_data:
        user_msg += f"\n\nमिट्टी स्वास्थ्य कार्ड से निकाला गया डेटा:\n{json.dumps(soil_data, ensure_ascii=False, indent=2)}"

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
    if not advice and hasattr(msg, "reasoning_content") and msg.reasoning_content:
        advice = msg.reasoning_content
    return advice or "सलाह उपलब्ध नहीं है। कृपया पुनः प्रयास करें।"


def text_to_speech(text: str, lang: str = "hi-IN") -> str:
    """TTS: Bulbul v3 speaks the advice. Returns base64 WAV."""
    clean = text.replace("**", "")
    if len(clean) > 2400:
        clean = clean[:2400] + " … बाकी सलाह के लिए कृपया KVK से संपर्क करें।"
    tts = client.text_to_speech.convert(
        text=clean,
        language_code=lang,
        model="bulbul:v3",
    )
    return tts.audios[0]  # already base64


def generate_report(transcript: str, advice: str,
                    photo_desc: str | None = None,
                    soil_data: dict | None = None) -> str:
    """Generate an HTML report."""
    now = datetime.now().strftime("%d %B %Y, %I:%M %p")
    sections = []
    sections.append(f"""
    <div class="report-section">
        <h3>🗣️ किसान की बात (Farmer's Query)</h3>
        <p class="transcript">{transcript}</p>
    </div>""")

    if photo_desc:
        sections.append(f"""
    <div class="report-section">
        <h3>📷 फसल/पत्ती फोटो विश्लेषण (Photo Analysis)</h3>
        <p>{photo_desc}</p>
    </div>""")

    if soil_data:
        rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in soil_data.items() if v
        )
        sections.append(f"""
    <div class="report-section">
        <h3>🧪 मिट्टी स्वास्थ्य कार्ड (Soil Health Card)</h3>
        <table class="soil-table"><thead><tr><th>Parameter</th><th>Value</th></tr></thead>
        <tbody>{rows}</tbody></table>
    </div>""")

    # Format advice with line breaks
    advice_html = advice.replace("\n", "<br>")
    sections.append(f"""
    <div class="report-section advice">
        <h3>💡 सलाह (Advisory)</h3>
        <div>{advice_html}</div>
    </div>""")

    report = f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<title>Kisan Awaaz — Advisory Report</title>
<style>
body {{ font-family: 'Segoe UI', Tahoma, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #1a1a1a; }}
h1 {{ color: #2d6a4f; border-bottom: 3px solid #95d5b2; padding-bottom: 10px; }}
h3 {{ color: #40916c; margin-top: 24px; }}
.meta {{ color: #666; font-size: 0.9em; margin-bottom: 24px; }}
.report-section {{ background: #f8f9fa; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }}
.report-section.advice {{ background: #d8f3dc; border-left: 4px solid #2d6a4f; }}
.transcript {{ font-style: italic; font-size: 1.1em; }}
.soil-table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
.soil-table th, .soil-table td {{ padding: 8px 12px; border: 1px solid #dee2e6; text-align: left; }}
.soil-table th {{ background: #e9ecef; }}
.footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #dee2e6; color: #888; font-size: 0.85em; text-align: center; }}
@media print {{ body {{ margin: 0; }} }}
</style>
</head>
<body>
<h1>🌾 Kisan Awaaz — Advisory Report</h1>
<p class="meta">Generated on {now}</p>
{"".join(sections)}
<div class="footer">
    <p>Kisan Awaaz — Powered by Sarvam AI | यह AI-जनित सलाह है। गंभीर मामलों में KVK/कृषि विशेषज्ञ से परामर्श करें।</p>
</div>
</body>
</html>"""
    return report


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/query")
async def query(
    audio: UploadFile | None = File(None),
    text_query: str | None = Form(None),
    photo: UploadFile | None = File(None),
    document: UploadFile | None = File(None),
    generate_report_flag: str | None = Form(None),
):
    """Main pipeline: accepts audio/text + optional photo + optional soil doc."""
    try:
        result = {
            "transcript": None,
            "language": None,
            "photo_analysis": None,
            "soil_data": None,
            "advice": None,
            "advice_audio_b64": None,
            "report_html": None,
        }

        # Step 1: Get the farmer's query
        if audio and audio.filename:
            audio_bytes = await audio.read()
            if len(audio_bytes) > 0:
                stt = transcribe_audio(audio_bytes, audio.filename)
                result["transcript"] = stt["transcript"]
                result["language"] = stt["language"]
        if text_query and text_query.strip():
            # Text query overrides or supplements audio
            if result["transcript"]:
                result["transcript"] += " " + text_query.strip()
            else:
                result["transcript"] = text_query.strip()

        if not result["transcript"]:
            return JSONResponse({"error": "No audio or text query provided."}, status_code=400)

        # Step 2: Analyse photo (optional)
        photo_desc = None
        if photo and photo.filename:
            photo_bytes = await photo.read()
            if len(photo_bytes) > 0:
                mime = photo.content_type or "image/jpeg"
                photo_desc = analyse_photo(photo_bytes, mime)
                result["photo_analysis"] = photo_desc

        # Step 3: Extract soil health card (optional)
        soil_data = None
        if document and document.filename:
            doc_bytes = await document.read()
            if len(doc_bytes) > 0:
                extraction = extract_soil_health_card(doc_bytes, document.filename)
                if extraction["status"] == "ok":
                    soil_data = extraction["data"]
                    result["soil_data"] = soil_data
                else:
                    result["soil_data"] = {"error": extraction.get("error", "Extraction failed")}

        # Step 4: Get advice from LLM
        advice = get_advice(result["transcript"], photo_desc, soil_data)
        result["advice"] = advice

        # Step 5: Convert advice to speech
        advice_audio = text_to_speech(advice)
        result["advice_audio_b64"] = advice_audio

        # Step 6: Generate report (optional)
        if generate_report_flag == "true":
            report = generate_report(
                result["transcript"], advice, photo_desc, soil_data
            )
            result["report_html"] = report

        return JSONResponse(result)

    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "kisan-awaaz"}
