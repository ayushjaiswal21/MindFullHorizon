let mediaRecorder;
let audioChunks = [];
let recordingTimer;
let startTime;

function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            startTime = Date.now();

            // Update UI
            document.getElementById('recordBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            document.getElementById('recordingStatus').textContent = 'Recording...';
            document.getElementById('recordingStatus').className = 'text-sm text-red-600 mb-2';

            // Start timer
            let seconds = 0;
            recordingTimer = setInterval(() => {
                seconds = Math.floor((Date.now() - startTime) / 1000);
                const minutes = Math.floor(seconds / 60);
                const remainingSeconds = seconds % 60;
                document.getElementById('timer').textContent =
                    `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;

                // Auto-stop after 2 minutes
                if (seconds >= 120) {
                    stopRecording();
                }
            }, 1000);

            // Start waveform visualization
            startWaveformVisualization(stream);
        })
        .catch(error => {
            console.error('Error accessing microphone:', error);
            alert('Error accessing microphone. Please check permissions.');
        });
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }

    clearInterval(recordingTimer);

    // Update UI
    document.getElementById('recordBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('uploadBtn').disabled = false;
    document.getElementById('recordingStatus').textContent = 'Recording stopped';
    document.getElementById('recordingStatus').className = 'text-sm text-green-600 mb-2';

    // Stop waveform visualization
    stopWaveformVisualization();
}

function uploadRecording() {
    if (audioChunks.length === 0) {
        alert('No recording to upload');
        return;
    }

    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice_log.wav');

    // Show upload status
    document.getElementById('uploadStatus').classList.remove('hidden');

    fetch('/api/upload-voice', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
        }
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('uploadStatus').classList.add('hidden');

        if (data.success) {
            location.reload(); // Refresh to show new voice log
        } else {
            alert('Upload failed: ' + data.message);
        }
    })
    .catch(error => {
        document.getElementById('uploadStatus').classList.add('hidden');
        console.error('Upload error:', error);
        alert('Upload failed. Please try again.');
    });
}

// Simple waveform visualization
let audioContext, analyser, dataArray, canvasCtx, animationId;

function startWaveformVisualization(stream) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    analyser.fftSize = 256;
    const bufferLength = analyser.frequencyBinCount;
    dataArray = new Uint8Array(bufferLength);

    const canvas = document.getElementById('waveform');
    canvasCtx = canvas.getContext('2d');
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);

    function draw() {
        const drawVisual = requestAnimationFrame(draw);

        analyser.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = '#f3f4f6';
        canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

        canvasCtx.lineWidth = 2;
        canvasCtx.strokeStyle = '#3b82f6';
        canvasCtx.beginPath();

        const sliceWidth = canvas.width * 1.0 / bufferLength;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * canvas.height / 2;

            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }

            x += sliceWidth;
        }

        canvasCtx.stroke();
    }

    draw();
}

function stopWaveformVisualization() {
    if (animationId) {
        cancelAnimationFrame(animationId);
    }
    if (audioContext) {
        audioContext.close();
    }
    const canvas = document.getElementById('waveform');
    const canvasCtx = canvas.getContext('2d');
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
}

function deleteVoiceLog(logId) {
    if (confirm('Are you sure you want to delete this voice log? This action cannot be undone.')) {
        fetch(`/api/delete-voice-log/${logId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the log entry from the DOM
                const logElement = document.querySelector(`[data-log-id="${logId}"]`);
                if (logElement) {
                    logElement.remove();
                }

                // Show success message
                showAlert('Voice log deleted successfully!', 'success');

                // If no logs left, show empty state
                const logsContainer = document.querySelector('.space-y-4');
                if (logsContainer && logsContainer.children.length === 0) {
                    location.reload(); // Refresh to show empty state
                }
            } else {
                showAlert('Failed to delete voice log: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Delete error:', error);
            showAlert('Failed to delete voice log. Please try again.', 'error');
        });
    }
}

function showAlert(message, type) {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} mb-4 p-4 rounded-lg text-sm ${
        type === 'success'
            ? 'bg-green-100 text-green-800 border border-green-200'
            : 'bg-red-100 text-red-800 border border-red-200'
    }`;
    alertDiv.textContent = message;

    // Insert at the top of the content area
    const container = document.querySelector('.patient-voice-logs-container .max-w-4xl');
    container.insertBefore(alertDiv, container.firstChild);

    // Remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Check for microphone permissions on page load
document.addEventListener('DOMContentLoaded', function() {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(() => {
                console.log('Microphone access granted');
            })
            .catch(() => {
                console.log('Microphone access denied');
                document.getElementById('recordingStatus').textContent = 'Microphone access required';
                document.getElementById('recordingStatus').className = 'text-sm text-red-600 mb-2';
            });
    }
});

// New event listener code
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('recordBtn')?.addEventListener('click', startRecording);
    document.getElementById('stopBtn')?.addEventListener('click', stopRecording);
    document.getElementById('uploadBtn')?.addEventListener('click', uploadRecording);

    document.body.addEventListener('click', function(event) {
        const target = event.target.closest('button');
        if (target && target.classList.contains('delete-voice-log-btn')) {
            const logId = target.dataset.logId;
            deleteVoiceLog(logId);
        }
    });
});