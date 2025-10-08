// MindFullHorizon - Complete JavaScript functionality
// Fixed version - October 2025

// ========================
// GLOBAL VARIABLES
// ========================

// Breathing Session Controls
let breathingSessionActive = false;
let breathingSessionPaused = false;
let breathingSessionTimer = null;
let breathingSessionDuration = 60; // default 60s, can be customized
let breathingSessionRemaining = 60;

// Yoga Timer Variables
let yogaTimer = null;
let yogaSessionActive = false;
let yogaSessionPaused = false;
let yogaSessionDuration = 0;
let yogaSessionRemaining = 0;
let yogaSessionStartTime = null;

// Breathing Animation
let breathingPhases = [];
let breathingPhaseIndex = 0;
let breathingPhaseTimeout = null;

// Chart Variables
let screenTimeChart = null;
let rpmUpdateInterval;
let aiProcessingModal;

// Guided Sessions
const guidedYogaSessions = {
    'morning': { name: 'Morning Energy Flow', duration: 15, difficulty: 'Beginner' },
    'desk': { name: 'Desk Worker\'s Relief', duration: 10, difficulty: 'All Levels' },
    'evening': { name: 'Evening Wind-Down', duration: 20, difficulty: 'Beginner' },
    'stress': { name: 'Stress Relief Flow', duration: 12, difficulty: 'All Levels' },
    'focus': { name: 'Focus & Clarity', duration: 18, difficulty: 'Intermediate' },
    'flexibility': { name: 'Flexibility Flow', duration: 25, difficulty: 'All Levels' }
};

// ========================
// BREATHING SESSION FUNCTIONS
// ========================

