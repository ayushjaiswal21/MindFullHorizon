
// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeMoodChart();
    initializeAssessmentChart();
});






function initializeMoodChart() {
    const canvas = document.getElementById('moodChart');
    const ctx = canvas.getContext('2d');
    
    // Get data from Flask template
    const moodData = JSON.parse('{{ mood_data | tojson }}');
    
    if (moodData.length === 0) {
        // Display a message if no data
        ctx.font = '16px Inter';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#6B7280';
        ctx.fillText('No mood data available yet', canvas.width / 2, canvas.height / 2);
        ctx.fillText('Start tracking your daily mood to see trends here', canvas.width / 2, canvas.height / 2 + 25);
        return;
    }
    
    // Extract dates and mood scores
    const dates = moodData.map(item => {
        const date = new Date(item.date);
        return (date.getMonth() + 1) + '/' + date.getDate();
    });
    const scores = moodData.map(item => item.score);
    
    drawLineChart(ctx, canvas, dates, scores, 'Mood Score', '#F59E0B');
}

function initializeAssessmentChart() {
    const canvas = document.getElementById('assessmentChart');
    const ctx = canvas.getContext('2d');
    
    // Get data from Flask template
    const labels = JSON.parse('{{ assessment_chart_labels | tojson }}');
    const gad7Data = JSON.parse('{{ assessment_chart_gad7_data | tojson }}');
    const phq9Data = JSON.parse('{{ assessment_chart_phq9_data | tojson }}');

    if (labels.length === 0) {
        // Display a message if no data
        ctx.font = '16px Inter';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#6B7280';
        ctx.fillText('No assessment data available yet', canvas.width / 2, canvas.height / 2);
        ctx.fillText('Complete your first assessment to see progress here', canvas.width / 2, canvas.height / 2 + 25);
        return;
    }
    
    drawDualLineChart(ctx, canvas, labels, gad7Data, phq9Data);
}

function drawLineChart(ctx, canvas, xData, yData, label, color) {
    const padding = 40;
    const width = canvas.width - 2 * padding;
    const height = canvas.height - 2 * padding;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Find min and max values
    const minY = Math.min(...yData);
    const maxY = Math.max(...yData);
    const yRange = maxY - minY || 1; // Avoid division by zero
    
    // Draw axes
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    
    // Y-axis
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, canvas.height - padding);
    ctx.stroke();
    
    // X-axis
    ctx.beginPath();
    ctx.moveTo(padding, canvas.height - padding);
    ctx.lineTo(canvas.width - padding, canvas.height - padding);
    ctx.stroke();
    
    // Draw grid lines and labels
    ctx.font = '12px Inter';
    ctx.fillStyle = '#6B7280';
    ctx.textAlign = 'center';
    
    // Y-axis labels
    for (let i = 0; i <= 5; i++) {
        const y = canvas.height - padding - (i / 5) * height;
        const value = minY + (i / 5) * yRange;
        
        ctx.fillText(value.toFixed(1), padding - 15, y + 4);
        
        if (i > 0) {
            ctx.strokeStyle = '#F3F4F6';
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(canvas.width - padding, y);
            ctx.stroke();
        }
    }
    
    // X-axis labels
    const step = Math.ceil(xData.length / 6);
    for (let i = 0; i < xData.length; i += step) {
        const x = padding + (i / (xData.length - 1)) * width;
        ctx.fillText(xData[i], x, canvas.height - padding + 20);
    }
    
    // Draw data line
    drawDataLine(ctx, canvas, padding, width, height, yData, minY, yRange, color);
}

