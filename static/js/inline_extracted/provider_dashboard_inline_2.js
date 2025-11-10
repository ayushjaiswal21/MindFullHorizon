
// Initialize Socket.IO
const socket = io();

// Connect to notification system
socket.on('connect', function() {
    console.log('Connected to notification system');
});

// Handle new appointment notifications
socket.on('new_appointment', function(data) {
    const assignmentText = data.unassigned ? ' (Unassigned - Available to All Providers)' : ' (Assigned to You)';
    const notificationTitle = `🔔 New Appointment Request${assignmentText}`;
    const notificationMessage = `${data.patient_name} requested a ${data.type} appointment for ${data.date} at ${data.time}`;
    
    // Show browser notification
    showNotification(notificationTitle, notificationMessage, 'info');
    
    // Show in-page notification
    showInPageNotification(data);
    
    // Refresh appointments to show the new one
    window.loadAppointments();
});

function showInPageNotification(appointmentData) {
    // Create a temporary notification banner
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 bg-blue-500 text-white p-4 rounded-lg shadow-lg z-50 max-w-sm';
    notification.innerHTML = `
        <div class="flex items-start">
            <i class="fas fa-calendar-plus text-xl mr-3 mt-1" aria-hidden="true"></i>
            <div class="flex-1">
                <h4 class="font-bold">New Appointment Request!</h4>
                <p class="text-sm mt-1">${appointmentData.patient_name} - ${appointmentData.type}</p>
                <p class="text-xs mt-1">${appointmentData.date} at ${appointmentData.time}</p>
                ${appointmentData.notes ? `<p class="text-xs mt-1 italic">"${appointmentData.notes}"</p>` : ''}
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-white hover:text-gray-200">
                <i class="fas fa-times" aria-hidden="true"></i>
            </button>
        </div>
        <div class="mt-3 flex space-x-2">
            <button onclick="filterAppointments('pending'); this.parentElement.parentElement.remove();" class="bg-white text-blue-500 px-3 py-1 rounded text-xs font-medium hover:bg-gray-100">
                View Pending
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 10000);
}

let currentAppointmentId = null;

// Load appointments on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Provider Dashboard loaded, initializing appointments...');
    console.log('👤 Current user session check...');
    
    // Add a small delay to ensure all scripts are loaded
    setTimeout(() => {
        console.log('⏰ Starting appointment load after delay...');
        window.loadAppointments();
    }, 500);
    
    // Also try to load immediately
    window.loadAppointments();
});

window.loadAppointments = function(status = 'all') {
    console.log('🔄 Loading appointments with status:', status);
    console.log('🌐 Fetching from URL:', `{{ url_for('provider.provider_appointments') }}?status=${status}`);
    
    // Show loading state
    const tbody = document.getElementById('appointmentsBody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-3 text-center text-gray-500"><i class="fas fa-spinner fa-spin mr-2" aria-hidden="true"></i>Loading appointments...</td></tr>';
    }
    
    // Get CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    console.log('🔐 CSRF Token found:', !!csrfToken);
    
    const headers = {
        'Content-Type': 'application/json'
    };
    
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }
    
    fetch(`{{ url_for('provider.provider_appointments') }}?status=${status}`, {
        method: 'GET',
        headers: headers,
        credentials: 'same-origin'
    })
        .then(response => {
            console.log('📡 Response status:', response.status);
            console.log('📡 Response ok:', response.ok);
            console.log('📡 Response headers:', Object.fromEntries(response.headers.entries()));
            
            if (!response.ok) {
                return response.text().then(text => {
                    console.error('❌ Response text:', text);
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('✅ Appointments data received:', data);
            if (data && data.success) {
                console.log('📊 Number of appointments:', data.appointments?.length || 0);
                console.log('📋 Appointments array:', data.appointments);
                displayAppointments(data.appointments || []);
            } else {
                console.error('❌ API returned error:', data);
                const errorMsg = data?.message || 'Unknown error occurred';
                document.getElementById('appointmentsBody').innerHTML = `<tr><td colspan="5" class="px-4 py-3 text-center text-red-500"><i class="fas fa-exclamation-triangle mr-2"></i>Failed to load appointments: ${errorMsg}</td></tr>`;
            }
        })
        .catch(error => {
            console.error('💥 Error loading appointments:', error);
            const errorMsg = error.message || 'Network error occurred';
            document.getElementById('appointmentsBody').innerHTML = `<tr><td colspan="5" class="px-4 py-3 text-center text-red-500"><i class="fas fa-exclamation-triangle mr-2"></i>Error loading appointments: ${errorMsg}<br><small class="text-gray-400 mt-1 block">Check browser console for details</small></td></tr>`;
        });
}

window.displayAppointments = function(appointments) {
    console.log('🎨 Displaying appointments:', appointments);
    const tbody = document.getElementById('appointmentsBody');
    if (!tbody) {
        console.error('❌ appointmentsBody element not found!');
        return;
    }
    
    console.log('🧹 Clearing existing appointments...');
    tbody.innerHTML = '';

    // Update counts
    console.log('🔢 Updating appointment counts...');
    updateAppointmentCounts(appointments);

    if (!appointments || appointments.length === 0) {
        console.log('📭 No appointments to display');
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-3 text-center text-gray-500"><i class="fas fa-calendar-times mr-2" aria-hidden="true"></i>No appointments found<br><small class="text-gray-400 mt-1 block">New appointment requests will appear here</small></td></tr>';
        return;
    }
    
    console.log(`📅 Rendering ${appointments.length} appointments...`);

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
        
        // Build notes preview
        const notesPreview = appointment.notes ? `<div class="text-xs text-gray-600 mt-1 italic">"${appointment.notes.substring(0, 50)}${appointment.notes.length > 50 ? '...' : ''}"</div>` : '';
        
        row.innerHTML = `
            <td class="px-4 py-3 text-sm">
                <div class="font-medium text-gray-900">${appointment.patient_name}${assignmentInfo}${urgencyBadge}</div>
                ${healthSummary}
                <button onclick="showPatientDetails(${appointment.patient_id}, '${appointment.patient_name}')" class="text-xs text-blue-600 hover:text-blue-800 mt-1">
                    <i class="fas fa-user-md mr-1"></i>View Full Report
                </button>
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
                        <button onclick="window.acceptAppointment(${appointment.id})" 
                                class="bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-xs font-medium transition-colors w-full" 
                                title="Accept${appointment.provider_id ? '' : ' & Assign to Me'}">
                            <i class="fas fa-check mr-1" aria-hidden="true"></i>Accept
                        </button>
                        <button onclick="window.showRejectModal(${appointment.id})" 
                                class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-xs font-medium transition-colors w-full" 
                                title="Reject">
                            <i class="fas fa-times mr-1" aria-hidden="true"></i>Reject
                        </button>
                    </div>
                ` : appointment.status === 'rejected' && appointment.rejection_reason ? `
                    <span class="text-xs text-gray-500 cursor-pointer" title="${appointment.rejection_reason}" onclick="alert('Rejection Reason: ${appointment.rejection_reason}')">
                        <i class="fas fa-info-circle mr-1"></i>View reason
                    </span>
                ` : appointment.status === 'accepted' ? `
                    <span class="text-xs text-green-600 font-medium">
                        <i class="fas fa-check-circle mr-1"></i>Accepted
                    </span>
                ` : ''}
            </td>
        `;
        tbody.appendChild(row);
        console.log(`✅ Appointment ${index + 1} rendered successfully`);
    });
    
    console.log('🎉 All appointments rendered successfully!');
    
    // Show success notification
    showTemporaryNotification(`✅ Loaded ${appointments.length} appointments successfully!`, 'success');
}

