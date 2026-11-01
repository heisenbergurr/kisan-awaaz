// 🌾 Kisan Awaaz — Frontend Controller

document.addEventListener('DOMContentLoaded', () => {
    // ── Elements ────────────────────────────────────────────────────────────
    const form = document.getElementById('queryForm');
    const recordBtn = document.getElementById('recordBtn');
    const stopBtn = document.getElementById('stopBtn');
    const recordingIndicator = document.getElementById('recordingIndicator');
    const timerElem = document.getElementById('timer');
    const audioPreview = document.getElementById('audioPreview');
    const previewPlayer = document.getElementById('previewPlayer');
    const clearAudioBtn = document.getElementById('clearAudio');
    const textQuery = document.getElementById('textQuery');

    const photoZone = document.getElementById('photoZone');
    const photoInput = document.getElementById('photoInput');
    const photoPreview = document.getElementById('photoPreview');
    const photoThumb = document.getElementById('photoThumb');

    const docZone = document.getElementById('docZone');
    const docInput = document.getElementById('docInput');
    const docPreview = document.getElementById('docPreview');
    const docThumb = document.getElementById('docThumb');
    const docFileName = document.getElementById('docFileName');

    const reportCheckbox = document.getElementById('reportCheckbox');
    const submitBtn = document.getElementById('submitBtn');

    const loadingDiv = document.getElementById('loading');
    const loadingText = document.getElementById('loadingText');
    const resultsDiv = document.getElementById('results');

    const resultTranscript = document.getElementById('resultTranscript');
    const resultLanguage = document.getElementById('resultLanguage');
    const resultPhotoCard = document.getElementById('resultPhotoCard');
    const resultPhotoAnalysis = document.getElementById('resultPhotoAnalysis');
    const resultSoilCard = document.getElementById('resultSoilCard');
    const resultSoilData = document.getElementById('resultSoilData');
    const resultAdvice = document.getElementById('resultAdvice');
    const advicePlayer = document.getElementById('advicePlayer');
    const resultReportCard = document.getElementById('resultReportCard');
    const downloadReportBtn = document.getElementById('downloadReport');
    const printReportBtn = document.getElementById('printReport');
    const newQueryBtn = document.getElementById('newQueryBtn');

    // ── State ───────────────────────────────────────────────────────────────
    let mediaRecorder = null;
    let audioChunks = [];
    let recordedAudioBlob = null;
    let recordStartTime = null;
    let timerInterval = null;
    let latestReportHtml = null;

    // ── Voice Recording ─────────────────────────────────────────────────────
    recordBtn.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            
            // Choose supported mimeType
            let mimeType = 'audio/webm';
            if (!MediaRecorder.isTypeSupported('audio/webm')) {
                if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    mimeType = 'audio/mp4';
                } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
                    mimeType = 'audio/ogg';
                }
            }

            mediaRecorder = new MediaRecorder(stream, { mimeType });

            mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };

            mediaRecorder.onstop = () => {
                stream.getTracks().forEach(track => track.stop());
                clearInterval(timerInterval);

                recordedAudioBlob = new Blob(audioChunks, { type: mimeType });
                const audioUrl = URL.createObjectURL(recordedAudioBlob);
                previewPlayer.src = audioUrl;

                recordingIndicator.classList.add('hidden');
                audioPreview.classList.remove('hidden');
                recordBtn.classList.remove('hidden');
            };

            mediaRecorder.start();
            recordStartTime = Date.now();
            updateTimer();
            timerInterval = setInterval(updateTimer, 1000);

            recordBtn.classList.add('hidden');
            recordingIndicator.classList.remove('hidden');
            audioPreview.classList.add('hidden');
        } catch (err) {
            console.error('Microphone error:', err);
            alert('माइक्रोफ़ोन चालू नहीं हो सका। कृपया अनुमति दें या नीचे सवाल टाइप करें।\n(Could not access microphone. Please grant permission or type your query below.)');
        }
    });

    stopBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
    });

    clearAudioBtn.addEventListener('click', () => {
        recordedAudioBlob = null;
        previewPlayer.src = '';
        audioPreview.classList.add('hidden');
    });

    function updateTimer() {
        if (!recordStartTime) return;
        const elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        timerElem.textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    }

    // ── File Upload & Dropzone Helpers ───────────────────────────────────────
    function setupDropzone(zone, input, previewContainer, thumbElem, nameElem) {
        zone.addEventListener('click', (e) => {
            if (e.target.closest('.remove-btn')) return;
            input.click();
        });

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                input.files = e.dataTransfer.files;
                handleFileSelect(input.files[0], previewContainer, thumbElem, nameElem, zone);
            }
        });

        input.addEventListener('change', () => {
            if (input.files && input.files[0]) {
                handleFileSelect(input.files[0], previewContainer, thumbElem, nameElem, zone);
            }
        });
    }

    function handleFileSelect(file, previewContainer, thumbElem, nameElem, zone) {
        if (!file) return;

        const content = zone.querySelector('.upload-content');
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                if (thumbElem) {
                    thumbElem.src = e.target.result;
                    thumbElem.classList.remove('hidden');
                }
            };
            reader.readAsDataURL(file);
        } else {
            if (thumbElem) thumbElem.classList.add('hidden');
        }

        if (nameElem) {
            nameElem.textContent = file.name;
        }

        content.classList.add('hidden');
        previewContainer.classList.remove('hidden');
    }

    // Setup remove buttons
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const targetId = btn.getAttribute('data-target');
            const targetInput = document.getElementById(targetId);
            if (targetInput) targetInput.value = '';

            const zone = btn.closest('.upload-zone');
            const preview = zone.querySelector('.preview-container');
            const content = zone.querySelector('.upload-content');
            preview.classList.add('hidden');
            content.classList.remove('hidden');
        });
    });

    setupDropzone(photoZone, photoInput, photoPreview, photoThumb, null);
    setupDropzone(docZone, docInput, docPreview, docThumb, docFileName);

    // ── Form Submission ─────────────────────────────────────────────────────
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const textVal = textQuery.value.trim();
        if (!recordedAudioBlob && !textVal) {
            alert('कृपया अपनी आवाज़ रिकॉर्ड करें या प्रश्न टाइप करें।\n(Please record your voice or type a question.)');
            return;
        }

        const formData = new FormData();

        if (recordedAudioBlob) {
            const ext = recordedAudioBlob.type.includes('mp4') ? 'mp4' : 'webm';
            formData.append('audio', recordedAudioBlob, `farmer_query.${ext}`);
        }

        if (textVal) {
            formData.append('text_query', textVal);
        }

        if (photoInput.files && photoInput.files[0]) {
            formData.append('photo', photoInput.files[0]);
        }

        if (docInput.files && docInput.files[0]) {
            formData.append('document', docInput.files[0]);
        }

        if (reportCheckbox.checked) {
            formData.append('generate_report_flag', 'true');
        }

        // UI transitions
        form.classList.add('hidden');
        loadingDiv.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Simulate progress steps for clarity
        const steps = [
            { id: 'step-stt', text: 'आपकी आवाज़ सुनी जा रही है… (Transcribing with Saaras)' },
            { id: 'step-photo', text: 'फसल की फोटो देखी जा रही है… (Analysing image with GLM Vision)' },
            { id: 'step-soil', text: 'मिट्टी स्वास्थ्य कार्ड पढ़ा जा रहा है… (Extracting with Sarvam Vision)' },
            { id: 'step-llm', text: 'कृषि सलाह तैयार की जा रही है… (Reasoning with Sarvam 105B)' },
            { id: 'step-tts', text: 'सलाह की आवाज़ बनाई जा रही है… (Synthesising speech with Bulbul)' }
        ];

        let currentStepIdx = 0;
        const progressTimer = setInterval(() => {
            if (currentStepIdx < steps.length) {
                const s = steps[currentStepIdx];
                document.querySelectorAll('.progress-steps .step').forEach(el => el.classList.remove('active'));
                const stepElem = document.getElementById(s.id);
                if (stepElem) stepElem.classList.add('active');
                loadingText.textContent = s.text;
                currentStepIdx++;
            }
        }, 3000);

        try {
            const response = await fetch('/api/query', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressTimer);

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Server error occurred');
            }

            const data = await response.json();
            renderResults(data);
        } catch (err) {
            clearInterval(progressTimer);
            console.error('Submission error:', err);
            alert(`त्रुटि (Error): ${err.message}\nकृपया पुनः प्रयास करें।`);
            loadingDiv.classList.add('hidden');
            form.classList.remove('hidden');
        }
    });

    // ── Render Results ──────────────────────────────────────────────────────
    function renderResults(data) {
        loadingDiv.classList.add('hidden');
        resultsDiv.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // 1. Transcript
        resultTranscript.textContent = data.transcript || '—';
        if (data.language) {
            resultLanguage.textContent = `पहचानी गई भाषा (Detected Language): ${data.language}`;
        } else {
            resultLanguage.textContent = '';
        }

        // 2. Photo Analysis
        if (data.photo_analysis) {
            resultPhotoAnalysis.textContent = data.photo_analysis;
            resultPhotoCard.classList.remove('hidden');
        } else {
            resultPhotoCard.classList.add('hidden');
        }

        // 3. Soil Data
        if (data.soil_data && typeof data.soil_data === 'object' && Object.keys(data.soil_data).length > 0) {
            let tableHtml = '<table class="soil-table"><thead><tr><th>मापदंड (Parameter)</th><th>मान (Value)</th></tr></thead><tbody>';
            for (const [k, v] of Object.entries(data.soil_data)) {
                if (v !== null && v !== undefined && v !== '') {
                    tableHtml += `<tr><td><strong>${k}</strong></td><td>${v}</td></tr>`;
                }
            }
            tableHtml += '</tbody></table>';
            resultSoilData.innerHTML = tableHtml;
            resultSoilCard.classList.remove('hidden');
        } else {
            resultSoilCard.classList.add('hidden');
        }

        // 4. Advice text
        resultAdvice.innerHTML = formatMarkdown(data.advice || '');

        // 5. Spoken advice audio
        if (data.advice_audio_b64) {
            advicePlayer.src = `data:audio/wav;base64,${data.advice_audio_b64}`;
            advicePlayer.play().catch(() => {
                // Autoplay may be restricted by some browsers until user interacts
                console.log('Autoplay was prevented by browser policy; user can click play.');
            });
        }

        // 6. Report
        if (data.report_html) {
            latestReportHtml = data.report_html;
            resultReportCard.classList.remove('hidden');
        } else {
            resultReportCard.classList.add('hidden');
        }
    }

    function formatMarkdown(text) {
        if (!text) return '';
        // Convert **bold** to <strong>
        let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Convert newlines to breaks
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    // ── Report Actions ──────────────────────────────────────────────────────
    downloadReportBtn.addEventListener('click', () => {
        if (!latestReportHtml) return;
        const blob = new Blob([latestReportHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `kisan_advisory_report_${Date.now()}.html`;
        a.click();
        URL.revokeObjectURL(url);
    });

    printReportBtn.addEventListener('click', () => {
        if (!latestReportHtml) return;
        const printWindow = window.open('', '_blank');
        printWindow.document.write(latestReportHtml);
        printWindow.document.close();
        printWindow.focus();
        setTimeout(() => printWindow.print(), 500);
    });

    // ── New Query ───────────────────────────────────────────────────────────
    newQueryBtn.addEventListener('click', () => {
        resultsDiv.classList.add('hidden');
        form.reset();

        recordedAudioBlob = null;
        previewPlayer.src = '';
        audioPreview.classList.add('hidden');
        recordBtn.classList.remove('hidden');
        recordingIndicator.classList.add('hidden');

        document.querySelectorAll('.preview-container').forEach(p => p.classList.add('hidden'));
        document.querySelectorAll('.upload-content').forEach(c => c.classList.remove('hidden'));

        form.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});