function drawDualLineChart(ctx, canvas, xLabels, data1, data2) {
    const padding = 40;
    const width = canvas.width - 2 * padding;
    const height = canvas.height - 2 * padding;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Find min and max values across both datasets
    const allData = [...data1, ...data2];
    const minY = Math.min(...allData);
    const maxY = Math.max(...allData);
    const yRange = maxY - minY || 1;
    
    // Draw axes (same as single line chart)
    ctx.strokeStyle = '#E5E7EB';
    ctx.lineWidth = 1;
    
    // Y-axis
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, canvas.height - padding);
    ctx.stroke();
    
    // X-axis
    ctx.beginPath();
    ctx.moveTo(padding, canvas.height - padding);
    ctx.lineTo(canvas.width - padding, canvas.height - padding);
    ctx.stroke();
    
    // Draw grid and labels (same as single line chart)
    ctx.font = '12px Inter';
    ctx.fillStyle = '#6B7280';
    ctx.textAlign = 'center';
    
    // Y-axis labels
    for (let i = 0; i <= 5; i++) {
        const y = canvas.height - padding - (i / 5) * height;
        const value = minY + (i / 5) * yRange;
        
        ctx.fillText(value.toFixed(0), padding - 15, y + 4);
        
        if (i > 0) {
            ctx.strokeStyle = '#F3F4F6';
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(canvas.width - padding, y);
            ctx.stroke();
        }
    }
    
    // X-axis labels
    const step = Math.ceil(xLabels.length / 6);
    for (let i = 0; i < xLabels.length; i += step) {
        const x = padding + (i / (xLabels.length - 1)) * width;
        ctx.fillText(xLabels[i], x, canvas.height - padding + 20);
    }
    
    // Draw both data lines
    drawDataLine(ctx, canvas, padding, width, height, data1, minY, yRange, '#3B82F6'); // Blue for GAD-7
    drawDataLine(ctx, canvas, padding, width, height, data2, minY, yRange, '#8B5CF6'); // Purple for PHQ-9
    
    // Draw legend
    ctx.font = '12px Inter';
    ctx.textAlign = 'left';
    
    // GAD-7 legend
    ctx.fillStyle = '#3B82F6';
    ctx.fillRect(canvas.width - 150, 20, 15, 3);
    ctx.fillStyle = '#374151';
    ctx.fillText('GAD-7 (Anxiety)', canvas.width - 130, 25);
    
    // PHQ-9 legend
    ctx.fillStyle = '#8B5CF6';
    ctx.fillRect(canvas.width - 150, 40, 15, 3);
    ctx.fillStyle = '#374151';
    ctx.fillText('PHQ-9 (Depression)', canvas.width - 130, 45);
}

function drawDataLine(ctx, canvas, padding, width, height, data, minY, yRange, color) {
    if (data.length === 0) return;
    
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 2;
    
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
        const x = padding + (i / (data.length - 1)) * width;
        const y = canvas.height - padding - ((data[i] - minY) / yRange) * height;
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
        
        // Draw data points
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, 2 * Math.PI);
        ctx.fill();
        ctx.beginPath();
    }
    ctx.stroke();
}

// Add goal completion functionality
document.addEventListener('DOMContentLoaded', function() {
    // Handle goal checkbox changes
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('goal-checkbox')) {
            const goalId = e.target.getAttribute('data-goal-id');
            const isCompleted = e.target.checked;
            
            updateGoalStatus(goalId, isCompleted);
        }
    });
    
    // Handle add goal form submission
    const addGoalForm = document.getElementById('add-goal-form');
    if (addGoalForm) {
        addGoalForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const description = document.getElementById('new-goal-description').value.trim();
            if (description) {
                addNewGoal(description);
            }
        });
    }
});

function updateGoalStatus(goalId, isCompleted) {
    fetch(`/patient/api/goals/${goalId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify({
            completed: isCompleted
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message || 'Goal updated successfully!', 'success');
            // Update the goal container background
            const goalContainer = document.querySelector(`input[data-goal-id="${goalId}"]`).closest('div');
            if (isCompleted) {
                goalContainer.classList.remove('bg-gray-100');
                goalContainer.classList.add('bg-green-100');
            } else {
                goalContainer.classList.remove('bg-green-100');
                goalContainer.classList.add('bg-gray-100');
            }
        } else {
            showNotification(data.message || 'Failed to update goal', 'error');
            // Revert checkbox state
            document.querySelector(`input[data-goal-id="${goalId}"]`).checked = !isCompleted;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating goal', 'error');
        // Revert checkbox state
        document.querySelector(`input[data-goal-id="${goalId}"]`).checked = !isCompleted;
    });
}

function addNewGoal(description) {
    fetch('/patient/api/goals', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify({
            title: description,
            category: 'mental_health',
            priority: 'medium'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message || 'Goal added successfully!', 'success');
            document.getElementById('new-goal-description').value = '';
            // Reload the page to show the new goal
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            showNotification(data.message || 'Failed to add goal', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error adding goal', 'error');
    });
}

function setNewGoal() {
    // Redirect to goals management page
    window.location.href = '/goals';
}

function showNotification(message, type) {
    // Simple notification system
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 p-4 rounded-lg text-white z-50 ${type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500'}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}
(function(){
  // Wrap fetch used for progress with debug output so when server returns 500, client logs useful info
  const originalFetch = window.fetch;
  window.fetch = function(input, init){
    if (typeof input === 'string' && input.includes('/api/progress')) {
      console.debug('[DEBUG] calling progress API', input, init);
      return originalFetch(input, init).then(res => {
        if (!res.ok) {
          console.warn('[DEBUG] progress API failed', res.status, res.statusText);
        }
        return res;
      }).catch(err => {
        console.error('[DEBUG] progress API network error', err);
        throw err;
      });
    }
    return originalFetch(input, init);
  };
})();