function updateAppointmentCounts(appointments) {
    const counts = {
        all: appointments.length,
        pending: appointments.filter(a => a.status === 'pending').length,
        accepted: appointments.filter(a => a.status === 'accepted').length,
        rejected: appointments.filter(a => a.status === 'rejected').length
    };

    // Update badge counts
    document.getElementById('allCount').textContent = counts.all;
    document.getElementById('pendingBadge').textContent = counts.pending;
    document.getElementById('acceptedCount').textContent = counts.accepted;
    document.getElementById('rejectedCount').textContent = counts.rejected;

    // Update pending notification
    const pendingNotification = document.getElementById('pendingNotification');
    const pendingCount = document.getElementById('pendingCount');
    
    if (counts.pending > 0) {
        pendingNotification.classList.remove('hidden');
        pendingCount.textContent = counts.pending;
    } else {
        pendingNotification.classList.add('hidden');
    }
}

window.filterAppointments = function(status) {
    // Update active filter button
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-status="${status}"]`).classList.add('active');
    
    // Load appointments with filter
    window.loadAppointments(status);
}

window.acceptAppointment = function(appointmentId) {
    // Disable the button to prevent double-clicks
            const acceptBtn = document.querySelector(`button[onclick="window.acceptAppointment(${appointmentId})"]`);
            if (acceptBtn) {
                acceptBtn.disabled = true;
                acceptBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1" aria-hidden="true"></i>Accepting...';    }

    fetch(`{{ url_for("accept_appointment", appointment_id=0) }}`.replace('0', appointmentId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Success', '✅ Appointment accepted successfully! Patient has been notified.', 'success');
            window.loadAppointments(); // Refresh the list
        } else {
            showNotification('Error', data.message || 'Failed to accept appointment', 'error');
            // Re-enable button on error
            if (acceptBtn) {
                acceptBtn.disabled = false;
                acceptBtn.innerHTML = '<i class="fas fa-check mr-1"></i>Accept';
            }
        }
    })
    .catch(error => {
        console.error('Error accepting appointment:', error);
        showNotification('Error', 'Failed to accept appointment', 'error');
        // Re-enable button on error
        if (acceptBtn) {
            acceptBtn.disabled = false;
            acceptBtn.innerHTML = '<i class="fas fa-check mr-1"></i>Accept';
        }
    });
}

window.showRejectModal = function(appointmentId) {
    currentAppointmentId = appointmentId;
    document.getElementById('rejectionModal').classList.remove('hidden');
    document.getElementById('rejectionReason').value = '';
}

function hideRejectModal() {
    document.getElementById('rejectionModal').classList.add('hidden');
    currentAppointmentId = null;
}

// Modal event listeners
document.getElementById('confirmReject').addEventListener('click', function() {
    const reason = document.getElementById('rejectionReason').value.trim();
    if (!reason) {
        alert('Please provide a reason for rejection');
        return;
    }
    
    rejectAppointment(currentAppointmentId, reason);
    hideRejectModal();
});

document.getElementById('cancelReject').addEventListener('click', hideRejectModal);

function rejectAppointment(appointmentId, reason) {
    // Show loading state
    const confirmBtn = document.getElementById('confirmReject');
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1" aria-hidden="true"></i>Rejecting...';

    fetch(`{{ url_for("reject_appointment", appointment_id=0) }}`.replace('0', appointmentId), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify({ reason: reason })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Success', '❌ Appointment rejected. Patient has been notified with the reason.', 'success');
            window.loadAppointments(); // Refresh the list
        } else {
            showNotification('Error', data.message || 'Failed to reject appointment', 'error');
        }
        // Reset button state
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = 'Reject';
    })
    .catch(error => {
        console.error('Error rejecting appointment:', error);
        showNotification('Error', 'Failed to reject appointment', 'error');
        // Reset button state
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = 'Reject';
    });
}

function showNotification(title, message, type) {
    // Browser notification
    if (Notification.permission === 'granted') {
        new Notification(title, {
            body: message,
            icon: '/static/images/icon-192x192.png'
        });
    }
    
    // Toast notification (you can implement a toast system here)
    console.log(`${type.toUpperCase()}: ${title} - ${message}`);
}

// Request notification permission
if (Notification.permission === 'default') {
    Notification.requestPermission();
}

function showPatientDetails(patientId, patientName) {
    if (!patientId) {
        alert('Patient information not available');
        return;
    }
    
    document.getElementById('patientDetailsModal').classList.remove('hidden');
    document.getElementById('patientDetailsContent').innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin text-2xl text-blue-500" aria-hidden="true"></i><p class="mt-2">Loading patient data...</p></div>';
    
    // Fetch detailed patient information
    fetch(`{{ url_for("wellness_report", user_id=0) }}`.replace('0', patientId))
        .then(response => response.text())
        .then(html => {
            // Extract the main content from the wellness report
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const mainContent = doc.querySelector('.max-w-7xl') || doc.querySelector('main') || doc.body;
            
            document.getElementById('patientDetailsContent').innerHTML = `
                <div class="mb-4">
                    <h4 class="text-xl font-semibold text-gray-800 mb-2">
                        <i class="fas fa-user-md mr-2 text-blue-500" aria-hidden="true"></i>${patientName}'s Health Report
                    </h4>
                    <div class="bg-blue-50 border-l-4 border-blue-400 p-4 mb-4">
                        <p class="text-sm text-blue-700">
                            <i class="fas fa-info-circle mr-1" aria-hidden="true"></i>
                            Review this patient's health data to make an informed decision about the appointment request.
                        </p>
                    </div>
                </div>
                <div class="wellness-report-content max-h-96 overflow-y-auto">
                    ${mainContent ? mainContent.innerHTML : '<p class="text-gray-500">No detailed health data available for this patient.</p>'}
                </div>
                <div class="mt-6 pt-4 border-t border-gray-200 text-center">
                    <button onclick="hidePatientDetails()" class="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded font-medium">
                        Close Report
                    </button>
                </div>
            `;
        })
        .catch(error => {
            console.error('Error loading patient details:', error);
            document.getElementById('patientDetailsContent').innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-exclamation-triangle text-red-500 text-3xl mb-4" aria-hidden="true"></i>
                    <p class="text-gray-600 mb-4">Unable to load patient health data.</p>
                    <button onclick="hidePatientDetails()" class="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded">
                        Close
                    </button>
                </div>
            `;
        });
}

