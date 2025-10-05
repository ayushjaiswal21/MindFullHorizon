// Breathing Session Controls
let breathingSessionActive = false;
let breathingSessionPaused = false;
let breathingSessionTimer = null;
let breathingSessionDuration = 60; // default 60s, can be customized
let breathingSessionRemaining = 60;

function startSession() {
    if (breathingSessionActive && !breathingSessionPaused) return;
    breathingSessionActive = true;
    breathingSessionPaused = false;
    document.getElementById('timer-display').classList.remove('hidden');
    document.getElementById('start-btn').classList.add('hidden');
    document.getElementById('pause-btn').classList.remove('hidden');
    document.getElementById('stop-btn').classList.remove('hidden');
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
    document.getElementById('start-btn').classList.remove('hidden');
    document.getElementById('pause-btn').classList.add('hidden');
}

function stopSession() {
    breathingSessionActive = false;
    breathingSessionPaused = false;
    clearInterval(breathingSessionTimer);
    breathingSessionTimer = null;
    breathingSessionRemaining = breathingSessionDuration;
    document.getElementById('timer-display').classList.add('hidden');
    document.getElementById('start-btn').classList.remove('hidden');
    document.getElementById('pause-btn').classList.add('hidden');
    document.getElementById('stop-btn').classList.add('hidden');
}

