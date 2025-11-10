
// Initialize Socket.IO
const socket = io();

// Connect to notification system
socket.on('connect', function() {
    console.log('Connected to notification system');
});

// Handle appointment accepted notifications
socket.on('appointment_accepted', function(data) {
    showToast('Appointment Accepted', `Your appointment on ${data.date} at ${data.time} has been accepted!`, 'success');
    showBrowserNotification('Appointment Accepted', `Your ${data.type} appointment on ${data.date} at ${data.time} has been accepted!`);
    
    // Refresh the page to update appointment status
    setTimeout(() => {
        window.location.reload();
    }, 2000);
});

// Handle appointment rejected notifications
socket.on('appointment_rejected', function(data) {
    showToast('Appointment Rejected', `Your appointment on ${data.date} at ${data.time} was rejected. Reason: ${data.reason}`, 'error');
    showBrowserNotification('Appointment Rejected', `Your ${data.type} appointment on ${data.date} at ${data.time} was rejected. Reason: ${data.reason}`);
    
    // Refresh the page to update appointment status
    setTimeout(() => {
        window.location.reload();
    }, 2000);
});

function showToast(title, message, type) {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    
    const bgColor = {
        'success': 'bg-green-500',
        'error': 'bg-red-500',
        'info': 'bg-blue-500',
        'warning': 'bg-yellow-500'
    }[type] || 'bg-gray-500';
    
    toast.className = `${bgColor} text-white px-6 py-4 rounded-lg shadow-lg max-w-sm transform transition-all duration-300 ease-in-out`;
    toast.innerHTML = `
        <div class="flex items-start">
            <div class="flex-1">
                <div class="font-semibold">${title}</div>
                <div class="text-sm mt-1">${message}</div>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

function showBrowserNotification(title, message) {
    if (Notification.permission === 'granted') {
        new Notification(title, {
            body: message,
            icon: '/static/images/icon-192x192.png',
            badge: '/static/images/icon-192x192.png'
        });
    }
}

// Request notification permission on page load
document.addEventListener('DOMContentLoaded', function() {
    if (Notification.permission === 'default') {
        Notification.requestPermission().then(function(permission) {
            if (permission === 'granted') {
                console.log('Notification permission granted');
            }
        });
    }
        <!-- Modal for Assessment -->
        <div id="assessmentModal" class="modal-overlay">
            <div class="modal-content">
                <span class="close-button">&times;</span>
                <h4>Assessment is loading...</h4>
                <p>Please wait a moment.</p>
            </div>
        </div>

        <style>
            .modal-overlay {
                display: none; /* Hidden by default */
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.6);
            }
            .modal-content {
                background-color: #fff;
                margin: 15% auto;
                padding: 25px;
                border-radius: 8px;
                width: 90%;
                max-width: 550px;
                position: relative;
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            }
            .close-button {
                color: #aaa;
                position: absolute;
                top: 10px;
                right: 15px;
                font-size: 28px;
                font-weight: bold;
                cursor: pointer;
            }
        </style>

        <script>
            // This script must run after the HTML for the modal exists on the page
            document.addEventListener('DOMContentLoaded', function() {

                // Find the elements we need
                const modal = document.getElementById("assessmentModal");
                const closeButton = modal.querySelector(".close-button");
                const startAssessmentButtons = document.querySelectorAll(".start-assessment-btn"); // Add this class to your 'Start Assessment' buttons

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
                    button.addEventListener('click', openModal);
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

            });
        