function startSession() {
    if (breathingSessionActive && !breathingSessionPaused) return;
    breathingSessionActive = true;
    breathingSessionPaused = false;
    
    const timerDisplay = document.getElementById('timer-display');
    const startBtn = document.getElementById('start-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (timerDisplay) timerDisplay.classList.remove('hidden');
    if (startBtn) startBtn.classList.add('hidden');
    if (pauseBtn) pauseBtn.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');
    
    if (!breathingSessionTimer) {
        breathingSessionRemaining = breathingSessionDuration;
    }
    updateBreathingTimerDisplay();
    breathingSessionTimer = setInterval(() => {
        if (!breathingSessionPaused && breathingSessionRemaining > 0) {
            breathingSessionRemaining--;
            updateBreathingTimerDisplay();
        } else if (breathingSessionRemaining <= 0) {
            stopSession();
            alert('Session complete!');
        }
    }, 1000);
}

function pauseSession() {
    if (!breathingSessionActive || breathingSessionPaused) return;
    breathingSessionPaused = true;
    clearInterval(breathingSessionTimer);
    breathingSessionTimer = null;
    
    const startBtn = document.getElementById('start-btn');
    const pauseBtn = document.getElementById('pause-btn');
    if (startBtn) startBtn.classList.remove('hidden');
    if (pauseBtn) pauseBtn.classList.add('hidden');
}

function stopSession() {
    breathingSessionActive = false;
    breathingSessionPaused = false;
    clearInterval(breathingSessionTimer);
    breathingSessionTimer = null;
    breathingSessionRemaining = breathingSessionDuration;
    
    const timerDisplay = document.getElementById('timer-display');
    const startBtn = document.getElementById('start-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (timerDisplay) timerDisplay.classList.add('hidden');
    if (startBtn) startBtn.classList.remove('hidden');
    if (pauseBtn) pauseBtn.classList.add('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');
}

function updateBreathingTimerDisplay() {
    const timerDisplay = document.getElementById('timer-display');
    if (timerDisplay) {
        const min = Math.floor(breathingSessionRemaining / 60).toString().padStart(2, '0');
        const sec = (breathingSessionRemaining % 60).toString().padStart(2, '0');
        timerDisplay.textContent = `${min}:${sec}`;
    }
}

// ========================
// YOGA TIMER FUNCTIONS (Missing functions that were causing errors)
// ========================

function startTimer() {
    if (yogaSessionActive && !yogaSessionPaused) return;
    
    yogaSessionActive = true;
    yogaSessionPaused = false;
    
    const timerDisplay = document.getElementById('timer-display');
    const startBtn = document.getElementById('start-timer-btn');
    const pauseBtn = document.getElementById('pause-timer-btn');
    const stopBtn = document.getElementById('stop-timer-btn');
    const statusElement = document.getElementById('session-status');
    
    if (yogaSessionDuration === 0) {
        yogaSessionDuration = 600; // Default 10 minutes
    }
    
    if (!yogaTimer) {
        yogaSessionRemaining = yogaSessionDuration;
        yogaSessionStartTime = new Date();
    }
    
    updateYogaTimerDisplay();
    updateYogaControls();
    if (statusElement) statusElement.textContent = 'Session in progress...';
    
    yogaTimer = setInterval(() => {
        if (!yogaSessionPaused && yogaSessionRemaining > 0) {
            yogaSessionRemaining--;
            updateYogaTimerDisplay();
            updateProgressBar();
        } else if (yogaSessionRemaining <= 0) {
            stopTimer();
            if (statusElement) statusElement.textContent = 'Session completed!';
            alert('Yoga session complete! Well done!');
        }
    }, 1000);
}

function pauseTimer() {
    if (!yogaSessionActive || yogaSessionPaused) return;
    
    yogaSessionPaused = true;
    clearInterval(yogaTimer);
    yogaTimer = null;
    
    const statusElement = document.getElementById('session-status');
    if (statusElement) statusElement.textContent = 'Session paused';
    
    updateYogaControls();
}

function stopTimer() {
    yogaSessionActive = false;
    yogaSessionPaused = false;
    clearInterval(yogaTimer);
    yogaTimer = null;
    yogaSessionRemaining = yogaSessionDuration;
    
    const statusElement = document.getElementById('session-status');
    if (statusElement) statusElement.textContent = 'Ready to begin your practice';
    
    updateYogaTimerDisplay();
    updateYogaControls();
    updateProgressBar();
}

function updateYogaTimerDisplay() {
    const timerDisplay = document.getElementById('timer-display');
    if (timerDisplay && yogaSessionRemaining >= 0) {
        const min = Math.floor(yogaSessionRemaining / 60).toString().padStart(2, '0');
        const sec = (yogaSessionRemaining % 60).toString().padStart(2, '0');
        timerDisplay.textContent = `${min}:${sec}`;
    }
}

function updateYogaControls() {
    const startBtn = document.getElementById('start-timer-btn');
    const pauseBtn = document.getElementById('pause-timer-btn');
    const stopBtn = document.getElementById('stop-timer-btn');
    
    if (yogaSessionActive && !yogaSessionPaused) {
        if (startBtn) startBtn.classList.add('hidden');
        if (pauseBtn) pauseBtn.classList.remove('hidden');
        if (stopBtn) stopBtn.classList.remove('hidden');
    } else if (yogaSessionPaused) {
        if (startBtn) startBtn.classList.remove('hidden');
        if (pauseBtn) pauseBtn.classList.add('hidden');
        if (stopBtn) stopBtn.classList.remove('hidden');
    } else {
        if (startBtn) startBtn.classList.remove('hidden');
        if (pauseBtn) pauseBtn.classList.add('hidden');
        if (stopBtn) stopBtn.classList.add('hidden');
    }
}

function updateProgressBar() {
    const progressBar = document.getElementById('progress-bar');
    if (progressBar && yogaSessionDuration > 0) {
        const progress = ((yogaSessionDuration - yogaSessionRemaining) / yogaSessionDuration) * 100;
        progressBar.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }
}

function setQuickSession(minutes) {
    yogaSessionDuration = minutes * 60;
    yogaSessionRemaining = yogaSessionDuration;
    updateYogaTimerDisplay();
    
    const statusElement = document.getElementById('session-status');
    if (statusElement) statusElement.textContent = `${minutes}-minute session selected`;
}

function startGuidedSession(type, sessionKey, duration) {
    const session = guidedYogaSessions[sessionKey];
    if (session) {
        yogaSessionDuration = session.duration * 60;
        yogaSessionRemaining = yogaSessionDuration;
        updateYogaTimerDisplay();
        
        const statusElement = document.getElementById('session-status');
        if (statusElement) statusElement.textContent = `Ready to start: ${session.name}`;
        
        // Auto-populate form if it exists
        const sessionNameSelect = document.getElementById('session_name');
        const durationInput = document.getElementById('duration_minutes');
        const difficultySelect = document.getElementById('difficulty_level');
        
        if (sessionNameSelect) sessionNameSelect.value = session.name;
        if (durationInput) durationInput.value = session.duration;
        if (difficultySelect) difficultySelect.value = session.difficulty;
        
        // Start timer automatically
        startTimer();
    }
}

// ========================
// BREATHING ANIMATION FUNCTIONS
// ========================

function startBreathing(type) {
    clearBreathingAnimation();
    const instruction = document.getElementById('breathing-instruction');
    const text = document.getElementById('breathing-text');
    const circle = document.getElementById('breathing-circle');
    let guide = '';
    
    switch(type) {
        case 'box':
            guide = 'Inhale 4s, Hold 4s, Exhale 4s, Hold 4s';
            breathingPhases = [
                {label: 'Inhale', duration: 4000, scale: 2},
                {label: 'Hold', duration: 4000, scale: 2},
                {label: 'Exhale', duration: 4000, scale: 1},
                {label: 'Hold', duration: 4000, scale: 1}
            ];
            break;
        case '478':
            guide = 'Inhale 4s, Hold 7s, Exhale 8s';
            breathingPhases = [
                {label: 'Inhale', duration: 4000, scale: 2},
                {label: 'Hold', duration: 7000, scale: 2},
                {label: 'Exhale', duration: 8000, scale: 1}
            ];
            break;
        case 'triangle':
            guide = 'Inhale 3s, Hold 3s, Exhale 3s';
            breathingPhases = [
                {label: 'Inhale', duration: 3000, scale: 2},
                {label: 'Hold', duration: 3000, scale: 2},
                {label: 'Exhale', duration: 3000, scale: 1}
            ];
            break;
        case 'coherence':
            guide = 'Inhale 5s, Exhale 5s';
            breathingPhases = [
                {label: 'Inhale', duration: 5000, scale: 2},
                {label: 'Exhale', duration: 5000, scale: 1}
            ];
            break;
        default:
            guide = 'Follow the instructions.';
            breathingPhases = [
                {label: 'Inhale', duration: 4000, scale: 2},
                {label: 'Exhale', duration: 4000, scale: 1}
            ];
    }
    
    breathingPhaseIndex = 0;
    if (instruction) instruction.textContent = `Selected: ${guide}`;
    runBreathingPhase();
}

function runBreathingPhase() {
    if (breathingPhases.length === 0) return;
    
    const phase = breathingPhases[breathingPhaseIndex];
    const text = document.getElementById('breathing-text');
    const circle = document.getElementById('breathing-circle');
    
    if (text) text.textContent = phase.label;
    if (circle) {
        circle.style.transition = 'transform ' + (phase.duration/1000) + 's ease-in-out';
        circle.style.transform = `scale(${phase.scale})`;
    }
    
    breathingPhaseTimeout = setTimeout(() => {
        breathingPhaseIndex = (breathingPhaseIndex + 1) % breathingPhases.length;
        runBreathingPhase();
    }, phase.duration);
}

function clearBreathingAnimation() {
    clearTimeout(breathingPhaseTimeout);
    const circle = document.getElementById('breathing-circle');
    if (circle) {
        circle.style.transition = '';
        circle.style.transform = 'scale(1)';
    }
    const text = document.getElementById('breathing-text');
    if (text) text.textContent = 'Breathe';
}

// ========================
// CHART FUNCTIONS
// ========================

async function initializeScreenTimeChart() {
    const ctx = document.getElementById('screen-time-chart');
    if (!ctx) return;

    if (screenTimeChart) {
        screenTimeChart.destroy();
    }

    try {
        const response = await fetch('/api/digital-detox-data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const screenTimeData = await response.json();

        if (!screenTimeData || screenTimeData.length === 0) {
            const canvasCtx = ctx.getContext('2d');
            canvasCtx.font = '16px Inter';
            canvasCtx.textAlign = 'center';
            canvasCtx.fillStyle = '#6b7280';
            canvasCtx.fillText('No screen time data available yet.', ctx.width / 2, ctx.height / 2);
            canvasCtx.fillText('Add data using the form below to see your trends.', ctx.width / 2, ctx.height / 2 + 25);
            return;
        }

        const dates = screenTimeData.map(item => new Date(item.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
        const hours = screenTimeData.map(item => item.hours);

        screenTimeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Screen Time (Hours)',
                    data: hours,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false,
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Hours'
                        },
                        beginAtZero: true
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error fetching screen time data:', error);
        const canvasCtx = ctx.getContext('2d');
        canvasCtx.font = '16px Inter';
        canvasCtx.textAlign = 'center';
        canvasCtx.fillStyle = '#ef4444';
        canvasCtx.fillText('Error loading chart data.', ctx.width / 2, ctx.height / 2);
    }
}

function initializeWellnessChart() {
    const ctx = document.getElementById('wellness-chart');
    if (!ctx) return;
    
    const existingChart = Chart.getChart(ctx);
    if (existingChart) {
        existingChart.destroy();
    }
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Wellness Score',
                data: [7.2, 6.8, 7.5, 6.9, 8.1, 7.8, 8.3],
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Weekly Wellness Trend'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 10
                }
            }
        }
    });
}

