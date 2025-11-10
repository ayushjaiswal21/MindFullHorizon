

// Complete appointment loading system
window.loadAppointments = function(status = 'all') {
    console.log('🔄 Loading appointments with status:', status);
    
    const tbody = document.getElementById('appointmentsBody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-3 text-center text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading appointments...</td></tr>';
    }
    
    fetch(`{{ url_for('provider.provider_appointments') }}?status=${status}`)
        .then(response => {
            console.log('📡 Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('✅ Appointments data received:', data);
            if (data && data.success) {
                displayAppointments(data.appointments || []);
            } else {
                const errorMsg = data?.message || 'Unknown error occurred';
                tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-3 text-center text-red-500"><i class="fas fa-exclamation-triangle mr-2" aria-hidden="true"></i>Failed to load appointments: ${errorMsg}</td></tr>`;
            }
        })
        .catch(error => {
            console.error('💥 Error loading appointments:', error);
            const errorMsg = error.message || 'Network error occurred';
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-3 text-center text-red-500"><i class="fas fa-exclamation-triangle mr-2"></i>Error loading appointments: ${errorMsg}</td></tr>`;
        });
};

function displayAppointments(appointments) {
    console.log('🎨 Displaying appointments:', appointments);
    const tbody = document.getElementById('appointmentsBody');
    if (!tbody) {
        console.error('❌ appointmentsBody element not found!');
        return;
    }
    
    tbody.innerHTML = '';
    
    // Update counts
    updateAppointmentCounts(appointments);
    
    if (!appointments || appointments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-3 text-center text-gray-500"><i class="fas fa-calendar-times mr-2"></i>No appointments found</td></tr>';
        return;
    }
    
    appointments.forEach((appointment, index) => {
        console.log(`🏗️ Rendering appointment ${index + 1}:`, appointment);
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50';
        
        const statusClass = {
            'pending': 'bg-yellow-100 text-yellow-800',
            'accepted': 'bg-green-100 text-green-800',
            'rejected': 'bg-red-100 text-red-800'
        }[appointment.status] || 'bg-gray-100 text-gray-800';
        
        const assignmentInfo = appointment.provider_id ? '' : ' <span class="text-xs text-blue-600">(Unassigned)</span>';
        const urgencyBadge = appointment.urgency_level === 'high' ? '<span class="ml-2 px-2 py-1 bg-red-100 text-red-800 text-xs rounded-full">High Priority</span>' : '';
        
        // Build health summary
        let healthSummary = '';
        if (appointment.patient_health_data) {
            const health = appointment.patient_health_data;
            const healthItems = [];
            
            if (health.latest_assessment) {
                const score = health.latest_assessment.score;
                const riskLevel = score > 15 ? 'High Risk' : score > 10 ? 'Moderate' : 'Low Risk';
                const riskColor = score > 15 ? 'text-red-600' : score > 10 ? 'text-yellow-600' : 'text-green-600';
                healthItems.push(`<span class="${riskColor}">${health.latest_assessment.type}: ${riskLevel} (${score})</span>`);
            }
            
            if (health.vital_signs && health.vital_signs.mood_score) {
                const moodColor = health.vital_signs.mood_score < 4 ? 'text-red-600' : health.vital_signs.mood_score < 7 ? 'text-yellow-600' : 'text-green-600';
                healthItems.push(`<span class="${moodColor}">Mood: ${health.vital_signs.mood_score}/10</span>`);
            }
            
            if (health.digital_wellness && health.digital_wellness.screen_time) {
                const screenTime = health.digital_wellness.screen_time;
                const screenColor = screenTime > 8 ? 'text-red-600' : screenTime > 6 ? 'text-yellow-600' : 'text-green-600';
                healthItems.push(`<span class="${screenColor}">Screen: ${screenTime}h/day</span>`);
            }
            
            healthSummary = healthItems.length > 0 ? `<div class="text-xs mt-1">${healthItems.join(' • ')}</div>` : '<div class="text-xs mt-1 text-gray-500">No recent health data</div>';
        }
        
        const notesPreview = appointment.notes ? `<div class="text-xs text-gray-600 mt-1 italic">"${appointment.notes.substring(0, 50)}${appointment.notes.length > 50 ? '...' : ''}"</div>` : '';
        
        row.innerHTML = `
            <td class="px-4 py-3 text-sm">
                <div class="font-medium text-gray-900">${appointment.patient_name}${assignmentInfo}${urgencyBadge}</div>
                ${healthSummary}
            </td>
            <td class="px-4 py-3 text-sm text-gray-700">
                <div class="font-medium">${appointment.date}</div>
                <div class="text-xs text-gray-500">${appointment.time}</div>
            </td>
            <td class="px-4 py-3 text-sm">
                <div class="font-medium text-gray-700">${appointment.type}</div>
                ${notesPreview}
            </td>
            <td class="px-4 py-3 text-sm">
                <span class="px-2 py-1 rounded-full text-xs font-medium ${statusClass}">
                    ${appointment.status.charAt(0).toUpperCase() + appointment.status.slice(1)}
                </span>
            </td>
            <td class="px-4 py-3 text-sm">
                ${appointment.status === 'pending' ? `
                    <div class="flex flex-col space-y-2">
                        <button onclick="acceptAppointment(${appointment.id})" 
                                class="bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-xs font-medium transition-colors w-full">
                            <i class="fas fa-check mr-1"></i>Accept
                        </button>
                        <button onclick="showRejectModal(${appointment.id})" 
                                class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-xs font-medium transition-colors w-full">
                            <i class="fas fa-times mr-1"></i>Reject
                        </button>
                    </div>
                ` : appointment.status === 'accepted' ? `
                    <span class="text-xs text-green-600 font-medium">
                        <i class="fas fa-check-circle mr-1"></i>Accepted
                    </span>
                ` : appointment.status === 'rejected' ? `
                    <span class="text-xs text-red-600 font-medium">
                        <i class="fas fa-times-circle mr-1"></i>Rejected
                    </span>
                ` : ''}
            </td>
        `;
        tbody.appendChild(row);
    });
    
    console.log('🎉 All appointments rendered successfully!');
}

function updateAppointmentCounts(appointments) {
    const counts = {
        all: appointments.length,
        pending: appointments.filter(a => a.status === 'pending').length,
        accepted: appointments.filter(a => a.status === 'accepted').length,
        rejected: appointments.filter(a => a.status === 'rejected').length
    };

    // Update badge counts
    const allCount = document.getElementById('allCount');
    const pendingBadge = document.getElementById('pendingBadge');
    const acceptedCount = document.getElementById('acceptedCount');
    const rejectedCount = document.getElementById('rejectedCount');
    
    if (allCount) allCount.textContent = counts.all;
    if (pendingBadge) pendingBadge.textContent = counts.pending;
    if (acceptedCount) acceptedCount.textContent = counts.accepted;
    if (rejectedCount) rejectedCount.textContent = counts.rejected;

    // Update pending notification
    const pendingNotification = document.getElementById('pendingNotification');
    const pendingCount = document.getElementById('pendingCount');
    
    if (pendingNotification && pendingCount) {
        if (counts.pending > 0) {
            pendingNotification.classList.remove('hidden');
            pendingCount.textContent = counts.pending;
        } else {
            pendingNotification.classList.add('hidden');
        }
    }
}

// Filter appointments function
window.filterAppointments = function(status) {
    // Update active filter button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeBtn = document.querySelector(`[data-status="${status}"]`);
    if (activeBtn) activeBtn.classList.add('active');
    
    // Load appointments with filter
    window.loadAppointments(status);
};

// Simple refresh function
window.refreshAppointments = function() {
    window.loadAppointments();
};

// Accept appointment function
function acceptAppointment(appointmentId) {
    console.log('✅ Accepting appointment:', appointmentId);
    
    // Disable the button to prevent double-clicks
    const acceptBtn = document.querySelector(`button[onclick="acceptAppointment(${appointmentId})"]`);
    if (acceptBtn) {
        acceptBtn.disabled = true;
        acceptBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Accepting...';
    }

    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    fetch(`{{ url_for('provider.accept_appointment', appointment_id=0) }}`.replace('0', appointmentId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Appointment accepted successfully');
            showNotification('Success', '✅ Appointment accepted successfully! Patient has been notified.', 'success');
            window.loadAppointments(); // Refresh the list
        } else {
            console.error('❌ Failed to accept appointment:', data);
            showNotification('Error', data.message || 'Failed to accept appointment', 'error');
            // Re-enable button on error
            if (acceptBtn) {
                acceptBtn.disabled = false;
                acceptBtn.innerHTML = '<i class="fas fa-check mr-1"></i>Accept';
            }
        }
    })
    .catch(error => {
        console.error('💥 Error accepting appointment:', error);
        showNotification('Error', 'Failed to accept appointment', 'error');
        // Re-enable button on error
        if (acceptBtn) {
            acceptBtn.disabled = false;
            acceptBtn.innerHTML = '<i class="fas fa-check mr-1" aria-hidden="true"></i>Accept';
        }
    });
}