function updateBreathingTimerDisplay() {
    const timerDisplay = document.getElementById('timer-display');
    if (timerDisplay) {
        const min = Math.floor(breathingSessionRemaining / 60).toString().padStart(2, '0');
        const sec = (breathingSessionRemaining % 60).toString().padStart(2, '0');
        timerDisplay.textContent = `${min}:${sec}`;
    }
}
// Breathing Exercise Logic
// --- Breathing Animation Logic ---
let breathingPhases = [];
let breathingPhaseIndex = 0;
let breathingPhaseTimeout = null;

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
    // initializeRealTimeFeatures();
    // initializeAIInteractionCues();

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

    // Destroy any existing charts on this canvas
    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
        existingChart.destroy();
    }

    // Additional cleanup: destroy all chart instances associated with this canvas
    Chart.helpers.each(Chart.instances, function(instance) {
        if (instance.canvas === canvas) {
            instance.destroy();
        }
    });

    // Clear the canvas to ensure it's clean
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

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

        // Only initialize correlation chart if we're not on the digital detox page
        // The digital detox page handles its own chart initialization
        if (!document.getElementById('digital-detox-form')) {
            initializeCorrelationChart();
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Breathing page scripts
    if (document.getElementById('start-4-7-8-breathing')) {
        document.getElementById('start-4-7-8-breathing').addEventListener('click', function() {
            startBreathing('478');
        });
    }
    if (document.getElementById('start-box-breathing')) {
        document.getElementById('start-box-breathing').addEventListener('click', function() {
            startBreathing('box');
        });
    }
    if (document.getElementById('start-diaphragmatic-breathing')) {
        document.getElementById('start-diaphragmatic-breathing').addEventListener('click', function() {
            startBreathing('default'); // Using default as there's no specific case for 'diaphragmatic'
        });
    }
    if (document.getElementById('start-pursed-lip-breathing')) {
        document.getElementById('start-pursed-lip-breathing').addEventListener('click', function() {
            startBreathing('default'); // Using default as there's no specific case for 'pursed-lip'
        });
    }
    if (document.getElementById('start-session-button')) {
        document.getElementById('start-session-button').addEventListener('click', function() {
            startSession();
        });
    }

    // Breathing session control buttons
    if (document.getElementById('start-btn')) {
        document.getElementById('start-btn').addEventListener('click', startSession);
    }
    if (document.getElementById('pause-btn')) {
        document.getElementById('pause-btn').addEventListener('click', pauseSession);
    }
    if (document.getElementById('stop-btn')) {
        document.getElementById('stop-btn').addEventListener('click', stopSession);
    }

    // ... (other page scripts)

    // Chat page scripts
    if (document.getElementById('chat-form')) {
        // Check if socket.io is available
        if (typeof io === 'undefined') {
            console.error('Socket.IO library not loaded');
            showChatError('Chat service is currently unavailable. Please refresh the page.');
            return;
        }

        let socket;
        try {
            socket = io({
                transports: ['websocket', 'polling'],
                timeout: 5000,
                reconnection: true,
                reconnectionAttempts: 3
            });
        } catch (error) {
            console.error('Failed to initialize socket connection:', error);
            showChatError('Failed to connect to chat service.');
            return;
        }

        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const chatMessages = document.getElementById('chat-messages');

        // Connection status handling
        socket.on('connect', function() {
            console.log('Chat connected');
            hideConnectionError();
        });

        socket.on('disconnect', function() {
            console.log('Chat disconnected');
            showConnectionError('Connection lost. Attempting to reconnect...');
        });

        socket.on('connect_error', function(error) {
            console.error('Chat connection error:', error);
            showConnectionError('Unable to connect to chat service.');
        });

        socket.on('reconnect', function() {
            console.log('Chat reconnected');
            hideConnectionError();
        });

        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (message && socket.connected) {
                // Show user message immediately
                const userMsg = document.createElement('div');
                userMsg.classList.add('chat-message', 'text-right');
                userMsg.innerHTML = `<div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-blue-600 text-white ml-auto text-right"><p>${escapeHtml(message)}</p></div>`;
                chatMessages.appendChild(userMsg);
                chatMessages.scrollTop = chatMessages.scrollHeight;

                try {
                    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
                    socket.emit('chat_message', { 
                        'message': message, 
                        'csrf_token': csrfToken 
                    });
                    chatInput.value = '';
                } catch (error) {
                    console.error('Error sending message:', error);
                    showChatError('Failed to send message. Please try again.');
                }
            } else if (!socket.connected) {
                showChatError('Not connected to chat service. Please wait for reconnection.');
            }
        });

        socket.on('chat_response', function(data) {
            try {
                // Split multiline bot responses for better display
                const botReplies = (data.reply || 'No response received').split(/\n+/);
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
            } catch (error) {
                console.error('Error handling chat response:', error);
                showChatError('Error displaying chat response.');
            }
        });

        // Helper functions
        function escapeHtml(text) {
            const map = {
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, function(m) { return map[m]; });
        }

        function showChatError(message) {
            const errorDiv = document.createElement('div');
            errorDiv.id = 'chat-error';
            errorDiv.className = 'chat-message text-center';
            errorDiv.innerHTML = `<div class="inline-block px-4 py-2 rounded-lg bg-red-100 text-red-800"><p><i class="fas fa-exclamation-triangle mr-2"></i>${message}</p></div>`;
            chatMessages.appendChild(errorDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function showConnectionError(message) {
            let errorDiv = document.getElementById('connection-error');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = 'connection-error';
                errorDiv.className = 'fixed top-20 left-1/2 transform -translate-x-1/2 bg-yellow-100 border border-yellow-400 text-yellow-800 px-4 py-2 rounded-md z-50';
                document.body.appendChild(errorDiv);
            }
            errorDiv.innerHTML = `<i class="fas fa-wifi mr-2"></i>${message}`;
            errorDiv.style.display = 'block';
        }

        function hideConnectionError() {
            const errorDiv = document.getElementById('connection-error');
            if (errorDiv) {
                errorDiv.style.display = 'none';
            }
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
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                messageDiv.className = 'mt-4 p-3 bg-green-100 border border-green-400 text-green-700 rounded';
                messageDiv.textContent = 'Data saved successfully! Analyzing your data...';
                messageDiv.classList.remove('hidden');
                
                form.reset();
                
                const analysisResponse = await fetch('/api/analyze-digital-detox', { 
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                    } 
                });
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
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
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

/* Advanced JavaScript for MindFullHorizon UI */

/* ===============================================
   ADVANCED NAVIGATION SYSTEM
   =============================================== */

let lastScrollTop = 0;
let isScrolling = false;

// Advanced Navigation Functions
function initializeAdvancedNavigation() {
    const nav = document.querySelector('.advanced-nav');
    if (!nav) return;

    // Navigation scroll behavior
    window.addEventListener('scroll', throttle(handleNavScroll, 16));
    handleNavScroll(); // Initial call

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', handleSmoothScroll);
    });

    // Mobile menu functionality
    initializeMobileMenu();

    // User menu functionality
    initializeUserMenu();

    // Logo interaction
    initializeLogoInteraction();

    // Navigation tooltips
    initializeNavTooltips();
}

