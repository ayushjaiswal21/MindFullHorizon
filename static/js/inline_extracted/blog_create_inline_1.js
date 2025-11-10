
// Word count functionality
function updateWordCount() {
    const content = document.getElementById('content').value;
    const wordCount = content.trim() === '' ? 0 : content.trim().split(/\s+/).length;
    document.getElementById('wordCount').textContent = wordCount;
}

// Preview functionality
function togglePreview() {
    const container = document.getElementById('previewContainer');
    const toggleText = document.getElementById('previewToggleText');
    
    if (container.classList.contains('hidden')) {
        updatePreview();
        container.classList.remove('hidden');
        toggleText.textContent = 'Hide Preview';
    } else {
        container.classList.add('hidden');
        toggleText.textContent = 'Show Preview';
    }
}

function updatePreview() {
    const title = document.getElementById('title').value || 'Untitled Post';
    const category = document.getElementById('category').value;
    const tags = document.getElementById('tags').value;
    const content = document.getElementById('content').value || 'No content yet...';
    
    document.getElementById('previewTitle').textContent = title;
    document.getElementById('previewCategory').textContent = category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' ');
    document.getElementById('previewTags').textContent = tags ? `Tags: ${tags}` : '';
    document.getElementById('previewContent').textContent = content;
}

// Save draft functionality (localStorage)
function saveDraft() {
    const draft = {
        title: document.getElementById('title').value,
        category: document.getElementById('category').value,
        tags: document.getElementById('tags').value,
        content: document.getElementById('content').value,
        timestamp: new Date().toISOString()
    };
    
    localStorage.setItem('blog_draft', JSON.stringify(draft));
    showMessageBox('Success', 'Draft saved successfully!', 'success');
}

// Load draft on page load
function loadDraft() {
    const savedDraft = localStorage.getItem('blog_draft');
    if (savedDraft) {
        const draft = JSON.parse(savedDraft);
        const timeDiff = (new Date() - new Date(draft.timestamp)) / 1000 / 60; // minutes
        
        if (timeDiff < 60 && confirm('A draft from ' + Math.round(timeDiff) + ' minutes ago was found. Load it?')) {
            document.getElementById('title').value = draft.title || '';
            document.getElementById('category').value = draft.category || 'general';
            document.getElementById('tags').value = draft.tags || '';
            document.getElementById('content').value = draft.content || '';
            updateWordCount();
        }
    }
}

// Auto-save draft every 30 seconds
setInterval(function() {
    const title = document.getElementById('title').value;
    const content = document.getElementById('content').value;
    
    if (title || content) {
        saveDraft();
    }
}, 30000);

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    loadDraft();
    
    const contentTextarea = document.getElementById('content');
    contentTextarea.addEventListener('input', updateWordCount);
    
    // Auto-resize textarea
    contentTextarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });
    
    // Clear draft on successful submission
    document.querySelector('form').addEventListener('submit', function() {
        localStorage.removeItem('blog_draft');
    });

    document.getElementById('toggle-preview-btn')?.addEventListener('click', togglePreview);
    document.getElementById('save-draft-btn')?.addEventListener('click', saveDraft);
});