// Show reject modal function
function showRejectModal(appointmentId) {
    console.log('❌ Showing reject modal for appointment:', appointmentId);
    
    // Store the appointment ID for later use
    window.currentAppointmentId = appointmentId;
    
    // Show the modal
    const modal = document.getElementById('rejectionModal');
    if (modal) {
        modal.classList.remove('hidden');
        // Clear any previous reason
        const reasonTextarea = document.getElementById('rejectionReason');
        if (reasonTextarea) {
            reasonTextarea.value = '';
        }
    }
}

// Hide reject modal function
function hideRejectModal() {
    const modal = document.getElementById('rejectionModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    window.currentAppointmentId = null;
}

// Reject appointment function
function rejectAppointment(appointmentId, reason) {
    console.log('❌ Rejecting appointment:', appointmentId, 'with reason:', reason);
    
    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    fetch(`{{ url_for('provider.reject_appointment', appointment_id=0) }}`.replace('0', appointmentId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ reason: reason || 'No reason provided' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Appointment rejected successfully');
            showNotification('Success', '❌ Appointment rejected. Patient has been notified with the reason.', 'success');
            window.loadAppointments(); // Refresh the list
        } else {
            console.error('❌ Failed to reject appointment:', data);
            showNotification('Error', data.message || 'Failed to reject appointment', 'error');
        }
    })
    .catch(error => {
        console.error('💥 Error rejecting appointment:', error);
        showNotification('Error', 'Failed to reject appointment', 'error');
    });
}

