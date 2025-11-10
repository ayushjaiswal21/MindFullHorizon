
document.addEventListener('DOMContentLoaded', function() {
    // Screen Time Chart
    const screenTimeCtx = document.getElementById('screenTimeChart').getContext('2d');
    new Chart(screenTimeCtx, {
        type: 'line',
        data: {
            labels: {{ analytics_data.chart_labels | tojson }},
            datasets: [{
                label: 'Average Daily Screen Time (hours)',
                data: {{ analytics_data.screen_time_data | tojson }},
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Daily Screen Time Trends'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    // Wellness Score Chart
    const wellnessCtx = document.getElementById('wellnessChart').getContext('2d');
    new Chart(wellnessCtx, {
        type: 'line',
        data: {
            labels: {{ analytics_data.chart_labels | tojson }},
            datasets: [{
                label: 'Average Wellness Score',
                data: {{ analytics_data.wellness_score_data | tojson }},
                borderColor: 'rgb(239, 68, 68)',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Wellness Score Trends'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 5
                }
            }
        }
    });
});
