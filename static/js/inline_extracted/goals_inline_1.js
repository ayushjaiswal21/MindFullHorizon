
let currentGoalId = null;

// Load goals on page load
document.addEventListener('DOMContentLoaded', function() {
    loadGoals();
    
    // Add event listeners
    document.getElementById('add-goal-btn').addEventListener('click', showAddGoalModal);
    document.getElementById('goal-form').addEventListener('submit', handleGoalSubmit);
    document.getElementById('progress-form').addEventListener('submit', handleProgressSubmit);
});

function loadGoals() {
    fetch('/patient/api/goals', {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Server returned non-JSON response. You may need to log in again.');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                displayGoals(data.goals);
            } else {
                showMessage('Error loading goals', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Error loading goals', 'error');
        });
}

function displayGoals(goals) {
    const container = document.getElementById('goals-container');
    const emptyState = document.getElementById('empty-state');
    
    if (goals.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }
    
    emptyState.classList.add('hidden');
    
    container.innerHTML = goals.map(goal => `
        <div class="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow duration-300">
            <div class="flex justify-between items-start mb-4">
                <div class="flex-1">
                    <h3 class="text-xl font-bold text-gray-900 mb-2">${goal.title}</h3>
                    <p class="text-gray-600 text-sm mb-2">${goal.description || 'No description'}</p>
                    <div class="flex items-center space-x-2 mb-2">
                        <span class="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">${goal.category.replace('_', ' ')}</span>
                        <span class="px-2 py-1 ${getPriorityColor(goal.priority)} text-xs rounded-full">${goal.priority}</span>
                        <span class="px-2 py-1 ${getStatusColor(goal.status)} text-xs rounded-full">${goal.status}</span>
                    </div>
                </div>
                <div class="flex space-x-2">
                    <button onclick="showProgressModal(${goal.id}, ${goal.current_value}, '${goal.status}')" 
                            class="text-green-600 hover:text-green-800" title="Update Progress">
                        <i class="fas fa-chart-line"></i>
                    </button>
                    <button onclick="deleteGoal(${goal.id})" 
                            class="text-red-600 hover:text-red-800" title="Delete Goal">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            
            ${goal.target_value ? `
                <div class="mb-4">
                    <div class="flex justify-between text-sm text-gray-600 mb-1">
                        <span>Progress</span>
                        <span>${goal.current_value}${goal.unit ? ' ' + goal.unit : ''} / ${goal.target_value}${goal.unit ? ' ' + goal.unit : ''}</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-indigo-600 h-2 rounded-full transition-all duration-300" style="width: ${Math.min(goal.progress_percentage, 100)}%"></div>
                    </div>
                    <div class="text-right text-xs text-gray-500 mt-1">${Math.round(goal.progress_percentage)}% complete</div>
                </div>
            ` : ''}
            
            <div class="text-xs text-gray-500">
                ${goal.target_date ? `Target: ${formatDate(goal.target_date)}` : 'No target date'} • 
                Created: ${goal.created_at}
            </div>
        </div>
    `).join('');
}

function showAddGoalModal() {
    document.getElementById('modal-title').textContent = 'Add New Goal';
    document.getElementById('goal-form').reset();
    currentGoalId = null;
    document.getElementById('goal-modal').classList.remove('hidden');
}

function hideGoalModal() {
    document.getElementById('goal-modal').classList.add('hidden');
}

function showProgressModal(goalId, currentValue, status) {
    document.getElementById('progress-goal-id').value = goalId;
    document.getElementById('current-value').value = currentValue;
    document.getElementById('goal-status').value = status;
    document.getElementById('progress-modal').classList.remove('hidden');
}

function hideProgressModal() {
    document.getElementById('progress-modal').classList.add('hidden');
}

function handleGoalSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const goalData = Object.fromEntries(formData.entries());
    
        fetch('/patient/api/goals', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify(goalData)
    })
    .then(response => {
        // Check if response is actually JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Server returned non-JSON response. You may need to log in again.');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showMessage(data.message, 'success');
            hideGoalModal();
            loadGoals();
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage(error.message || 'Error creating goal', 'error');
    });
}

function handleProgressSubmit(e) {
    e.preventDefault();
    
    const goalId = document.getElementById('progress-goal-id').value;
    const formData = new FormData(e.target);
    const updateData = Object.fromEntries(formData.entries());
    
    fetch(`/patient/api/goals/${goalId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify(updateData)
    })
    .then(response => {
        // Check if response is actually JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Server returned non-JSON response. You may need to log in again.');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showMessage(data.message, 'success');
            hideProgressModal();
            loadGoals();
        } else {
            showMessage(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage('Error updating goal', 'error');
    });
}

function deleteGoal(goalId) {
    if (confirm('Are you sure you want to delete this goal?')) {
        fetch(`/patient/api/goals/${goalId}`, {
            method: 'DELETE',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            }
        })
        .then(response => {
        // Check if response is actually JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Server returned non-JSON response. You may need to log in again.');
        }
        return response.json();
    })
        .then(data => {
            if (data.success) {
                showMessage(data.message, 'success');
                loadGoals();
            } else {
                showMessage(data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Error deleting goal', 'error');
        });
    }
}

function showMessage(message, type) {
    const container = document.getElementById('message-container');
    const messageDiv = document.getElementById('message');
    
    messageDiv.textContent = message;
    messageDiv.className = `p-4 rounded-lg ${type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`;
    container.classList.remove('hidden');
    
    setTimeout(() => {
        container.classList.add('hidden');
    }, 5000);
}

function getPriorityColor(priority) {
    switch(priority) {
        case 'high': return 'bg-red-100 text-red-800';
        case 'medium': return 'bg-yellow-100 text-yellow-800';
        case 'low': return 'bg-green-100 text-green-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

function getStatusColor(status) {
    switch(status) {
        case 'completed': return 'bg-green-100 text-green-800';
        case 'active': return 'bg-blue-100 text-blue-800';
        case 'paused': return 'bg-gray-100 text-gray-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString();
}
