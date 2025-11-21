document.addEventListener('DOMContentLoaded', function () {
    const chatForm = document.getElementById('chat-form');
    const chatContainer = document.getElementById('chat-container');
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    if (chatForm) {
        chatForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            const userInput = document.getElementById('chat-input').value;
            if (!userInput) return;

            // Display user message
            appendMessage(userInput, 'user-message');
            document.getElementById('chat-input').value = '';

            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ prompt: userInput })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                
                // Display AI response
                appendMessage(data.response, 'ai-message');

            } catch (error) {
                console.error('Error fetching AI response:', error);
                appendMessage('Sorry, something went wrong. Please try again.', 'ai-message error');
            }
        });
    }

    function appendMessage(text, className) {
        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${className}`;
        messageElement.textContent = text;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});

// Breathing exercise guided session function (globally accessible)
function startGuidedSession(type, name, durationMinutes) {
    // Convert duration to seconds
    const duration = durationMinutes * 60;
    
    // Update UI to show guided session started
    const instruction = document.getElementById('breathing-instruction');
    if (instruction) {
        instruction.textContent = `Starting ${name} session...`;
    }
    
    // Show timer
    const timerDisplay = document.getElementById('timer-display');
    if (timerDisplay) {
        timerDisplay.classList.remove('hidden');
    }
    
    // Start the session timer
    let remainingTime = duration;
    const sessionInterval = setInterval(() => {
        remainingTime--;
        updateSessionTimer(remainingTime);
        
        if (remainingTime <= 0) {
            clearInterval(sessionInterval);
            if (instruction) {
                instruction.textContent = `${name} session completed!`;
            }
            // Reset breathing
            if (typeof stopBreathing === 'function') {
                stopBreathing();
            }
        }
    }, 1000);
    
    // Start appropriate breathing pattern based on type
    if (type === 'breathing') {
        if (name === 'morning') {
            startBreathing('box'); // Energizing
        } else if (name === 'stress') {
            startBreathing('478'); // Calming
        } else if (name === 'sleep') {
            startBreathing('coherence'); // Relaxing
        }
    }
}

// Helper function to update session timer (globally accessible)
function updateSessionTimer(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    const timerDisplay = document.getElementById('timer-display');
    if (timerDisplay) {
        timerDisplay.textContent = 
            `${minutes}:${remainingSeconds < 10 ? '0' : ''}${remainingSeconds}`;
    }
}