function handleNavScroll() {
    const nav = document.querySelector('.advanced-nav');
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    // Add/remove scrolled class based on scroll position
    if (scrollTop > 50) {
        nav.classList.add('scrolled');
    } else {
        nav.classList.remove('scrolled');
    }

    // Hide/show nav on scroll direction
    if (scrollTop > lastScrollTop && scrollTop > 100) {
        nav.classList.add('nav-hidden');
    } else {
        nav.classList.remove('nav-hidden');
    }

    lastScrollTop = scrollTop;
}

function handleSmoothScroll(e) {
    e.preventDefault();
    const targetId = this.getAttribute('href');
    const targetElement = document.querySelector(targetId);

    if (targetElement) {
        const navHeight = document.querySelector('.advanced-nav').offsetHeight;
        const targetPosition = targetElement.offsetTop - navHeight - 20;

        window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
        });

        // Update URL hash
        history.pushState(null, null, targetId);
    }
}

function initializeMobileMenu() {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    if (!mobileMenuBtn || !mobileMenu) return;

    mobileMenuBtn.addEventListener('click', toggleMobileMenu);

    // Close mobile menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!mobileMenuBtn.contains(e.target) && !mobileMenu.contains(e.target)) {
            mobileMenu.classList.remove('open');
            mobileMenuBtn.classList.remove('active');
        }
    });

    // Close mobile menu when clicking on menu items
    mobileMenu.querySelectorAll('.mobile-menu-item').forEach(item => {
        item.addEventListener('click', () => {
            mobileMenu.classList.remove('open');
            mobileMenuBtn.classList.remove('active');
        });
    });

    // Handle escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mobileMenu.classList.contains('open')) {
            toggleMobileMenu();
        }
    });
}

function toggleMobileMenu() {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    mobileMenuBtn.classList.toggle('active');
    mobileMenu.classList.toggle('open');

    // Prevent body scroll when mobile menu is open
    document.body.style.overflow = mobileMenu.classList.contains('open') ? 'hidden' : '';
}

function initializeUserMenu() {
    const userMenuBtn = document.querySelector('.user-menu-btn');
    const userMenu = document.getElementById('user-menu');

    if (!userMenuBtn || !userMenu) return;

    userMenuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        userMenu.classList.toggle('open');
    });

    // Close user menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!userMenuBtn.contains(e.target) && !userMenu.contains(e.target)) {
            userMenu.classList.remove('open');
        }
    });

    // Handle escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && userMenu.classList.contains('open')) {
            userMenu.classList.remove('open');
        }
    });
}

function initializeLogoInteraction() {
    const logo = document.querySelector('.advanced-logo');
    if (!logo) return;

    logo.addEventListener('mouseenter', () => {
        const icon = logo.querySelector('.logo-icon');
        if (icon) {
            icon.style.transform = 'scale(1.1) rotate(5deg)';
        }
    });

    logo.addEventListener('mouseleave', () => {
        const icon = logo.querySelector('.logo-icon');
        if (icon) {
            icon.style.transform = 'scale(1) rotate(0deg)';
        }
    });
}

function initializeNavTooltips() {
    const navItems = document.querySelectorAll('.nav-link-item[data-tooltip]');

    navItems.forEach(item => {
        item.addEventListener('mouseenter', showNavTooltip);
        item.addEventListener('mouseleave', hideNavTooltip);
    });
}

