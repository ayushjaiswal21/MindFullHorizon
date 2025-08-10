// Function to handle login based on user role
function handleLogin(role) {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    // In a real application, this would be an API call
    // For now, we'll use dummy logic to redirect
    if (role === 'patient') {
        window.location.href = 'patient_dashboard.html';
    } else if (role === 'doctor') {
        window.location.href = 'doctor_dashboard.html';
    } else {
        showMessageBox("Error", "Invalid credentials. Please try again.");
    }
}

// Function to handle registration (placeholder)
function handleRegister() {
    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const role = document.getElementById('register-role').value;

    // This would be a real API call to your Flask backend
    // For now, we'll show a message and redirect
    showMessageBox("Success", `Account created for ${name} (${role}). You can now log in.`);
    setTimeout(() => {
        window.location.href = 'login.html';
    }, 2000);
}

// Function to handle logout
function handleLogout() {
    showMessageBox("Logged Out", "You have been successfully logged out.");
    setTimeout(() => {
        window.location.href = 'index.html';
    }, 2000);
}

// Function to handle assessment submission (placeholder)
document.addEventListener('DOMContentLoaded', () => {
    const assessmentForm = document.getElementById('assessment-form');
    if (assessmentForm) {
        assessmentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            // This would be a real API call to submit assessment data
            showMessageBox("Assessment Submitted", "Your assessment has been submitted for analysis.");
            setTimeout(() => {
                window.location.href = 'result.html';
            }, 1000);
        });
    }

    const feedbackForm = document.getElementById('feedback-form');
    if (feedbackForm) {
        feedbackForm.addEventListener('submit', function(e) {
            e.preventDefault();
            // This would be a real API call to submit feedback
            showMessageBox("Feedback Submitted", "Thank you for your valuable feedback! It helps improve our model.");
            setTimeout(() => {
                window.location.href = 'patient_dashboard.html';
            }, 1000);
        });
    }

    // Function to view a specific patient's profile
    window.viewPatientProfile = function(name, risk) {
        window.location.href = `patient_profile.html?name=${encodeURIComponent(name)}&risk=${encodeURIComponent(risk)}`;
    };
});

// Custom Message Box Functions
function showMessageBox(title, message) {
    const messageBox = document.getElementById('message-box');
    document.getElementById('message-title').innerText = title;
    document.getElementById('message-text').innerText = message;
    messageBox.style.display = 'flex';
}

function hideMessageBox() {
    const messageBox = document.getElementById('message-box');
    messageBox.style.display = 'none';
}
