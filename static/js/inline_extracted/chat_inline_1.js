/* Chat UI. All server and user text is inserted with textContent / DOM nodes (no HTML parsing). */
const BOT_NAME = 'Anya';
let crisisShown = false;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function appendLocalMessage(user, text) {
  const chatMessages = document.getElementById('chat-messages');
  if (!chatMessages) return;
  const styles = {
    'You': ['bg-blue-100 ml-auto max-w-xs', 'text-blue-800', 'text-gray-800'],
    [BOT_NAME]: ['bg-gray-100 mr-auto max-w-xs', 'text-gray-800', 'text-gray-700'],
  };
  const [box, nameCls, textCls] = styles[user] || ['bg-yellow-100 mx-auto max-w-xs text-center', 'text-yellow-800', 'text-yellow-700'];
  const msgDiv = el('div', 'mb-4 p-3 rounded-lg ' + box);
  msgDiv.append(el('p', 'font-semibold text-sm ' + nameCls, user), el('p', textCls, String(text)));
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getBanner() {
  let banner = document.getElementById('chat-banner');
  if (!banner) {
    banner = el('div', 'p-4 mb-4');
    banner.id = 'chat-banner';
    banner.setAttribute('role', 'alert');
    (document.querySelector('.container') || document.body).prepend(banner);
  }
  banner.textContent = '';
  banner.style.display = 'block';
  return banner;
}

function helplineList(helplines) {
  const ul = el('ul', 'mt-2 space-y-1');
  (Array.isArray(helplines) ? helplines : []).forEach(h => {
    const li = el('li');
    const tel = String(h.tel || '').replace(/[^0-9]/g, '');
    const label = h.name + ': ' + h.number;
    if (tel) {
      const a = el('a', 'font-semibold underline', label);
      a.href = 'tel:' + tel;
      li.appendChild(a);
    } else {
      li.appendChild(el('span', 'font-semibold', label));
    }
    li.append(' (' + h.hours + ')');
    ul.appendChild(li);
  });
  return ul;
}

/* Crisis: prominent card with the helplines the API returned; cheerful prompts go away. */
function showCrisisBanner(helplines) {
  crisisShown = true;
  const banner = getBanner();
  banner.className = 'bg-red-100 border-l-4 border-red-600 text-red-900 p-4 mb-4 text-lg';
  banner.append(el('p', 'font-bold', 'You are not alone. If you are in immediate danger, call 112 now.'),
                el('p', null, 'Free support, any time:'), helplineList(helplines));
  document.querySelectorAll('.cheerful-prompt').forEach(n => n.remove());
  const input = document.getElementById('chat-input');
  if (input) input.placeholder = 'Type here when you are ready...';
  banner.scrollIntoView({ block: 'nearest' });
}

function showSupportInfo(helplines) {
  const banner = getBanner();
  banner.className = 'bg-blue-50 border-l-4 border-blue-400 text-blue-900 p-3 mb-4 text-sm';
  banner.append(el('p', null, 'Support lines you can use or share:'), helplineList(helplines));
}

function showAppointmentBanner(onBook) {
  const banner = getBanner();
  banner.className = 'bg-yellow-200 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-4';
  const btn = el('button', 'ml-2 bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded', 'Book');
  btn.type = 'button';
  btn.addEventListener('click', onBook);
  banner.append('It may help to speak to a clinician. ', btn);
}

document.addEventListener('DOMContentLoaded', function () {
  const chatForm = document.getElementById('chat-form');
  const chatInput = document.getElementById('chat-input');
  const chatMessages = document.getElementById('chat-messages');
  if (!chatForm || !chatInput || !chatMessages) return;

  appendLocalMessage(BOT_NAME, "Hello, I'm Anya, an AI companion (not a therapist). How are you feeling today?");

  chatForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    e.stopPropagation();

    const text = chatInput.value.trim();
    if (!text) return;

    const csrfToken = document.querySelector('input[name="csrf_token"]');
    if (!csrfToken) {
      appendLocalMessage('System', 'Error: Security token not found. Please refresh the page.');
      return;
    }
    const tokenValue = csrfToken.value;

    appendLocalMessage('You', text);
    chatInput.value = '';

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': tokenValue },
        body: JSON.stringify({ message: text })
      });
      const json = await res.json();

      if (json.ok) {
        appendLocalMessage(BOT_NAME, json.reply);
        const hasLines = Array.isArray(json.helplines) && json.helplines.length > 0;
        if (json.escalate || json.recommended_action === 'emergency_hotline') {
          showCrisisBanner(json.helplines);
        } else if (json.recommended_action === 'recommend_appointment' && !crisisShown) {
          showAppointmentBanner(async () => {
            await fetch('/api/chat/book-appointment', {
              method: 'POST', credentials: 'include',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': tokenValue },
              body: JSON.stringify({ user_message: text })
            });
            alert('Appointment requested. A provider will contact you shortly.');
            document.getElementById('chat-banner').style.display = 'none';
          });
        } else if (hasLines && !crisisShown) {
          showSupportInfo(json.helplines);
        }
      } else {
        appendLocalMessage('System', 'Sorry, something went wrong. Try again later.');
      }
    } catch (err) {
      appendLocalMessage('System', 'Network error. Please check your connection and try again.');
    }
  });
});

function showChatError(message) {
  const chatMessages = document.getElementById('chat-messages');
  if (chatMessages) appendLocalMessage('System', message);
}
