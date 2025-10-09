// MindFullHorizon - Complete JavaScript functionality
// Fixed version - October 2025

// Assessment variables
let currentAssessmentType = null;
let currentQuestionIndex = 0;
let assessmentQuestions = [];
let assessmentResponses = {};

async function fetchAssessmentQuestions(assessmentType) {
    console.log(`Fetching questions for: ${assessmentType}`);
    try {
        const response = await fetch(`/api/assessment/questions/${assessmentType}`);
        console.log('Response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Received data:', data);
        if (data.success && data.questions) {
            console.log('Successfully fetched questions.');
            return data.questions;
        } else {
            console.error('API call successful, but no questions returned:', data.message);
            return [];
        }
    } catch (error) {
        console.error('Error fetching or parsing assessment questions:', error);
        return [];
    }
}

function previousQuestion() {
    if (currentQuestionIndex > 0) {
        currentQuestionIndex--;
        renderQuestion();
    }
}

function renderQuestion() {
    const questionContainer = document.getElementById('assessment-question-container');
    const questionText = document.getElementById('assessment-question');
    const optionsContainer = document.getElementById('assessment-options');
    const progressText = document.getElementById('assessment-progress');

    if (!questionContainer || !questionText || !optionsContainer || !progressText) {
        console.error('Assessment modal elements not found');
        return;
    }

    // Clear previous options
    optionsContainer.innerHTML = '';

    // Get the current question
    const question = assessmentQuestions[currentQuestionIndex];
    questionText.textContent = question.question;

    // Render options
    question.options.forEach((option, index) => {
        const optionElement = document.createElement('div');
        optionElement.className = 'assessment-option';
        optionElement.innerHTML = `
            <input type="radio" id="option-${index}" name="assessment-option" value="${index}" onchange="selectAnswer(${index})">
            <label for="option-${index}">${option}</label>
        `;
        optionsContainer.appendChild(optionElement);
    });

    // Update progress text
    progressText.textContent = `Question ${currentQuestionIndex + 1} of ${assessmentQuestions.length}`;

        // Check the previously selected answer for this question
    const selectedValue = assessmentResponses[currentQuestionIndex];
    if (selectedValue !== undefined) {
        const selectedRadio = optionsContainer.querySelector(`input[value="${selectedValue}"]`);
        if (selectedRadio) {
            selectedRadio.checked = true;
        }
    }

    // Update button visibility
    const nextButton = document.getElementById('assessment-next-btn');
    const prevButton = document.getElementById('assessment-prev-btn');
    const submitButton = document.getElementById('assessment-submit-btn');

    if (prevButton) {
        prevButton.classList.toggle('hidden', currentQuestionIndex === 0);
    }

    if (currentQuestionIndex === assessmentQuestions.length - 1) {
        if(nextButton) nextButton.classList.add('hidden');
        if(submitButton) submitButton.classList.remove('hidden');
    } else {
        if(nextButton) nextButton.classList.remove('hidden');
        if(submitButton) submitButton.classList.add('hidden');
    }
}

function selectAnswer(value) {
    assessmentResponses[currentQuestionIndex] = value;
}

function nextQuestion() {
    if (assessmentResponses[currentQuestionIndex] === undefined) {
        alert('Please select an answer before continuing.');
        return;
    }

    if (currentQuestionIndex < assessmentQuestions.length - 1) {
        currentQuestionIndex++;
        renderQuestion();
    }
}

async function completeAssessment() {
    const submitButton = document.getElementById('assessment-submit-btn');
    submitButton.disabled = true;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Submitting...';

    // Manually get the value of the last question's response
    const lastAnswer = document.querySelector('input[name="assessment-option"]:checked');
    if (lastAnswer) {
        selectAnswer(parseInt(lastAnswer.value));
    }

    // Verify that all questions have been answered
    const unansweredQuestionIndex = assessmentQuestions.findIndex((_, index) => assessmentResponses[index] === undefined);

    if (unansweredQuestionIndex !== -1) {
        alert('Please answer all questions before submitting.');
        currentQuestionIndex = unansweredQuestionIndex;
        renderQuestion();
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
        return;
    }

    const totalScore = Object.values(assessmentResponses).reduce((sum, value) => sum + value, 0);

    const payload = {
        assessment_type: currentAssessmentType,
        score: totalScore,
        responses: assessmentResponses
    };

    try {
        const response = await fetch('/api/save-assessment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.success) {
            alert('Assessment submitted successfully!');
            closeAssessment();
            displayAiInsights(data.ai_insights);
        } else {
            throw new Error(data.message || 'Failed to save assessment.');
        }
    } catch (error) {
        console.error('Error submitting assessment:', error);
        alert(`An error occurred: ${error.message}`);
        // Re-enable the button if submission fails
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
    }
}

