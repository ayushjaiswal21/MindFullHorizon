function toggleContent(entryId) {
    const fullContent = document.getElementById(entryId + '-full');
    const button = event.target;

    if (fullContent.classList.contains('hidden')) {
        fullContent.classList.remove('hidden');
        button.textContent = 'Read less';
    } else {
        fullContent.classList.add('hidden');
        button.textContent = 'Read more';
    }
}

function deleteJournalEntry(entryId) {
    if (confirm('Are you sure you want to delete this journal entry? This action cannot be undone.')) {
        fetch(`/api/delete-journal-entry/${entryId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').getAttribute('content') : ''
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the entry from the DOM
                const entryElement = document.querySelector(`[data-entry-id="${entryId}"]`);
                if (entryElement) {
                    entryElement.remove();
                }

                // Show success message
                showJournalAlert('Journal entry deleted successfully!', 'success');

                // If no entries left, show empty state
                const entriesContainer = document.querySelector('.space-y-4');
                if (entriesContainer && entriesContainer.children.length === 0) {
                    location.reload(); // Refresh to show empty state
                }
            } else {
                showJournalAlert('Failed to delete journal entry: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Delete error:', error);
            showJournalAlert('Failed to delete journal entry. Please try again.', 'error');
        });
    }
}

function showJournalAlert(message, type) {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} mb-4 p-4 rounded-lg text-sm ${
        type === 'success'
            ? 'bg-green-100 text-green-800 border border-green-200'
            : 'bg-red-100 text-red-800 border border-red-200'
    }`;
    alertDiv.textContent = message;

    // Insert at the top of the content area
    const container = document.querySelector('.patient-journal-container .max-w-4xl');
    container.insertBefore(alertDiv, container.firstChild);

    // Remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// New event listener code
document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(event) {
        const target = event.target.closest('button');

        if (!target) return;

        if (target.classList.contains('delete-journal-entry-btn')) {
            const entryId = target.dataset.entryId;
            deleteJournalEntry(entryId);
        } else if (target.classList.contains('toggle-content-btn')) {
            const entryId = target.dataset.entryId;
            toggleContent(entryId);
        }
    });
});