function hidePatientDetails() {
    document.getElementById('patientDetailsModal').classList.add('hidden');
}

function openMessage(patientId) {
    const text = prompt('Send a quick message to patient:');
    if (!text || !text.trim()) return;

    fetch('{{ url_for("api_message") }}', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify({ recipient_id: patientId, message: text.trim() })
    }).then(r => r.json()).then(data => {
        if (data && data.success) {
            alert('Message sent successfully.');
        } else {
            alert('Failed to send message: ' + (data.error || 'Unknown error'));
        }
    }).catch(err => {
        console.error('Message send failed', err);
        alert('Failed to send message.');
    });
}

// Test API function to debug appointment loading
window.testAPI = function() {
    console.log('🧪 Testing API endpoint...');
    
    // Test 1: Check if we can reach the endpoint
    const testUrl = '{{ url_for('provider.provider_appointments') }}';
    console.log('🎯 Testing URL:', testUrl);
    
    // Test 2: Check session info
    console.log('🔍 Current page URL:', window.location.href);
    console.log('🔍 User agent:', navigator.userAgent);
    
    // Test 3: Try a simple fetch
    fetch(testUrl)
        .then(response => {
            console.log('✅ API Response Status:', response.status);
            console.log('✅ API Response Headers:', Object.fromEntries(response.headers.entries()));
            return response.text();
        })
        .then(text => {
            console.log('📄 Raw API Response:', text);
            try {
                const data = JSON.parse(text);
                console.log('📊 Parsed API Response:', data);
                alert(`API Test Results:\nStatus: Success\nAppointments: ${data.appointments?.length || 0}\nCheck console for details`);
            } catch (e) {
                console.error('❌ Failed to parse JSON:', e);
                alert(`API Test Results:\nStatus: Error\nResponse is not valid JSON\nCheck console for details`);
            }
        })
        .catch(error => {
            console.error('💥 API Test Failed:', error);
            alert(`API Test Results:\nStatus: Failed\nError: ${error.message}\nCheck console for details`);
        });
}

// Show temporary notification
window.showTemporaryNotification = function(message, type = 'info') {
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
                <i class="fas fa-times"></i>
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
}
