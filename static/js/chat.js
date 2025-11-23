document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('chat-messages');
  if (container) {
    const chatId = container.dataset.chatId || 1;
    let lastMessageCount = 0;
    let pollingInterval = null;
    
    async function fetchMessages() {
      try {
        const res = await fetch(`/api/chats/${chatId}/messages`);
        if (!res.ok) {
          if (res.status === 429) {
            console.log('Rate limited, waiting longer...');
            // If rate limited, increase polling interval
            if (pollingInterval) {
              clearInterval(pollingInterval);
              pollingInterval = setInterval(fetchMessages, 30000); // 30 seconds
            }
          }
          return;
        }
        const msgs = await res.json();
        
        // Only update if there are new messages to avoid clearing existing ones
        if (msgs.length > lastMessageCount) {
          // Get current messages to avoid duplicates
          const currentMessages = container.querySelectorAll('.chat-message, [class*="bg-"]');
          const currentTexts = Array.from(currentMessages).map(el => {
            const textEl = el.querySelector('p:last-child');
            return textEl ? textEl.textContent.trim() : '';
          });
          
          // Add only new messages
          msgs.forEach(msg => {
            if (!currentTexts.includes(msg.text)) {
              const msgDiv = document.createElement('div');
              msgDiv.className = 'mb-2';
              msgDiv.innerHTML = `<div><b>${msg.user}:</b> ${msg.text}</div>`;
              container.appendChild(msgDiv);
            }
          });
          
          lastMessageCount = msgs.length;
          container.scrollTop = container.scrollHeight;
        }
      } catch (err) {
        console.error('Error fetching messages:', err);
      }
    }
    
    // Clear any existing polling
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }
    
    // Initial fetch
    fetchMessages();
    // Poll every 30 seconds to avoid rate limiting
    pollingInterval = setInterval(fetchMessages, 30000);
    
    // Clean up when page unloads
    window.addEventListener('beforeunload', () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    });
  }
});