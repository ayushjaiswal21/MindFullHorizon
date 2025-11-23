let timerInterval;
let sessionDuration = 0; // in seconds
let timeElapsed = 0;
let isPaused = false;

const timerDisplay = document.getElementById('timer-display');
const progressBar = document.getElementById('progress-bar');
const sessionStatus = document.getElementById('session-status');

const startBtn = document.getElementById('start-timer-btn');
const pauseBtn = document.getElementById('pause-timer-btn');
const stopBtn = document.getElementById('stop-timer-btn');

function updateTimerDisplay() {
    const minutes = Math.floor(timeElapsed / 60);
    const seconds = timeElapsed % 60;
    timerDisplay.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

    if (sessionDuration > 0) {
        const progress = (timeElapsed / sessionDuration) * 100;
        progressBar.style.width = `${progress}%`;
    }
}

function startTimer() {
    if (sessionDuration === 0) {
        alert('Please set a session duration first (e.g., 5 min, 10 min, or a guided session).');
        return;
    }

    if (timerInterval) clearInterval(timerInterval);

    isPaused = false;
    sessionStatus.textContent = 'Session in progress...';
    startBtn.classList.add('hidden');
    pauseBtn.classList.remove('hidden');
    stopBtn.classList.remove('hidden');

    timerInterval = setInterval(() => {
        if (!isPaused) {
            timeElapsed++;
            updateTimerDisplay();

            if (timeElapsed >= sessionDuration) {
                stopTimer();
                sessionStatus.textContent = 'Session completed!';
                playBeep();
                // Optionally log session here or trigger a modal
            }
        }
    }, 1000);
}

function playBeep() {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(440, audioCtx.currentTime); // A4
    gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);

    oscillator.start();
    oscillator.stop(audioCtx.currentTime + 0.5); // Play for 0.5 seconds
}

function pauseTimer() {
    isPaused = !isPaused;
    if (isPaused) {
        sessionStatus.textContent = 'Session paused.';
        pauseBtn.innerHTML = '<i class="fas fa-play mr-2"></i>Resume';
    } else {
        sessionStatus.textContent = 'Session in progress...';
        pauseBtn.innerHTML = '<i class="fas fa-pause mr-2"></i>Pause';
    }
}

function stopTimer() {
    clearInterval(timerInterval);
    timeElapsed = 0;
    isPaused = false;
    sessionDuration = 0; // Reset duration
    updateTimerDisplay();
    sessionStatus.textContent = 'Ready to begin your practice';
    startBtn.classList.remove('hidden');
    pauseBtn.classList.add('hidden');
    stopBtn.classList.add('hidden');
    progressBar.style.width = '0%';
}

function setQuickSession(durationMinutes) {
    sessionDuration = durationMinutes * 60;
    timeElapsed = 0;
    updateTimerDisplay();
    sessionStatus.textContent = `Quick session set for ${durationMinutes} minutes.`;
    startBtn.classList.remove('hidden');
    pauseBtn.classList.add('hidden');
    stopBtn.classList.add('hidden');
    progressBar.style.width = '0%';
}

function startGuidedSession(type, name, durationMinutes) {
    setQuickSession(durationMinutes); // Use quick session setter
    sessionStatus.textContent = `Starting guided ${type} session: ${name} (${durationMinutes} minutes)`;
    startTimer(); // Automatically start the timer
    // In a real app, you'd also load guided audio/video here
    alert(`Starting guided ${type} session: ${name} for ${durationMinutes} minutes.`);
}

document.addEventListener('DOMContentLoaded', function () {
    // Attach event listeners to timer controls
    startBtn?.addEventListener('click', startTimer);
    pauseBtn?.addEventListener('click', pauseTimer);
    stopBtn?.addEventListener('click', stopTimer);

    // Attach event listeners to quick session buttons
    document.querySelectorAll('.quick-session-btn').forEach(button => {
        button.addEventListener('click', function () {
            const duration = parseInt(this.dataset.duration);
            setQuickSession(duration);
        });
    });

    // Attach event listeners to guided yoga session cards
    document.querySelectorAll('.start-guided-session-card').forEach(card => {
        card.addEventListener('click', function () {
            const type = this.dataset.sessionType;
            const name = this.dataset.sessionName;
            const duration = parseInt(this.dataset.sessionDuration);
            startGuidedSession(type, name, duration);
        });
    });
});
