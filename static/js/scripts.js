// Enhanced JavaScript for Flask Mental Health Application with AI Integration

// Global variables for real-time updates
let rpmUpdateInterval;
let aiProcessingModal;

// Chart Initialization Functions
let screenTimeChart = null;

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
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Screen Time: ${context.parsed.x}h, Academic Score: ${context.parsed.y}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Screen Time (Hours)'
                        }
                    },
                    y: {
                        type: 'linear',
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Academic Score'
                        },
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error fetching correlation data:', error);
        ctx.font = '16px Inter';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#ef4444';
        ctx.fillText('Error loading chart data.', canvas.width / 2, canvas.height / 2);
    }
}

// Initialize all charts when the page loads
function initializeChartJS() {
    if (typeof Chart !== 'undefined') {
        initializeScreenTimeChart();
        initializeWellnessChart();
        initializeCorrelationChart();
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // ... (other page scripts)

    // Chat page scripts
    if (document.getElementById('chat-form')) {
        const socket = io();

        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const chatMessages = document.getElementById('chat-messages');

        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const message = chatInput.value;
            if (message) {
                socket.emit('chat_message', { 'message': message });
                chatInput.value = '';
            }
        });

        socket.on('chat_response', function(data) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('chat-message');
            if (data.is_crisis) {
                messageElement.innerHTML = `<div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-red-200 text-red-800"><p>${data.reply}</p></div>`;
            } else {
                messageElement.innerHTML = `<div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-gray-200 text-gray-800"><p>${data.reply}</p></div>`;
            }
            chatMessages.appendChild(messageElement);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }
});

function setupDigitalDetoxForm() {
    const form = document.getElementById('digital-detox-form');
    const messageDiv = document.getElementById('form-message');

    form.addEventListener('submit', async function(event) {
        event.preventDefault(); 

        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Saving...';

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/api/submit-digital-detox', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                messageDiv.className = 'mt-4 p-3 bg-green-100 border border-green-400 text-green-700 rounded';
                messageDiv.textContent = 'Data saved successfully! Analyzing your data...';
                messageDiv.classList.remove('hidden');
                
                form.reset();
                
                const analysisResponse = await fetch('/api/analyze-digital-detox', { method: 'POST' });
                const analysisResult = await analysisResponse.json();

                if (analysisResult.success) {
                    document.getElementById('ai-score').textContent = analysisResult.insights.ai_score;
                    document.getElementById('ai-suggestion').textContent = analysisResult.insights.ai_suggestion;
                    document.getElementById('last-analysis-time').textContent = new Date().toLocaleTimeString();
                    messageDiv.textContent = 'Data saved and analyzed successfully!';
                } else {
                    messageDiv.className = 'mt-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded';
                    messageDiv.textContent = analysisResult.message || 'Failed to analyze data.';
                    console.error('Error in digital detox analysis:', analysisResult.message);
                }

            } else {
                messageDiv.className = 'mt-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded';
                messageDiv.textContent = result.message || 'Failed to save data. Please try again.';
                messageDiv.classList.remove('hidden');
            }
        } catch (error) {
            messageDiv.className = 'mt-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded';
            messageDiv.textContent = 'Network error. Please check your connection and try again.';
            messageDiv.classList.remove('hidden');
            console.error('Error in digital detox form submission:', error);
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-save mr-2"></i>Save Today\'s Data';
        }
    });
}

// Yoga Timer Functionality
let yogaTimer = null;
let yogaTimerDuration = 0;
let yogaTimerRemaining = 0;
let isYogaTimerRunning = false;
let isYogaTimerPaused = false;

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}

function updateYogaTimerDisplay() {
    const timerDisplay = document.getElementById('timer-display');
    const sessionStatus = document.getElementById('session-status');
    const progressBar = document.getElementById('progress-bar');

    if (timerDisplay) {
        timerDisplay.textContent = formatTime(yogaTimerRemaining);
    }

    if (sessionStatus) {
        if (isYogaTimerRunning && !isYogaTimerPaused) {
            sessionStatus.textContent = 'Session in progress...';
        } else if (isYogaTimerPaused) {
            sessionStatus.textContent = 'Session paused';
        } else {
            sessionStatus.textContent = 'Ready to begin your practice';
        }
    }

    if (progressBar) {
        const progress = ((yogaTimerDuration - yogaTimerRemaining) / yogaTimerDuration) * 100;
        progressBar.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }
}

