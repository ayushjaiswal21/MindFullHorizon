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
                }
            }
        });
    } catch (error) {
        console.error('Error fetching screen time data:', error);
    }
}

// Global variables for yoga exercises
let yogaSessionTimer = null;
let yogaSessionStartTime = null;
let yogaSessionDuration = 0;
let isYogaSessionActive = false;
let currentYogaSessionName = '';

const guidedYogaSessions = { // Renamed to avoid conflict with breathing guidedSessions
    'morning': { name: 'Morning Energy Flow', duration: 15, difficulty: 'Beginner' },
    'desk': { name: 'Desk Worker\'s Relief', duration: 10, difficulty: 'All Levels' },
    'evening': { name: 'Evening Wind-Down', duration: 20, difficulty: 'Beginner' },
    'stress': { name: 'Stress Relief Flow', duration: 12, difficulty: 'All Levels' },
    'focus': { name: 'Focus & Clarity', duration: 18, difficulty: 'Intermediate' },
    'flexibility': { name: 'Flexibility Flow', duration: 25, difficulty: 'All Levels' }
};

// Auto-hide flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert-success, .alert-error');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // --- Advanced FAQ (generalized for any container) ---
    const faqContainers = Array.from(document.querySelectorAll('#faq-list, .faq-container'));
    faqContainers.forEach(container => {
        // Determine controls in scope of this container
        const items = Array.from(container.querySelectorAll('.faq-item'));
        const searchInput = container.querySelector('[data-role="faq-search"], #faq-search');
        const expandBtn = container.querySelector('[data-action="expand"], #faq-expand');
        const collapseBtn = container.querySelector('[data-action="collapse"], #faq-collapse');
        const storageKey = `faq_open_id_${container.getAttribute('data-key') || 'default'}`;

        // Restore previously opened item for this container
        const savedOpenId = localStorage.getItem(storageKey);
        if (savedOpenId) {
            const saved = document.getElementById(savedOpenId);
            if (saved && container.contains(saved)) openFAQ(saved, false);
        }

        // Deep link support: only open if the item is in this container
        if (location.hash) {
            const target = document.querySelector(location.hash);
            if (target && container.contains(target)) {
                openFAQ(target, true);
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        // Wire individual items
        items.forEach(item => {
            const btn = item.querySelector('.faq-question');
            const panel = item.querySelector('.faq-answer');
            const chevron = item.querySelector('.faq-chevron');

            // Initialize collapsed
            if (panel) {
                panel.style.maxHeight = '0px';
                panel.setAttribute('aria-hidden', 'true');
            }
            if (btn) btn.setAttribute('aria-expanded', 'false');
            if (chevron) {
                chevron.style.transition = 'transform 0.25s ease';
                chevron.style.transform = 'rotate(0deg)';
            }

            // Toggle on click and Enter/Space
            const toggle = (e) => {
                if (e && e.type === 'keydown' && !['Enter', ' '].includes(e.key)) return;
                const isOpen = item.classList.contains('open');
                if (isOpen) {
                    closeFAQ(item);
                    localStorage.removeItem(storageKey);
                } else {
                    // Close others for single-open behavior within this container
                    items.forEach(i => closeFAQ(i));
                    openFAQ(item, true);
                    localStorage.setItem(storageKey, item.id);
                    // Update hash for sharing
                    history.replaceState(null, '', `#${item.id}`);
                }
            };

            btn.addEventListener('click', toggle);
            btn.addEventListener('keydown', toggle);
            btn.setAttribute('role', 'button');
            btn.setAttribute('tabindex', '0');
        });

        // Expand/collapse all controls
        if (expandBtn) expandBtn.addEventListener('click', () => {
            items.forEach(i => openFAQ(i, false));
            localStorage.removeItem(storageKey);
        });
        if (collapseBtn) collapseBtn.addEventListener('click', () => {
            items.forEach(i => closeFAQ(i));
            localStorage.removeItem(storageKey);
        });

        // Search filter by text and tags
        if (searchInput) {
            const filter = () => {
                const q = searchInput.value.trim().toLowerCase();
                items.forEach(item => {
                    const text = item.textContent.toLowerCase();
                    const tags = (item.getAttribute('data-tags') || '').toLowerCase();
                    const match = !q || text.includes(q) || tags.includes(q);
                    item.style.display = match ? '' : 'none';
                });
            };
            searchInput.addEventListener('input', filter);
        }
    });

    // Initialize real-time features
    initializeRealTimeFeatures();
    initializeAIInteractionCues();

    // Highlight active nav link
    const navLinks = document.querySelectorAll('.nav-item');
    const currentPath = window.location.pathname.replace(/\/$/, '');

    navLinks.forEach(link => {
        try {
            const hrefPath = new URL(link.href, window.location.origin).pathname.replace(/\/$/, '');
            const isRoot = hrefPath === '' || hrefPath === '/';
            const match = (!isRoot && currentPath.startsWith(hrefPath)) || (isRoot && currentPath === '/');
            if (match) {
                link.classList.add('active');
            }
        } catch (e) {
            // Ignore malformed hrefs
        }
    });
    
});