function showNavTooltip(e) {
    const tooltip = document.createElement('div');
    tooltip.className = 'nav-tooltip';
    tooltip.textContent = e.target.getAttribute('data-tooltip') || e.target.textContent.trim();

    document.body.appendChild(tooltip);

    const rect = e.target.getBoundingClientRect();
    tooltip.style.left = rect.left + rect.width / 2 + 'px';
    tooltip.style.top = rect.bottom + 10 + 'px';

    // Animate in
    requestAnimationFrame(() => {
        tooltip.style.opacity = '1';
        tooltip.style.transform = 'translateX(-50%) translateY(0)';
    });

    e.target._tooltip = tooltip;
}

function hideNavTooltip(e) {
    const tooltip = e.target._tooltip;
    if (tooltip) {
        tooltip.style.opacity = '0';
        tooltip.style.transform = 'translateX(-50%) translateY(-5px)';

        setTimeout(() => {
            if (tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
            }
        }, 200);

        delete e.target._tooltip;
    }
}

/* ===============================================
   ADVANCED ANIMATIONS AND INTERACTIONS
   =============================================== */

// Intersection Observer for scroll animations
function initializeScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');

                // Special handling for statistics
                if (entry.target.classList.contains('stat-number')) {
                    animateNumber(entry.target);
                }

                // Special handling for progress bars
                if (entry.target.classList.contains('metric-fill')) {
                    animateProgressBar(entry.target);
                }

                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe all elements that need animation
    document.querySelectorAll('.animate-on-scroll, .feature-card, .testimonial-card, .blog-preview-card').forEach(el => {
        observer.observe(el);
    });

    // Observe statistics numbers
    document.querySelectorAll('.stat-number').forEach(el => {
        observer.observe(el);
    });

    // Observe progress bars
    document.querySelectorAll('.metric-fill').forEach(el => {
        observer.observe(el);
    });
}

// Animated number counter
function animateNumber(element) {
    const target = parseInt(element.getAttribute('data-target')) || 0;
    const duration = 2000; // 2 seconds
    const step = target / (duration / 16); // 60fps
    let current = 0;

    const timer = setInterval(() => {
        current += step;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }

        // Format number based on content
        if (element.textContent.includes('%')) {
            element.textContent = Math.floor(current) + '%';
        } else if (element.textContent.includes('K')) {
            element.textContent = Math.floor(current / 1000) + 'K+';
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Animated progress bar
function animateProgressBar(element) {
    const targetWidth = element.style.width || '0%';
    element.style.width = '0%';

    setTimeout(() => {
        element.style.transition = 'width 1.5s ease-out';
        element.style.width = targetWidth;
    }, 500);
}

// Initialize scroll to top functionality
function initializeScrollToTop() {
    const scrollBtn = document.getElementById('scroll-to-top');
    if (!scrollBtn) return;

    // Show/hide scroll button based on scroll position
    window.addEventListener('scroll', throttle(() => {
        if (window.pageYOffset > 300) {
            scrollBtn.classList.add('visible');
        } else {
            scrollBtn.classList.remove('visible');
        }
    }, 100));

    // Scroll to top when clicked
    scrollBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// Loading overlay management
function showLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Advanced alert system
function initializeAlerts() {
    const alerts = document.querySelectorAll('.advanced-alert');

    alerts.forEach((alert, index) => {
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (alert && !alert.classList.contains('dismissed')) {
                closeAlert(alert);
            }
        }, 5000 + (index * 1000)); // Stagger auto-hide

        // Manual close button
        const closeBtn = alert.querySelector('.alert-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => closeAlert(alert));
        }
    });
}

function closeAlert(alert) {
    if (!alert) return;

    alert.classList.add('dismissed');

    setTimeout(() => {
        if (alert.parentNode) {
            alert.parentNode.removeChild(alert);
        }
    }, 300);
}

/* ===============================================
   PERFORMANCE OPTIMIZATIONS
   =============================================== */

// Throttle function for scroll events
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// Debounce function for resize events
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Lazy loading for images
function initializeLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
}

// Preload critical resources
function preloadCriticalResources() {
    const criticalImages = [
        '/static/images/hero_image.png',
        'https://images.unsplash.com/photo-1494790108755-2616c96cea64?w=150&h=150&fit=crop&crop=face',
        'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face'
    ];

    criticalImages.forEach(src => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = src;
        document.head.appendChild(link);
    });
}

