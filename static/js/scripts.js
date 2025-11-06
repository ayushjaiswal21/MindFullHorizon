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