// Enhanced JavaScript for Flask Mental Health Application

// Auto-hide flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert-success, .alert-error');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });
});

// Function to show custom message box
function showMessageBox(title, message, type = 'info') {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    
    // Create modal content
    const modal = document.createElement('div');
    modal.className = 'bg-white rounded-lg p-6 max-w-md mx-4 shadow-xl';
    
    const iconClass = type === 'success' ? 'fas fa-check-circle text-green-500' : 
                     type === 'error' ? 'fas fa-exclamation-triangle text-red-500' :
                     'fas fa-info-circle text-blue-500';
    
    modal.innerHTML = `
        <div class="text-center">
            <i class="${iconClass} text-4xl mb-4"></i>
            <h3 class="text-lg font-semibold text-gray-800 mb-2">${title}</h3>
            <p class="text-gray-600 mb-4">${message}</p>
            <button onclick="hideMessageBox()" class="btn-primary">OK</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Store reference for hiding
    window.currentMessageBox = overlay;
}

function hideMessageBox() {
    if (window.currentMessageBox) {
        window.currentMessageBox.remove();
        window.currentMessageBox = null;
    }
}

// Enhanced form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('border-red-500');
            isValid = false;
        } else {
            input.classList.remove('border-red-500');
        }
    });
    
    return isValid;
}

// Real-time form validation
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.hasAttribute('required') && !this.value.trim()) {
                this.classList.add('border-red-500');
            } else {
                this.classList.remove('border-red-500');
            }
        });
    });
});

// Progress bar animation
function animateProgressBar(elementId, targetPercent) {
    const progressBar = document.getElementById(elementId);
    if (progressBar) {
        let currentPercent = 0;
        const increment = targetPercent / 50; // 50 steps for smooth animation
        
        const timer = setInterval(() => {
            currentPercent += increment;
            if (currentPercent >= targetPercent) {
                currentPercent = targetPercent;
                clearInterval(timer);
            }
            progressBar.style.width = currentPercent + '%';
        }, 20);
    }
}

// Smooth scroll to element
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

// Copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showMessageBox('Success', 'Text copied to clipboard!', 'success');
    }).catch(err => {
        showMessageBox('Error', 'Failed to copy text to clipboard.', 'error');
    });
}

// Format date for display
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

// Auto-resize textarea
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Initialize auto-resize for all textareas
document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            autoResizeTextarea(this);
        });
    });
});

// Loading spinner utility
function showLoadingSpinner(buttonElement) {
    const originalText = buttonElement.innerHTML;
    buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Loading...';
    buttonElement.disabled = true;
    
    return function hideSpinner() {
        buttonElement.innerHTML = originalText;
        buttonElement.disabled = false;
    };
}

// Enhanced table sorting
function sortTable(tableId, columnIndex, dataType = 'string') {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        if (dataType === 'number') {
            return parseFloat(aValue) - parseFloat(bValue);
        } else if (dataType === 'date') {
            return new Date(aValue) - new Date(bValue);
        } else {
            return aValue.localeCompare(bValue);
        }
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

// Search functionality for tables
function searchTable(tableId, searchInputId) {
    const searchInput = document.getElementById(searchInputId);
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tbody tr');
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

// Mobile menu toggle
function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenu) {
        mobileMenu.classList.toggle('hidden');
    }
}

// Notification system
class NotificationSystem {
    constructor() {
        this.container = this.createContainer();
    }
    
    createContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.className = 'fixed top-20 right-4 z-50 space-y-2';
        document.body.appendChild(container);
        return container;
    }
    
    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-500' : 
                       type === 'error' ? 'bg-red-500' : 
                       type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500';
        
        notification.className = `${bgColor} text-white px-4 py-3 rounded-lg shadow-lg transform translate-x-full transition-transform duration-300`;
        notification.innerHTML = `
            <div class="flex items-center justify-between">
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        this.container.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);
        
        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.add('translate-x-full');
                setTimeout(() => {
                    if (notification.parentElement) {
                        notification.remove();
                    }
                }, 300);
            }, duration);
        }
    }
}

// Initialize notification system
const notifications = new NotificationSystem();

// Utility function to show notifications
function showNotification(message, type = 'info', duration = 5000) {
    notifications.show(message, type, duration);
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'absolute bg-gray-800 text-white text-sm px-2 py-1 rounded shadow-lg z-50';
            tooltip.textContent = this.getAttribute('data-tooltip');
            tooltip.id = 'tooltip';
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltip = document.getElementById('tooltip');
            if (tooltip) {
                tooltip.remove();
            }
        });
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
});


// A reusable function to draw a line chart on a canvas
function drawLineChart(ctx, canvas, xLabels, yData, label, color) {
    const padding = 40;
    const width = canvas.width - 2 * padding;
    const height = canvas.height - 2 * padding;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (yData.length === 0) return;

    // Set up scales
    const maxY = Math.max(...yData) + 1;
    const minY = 0;
    const yRange = maxY - minY || 1;
    
    // Draw axes
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, padding + height);
    ctx.moveTo(padding, padding + height);
    ctx.lineTo(padding + width, padding + height);
    ctx.stroke();
    
    // Draw grid lines
    ctx.strokeStyle = '#f3f4f6';
    for (let i = 1; i <= 4; i++) {
        const y = padding + (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(padding + width, y);
        ctx.stroke();
    }

    // Draw data line
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    for (let i = 0; i < yData.length; i++) {
        const x = padding + (width / (yData.length - 1)) * i;
        const y = padding + height - ((yData[i] - minY) / yRange) * height;
        
        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();
    
    // Draw data points and labels
    ctx.fillStyle = color;
    ctx.font = '12px Inter';
    ctx.textAlign = 'center';
    for (let i = 0; i < yData.length; i++) {
        const x = padding + (width / (yData.length - 1)) * i;
        const y = padding + height - ((yData[i] - minY) / yRange) * height;
        
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();
        
        // Label points with the value
        ctx.fillStyle = '#6b7280';
        ctx.fillText(yData[i], x, y - 10);
        
        // X-axis labels
        ctx.fillText(xLabels[i], x, padding + height + 20);
    }

    // Y-axis labels
    for (let i = 0; i <= 4; i++) {
        const value = minY + (yRange / 4) * (4 - i);
        const y = padding + (height / 4) * i;
        ctx.fillStyle = '#6b7280';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round(value * 10) / 10, padding - 10, y + 4);
    }
    
    // Y-axis label
    ctx.save();
    ctx.translate(padding - 30, padding + height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(label, 0, 0);
    ctx.restore();
}