/* ===============================================
   FORM ENHANCEMENTS
   =============================================== */

// Enhanced form validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');

    forms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);

        // Real-time validation
        form.querySelectorAll('input, textarea, select').forEach(field => {
            field.addEventListener('blur', () => validateField(field));
            field.addEventListener('input', () => clearFieldError(field));
        });
    });
}

function handleFormSubmit(e) {
    const form = e.target;
    const fields = form.querySelectorAll('input, textarea, select');
    let isValid = true;

    fields.forEach(field => {
        if (!validateField(field)) {
            isValid = false;
        }
    });

    if (!isValid) {
        e.preventDefault();
        showFormError(form, 'Please correct the errors above and try again.');
    } else {
        // Show loading state
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
        }

        // Hide any existing errors
        hideFormError(form);
    }
}

function validateField(field) {
    const value = field.value.trim();
    const type = field.type;
    const required = field.hasAttribute('required');
    let isValid = true;
    let errorMessage = '';

    // Required field validation
    if (required && !value) {
        isValid = false;
        errorMessage = 'This field is required';
    }

    // Type-specific validation
    if (isValid && value) {
        switch (type) {
            case 'email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                    isValid = false;
                    errorMessage = 'Please enter a valid email address';
                }
                break;
            case 'password':
                if (value.length < 8) {
                    isValid = false;
                    errorMessage = 'Password must be at least 8 characters long';
                }
                break;
        }
    }

    if (isValid) {
        clearFieldError(field);
        return true;
    } else {
        showFieldError(field, errorMessage);
        return false;
    }
}

function showFieldError(field, message) {
    clearFieldError(field);

    field.classList.add('error');

    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error';
    errorDiv.textContent = message;

    field.parentNode.appendChild(errorDiv);
}

function clearFieldError(field) {
    field.classList.remove('error');
    const errorDiv = field.parentNode.querySelector('.field-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

function showFormError(form, message) {
    hideFormError(form);

    const errorDiv = document.createElement('div');
    errorDiv.className = 'form-error';
    errorDiv.textContent = message;

    form.insertBefore(errorDiv, form.firstChild);
}

function hideFormError(form) {
    const errorDiv = form.querySelector('.form-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

/* ===============================================
   ADVANCED UI COMPONENTS
   =============================================== */

// Initialize tooltips
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');

    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
        element.addEventListener('focus', showTooltip);
        element.addEventListener('blur', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltip = document.createElement('div');
    tooltip.className = 'advanced-tooltip';
    tooltip.textContent = e.target.getAttribute('data-tooltip');

    document.body.appendChild(tooltip);

    const rect = e.target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    let left = rect.left + rect.width / 2 - tooltipRect.width / 2;
    let top = rect.top - tooltipRect.height - 10;

    // Adjust position if tooltip goes off screen
    if (left < 10) left = 10;
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }
    if (top < 10) top = rect.bottom + 10;

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';

    // Animate in
    requestAnimationFrame(() => {
        tooltip.style.opacity = '1';
        tooltip.style.transform = 'translateY(0)';
    });

    e.target._tooltip = tooltip;
}

function hideTooltip(e) {
    const tooltip = e.target._tooltip;
    if (tooltip) {
        tooltip.style.opacity = '0';
        tooltip.style.transform = 'translateY(-5px)';

        setTimeout(() => {
            if (tooltip.parentNode) {
                tooltip.parentNode.removeChild(tooltip);
            }
        }, 200);

        delete e.target._tooltip;
    }
}

// Initialize advanced UI features
function initializeAdvancedUI() {
    initializeAdvancedNavigation();
    initializeScrollAnimations();
    initializeScrollToTop();
    initializeAlerts();
    initializeFormValidation();
    initializeTooltips();
    initializeLazyLoading();
}

// Utility function to check if element is in viewport
function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Handle window resize
window.addEventListener('resize', debounce(() => {
    // Recalculate positions and sizes
    const tooltips = document.querySelectorAll('.advanced-tooltip');
    tooltips.forEach(tooltip => {
        if (tooltip.parentNode) {
            tooltip.parentNode.removeChild(tooltip);
        }
    });
}, 250));

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Pause animations and timers when tab is not visible
        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            el.style.animationPlayState = 'paused';
        });
    } else {
        // Resume animations when tab becomes visible
        document.querySelectorAll('.animate-on-scroll').forEach(el => {
            el.style.animationPlayState = 'running';
        });
    }
});

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize existing functionality
    if (typeof initializeChartJS === 'function') {
        initializeChartJS();
    }

    // Initialize advanced UI features
    initializeAdvancedUI();

    // Initialize page-specific features
    initializePageSpecificFeatures();

    // Hide loading overlay after a delay
    setTimeout(hideLoadingOverlay, 1000);
});

