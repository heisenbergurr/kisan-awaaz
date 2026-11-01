# 🌾 Kisan Awaaz (किसान आवाज़)
### Voice-First Multimodal Agronomy Hotline & Web Portal powered by Sarvam AI

Kisan Awaaz is an AI-powered agricultural advisory hotline designed specifically for Indian farmers. It takes spoken voice queries in regional dialects/code-mixed Hindi, diseased crop/leaf photographs, and official Soil Health Cards, and provides structured agronomic advice with a spoken audio response and printable reports.

---

## 🚀 Multimodal Pipeline & Sarvam AI Models

| Modality | Task | Model / API | Notes |
|---|---|---|---|
| **Voice In** 🎤 | Transcribing farmer speech in dialect/code-mixed Hindi | **Saaras v4** (`speech_to_text.transcribe`) | Auto-detects 22 Indic languages, robust to dialect accents & code-mixing. |
| **Vision (Crop)** 🌿 | Disease, pest, and nutrient deficiency detection | **GLM-5.3 Flash** (`chat.completions` with image) | Analyzes leaf spots, discoloration, lesions, and symptoms. |
| **Vision (Docs)** 🧪 | Digitizing physical Soil Health Cards (SHC) | **Sarvam Vision 2.1** (`doc_ai.extract`) | Structured JSON extraction for pH, Organic Carbon, N, P, K, Zn, etc. |
| **Reasoning** 🧠 | Agronomic diagnosis, treatment & safety instructions | **Sarvam 105B Conversations** (`sarvam-105b-conversations`) | Generates structured advice in clear Hindi: समस्या, कारण, उपाय, सावधानी. |
| **Voice Out** 🔊 | Speaking the advisory back to the farmer | **Bulbul v3** (`text_to_speech.convert`) | Natural Indic voice synthesis in Hindi (`hi-IN`). |
| **Report** 📋 | Generating farmer advisory summaries | Web PDF/Print engine | Downloadable/printable HTML report for KVK or farmer records. |

---

## 🛠️ Project Structure

```text
sarvam-test/
├── app.py                  # FastAPI web server & multi-modal orchestration pipeline
├── kisan.py                # Standalone CLI prototype for audio & image queries
├── chat.py                 # Initial minimal Sarvam API verification script
├── templates/
│   └── index.html          # Responsive Hindi/English farmer-friendly UI
├── static/
│   ├── style.css           # Earthy agricultural design system, mobile-optimized
│   └── app.js              # MediaRecorder voice capture, drag-and-drop, audio player
├── .env                    # SARVAM_API_KEY (git-ignored)
└── .venv/                  # Virtual environment
```

---

## 🏃 Running the Application

### 1. Web Portal (FastAPI)
The web server is currently running on **port 8000**:
```bash
# In sarvam-test directory:
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

### 2. CLI Prototype
```bash
# Test with self-generated Bulbul synthetic audio:
.venv/bin/python kisan.py --generate-test

# Test with your own audio file:
.venv/bin/python kisan.py farmer_query.wav

# Test with audio + leaf photo:
.venv/bin/python kisan.py farmer_query.wav --photo diseased_leaf.jpg
```

---

## 🌟 Web Portal Features
- **One-Touch Voice Recording**: Browser-native microphone recording with real-time audio playback preview.
- **Text Alternative**: Text area for typing questions in English or Hindi.
- **Leaf Photo Upload**: Drag-and-drop or camera capture on mobile devices.
- **Soil Health Card Upload**: Scans or PDFs parsed through Sarvam Vision into nutrient tables.
- **Instant Audio Playback**: Direct playback of the Bulbul synthesized speech advisory.
- **Printable Advisory Reports**: Generates formal reports that can be printed or saved to PDF.