async function initializeCorrelationChart() {
    const canvas = document.getElementById('correlation-chart');
    if (!canvas) return;

    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
        existingChart.destroy();
    }

    const ctx = canvas.getContext('2d');

    try {
        const response = await fetch('/api/digital-detox-data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const screenTimeData = await response.json();

        let correlationData = [];
        if (screenTimeData && screenTimeData.length > 0) {
            correlationData = screenTimeData.map(log => ({
                x: log.hours,
                y: log.academic_score
            }));
        } else {
            correlationData = [
                { x: 3, y: 90 }, { x: 5, y: 85 }, { x: 7, y: 70 }, { x: 4, y: 92 }, { x: 6, y: 78 }
            ];
        }

        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Screen Time vs Academic Score',
                    data: correlationData,
                    backgroundColor: '#8b5cf6',
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false,
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Screen Time (Hours)'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Academic Score'
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error fetching screen time data:', error);
    }
}

// ========================
// MODAL FUNCTIONALITY
// ========================

function initializeModals() {
    // Find the elements we need
    const modal = document.getElementById("assessmentModal");
    const closeButton = modal ? modal.querySelector(".close-button") : null;
    const startAssessmentButtons = document.querySelectorAll(".start-assessment-btn");

    // Function to open the modal
    function openModal() {
        if (modal) {
            modal.style.display = "block";
        }
    }

    // Function to close the modal
    function closeModal() {
        if (modal) {
            modal.style.display = "none";
        }
    }

    // Add click listeners to all 'Start Assessment' buttons
    startAssessmentButtons.forEach(button => {
        button.addEventListener('click', openModal);
    });

    // When the user clicks on the close button (x), close the modal
    if (closeButton) {
        closeButton.addEventListener('click', closeModal);
    }

    // When the user clicks anywhere outside of the modal content, close it
    window.addEventListener('click', function(event) {
        if (event.target == modal) {
            closeModal();
        }
    });
}

