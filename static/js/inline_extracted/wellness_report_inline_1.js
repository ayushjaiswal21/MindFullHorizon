
const reportData = JSON.parse(document.getElementById('report-data').textContent);

document.addEventListener('DOMContentLoaded', function() {
    initializeWellnessTrendsChart();
    initializeMoodTrendsChart();
    initializeMhAssessmentTrendsChart();
});

function initializeWellnessTrendsChart() {
    const ctx = document.getElementById('wellness-trends-chart');
    if (!ctx) return;
    
    const wellnessData = reportData.wellness;
    
    if (!wellnessData || wellnessData.length === 0) return;
    
    // Sort data by date in ascending order for chart display
    wellnessData.sort((a, b) => new Date(a.date) - new Date(b.date));

    const dates = wellnessData.map(item => {
        const date = new Date(item.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    const screenTime = wellnessData.map(item => item.screen_time_hours);
    const academicScores = wellnessData.map(item => item.academic_score);
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Screen Time (Hours)',
                    data: screenTime,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    yAxisID: 'y',
                    tension: 0.3
                },
                {
                    label: 'Academic Score',
                    data: academicScores,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Screen Time (Hours)'
                    },
                    min: 0
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Academic Score'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    min: 0,
                    max: 100
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        afterLabel: function(context) {
                            if (context.datasetIndex === 0) return 'Hours of screen time';
                            if (context.datasetIndex === 1) return 'Academic performance score';
                            return '';
                        }
                    }
                }
            }
        }
    });
}

function initializeMoodTrendsChart() {
    const ctx = document.getElementById('mood-trends-chart');
    if (!ctx) return;

    const labels = reportData.mood_labels;
    const data = reportData.mood_data;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(dateString => new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
            datasets: [{
                label: 'Mood Score (1-10)',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Mood Score'
                    },
                    min: 0,
                    max: 10
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            return new Date(context[0].label).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
                        },
                        label: function(context) {
                            return `Mood Score: ${context.raw}`;
                        }
                    }
                }
            }
        }
    });
}

function initializeMhAssessmentTrendsChart() {
    const ctx = document.getElementById('mh-assessment-trends-chart');
    if (!ctx) return;

    const labels = reportData.mh_labels;
    const gad7Data = reportData.gad7;
    const phq9Data = reportData.phq9;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(dateString => new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
            datasets: [
                {
                    label: 'GAD-7 Score',
                    data: gad7Data,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    tension: 0.3,
                    spanGaps: true // Connects null data points
                },
                {
                    label: 'PHQ-9 Score',
                    data: phq9Data,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.3,
                    spanGaps: true // Connects null data points
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Assessment Score'
                    },
                    min: 0
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            return new Date(context[0].label).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
                        },
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.raw !== null) {
                                label += context.raw;
                            } else {
                                label += 'No Data';
                            }
                            return label;
                        }
                    }
                }
            }
        }
    });
}

function exportReport() {
    // Quote every field and neutralise spreadsheet formulas (=, +, -, @ at the start).
    const cell = v => { v = String(v ?? ''); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
    const row = [reportData.patient, reportData.email, reportData.institution, reportData.overall_score,
                 reportData.points, reportData.streak, new Date().toLocaleDateString()].map(cell).join(',');
    const csv = "Patient,Email,Institution,Overall Score,Total Points,Current Streak,Report Date
" + row;

    const link = document.createElement("a");
    link.setAttribute("href", "data:text/csv;charset=utf-8," + encodeURIComponent(csv));
    link.setAttribute("download", `wellness_report_${String(reportData.patient).replace(/\s+/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