function closeAssessment() {
    const modal = document.getElementById('assessmentModal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Reset state
    currentAssessmentType = null;
    currentQuestionIndex = 0;
    assessmentQuestions = [];
    assessmentResponses = {};
}

function displayAiInsights(insights) {
    const insightsContainer = document.getElementById('aiInsightsContent');
    const summaryEl = document.getElementById('aiSummary');
    const recommendationsEl = document.getElementById('aiRecommendations');
    const resourcesEl = document.getElementById('aiResources');
    const noInsightsMessage = document.getElementById('noInsightsMessage');

    if (!insightsContainer || !summaryEl || !recommendationsEl || !resourcesEl) {
        console.error('AI insights elements not found on the page.');
        location.reload(); // Fallback to reload if elements are missing
        return;
    }

    if (insights) {
        summaryEl.textContent = insights.summary || 'No summary available.';
        
        recommendationsEl.innerHTML = insights.recommendations
            .map(rec => `<li class="flex items-start"><i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i><span>${rec}</span></li>`)
            .join('');

        resourcesEl.innerHTML = insights.resources
            .map(res => `<li class="flex items-start"><i class="fas fa-external-link-alt text-blue-500 mt-1 mr-2"></i><span>${res}</span></li>`)
            .join('');

        insightsContainer.classList.remove('hidden');
        if (noInsightsMessage) {
            noInsightsMessage.classList.add('hidden');
        }

        // Scroll to the insights section
        insightsContainer.scrollIntoView({ behavior: 'smooth' });
    }
}

async function startAssessment(assessmentType) {
    currentAssessmentType = assessmentType;
    currentQuestionIndex = 0;
    assessmentResponses = {};

    // Show loading state
    const questionContainer = document.getElementById('assessment-question-container');
    const loadingIndicator = document.getElementById('assessment-loading');
    const modal = document.getElementById('assessmentModal');

    if (loadingIndicator) loadingIndicator.classList.remove('hidden');
    if (questionContainer) questionContainer.classList.add('hidden');
    if (modal) modal.style.display = 'block';

    // Fetch questions
    assessmentQuestions = await fetchAssessmentQuestions(assessmentType);

    // Hide loading state
    if (loadingIndicator) loadingIndicator.classList.add('hidden');

    if (assessmentQuestions.length > 0) {
        if (questionContainer) questionContainer.classList.remove('hidden');
        renderQuestion();
    } else {
        // Handle error
        const errorContainer = document.getElementById('assessment-error');
        if (errorContainer) errorContainer.classList.remove('hidden');
    }
}
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
let wellnessChart = null;
let correlationChart = null;
let rpmUpdateInterval;
let aiProcessingModal;
let chartInitializationLock = false; // Prevent concurrent chart initialization

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

// Debounced chart initialization to prevent flickering
let chartInitTimeout = null;
function initializeChartsDebounced() {
    if (chartInitTimeout) {
        clearTimeout(chartInitTimeout);
    }
    
    chartInitTimeout = setTimeout(() => {
        // Only initialize charts if elements exist and not already initialized
        if (document.getElementById('screen-time-chart') && !screenTimeChart) {
            initializeScreenTimeChart();
        }
        
        if (document.getElementById('wellness-chart') && !wellnessChart) {
            initializeWellnessChart();
        }
        
        if (document.getElementById('correlation-chart') && !correlationChart) {
            initializeCorrelationChart();
        }
    }, 100); // 100ms debounce
}

async function initializeScreenTimeChart() {
    // Prevent concurrent initialization
    if (chartInitializationLock) return;
    chartInitializationLock = true;
    
    const ctx = document.getElementById('screen-time-chart');
    if (!ctx) {
        chartInitializationLock = false;
        return;
    }

    // Destroy existing chart if it exists
    if (screenTimeChart) {
        screenTimeChart.destroy();
        screenTimeChart = null;
    }
    
    const existingChart = Chart.getChart(ctx);
    if (existingChart) {
        existingChart.destroy();
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
    } finally {
        chartInitializationLock = false;
    }
}

function initializeWellnessChart() {
    // Prevent concurrent initialization
    if (chartInitializationLock) return;
    
    const ctx = document.getElementById('wellness-chart');
    if (!ctx) return;

    // Destroy existing chart if it exists
    if (wellnessChart) {
        wellnessChart.destroy();
        wellnessChart = null;
    }

    const existingChart = Chart.getChart(ctx);
    if (existingChart) {
        existingChart.destroy();
    }

    // Defensive: destroy any chart on this canvas before creating a new one
    if (typeof Chart !== 'undefined' && Chart.instances) {
        Object.values(Chart.instances).forEach(chart => {
            if (chart.canvas === ctx) chart.destroy();
        });
    }

    wellnessChart = new Chart(ctx, {
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
    // Prevent concurrent initialization
    if (chartInitializationLock) return;
    
    const canvas = document.getElementById('correlation-chart');
    if (!canvas) return;

    // Destroy existing chart if it exists
    if (correlationChart) {
        correlationChart.destroy();
        correlationChart = null;
    }

    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
        existingChart.destroy();
    }

    // Defensive: destroy any chart on this canvas before creating a new one
    if (typeof Chart !== 'undefined' && Chart.instances) {
        Object.values(Chart.instances).forEach(chart => {
            if (chart.canvas === canvas) chart.destroy();
        });
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

        correlationChart = new Chart(ctx, {
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
        button.addEventListener('click', () => {
            const assessmentType = button.dataset.assessmentType;
            if (assessmentType) {
                startAssessment(assessmentType);
            } else {
                console.error('No assessment type specified on the button.');
            }
        });
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
// CHAT FUNCTIONALITY
// ========================

let socket;

function initializeChat() {
    if (typeof io === 'undefined') {
        console.error('Socket.IO not loaded');
        return;
    }

    socket = io();

    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    if (!chatForm || !chatInput || !chatMessages) {
        return; // Not on the chat page
    }

    socket.on('connect', () => {
        console.log('Connected to chat server');
    });

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            appendMessage(message, 'user');
            socket.emit('chat_message', { message: message });
            chatInput.value = '';
        }
    });

    socket.on('chat_response', (data) => {
        appendMessage(data.reply, 'bot');
    });

    socket.on('error', (data) => {
        console.error('Chat error:', data.message);
        appendMessage(`Error: ${data.message}`, 'system');
    });

    function appendMessage(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${sender}`;
        messageElement.innerHTML = `<div class="message-bubble">${message}</div>`;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
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

    // Initialize chat
    initializeChat();
    
    // Initialize charts with debouncing to prevent flickering
    initializeChartsDebounced();
    
    console.log('MindFullHorizon JavaScript initialized successfully');
});
