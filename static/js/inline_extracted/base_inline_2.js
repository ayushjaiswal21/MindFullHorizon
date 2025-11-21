
function isModalVisible(modal) {
  if (!modal) return false;
  if (modal.classList && modal.classList.contains('visible')) return true;
  if (modal.classList && !modal.classList.contains('hidden')) return true;
  const s = window.getComputedStyle(modal);
  return (s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0');
}

document.addEventListener('click', function (e) {
  try {
    const modal = document.getElementById('assessmentModal');
    if (isModalVisible(modal) && modal.contains(e.target)) {
      // If click is inside modal, ignore global handlers
      return;
    }
  } catch (err) { /* defensive */ }

  // existing global logic continues...
});

    document.addEventListener('DOMContentLoaded', function() {
        // Initialize socket.io connection with error handling
        if (typeof io !== 'undefined') {
            try {
                const socket = io({
                    transports: ['websocket'],
                    upgrade: false,
                    secure: true
                });
                
                socket.on('connect', function() {
                    console.log('Connected to WebSocket server');
                });
                
                socket.on('connect_error', function(error) {
                    console.error('WebSocket connection error:', error);
                });
                
                window.socket = socket; // Make socket available globally if needed
            } catch (error) {
                console.error('Error initializing WebSocket:', error);
            }
        } else {
            console.warn('Socket.IO not loaded. Some real-time features may not work.');
        }
    });
    