// Show notification function
function showNotification(title, message, type) {
    console.log(`📢 ${type.toUpperCase()}: ${title} - ${message}`);
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-20 right-4 p-4 rounded-lg shadow-lg z-50 max-w-sm ${
        type === 'success' ? 'bg-green-500 text-white' : 
        type === 'error' ? 'bg-red-500 text-white' : 
        'bg-blue-500 text-white'
    }`;
    notification.innerHTML = `
        <div class="flex items-center">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-white hover:text-gray-200">
                <i class="fas fa-times" aria-hidden="true"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
    
    // Browser notification if permission granted
    if (Notification.permission === 'granted') {
        new Notification(title, {
            body: message,
            icon: '/static/images/icon-192x192.png'
        });
    }
}

// Load appointments when page is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Page loaded, loading appointments...');
    setTimeout(function() {
        window.loadAppointments();
    }, 500);
    
    // Set up modal event listeners
    const confirmRejectBtn = document.getElementById('confirmReject');
    const cancelRejectBtn = document.getElementById('cancelReject');
    
    if (confirmRejectBtn) {
        confirmRejectBtn.addEventListener('click', function() {
            const reason = document.getElementById('rejectionReason')?.value?.trim() || '';
            if (window.currentAppointmentId) {
                rejectAppointment(window.currentAppointmentId, reason);
                hideRejectModal();
            }
        });
    }
    
    if (cancelRejectBtn) {
        cancelRejectBtn.addEventListener('click', hideRejectModal);
    }
    
    // Request notification permission
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }
});
