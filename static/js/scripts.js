// Enhanced JavaScript for Flask Mental Health Application with AI Integration

// Global variables for real-time updates
let rpmUpdateInterval;
let aiProcessingModal;

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
    
    // Initialize real-time features
    initializeRealTimeFeatures();
    initializeAIInteractionCues();
    initializeEnhancedForms();
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

// Enhanced form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('border-red-500');
            isValid = false;
        } else {
            input.classList.remove('border-red-500');
        }
    });
    
    return isValid;
}

// Real-time form validation
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.hasAttribute('required') && !this.value.trim()) {
                this.classList.add('border-red-500');
            } else {
                this.classList.remove('border-red-500');
            }
        });
    });
});

// Progress bar animation
function animateProgressBar(elementId, targetPercent) {
    const progressBar = document.getElementById(elementId);
    if (progressBar) {
        let currentPercent = 0;
        const increment = targetPercent / 50; // 50 steps for smooth animation
        
        const timer = setInterval(() => {
            currentPercent += increment;
            if (currentPercent >= targetPercent) {
                currentPercent = targetPercent;
                clearInterval(timer);
            }
            progressBar.style.width = currentPercent + '%';
        }, 20);
    }
}

// Smooth scroll to element
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

// Copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showMessageBox('Success', 'Text copied to clipboard!', 'success');
    }).catch(err => {
        showMessageBox('Error', 'Failed to copy text to clipboard.', 'error');
    });
}

// Format date for display
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

// Auto-resize textarea
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Initialize auto-resize for all textareas
document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            autoResizeTextarea(this);
        });
    });
});

// Loading spinner utility
function showLoadingSpinner(buttonElement) {
    const originalText = buttonElement.innerHTML;
    buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Loading...';
    buttonElement.disabled = true;
    
    return function hideSpinner() {
        buttonElement.innerHTML = originalText;
        buttonElement.disabled = false;
    };
}

// Enhanced table sorting
function sortTable(tableId, columnIndex, dataType = 'string') {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        if (dataType === 'number') {
            return parseFloat(aValue) - parseFloat(bValue);
        } else if (dataType === 'date') {
            return new Date(aValue) - new Date(bValue);
        } else {
            return aValue.localeCompare(bValue);
        }
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

// Search functionality for tables
function searchTable(tableId, searchInputId) {
    const searchInput = document.getElementById(searchInputId);
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tbody tr');
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

// Mobile menu toggle
function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenu) {
        mobileMenu.classList.toggle('hidden');
    }
}

// Notification system
class NotificationSystem {
    constructor() {
        this.container = this.createContainer();
    }
    
    createContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'fixed top-20 right-4 z-50 space-y-2';
        document.body.appendChild(container);
        return container;
    }
    
    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-500' : 
                       type === 'error' ? 'bg-red-500' : 
                       type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500';
        
        notification.className = `${bgColor} text-white px-4 py-3 rounded-lg shadow-lg transform translate-x-full transition-transform duration-300`;
        notification.innerHTML = `
            <div class="flex items-center justify-between">
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        this.container.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);
        
        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.add('translate-x-full');
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }, duration);
        }
    }
}

// Initialize notification system
const notifications = new NotificationSystem();

// Utility function to show notifications
function showNotification(message, type = 'info', duration = 5000) {
    notifications.show(message, type, duration);
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'absolute bg-gray-800 text-white text-sm px-2 py-1 rounded shadow-lg z-50';
            tooltip.textContent = this.getAttribute('data-tooltip');
            tooltip.id = 'tooltip';
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltip = document.getElementById('tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        });
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
});

// ============= NEW ENHANCED FEATURES =============

// Real-time RPM data updates
function initializeRealTimeFeatures() {
    if (window.location.pathname.includes('patient-dashboard')) {
        startRPMUpdates();
    }
}

function startRPMUpdates() {
    // Update RPM data every 10 seconds
    // rpmUpdateInterval = setInterval(updateRPMData, 10000); // Disabled to prevent excessive API calls
    
    // Initial update
    // updateRPMData(); // Also disabling the initial call on page load
}

function updateRPMData() {
    fetch('/api/rpm-data')
        .then(response => response.json())
        .then(data => {
            // Update heart rate
            const heartRateElement = document.getElementById('heart-rate');
            if (heartRateElement) {
                animateNumberChange(heartRateElement, data.heart_rate);
            }
            
            // Update sleep duration
            const sleepElement = document.getElementById('sleep-duration');
            if (sleepElement) {
                animateNumberChange(sleepElement, data.sleep_duration + 'h');
            }
            
            // Update steps
            const stepsElement = document.getElementById('steps');
            if (stepsElement) {
                animateNumberChange(stepsElement, data.steps.toLocaleString());
            }
            
            // Update mood score
            const moodElement = document.getElementById('mood-score');
            if (moodElement) {
                animateNumberChange(moodElement, data.mood_score + '/10');
            }
            
            // Update timestamp
            const timestampElement = document.getElementById('rpm-timestamp');
            if (timestampElement) {
                timestampElement.textContent = `Last updated: ${data.timestamp}`;
            }
            
            // Show alerts if any
            if (data.alerts && data.alerts.length > 0) {
                data.alerts.forEach(alert => {
                    showNotification(alert, 'warning', 8000);
                });
            }
        })
        .catch(error => {
            console.error('Error updating RPM data:', error);
        });
}

function animateNumberChange(element, newValue) {
    element.style.transform = 'scale(1.1)';
    element.style.color = '#10b981';
    element.textContent = newValue;
    
    setTimeout(() => {
        element.style.transform = 'scale(1)';
        element.style.color = '';
    }, 300);
}

// AI Interaction Cues
function initializeAIInteractionCues() {
    // Add AI processing modal
    createAIProcessingModal();
}

function createAIProcessingModal() {
    const modal = document.createElement('div');
    modal.id = 'ai-processing-modal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden';
    modal.innerHTML = `
        <div class="bg-white rounded-lg p-8 max-w-md mx-4 shadow-xl text-center">
            <div class="mb-4">
                <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
            <h3 class="text-xl font-semibold text-gray-800 mb-2">🧠 Analyzing with Mindwell...</h3>
            <p class="text-gray-600 mb-4" id="ai-status">Processing your data with AI...</p>
            <div class="bg-gray-100 rounded-lg p-3 text-sm text-left" id="ai-debug-info" style="display: none;">
                <strong>Debug Info:</strong>
                <div id="ai-raw-output"></div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    aiProcessingModal = modal;
}

