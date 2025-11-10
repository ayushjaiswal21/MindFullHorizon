document.addEventListener('DOMContentLoaded', function() {
    // Connect breathing exercise buttons to functions from scripts.js
    document.getElementById('start-box-breathing').addEventListener('click', function() {
        startBreathing('box');
    });
    
    document.getElementById('start-4-7-8-breathing').addEventListener('click', function() {
        startBreathing('478');
    });
    
    document.getElementById('start-diaphragmatic-breathing').addEventListener('click', function() {
        startBreathing('coherence'); // Using coherence pattern for diaphragmatic
    });
    
    document.getElementById('start-pursed-lip-breathing').addEventListener('click', function() {
        startBreathing('triangle'); // Using triangle pattern for pursed-lip
    });
    
    // Session controls
    document.getElementById('start-btn').addEventListener('click', function() {
        startSession();
    });
    
    document.getElementById('pause-btn').addEventListener('click', function() {
        pauseSession();
    });
    
    document.getElementById('stop-btn').addEventListener('click', function() {
        stopSession();
    });

    // New event listener code to append
    document.querySelectorAll('.start-guided-session-btn').forEach(button => {
        button.addEventListener('click', function() {
            const sessionType = this.dataset.sessionType;
            const sessionName = this.dataset.sessionName;
            const sessionDuration = parseInt(this.dataset.sessionDuration);
            startGuidedSession(sessionType, sessionName, sessionDuration);
        });
    });
});

// startGuidedSession function is already defined in scripts.js