// Page-specific initializations
function initializePageSpecificFeatures() {
    const currentPath = window.location.pathname;

    if (currentPath === '/' || currentPath === '/index') {
        // Homepage specific features
        initializeHeroAnimations();
        initializeFeatureCards();
        initializeStatisticsCounter();
    } else if (currentPath.includes('/dashboard')) {
        // Dashboard specific features
        initializeDashboardFeatures();
    } else if (currentPath.includes('/yoga')) {
        // Yoga page specific features
        initializeYogaFeatures();
    }
}

function initializeHeroAnimations() {
    // Animate hero title lines sequentially
    const titleLines = document.querySelectorAll('.title-line');
    titleLines.forEach((line, index) => {
        setTimeout(() => {
            line.style.animation = 'titleSlideIn 0.8s ease-out forwards';
        }, index * 300);
    });

    // Initialize hero stats animation
    const heroStats = document.querySelectorAll('.hero-stats .stat-item');
    heroStats.forEach((stat, index) => {
        setTimeout(() => {
            stat.style.opacity = '1';
            stat.style.transform = 'translateY(0)';
        }, 1000 + (index * 200));
    });
}

function initializeFeatureCards() {
    const featureCards = document.querySelectorAll('.feature-card');

    featureCards.forEach((card, index) => {
        card.addEventListener('mouseenter', () => {
            const icon = card.querySelector('.feature-icon');
            if (icon) {
                icon.style.transform = 'scale(1.1) rotate(5deg)';
            }
        });

        card.addEventListener('mouseleave', () => {
            const icon = card.querySelector('.feature-icon');
            if (icon) {
                icon.style.transform = 'scale(1) rotate(0deg)';
            }
        });
    });
}

function initializeStatisticsCounter() {
    // This function is called by the scroll observer
    // Numbers are animated when they come into view
}

function initializeDashboardFeatures() {
    // Dashboard specific enhancements
    const charts = document.querySelectorAll('.chart-container');
    charts.forEach(chart => {
        chart.classList.add('animate-on-scroll');
    });
}

function initializeYogaFeatures() {
    // Yoga page specific enhancements
    if (typeof setupDigitalDetoxForm === 'function') {
        setupDigitalDetoxForm();
    }
}

// Export functions for global use
window.showLoadingOverlay = showLoadingOverlay;
window.hideLoadingOverlay = hideLoadingOverlay;
window.showMessageBox = showMessageBox;
window.hideMessageBox = hideMessageBox;