// ========================
// UTILITY FUNCTIONS
// ========================

function allowed_file(filename) {
    const allowedExtensions = ['png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'ogg'];
    const extension = filename.split('.').pop().toLowerCase();
    return allowedExtensions.includes(extension);
}

// Auto-hide flash messages after 5 seconds
function initializeFlashMessages() {
    const alerts = document.querySelectorAll('.alert-success, .alert-error');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });
}

// ========================
// MESSAGE BOX FUNCTIONALITY
// ========================

function showMessageBox(title, message, type) {
    // Create message box dynamically
    const messageBox = document.createElement('div');
    messageBox.className = `fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm ${getMessageBoxClass(type)}`;
    messageBox.innerHTML = `
        <div class="flex items-start">
            <div class="flex-shrink-0">
                <i class="${getMessageBoxIcon(type)} text-lg"></i>
            </div>
            <div class="ml-3 w-0 flex-1">
                <p class="text-sm font-medium">${title}</p>
                <p class="mt-1 text-sm">${message}</p>
            </div>
            <div class="ml-4 flex-shrink-0 flex">
                <button onclick="this.parentElement.parentElement.parentElement.remove()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(messageBox);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (messageBox.parentNode) {
            messageBox.remove();
        }
    }, 5000);
}

function getMessageBoxClass(type) {
    switch (type) {
        case 'success': return 'bg-green-100 border border-green-400 text-green-700';
        case 'error': return 'bg-red-100 border border-red-400 text-red-700';
        case 'warning': return 'bg-yellow-100 border border-yellow-400 text-yellow-700';
        case 'info': return 'bg-blue-100 border border-blue-400 text-blue-700';
        default: return 'bg-gray-100 border border-gray-400 text-gray-700';
    }
}

function getMessageBoxIcon(type) {
    switch (type) {
        case 'success': return 'fas fa-check-circle text-green-500';
        case 'error': return 'fas fa-exclamation-triangle text-red-500';
        case 'warning': return 'fas fa-exclamation-triangle text-yellow-500';
        case 'info': return 'fas fa-info-circle text-blue-500';
        default: return 'fas fa-info-circle text-gray-500';
    }
}

// ========================
// INITIALIZATION
// ========================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize flash messages
    initializeFlashMessages();
    
    // Initialize modals
    initializeModals();
    
    // Initialize charts if elements exist
    if (document.getElementById('screen-time-chart')) {
        initializeScreenTimeChart();
    }
    
    if (document.getElementById('wellness-chart')) {
        initializeWellnessChart();
    }
    
    if (document.getElementById('correlation-chart')) {
        initializeCorrelationChart();
    }
    
    console.log('MindFullHorizon JavaScript initialized successfully');
});