function startTimer() {
    if (yogaTimerDuration <= 0) {
        alert('Please set a session duration first using the quick session buttons or manually.');
        return;
    }

    if (isYogaTimerRunning && !isYogaTimerPaused) {
        return; // Already running
    }

    const startBtn = document.getElementById('start-timer-btn');
    const pauseBtn = document.getElementById('pause-timer-btn');
    const stopBtn = document.getElementById('stop-timer-btn');

    if (isYogaTimerPaused) {
        // Resume timer
        isYogaTimerPaused = false;
        isYogaTimerRunning = true;
    } else {
        // Start new timer
        isYogaTimerRunning = true;
        isYogaTimerPaused = false;
        yogaTimerRemaining = yogaTimerDuration;
    }

    // Update button visibility
    if (startBtn) startBtn.classList.add('hidden');
    if (pauseBtn) pauseBtn.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');

    yogaTimer = setInterval(() => {
        if (yogaTimerRemaining > 0) {
            yogaTimerRemaining--;
            updateYogaTimerDisplay();
        } else {
            stopTimer();
            alert('Session completed! Great job on your yoga practice!');
        }
    }, 1000);

    updateYogaTimerDisplay();
}

function pauseTimer() {
    if (!isYogaTimerRunning || isYogaTimerPaused) {
        return;
    }

    const startBtn = document.getElementById('start-timer-btn');
    const pauseBtn = document.getElementById('pause-timer-btn');
    const stopBtn = document.getElementById('stop-timer-btn');

    isYogaTimerPaused = true;
    isYogaTimerRunning = false;
    clearInterval(yogaTimer);

    // Update button visibility
    if (startBtn) startBtn.classList.remove('hidden');
    if (pauseBtn) pauseBtn.classList.add('hidden');

    updateYogaTimerDisplay();
}

function stopTimer() {
    const startBtn = document.getElementById('start-timer-btn');
    const pauseBtn = document.getElementById('pause-timer-btn');
    const stopBtn = document.getElementById('stop-timer-btn');

    isYogaTimerRunning = false;
    isYogaTimerPaused = false;
    clearInterval(yogaTimer);
    yogaTimerRemaining = yogaTimerDuration;

    // Update button visibility
    if (startBtn) startBtn.classList.remove('hidden');
    if (pauseBtn) pauseBtn.classList.add('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');

    updateYogaTimerDisplay();
}

function setQuickSession(minutes) {
    yogaTimerDuration = minutes * 60;
    yogaTimerRemaining = yogaTimerDuration;
    updateYogaTimerDisplay();

    // Update button text to show selected duration
    const startBtn = document.getElementById('start-timer-btn');
    if (startBtn) {
        startBtn.innerHTML = `<i class="fas fa-play mr-2"></i>Start ${minutes} min Session`;
    }
}

function startGuidedSession(type, sessionType, duration) {
    // Set the session duration
    setQuickSession(duration);

    // Start the timer
    setTimeout(() => {
        startTimer();
    }, 100);

    // You could add session-specific instructions here
    const sessionStatus = document.getElementById('session-status');
    if (sessionStatus) {
        sessionStatus.textContent = `Starting ${sessionType} session...`;
    }
}

// Initialize yoga timer when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize timer display
    updateYogaTimerDisplay();

    // Setup yoga form submission
    const yogaForm = document.getElementById('yoga-log-form');
    if (yogaForm) {
        yogaForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            const formData = new FormData(yogaForm);
            const data = Object.fromEntries(formData.entries());

            try {
                const response = await fetch('/yoga', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: new URLSearchParams(data)
                });

                if (response.ok) {
                    // Refresh the page to show updated logs
                    window.location.reload();
                } else {
                    alert('Failed to log yoga session. Please try again.');
                }
            } catch (error) {
                console.error('Error logging yoga session:', error);
                alert('Network error. Please check your connection and try again.');
            }
        });
    }
});