
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
    