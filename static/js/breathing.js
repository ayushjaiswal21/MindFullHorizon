// Breathing exercise functionality
let breathingInterval;
let isBreathing = false;
let currentPattern = null;
let remainingTime = 0;

// Breathing patterns in seconds
const patterns = {
    'box': { inhale: 4, hold: 4, exhale: 4, rest: 4 },
    '478': { inhale: 4, hold: 7, exhale: 8, rest: 0 },
    'coherence': { inhale: 5, hold: 0, exhale: 5, rest: 0 },
    'triangle': { inhale: 4, hold: 0, exhale: 6, rest: 0 }
};

function startBreathing(pattern) {
    if (isBreathing) {
        stopBreathing();
    }
    
    currentPattern = pattern;
    isBreathing = true;
    const patternData = patterns[pattern];
    
    // Update UI
    const circle = document.getElementById('breathing-circle');
    if (circle) {
        circle.classList.add('active');
    }
    document.getElementById('breathing-instruction').textContent = 'Breathe In';
    const textElement = document.getElementById('breathing-text');
    if (textElement) {
        textElement.textContent = patternData.inhale;
    }
    
    let phase = 'inhale';
    remainingTime = patternData[phase];
    
    breathingInterval = setInterval(() => {
        remainingTime--;
        
        if (remainingTime <= 0) {
            // Move to next phase
            switch(phase) {
                case 'inhale':
                    phase = patternData.hold > 0 ? 'hold' : 'exhale';
                    remainingTime = patternData[phase];
                    document.getElementById('breathing-instruction').textContent = 
                        phase === 'hold' ? 'Hold' : 'Breathe Out';
                    const circle1 = document.getElementById('breathing-circle');
                    if (circle1) {
                        circle1.classList.remove('inhale');
                        circle1.classList.add(phase);
                    }
                    break;
                    
                case 'hold':
                    phase = 'exhale';
                    remainingTime = patternData.exhale;
                    document.getElementById('breathing-instruction').textContent = 'Breathe Out';
                    const circle2 = document.getElementById('breathing-circle');
                    if (circle2) {
                        circle2.classList.remove('hold');
                        circle2.classList.add('exhale');
                    }
                    break;
                    
                case 'exhale':
                    if (patternData.rest > 0) {
                        phase = 'rest';
                        remainingTime = patternData.rest;
                        document.getElementById('breathing-instruction').textContent = 'Rest';
                        const circle3 = document.getElementById('breathing-circle');
                        if (circle3) {
                            circle3.classList.remove('exhale');
                        }
                    } else {
                        // Restart the cycle
                        phase = 'inhale';
                        remainingTime = patternData.inhale;
                        document.getElementById('breathing-instruction').textContent = 'Breathe In';
                        const circle4 = document.getElementById('breathing-circle');
                        if (circle4) {
                            circle4.classList.remove('exhale');
                            circle4.classList.add('inhale');
                        }
                    }
                    break;
                    
                case 'rest':
                    // Restart the cycle
                    phase = 'inhale';
                    remainingTime = patternData.inhale;
                    document.getElementById('breathing-instruction').textContent = 'Breathe In';
                    const circle5 = document.getElementById('breathing-circle');
                    if (circle5) {
                        circle5.classList.remove('rest');
                        circle5.classList.add('inhale');
                    }
                    break;
            }
        }
        
        // Update timer display
        const textElement2 = document.getElementById('breathing-text');
        if (textElement2) {
            textElement2.textContent = remainingTime > 0 ? remainingTime : 1;
        }
        
    }, 1000);
}

function stopBreathing() {
    if (breathingInterval) {
        clearInterval(breathingInterval);
        breathingInterval = null;
    }
    
    isBreathing = false;
    currentPattern = null;
    
    // Reset UI
    const circle = document.getElementById('breathing-circle');
    if (circle) {
        circle.className = 'breathing-circle';
    }
    
    const instruction = document.getElementById('breathing-instruction');
    if (instruction) {
        instruction.textContent = 'Select an exercise to begin';
    }
    
    const textElement = document.getElementById('breathing-text');
    if (textElement) {
        textElement.textContent = 'Breathe';
    }
}

// Session management
let sessionTimer;
let sessionDuration = 300; // 5 minutes in seconds

function startSession() {
    if (sessionTimer) return;
    
    let timeLeft = sessionDuration;
    updateSessionTimer(timeLeft);
    
    sessionTimer = setInterval(() => {
        timeLeft--;
        updateSessionTimer(timeLeft);
        
        if (timeLeft <= 0) {
            stopSession();
        }
    }, 1000);
    
    // Enable/disable buttons
    document.getElementById('start-btn').disabled = true;
    document.getElementById('pause-btn').disabled = false;
    document.getElementById('stop-btn').disabled = false;
}

function pauseSession() {
    if (sessionTimer) {
        clearInterval(sessionTimer);
        sessionTimer = null;
        
        // Update button states
        document.getElementById('pause-btn').textContent = 'Resume';
        document.getElementById('pause-btn').onclick = resumeSession;
    }
}

function resumeSession() {
    if (!sessionTimer) {
        startSession();
        document.getElementById('pause-btn').textContent = 'Pause';
        document.getElementById('pause-btn').onclick = pauseSession;
    }
}

function stopSession() {
    if (sessionTimer) {
        clearInterval(sessionTimer);
        sessionTimer = null;
    }
    
    // Reset timer display
    updateSessionTimer(sessionDuration);
    
    // Reset button states
    document.getElementById('start-btn').disabled = false;
    document.getElementById('pause-btn').disabled = true;
    document.getElementById('stop-btn').disabled = true;
    document.getElementById('pause-btn').textContent = 'Pause';
    document.getElementById('pause-btn').onclick = pauseSession;
    
    // Stop any active breathing
    stopBreathing();
}

function updateSessionTimer(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    const timerDisplay = document.getElementById('timer-display');
    if (timerDisplay) {
        timerDisplay.textContent = 
            `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
        timerDisplay.classList.remove('hidden');
    }
}

// Initialize the breathing exercise
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for breathing exercise buttons
    const startBoxBtn = document.getElementById('start-box-breathing');
    const start478Btn = document.getElementById('start-4-7-8-breathing');
    const startDiaphragmaticBtn = document.getElementById('start-diaphragmatic-breathing');
    const startPursedLipBtn = document.getElementById('start-pursed-lip-breathing');
    
    if (startBoxBtn) startBoxBtn.addEventListener('click', () => startBreathing('box'));
    if (start478Btn) start478Btn.addEventListener('click', () => startBreathing('478'));
    if (startDiaphragmaticBtn) startDiaphragmaticBtn.addEventListener('click', () => startBreathing('coherence'));
    if (startPursedLipBtn) startPursedLipBtn.addEventListener('click', () => startBreathing('triangle'));
    
    // Add event listeners for session controls
    const startBtn = document.getElementById('start-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (startBtn) startBtn.addEventListener('click', startSession);
    if (pauseBtn) pauseBtn.addEventListener('click', pauseSession);
    if (stopBtn) stopBtn.addEventListener('click', stopSession);
    
    // Initialize button states
    if (pauseBtn) pauseBtn.disabled = true;
    if (stopBtn) stopBtn.disabled = true;
});