// Function to show custom message box
function showMessageBox(title, message, type = 'info') {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    
    // Create modal content
    const modal = document.createElement('div');
    modal.className = 'bg-white rounded-lg p-6 max-w-md mx-4 shadow-xl';
    
    const iconClass = type === 'success' ? 'fas fa-check-circle text-green-500' : 
                     type === 'error' ? 'fas fa-exclamation-triangle text-red-500' :
                     'fas fa-info-circle text-blue-500';
    
    modal.innerHTML = `
        <div class="text-center">
            <i class="${iconClass} text-4xl mb-4"></i>
            <h3 class="text-lg font-semibold text-gray-800 mb-2">${title}</h3>
            <p class="text-gray-600 mb-4">${message}</p>
            <button onclick="hideMessageBox()" class="btn-primary">OK</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Store reference for hiding
    window.currentMessageBox = overlay;
}

function hideMessageBox() {
    if (window.currentMessageBox) {
        window.currentMessageBox.remove();
        window.currentMessageBox = null;
    }
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
                // Show user message immediately
                const userMsg = document.createElement('div');
                    userMsg.classList.add('chat-message', 'text-right');
                    userMsg.innerHTML = `<div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-blue-600 text-white ml-auto text-right"><p>${escapeHtml(message)}</p></div>`;
                    chatMessages.appendChild(userMsg);
                    chatMessages.scrollTop = chatMessages.scrollHeight;

                socket.emit('chat_message', { 'message': message });
                chatInput.value = '';
            }
        });

        socket.on('chat_response', function(data) {
            // Split multiline bot responses for better display
            const botReplies = data.reply.split(/\n+/);
            botReplies.forEach(function(reply) {
                if (reply.trim() === '') return;
                const messageElement = document.createElement('div');
                    messageElement.classList.add('chat-message', 'text-left');
                    if (data.is_crisis) {
                        messageElement.innerHTML = `<div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-red-200 text-red-800 mr-auto text-left"><p>${escapeHtml(reply)}</p></div>`;
                    } else {
                        messageElement.innerHTML = `<div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-gray-200 text-gray-800 mr-auto text-left"><p>${escapeHtml(reply)}</p></div>`;
                    }
                chatMessages.appendChild(messageElement);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            });
        });

        // Helper to escape HTML
        function escapeHtml(text) {
            const map = {
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, function(m) { return map[m]; });
        }
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

// Cleanup function
function cleanup() {
    if (rpmUpdateInterval) {
        clearInterval(rpmUpdateInterval);
    }
}

// A reusable function to draw a line chart on a canvas
function drawLineChart(ctx, canvas, xLabels, yData, label, color) {
    const padding = 40;
    const width = canvas.width - 2 * padding;
    const height = canvas.height - 2 * padding;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (yData.length === 0) return;

    // Set up scales
    const maxY = Math.max(...yData) + 1;
    const minY = 0;
    const yRange = maxY - minY || 1;
    
    // Draw axes
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, padding + height);
    ctx.moveTo(padding, padding + height);
    ctx.lineTo(padding + width, padding + height);
    ctx.stroke();
    
    // Draw grid lines
    ctx.strokeStyle = '#f3f4f6';
    for (let i = 1; i <= 4; i++) {
        const y = padding + (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(padding + width, y);
        ctx.stroke();
    }

    // Draw data line
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    for (let i = 0; i < yData.length; i++) {
        const x = padding + (width / (yData.length - 1)) * i;
        const y = padding + height - ((yData[i] - minY) / yRange) * height;
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
    
    // Draw data points and labels
    ctx.fillStyle = color;
    ctx.font = '12px Inter';
    ctx.textAlign = 'center';
    for (let i = 0; i < yData.length; i++) {
        const x = padding + (width / (yData.length - 1)) * i;
        const y = padding + height - ((yData[i] - minY) / yRange) * height;
        
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();
        
        // Label points with the value
        ctx.fillStyle = '#6b7280';
        ctx.fillText(yData[i], x, y - 10);
        
        // X-axis labels
        ctx.fillText(xLabels[i], x, padding + height + 20);
    }

    // Y-axis labels
    for (let i = 0; i <= 4; i++) {
        const value = minY + (yRange / 4) * (4 - i);
        const y = padding + (height / 4) * i;
        ctx.fillStyle = '#6b7280';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round(value * 10) / 10, padding - 10, y + 4);
    }
    
    // Y-axis label
    ctx.save();
    ctx.translate(padding - 30, padding + height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(label, 0, 0);
    ctx.restore();
}

// FAQ helpers for accordion behavior
function openFAQ(item, animate = true) {
    if (!item || item.classList.contains('open')) return;
    const btn = item.querySelector('.faq-question');
    const panel = item.querySelector('.faq-answer');
    const chevron = item.querySelector('.faq-chevron');
    if (!btn || !panel) return;

    item.classList.add('open');
    btn.setAttribute('aria-expanded', 'true');
    panel.setAttribute('aria-hidden', 'false');

    // Chevron rotation (inline style to avoid dependency on utilities)
    if (chevron) {
        if (!chevron.style.transition) chevron.style.transition = 'transform 0.25s ease';
        chevron.style.transform = 'rotate(180deg)';
    }

    // Smooth height animation
    panel.style.display = 'block';
    panel.style.overflow = 'hidden';
    const targetHeight = panel.scrollHeight;
    if (animate) {
        panel.style.maxHeight = targetHeight + 'px';
    } else {
        panel.style.maxHeight = 'none';
    }
}

function closeFAQ(item) {
    if (!item) return;
    const btn = item.querySelector('.faq-question');
    const panel = item.querySelector('.faq-answer');
    const chevron = item.querySelector('.faq-chevron');
    if (!btn || !panel) return;

    item.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
    panel.setAttribute('aria-hidden', 'true');

    if (chevron) {
        if (!chevron.style.transition) chevron.style.transition = 'transform 0.25s ease';
        chevron.style.transform = 'rotate(0deg)';
    }

    panel.style.overflow = 'hidden';
    panel.style.maxHeight = '0px';
}
