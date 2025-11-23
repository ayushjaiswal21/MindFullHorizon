
/* Helper UI functions */
function appendLocalMessage(user, text) {
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) return;
  const msgDiv = document.createElement('div');
  msgDiv.className = 'mb-4 p-3 rounded-lg';
  
  // Different styling for user vs bot
  if (user === 'You') {
    msgDiv.className += ' bg-blue-100 ml-auto max-w-xs';
    msgDiv.innerHTML = `<p class="font-semibold text-blue-800 text-sm">${user}</p><p class="text-gray-800">${text}</p>`;
  } else if (user === 'Dr. Anya') {
    msgDiv.className += ' bg-gray-100 mr-auto max-w-xs';
    msgDiv.innerHTML = `<p class="font-semibold text-gray-800 text-sm">${user}</p><p class="text-gray-700">${text}</p>`;
  } else {
    msgDiv.className += ' bg-yellow-100 mx-auto max-w-xs text-center';
    msgDiv.innerHTML = `<p class="font-semibold text-yellow-800 text-sm">${user}</p><p class="text-yellow-700">${text}</p>`;
  }
  
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showBanner(message) {
    const banner = document.getElementById('chat-banner');
    if (!banner) {
        const topLevelContainer = document.querySelector('.container') || document.body;
        const newBanner = document.createElement('div');
        newBanner.id = 'chat-banner';
        newBanner.className = 'bg-yellow-200 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-4';
        newBanner.setAttribute('role', 'alert');
        topLevelContainer.prepend(newBanner);
        newBanner.innerHTML = message;
    } else {
        banner.innerHTML = message;
        banner.style.display = 'block';
    }
}


/* replace or add in chat_inline_1.js */
document.addEventListener('DOMContentLoaded', function() {
    console.log('Chat script loaded');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    
    if (!chatForm) {
        console.error('Chat form not found');
        return;
    }
    if (!chatInput) {
        console.error('Chat input not found');
        return;
    }
    if (!chatMessages) {
        console.error('Chat messages container not found');
        return;
    }
    
    // Add welcome message
    appendLocalMessage('Dr. Anya', 'Hello! I\'m Dr. Anya, your AI psychologist. How are you feeling today?');
    
    chatForm.addEventListener('submit', async function(e){
      console.log('Form submit triggered');
      e.preventDefault();
      e.stopPropagation(); // Extra prevention of default behavior
      
      const text = chatInput.value.trim();
      console.log('Message text:', text);
      if(!text) return;
      
      // Get CSRF token from the form input
      const csrfToken = document.querySelector('input[name="csrf_token"]');
      if (!csrfToken) {
        console.error('CSRF token input not found');
        appendLocalMessage('System', 'Error: Security token not found. Please refresh the page.');
        return;
      }
      
      const tokenValue = csrfToken.value;
      console.log('CSRF token found:', tokenValue ? 'Yes' : 'No');
      
      appendLocalMessage('You', text);
      chatInput.value = '';
    
      try {
        console.log('Sending request to /api/chat');
        const res = await fetch('/api/chat', {
          method: 'POST',
          credentials: 'include',
          headers: { 
              'Content-Type': 'application/json',
              'X-CSRFToken': tokenValue
          },
          body: JSON.stringify({ message: text })
        });
        
        console.log('Response status:', res.status);
        const json = await res.json();
        console.log('Response data:', json);
        
        if (json.ok) {
          appendLocalMessage('Dr. Anya', json.reply);
          if (json.recommended_action === 'recommend_appointment') {
            showBanner("It may help to speak to a clinician. <button id='bookNow' class='bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded'>Book</button>");
            document.getElementById('bookNow').addEventListener('click', async ()=>{
              await fetch('/api/chat/book-appointment', {
                method: 'POST', credentials:'include',
                headers: {
                    'Content-Type':'application/json',
                    'X-CSRFToken': tokenValue
                },
                body: JSON.stringify({ user_message: text })
              });
              alert('Appointment requested. A provider will contact you shortly.');
              document.getElementById('chat-banner').style.display = 'none';
            });
          } else if (json.recommended_action === 'emergency_hotline') {
            showBanner("If you are in immediate danger, please call your local emergency services now.");
          }
        } else {
          console.error('API returned error:', json);
          appendLocalMessage('System', 'Sorry, something went wrong. Try again later.');
        }
      } catch (err) {
        console.error('Network error:', err);
        appendLocalMessage('System', 'Network error. Please check your connection and try again.');
      }
    });

    if (typeof io !== 'undefined') {
        // Chat functionality is initialized in scripts.js
        console.log('Chat page loaded, SocketIO should initialize');
    } else {
        // It's fine if socketio is not there, we are using fetch
        // console.error('SocketIO not loaded');
        // showChatError('Chat service unavailable. Please refresh the page.');
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