// Loading state management
function showLoading(elementId, message = 'Loading...') {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div class="flex items-center justify-center p-4">
                <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                <span class="ml-2 text-gray-600">${message}</span>
            </div>
        `;
    }
}

function hideLoading(elementId, originalContent) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = originalContent;
    }
}

// Enhanced form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        const value = input.value.trim();
        const fieldName = input.name || input.id;
        
        // Remove existing error styling
        input.classList.remove('border-red-500', 'bg-red-50');
        const existingError = input.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
        
        // Validate required fields
        if (!value) {
            showFieldError(input, `${fieldName} is required`);
            isValid = false;
            return;
        }
        
        // Email validation
        if (input.type === 'email' && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                showFieldError(input, 'Please enter a valid email address');
                isValid = false;
                return;
            }
        }
        
        // Password validation
        if (input.type === 'password' && value) {
            if (value.length < 8) {
                showFieldError(input, 'Password must be at least 8 characters long');
                isValid = false;
                return;
            }
        }
        
        // Number validation
        if (input.type === 'number' && value) {
            const num = parseFloat(value);
            if (isNaN(num)) {
                showFieldError(input, 'Please enter a valid number');
                isValid = false;
                return;
            }
        }
    });
    
    return isValid;
}

function showFieldError(input, message) {
    input.classList.add('border-red-500', 'bg-red-50');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error text-red-500 text-sm mt-1';
    errorDiv.textContent = message;
    input.parentNode.appendChild(errorDiv);
}

// Enhanced form submission with loading states and validation
function submitFormWithLoading(formId, submitButtonId) {
    const form = document.getElementById(formId);
    const submitButton = document.getElementById(submitButtonId);
    
    if (form && submitButton) {
        const originalText = submitButton.textContent;
        
        form.addEventListener('submit', function(e) {
            // Validate form before submission
            if (!validateForm(formId)) {
                e.preventDefault();
                return false;
            }
            
            submitButton.disabled = true;
            submitButton.innerHTML = `
                <div class="flex items-center justify-center">
                    <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Processing...
                </div>
            `;
        });
    }
}

// Make functions available globally
window.initializeAdvancedUI = initializeAdvancedUI;
window.toggleMobileMenu = toggleMobileMenu;
window.toggleUserMenu = toggleUserMenu;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.submitFormWithLoading = submitFormWithLoading;
window.validateForm = validateForm;
window.showFieldError = showFieldError;

// Global error handling
window.addEventListener('error', function(e) {
    console.error('Global JavaScript error:', e.error);
    // Log error to server if needed
    if (typeof fetch !== 'undefined') {
        const csrfTokenElement = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenElement ? csrfTokenElement.getAttribute('content') : '';

        fetch('/api/log-error', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken && { 'X-CSRFToken': csrfToken })
            },
            body: JSON.stringify({
                message: e.message,
                filename: e.filename,
                lineno: e.lineno,
                colno: e.colno,
                stack: e.error ? e.error.stack : null
            })
        }).catch(err => console.error('Failed to log error:', err));
    }
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    // Log error to server if needed
    if (typeof fetch !== 'undefined') {
        const csrfTokenElement = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfTokenElement ? csrfTokenElement.getAttribute('content') : '';

        fetch('/api/log-error', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(csrfToken && { 'X-CSRFToken': csrfToken })
            },
            body: JSON.stringify({
                message: 'Unhandled promise rejection',
                reason: e.reason ? e.reason.toString() : 'Unknown',
                stack: e.reason && e.reason.stack ? e.reason.stack : null
            })
        }).catch(err => console.error('Failed to log promise rejection:', err));
    }
});

// Safe async function wrapper
function safeAsync(fn) {
    return async function(...args) {
        try {
            return await fn.apply(this, args);
        } catch (error) {
            console.error('Async function error:', error);
            // Show user-friendly error message
            if (typeof showMessageBox === 'function') {
                showMessageBox('An error occurred. Please try again.', 'error');
            }
            throw error;
        }
    };
}

window.safeAsync = safeAsync;
function drawChart(canvas, ctx, yData, xLabels, color, label, padding) {
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
window.drawChart = drawChart;
window.initializeChartJS = initializeChartJS;

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