function showAIProcessing(message = 'Processing your data with AI...', showDebug = false) {
    const modal = document.getElementById('ai-processing-modal');
    const statusElement = document.getElementById('ai-status');
    const debugInfo = document.getElementById('ai-debug-info');
    
    statusElement.textContent = message;
    debugInfo.style.display = showDebug ? 'block' : 'none';
    modal.classList.remove('hidden');
}

function hideAIProcessing() {
    const modal = document.getElementById('ai-processing-modal');
    modal.classList.add('hidden');
}

function updateAIDebugInfo(data) {
    const debugOutput = document.getElementById('ai-raw-output');
    if (debugOutput) {
        debugOutput.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    }
}

// Enhanced Forms with AJAX
function initializeEnhancedForms() {
    // Enhanced digital detox form
    const detoxForm = document.getElementById('digital-detox-form');
    if (detoxForm) {
        detoxForm.addEventListener('submit', handleDigitalDetoxSubmission);
    }
    
    // Enhanced chat functionality
    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
        chatForm.addEventListener('submit', handleChatMessage);
    }
}

function handleDigitalDetoxSubmission(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const data = {
        screen_time: formData.get('screen_time'),
        academic_score: formData.get('academic_score'),
        social_interactions: formData.get('social_interactions')
    };
    
    // Show AI processing
    showAIProcessing('🔍 Analyzing your digital wellness patterns...', true);
    
    // Submit via AJAX
    fetch('/api/submit-digital-detox', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        hideAIProcessing();
        
        if (result.success) {
            // Update debug info
            updateAIDebugInfo(result.ai_analysis);
            
            // Show success with gamification feedback
            showGamificationFeedback(result);
            
            // Update UI with new data
            updateDigitalDetoxUI(result);
            
            // Reset form
            event.target.reset();
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    })
    .catch(error => {
        hideAIProcessing();
        showNotification('Network error occurred', 'error');
        console.error('Error:', error);
    });
}

function showGamificationFeedback(result) {
    let message = `🎉 You earned ${result.points_earned} points!`;
    
    if (result.badge_earned) {
        message += ` 🏆 New badge unlocked: ${result.badge_earned}!`;
    }
    
    message += ` AI Analysis: ${result.ai_analysis.score}`;
    
    // Create animated feedback popup
    const popup = document.createElement('div');
    popup.className = 'fixed top-4 right-4 bg-green-500 text-white p-4 rounded-lg shadow-lg z-50 transform translate-x-full transition-transform duration-300';
    popup.innerHTML = `
        <div class="flex items-center">
            <span class="text-2xl mr-3">🎉</span>
            <div>
                <div class="font-semibold">${message}</div>
                <div class="text-sm opacity-90">AI processing time: ${result.analysis_time}s</div>
            </div>
        </div>
    `;
    
    document.body.appendChild(popup);
    
    // Animate in
    setTimeout(() => {
        popup.style.transform = 'translateX(0)';
    }, 100);
    
    // Animate out and remove
    setTimeout(() => {
        popup.style.transform = 'translateX(full)';
        setTimeout(() => popup.remove(), 300);
    }, 5000);
}

function updateDigitalDetoxUI(result) {
    // Update AI analysis display
    const scoreElement = document.getElementById('ai-score');
    if (scoreElement) {
        scoreElement.textContent = result.ai_analysis.score;
        scoreElement.className = `px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(result.ai_analysis.score)}`;
    }
    
    const suggestionElement = document.getElementById('ai-suggestion');
    if (suggestionElement) {
        suggestionElement.textContent = result.ai_analysis.suggestion;
    }
}

