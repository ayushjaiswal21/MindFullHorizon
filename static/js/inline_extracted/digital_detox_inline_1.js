
document.addEventListener('DOMContentLoaded', function() {
    let screenTimeChart;
    let correlationChart;

    // Handle screen_time_log data - use empty array if not available
    let screenTimeLog = window.screen_time_log || [];
    if (!Array.isArray(screenTimeLog)) {
        console.warn('Screen time log is not an array, using empty array');
        screenTimeLog = [];
    }

    function initializeCharts() {
        const screenTimeCtx = document.getElementById('screen-time-chart').getContext('2d');
        const correlationCtx = document.getElementById('correlation-chart').getContext('2d');

        if (screenTimeChart) {
            screenTimeChart.destroy();
        }
        if (correlationChart) {
            correlationChart.destroy();
        }

        const labels = screenTimeLog.map(log => log.date).reverse();
        const screenTimeData = screenTimeLog.map(log => log.hours).reverse();
        const academicData = screenTimeLog.map(log => log.academic_score).reverse();

        screenTimeChart = new Chart(screenTimeCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Screen Time (hours)',
                    data: screenTimeData,
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Hours' }
                    }
                }
            }
        });

        correlationChart = new Chart(correlationCtx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Screen Time vs. Academic Score',
                    data: screenTimeLog.map(log => ({ x: log.hours, y: log.academic_score })),
                    backgroundColor: 'rgba(153, 102, 255, 0.6)'
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: 'Screen Time (hours)' }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Academic Score' }
                    }
                }
            }
        });
    }

    initializeCharts();

    const form = document.getElementById('digital-detox-form');
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Saving...';

        const formData = new FormData(form);
        const data = {
            screen_time: formData.get('screen_time'),
            academic_score: formData.get('academic_score'),
            social_interactions: formData.get('social_interactions'),
            csrf_token: formData.get('csrf_token')
        };

        try {
            const response = await fetch('/api/log-digital-detox', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': data.csrf_token
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorText = await response.text();
                let errorMessage;
                try {
                    const errorData = JSON.parse(errorText);
                    errorMessage = errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                } catch {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }

            const result = await response.json();

            if (result.success) {
                // Update UI with new data
                const aiScore = result.ai_analysis?.ai_score || 'N/A';
                const aiSuggestion = result.ai_analysis?.ai_suggestion || 'No suggestion available';
                
                document.getElementById('ai-score').textContent = aiScore;
                document.getElementById('ai-suggestion').textContent = aiSuggestion;
                document.getElementById('last-analysis-time').textContent = new Date().toLocaleTimeString();
                
                // Add new data to the log and re-initialize charts
                if (result.log) {
                    screenTimeLog.push(result.log);
                    initializeCharts();
                }
                
                form.reset();
                
                // Show success message
                const formMessage = document.getElementById('form-message');
                formMessage.textContent = result.message || 'Data saved successfully!';
                formMessage.className = 'mt-4 text-green-600';
                formMessage.classList.remove('hidden');

            } else {
                throw new Error(result.message || 'Failed to save data.');
            }

        } catch (error) {
            const formMessage = document.getElementById('form-message');
            formMessage.textContent = error.message;
            formMessage.className = 'mt-4 text-red-600';
            formMessage.classList.remove('hidden');
        } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-save mr-2"></i>Save Today\'s Data';
        }
    });
});
