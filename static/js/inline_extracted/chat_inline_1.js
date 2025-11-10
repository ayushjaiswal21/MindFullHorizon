
// Initialize chat when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (typeof io !== 'undefined') {
        // Chat functionality is initialized in scripts.js
        console.log('Chat page loaded, SocketIO should initialize');
    } else {
        console.error('SocketIO not loaded');
        showChatError('Chat service unavailable. Please refresh the page.');
    }
});

function showChatError(message) {
    const chatMessages = document.getElementById('chat-messages');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'chat-message text-center';
    errorDiv.innerHTML = `<div class="inline-block px-4 py-2 rounded-lg bg-red-100 text-red-800"><p><i class="fas fa-exclamation-triangle mr-2"></i>${message}</p></div>`;
    chatMessages.appendChild(errorDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}