function getScoreColor(score) {
    switch(score.toLowerCase()) {
        case 'excellent': return 'bg-green-100 text-green-800';
        case 'good': return 'bg-blue-100 text-blue-800';
        case 'fair': return 'bg-yellow-100 text-yellow-800';
        case 'poor': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

function handleChatMessage(event) {
    event.preventDefault();
    
    const messageInput = event.target.querySelector('input[name="message"]');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addChatMessage(message, 'user');
    
    // Clear input
    messageInput.value = '';
    
    // Show typing indicator
    addTypingIndicator();
    
    // Send to server
    fetch('/api/chat-message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(result => {
        removeTypingIndicator();
        
        if (result.success) {
            addChatMessage(result.response, 'bot', result.timestamp);
        } else {
            addChatMessage('Sorry, I encountered an error. Please try again.', 'bot');
        }
    })
    .catch(error => {
        removeTypingIndicator();
        addChatMessage('Connection error. Please check your internet connection.', 'bot');
        console.error('Chat error:', error);
    });
}

function addChatMessage(message, sender, timestamp = null) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `mb-4 ${sender === 'user' ? 'text-right' : 'text-left'}`;
    
    const time = timestamp || new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    messageDiv.innerHTML = `
        <div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
            sender === 'user' 
                ? 'bg-blue-500 text-white' 
                : 'bg-gray-200 text-gray-800'
        }">
            <p>${message}</p>
            <p class="text-xs mt-1 opacity-70">${time}</p>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTypingIndicator() {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.className = 'mb-4 text-left';
    typingDiv.innerHTML = `
        <div class="inline-block max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-gray-200 text-gray-800">
            <div class="flex items-center">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <span class="ml-2 text-sm">Bot is typing...</span>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Enhanced Chart.js Integration (replacing canvas charts)
function initializeChartJS() {
    // Initialize Chart.js charts if the library is loaded
    if (typeof Chart !== 'undefined') {
        initializeWellnessChart();
        initializeScreenTimeChart();
        initializeCorrelationChart();
    }
}

function initializeWellnessChart() {
    const ctx = document.getElementById('wellness-trend-chart');
    if (!ctx) return;
    
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

function initializeScreenTimeChart() {
    const ctx = document.getElementById('screen-time-chart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Screen Time (hours)',
                data: [8.5, 9.2, 7.8, 8.9, 6.5, 5.2, 4.8],
                backgroundColor: 'rgba(239, 68, 68, 0.8)',
                borderColor: 'rgb(239, 68, 68)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Daily Screen Time'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function initializeCorrelationChart() {
    const ctx = document.getElementById('correlation-chart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Screen Time vs Academic Score',
                data: [
                    {x: 8.5, y: 75},
                    {x: 9.2, y: 72},
                    {x: 7.8, y: 78},
                    {x: 8.9, y: 70},
                    {x: 6.5, y: 85},
                    {x: 5.2, y: 88},
                    {x: 4.8, y: 92}
                ],
                backgroundColor: 'rgba(16, 185, 129, 0.8)',
                borderColor: 'rgb(16, 185, 129)'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Screen Time vs Academic Performance Correlation'
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Screen Time (hours)'
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
}

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


// Breathing Exercise Visualizer
let breathingInterval;

function startBreathing(type) {
    clearInterval(breathingInterval);

    const visualizer = document.getElementById('breathing-visualizer');
    const circle = document.getElementById('breathing-circle');
    const instruction = document.getElementById('breathing-instruction');

    if (!visualizer || !circle || !instruction) {
        console.error('Breathing visualizer elements not found.');
        return;
    }

    const animations = {
        box: [
            { instruction: 'Breathe In (4s)', duration: 4000, scale: 1.5 },
            { instruction: 'Hold (4s)', duration: 4000, scale: 1.5 },
            { instruction: 'Breathe Out (4s)', duration: 4000, scale: 1 },
            { instruction: 'Hold (4s)', duration: 4000, scale: 1 },
        ],
        '478': [
            { instruction: 'Breathe In (4s)', duration: 4000, scale: 1.5 },
            { instruction: 'Hold (7s)', duration: 7000, scale: 1.5 },
            { instruction: 'Breathe Out (8s)', duration: 8000, scale: 1 },
        ],
    };

    const sequence = animations[type];
    let currentStep = 0;

    function runStep() {
        const step = sequence[currentStep];
        instruction.textContent = step.instruction;
        
        circle.style.transitionDuration = `${step.duration}ms`;
        circle.style.transform = `scale(${step.scale})`;
        
        breathingInterval = setTimeout(() => {
            currentStep = (currentStep + 1) % sequence.length;
            runStep();
        }, step.duration);
    }

    clearTimeout(breathingInterval);
    runStep();
}

