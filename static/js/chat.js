document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('chat-messages');
  if (container) {
    const chatId = container.dataset.chatId || 1;
    async function fetchMessages() {
      const res = await fetch(`/api/chats/${chatId}/messages`);
      if (!res.ok) return;
      const msgs = await res.json();
      container.innerHTML = msgs.map(m => `<div><b>${m.user}:</b> ${m.text}</div>`).join('');
    }
    fetchMessages();
    setInterval(fetchMessages, 5000);
  }
});